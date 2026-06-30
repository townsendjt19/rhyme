"""
Forex Bot — Live / Paper Trading Loop
--------------------------------------
Runs on every candle close for each configured pair and mode.

Modes
-----
  Default (no flags) : built-in six-filter strategy, live OANDA account
  --paper-trade      : external plugin strategy on OANDA practice account,
                       enhanced console logging, no changes to .env required

Usage examples
--------------
  # Paper trade RSI 2.5R on GBP_USD (practice account):
  python main.py --paper-trade

  # Paper trade with a different plugin or pairs:
  python main.py --paper-trade --signals-module D:/forex_bot/macd_rsi_plugin.py --pairs GBP_USD,USD_JPY

  # Live built-in strategy (original behaviour):
  python main.py --mode intraday --pairs EUR_USD,GBP_USD,USD_JPY
"""
from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import sys
import time

import requests.exceptions

# Ensure the terminal can handle unicode (arrows, etc.) even on Windows cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from data import fetch_candles
from indicators import add_emas, detect_fractals
from strategy import evaluate, Signal
from risk import (
    lot_size,
    units_from_lots,
    partial_close_size,
    trailing_stop_price,
    should_advance_stop,
    dynamic_pip_value,
)
from broker import (
    get_account_balance,
    get_open_trades,
    place_market_order,
    close_trade,
    advance_trailing_stop,
)

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_FILE = Path(__file__).parent / "paper_trader.log"

_fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_fmt)

_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_stdout_handler, _file_handler])
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_PAPER_PLUGIN = Path(__file__).parent / "rsi_plugin_25r.py"
DEFAULT_PAPER_PAIRS  = ["GBP_USD", "USD_CAD"]
PAPER_TRADES_CSV     = Path(__file__).parent / "paper_trades.csv"
PIDFILE              = Path(__file__).parent / "paper_trader.pid"


# ── Single-instance lock ───────────────────────────────────────────────────────

def _pid_alive(pid: int) -> bool:
    """Return True if the given PID is currently running."""
    if sys.platform == "win32":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _find_running_main_pids(exclude_pid: int) -> list[int]:
    """Scan all python.exe processes for ones running main.py --paper-trade.

    This catches orphan instances that were started without writing the pidfile,
    which is the failure mode that allowed duplicate bots to run simultaneously.
    Falls back silently if the OS query fails (the pidfile check still runs).
    """
    import subprocess
    found: list[int] = []
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["wmic", "process", "where", "name='python.exe'",
                 "get", "CommandLine,ProcessId", "/format:csv"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.splitlines():
                # CSV rows: Node,CommandLine,ProcessId
                # Skip header, blank lines, and lines without main.py
                if "main.py" not in line or "--paper-trade" not in line:
                    continue
                try:
                    pid = int(line.rsplit(",", 1)[-1].strip())
                except ValueError:
                    continue
                if pid != exclude_pid:
                    found.append(pid)
        else:
            result = subprocess.run(
                ["pgrep", "-f", "main.py.*--paper-trade"],
                capture_output=True, text=True, timeout=10,
            )
            for token in result.stdout.split():
                try:
                    pid = int(token)
                    if pid != exclude_pid:
                        found.append(pid)
                except ValueError:
                    pass
    except Exception as e:
        logger.warning("Orphan process scan failed (%s) — relying on pidfile check only.", e)
    return found


def _acquire_pidfile() -> None:
    """Write PID to lockfile. Exit if any main.py --paper-trade instance is already running.

    Two-layer check:
    1. Scan all python processes for orphan main.py instances not tracked by the pidfile.
    2. Check the pidfile for the instance that last registered itself.
    """
    my_pid = os.getpid()

    # Layer 1: catch orphans the pidfile doesn't know about
    orphans = _find_running_main_pids(exclude_pid=my_pid)
    if orphans:
        pids_str = ", ".join(str(p) for p in orphans)
        print(f"ERROR: paper trader already running (unregistered PID(s): {pids_str}).")
        print(f"       These were started without writing the pidfile — kill them first:")
        for p in orphans:
            print(f"         Stop-Process -Id {p} -Force")
        sys.exit(1)

    # Layer 2: check the registered pidfile instance
    if PIDFILE.exists():
        try:
            existing_pid = int(PIDFILE.read_text().strip())
        except ValueError:
            existing_pid = None

        if existing_pid and existing_pid != my_pid:
            if _pid_alive(existing_pid):
                print(f"ERROR: paper trader is already running as PID {existing_pid}.")
                print(f"       Kill it first:  Stop-Process -Id {existing_pid} -Force")
                print(f"       Or delete the lockfile: {PIDFILE}")
                sys.exit(1)
            else:
                logger.warning("Stale pidfile (PID %d no longer alive) — removing.", existing_pid)

    PIDFILE.write_text(str(my_pid))


def _release_pidfile() -> None:
    try:
        PIDFILE.unlink(missing_ok=True)
    except Exception:
        pass

TF_MAP = {
    "swing":    ("D",   "H4",  3600 * 4),
    "intraday": ("H4",  "H1",  3600),
    "scalp":    ("H1",  "M15", 900),
}

# In-memory trade state for built-in strategy (trade_id → metadata)
_active_trades: dict[str, dict] = {}


# ── Plugin loader ─────────────────────────────────────────────────────────────

def _load_plugin(module_path: str) -> Callable:
    path = Path(module_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Plugin not found: {path}")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod  = importlib.util.module_from_spec(spec)       # type: ignore[arg-type]
    spec.loader.exec_module(mod)                        # type: ignore[union-attr]
    if not hasattr(mod, "generate_signal"):
        raise AttributeError(f"{path.name} must define generate_signal()")
    fn = mod.generate_signal
    fn.__module__ = path.stem
    return fn


# ── Candle helpers ────────────────────────────────────────────────────────────

def candle_seconds(mode: str) -> int:
    return TF_MAP[mode][2]


def sleep_until_next_candle(candle_secs: int) -> None:
    now                 = int(time.time())
    seconds_into_candle = now % candle_secs
    wait                = (candle_secs - seconds_into_candle) + 5   # 5 s margin
    next_candle         = datetime.fromtimestamp(now + wait, tz=timezone.utc)
    next_candle_local   = next_candle.astimezone()
    logger.info(
        "Next candle at %s (%s local) — sleeping %ds",
        next_candle.strftime("%H:%M:%S UTC"),
        next_candle_local.strftime("%H:%M:%S"),
        wait,
    )
    time.sleep(wait)


# ── Console status helpers ────────────────────────────────────────────────────

def _safe_print(*args, **kwargs) -> None:
    """print() that never raises — also mirrors output to the UTF-8 log file."""
    msg = " ".join(str(a) for a in args)
    # Write to log file first (always UTF-8, never fails on encoding)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except Exception:
        pass
    # Write to stdout (may be cp1252 terminal — replace unencodable chars)
    try:
        print(msg, **{k: v for k, v in kwargs.items() if k != "end"})
    except Exception:
        try:
            sys.stdout.buffer.write((msg + "\n").encode("ascii", errors="replace"))
        except Exception:
            pass

_SEP = "=" * 64

def _print_cycle_header(balance: float, open_trades: list[dict], mode: str, pairs: list[str]) -> None:
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    _safe_print(_SEP)
    _safe_print(f"  PAPER TRADE  |  {now}  |  mode={mode}")
    _safe_print(f"  Balance : ${balance:,.2f}   Open positions : {len(open_trades)}")
    if open_trades:
        for t in open_trades:
            inst  = t.get("instrument", "?")
            side  = "LONG" if float(t.get("currentUnits", 0)) > 0 else "SHORT"
            upl   = float(t.get("unrealizedPL", 0))
            sign  = "+" if upl >= 0 else ""
            _safe_print(f"    [{inst}] {side}  unrealised P&L: {sign}{upl:.2f}")
    _safe_print(f"  Pairs   : {', '.join(pairs)}")
    _safe_print(_SEP)


def _print_signal(instrument: str, signal: Signal, units: int, lots: float) -> None:
    side  = "LONG " if signal.direction == "long" else "SHORT"
    tp    = signal.take_profits[0]
    risk  = abs(signal.entry_price - signal.stop_loss)
    r_pct = risk / signal.entry_price * 100
    # Replace unicode arrows with ASCII so cp1252 terminals don't crash
    reason = (signal.reason or "").replace("→", "->").replace("←", "<-").replace("↔", "<->")
    _safe_print(f"  >> SIGNAL  {side}  {instrument}")
    _safe_print(f"     Entry : {signal.entry_price:.5f}")
    _safe_print(f"     SL    : {signal.stop_loss:.5f}  (risk {r_pct:.3f}%)")
    _safe_print(f"     TP    : {tp:.5f}  (2.5R target)")
    _safe_print(f"     Size  : {lots:.2f} lots / {abs(units):,} units")
    if reason:
        _safe_print(f"     Reason: {reason}")


def _print_fill(instrument: str, response: dict) -> None:
    fill = response.get("orderFillTransaction", {})
    fill_price = fill.get("price", "?")
    trade_id   = fill.get("tradeOpened", {}).get("tradeID", "?")
    _safe_print(f"  >> FILLED  {instrument}  @ {fill_price}  trade_id={trade_id}")


def _print_no_signal(instrument: str, reason: str = "") -> None:
    suffix = f"  ({reason})" if reason else ""
    _safe_print(f"  -- {instrument}  no signal{suffix}")


def _log_trade_csv(instrument: str, signal: Signal, lots: float, units: int, response: dict) -> None:
    """Append one filled trade row to paper_trades.csv."""
    import csv
    fill     = response.get("orderFillTransaction", {})
    trade_id = fill.get("tradeOpened", {}).get("tradeID", "")
    fill_px  = fill.get("price", signal.entry_price)
    now      = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    write_header = not PAPER_TRADES_CSV.exists()

    with PAPER_TRADES_CSV.open("a", newline="") as fh:
        w = csv.writer(fh)
        if write_header:
            w.writerow([
                "time", "pair", "strategy", "direction",
                "entry", "sl", "tp", "lots", "units", "trade_id", "reason",
            ])
        w.writerow([
            now,
            instrument,
            "rsi_plugin_25r",
            signal.direction,
            fill_px,
            f"{signal.stop_loss:.5f}",
            f"{signal.take_profits[0]:.5f}",
            f"{lots:.2f}",
            abs(units),
            trade_id,
            signal.reason or "",
        ])


# ── Paper trade loop ──────────────────────────────────────────────────────────

def run_once_paper(pairs: list[str], mode: str, plugin: Callable) -> None:
    """One iteration of the paper trade loop using an external signal plugin."""
    htf_gran, ltf_gran, _ = TF_MAP[mode]

    try:
        balance     = get_account_balance()
        open_trades = get_open_trades()
    except Exception as e:
        logger.error("Could not fetch account data: %s", e)
        return

    open_instruments = {t.get("instrument") for t in open_trades}
    _print_cycle_header(balance, open_trades, mode, pairs)

    for instrument in pairs:
        # Don't stack positions on the same pair
        if instrument in open_instruments:
            _print_no_signal(instrument, "position already open")
            continue

        try:
            htf_df = fetch_candles(instrument, htf_gran, count=250)
            ltf_df = fetch_candles(instrument, ltf_gran, count=250)
        except requests.exceptions.Timeout:
            logger.error(
                "[%s] Candle fetch TIMED OUT after 30s — skipping instrument this cycle",
                instrument,
            )
            continue
        except Exception as e:
            logger.error("[%s] Candle fetch failed: %s", instrument, e)
            continue

        htf_df = add_emas(detect_fractals(htf_df))
        ltf_df = add_emas(detect_fractals(ltf_df))

        try:
            signal = plugin(instrument, htf_df, ltf_df, mode)
        except Exception as e:
            logger.error("[%s] Plugin error: %s", instrument, e)
            continue

        if signal is None:
            _print_no_signal(instrument)
            continue

        # Size the position (2 % risk)
        pv   = dynamic_pip_value(instrument, signal.entry_price)
        lots = lot_size(balance, signal.entry_price, signal.stop_loss, instrument,
                        pip_value_usd=pv)
        if lots < 0.01:
            _print_no_signal(instrument, f"lot size too small ({lots:.4f})")
            continue

        units = units_from_lots(lots, instrument)
        if signal.direction == "short":
            units = -units

        tp = signal.take_profits[0]   # all 3 slots equal in RSI plugin

        _print_signal(instrument, signal, units, lots)

        try:
            response = place_market_order(
                instrument=instrument,
                units=units,
                stop_loss=signal.stop_loss,
                take_profit=tp,
                client_extensions={"comment": signal.reason[:128] if signal.reason else ""},
            )
            _print_fill(instrument, response)
            _log_trade_csv(instrument, signal, lots, units, response)
        except Exception as e:
            logger.error("[%s] Order failed: %s", instrument, e)


# ── Built-in strategy loop (original behaviour) ───────────────────────────────

def manage_open_trades(mode: str, instrument: str) -> None:
    """Advance trailing stop and partial close for built-in strategy trades."""
    open_trades = get_open_trades()
    _, ltf_gran, _ = TF_MAP[mode]
    ltf_df = fetch_candles(instrument, ltf_gran, count=50)
    ltf_df = add_emas(ltf_df)

    for t in open_trades:
        tid  = t["id"]
        inst = t.get("instrument", "")
        if inst != instrument:
            continue

        state = _active_trades.get(tid)
        if state is None:
            continue

        current_price = float(t.get("price", 0))
        direction     = state["direction"]
        tps           = state["tps"]
        tp_idx        = state["tp_idx"]
        ema_20        = float(ltf_df.iloc[-1]["ema_20"])

        if tp_idx > 0 and tp_idx < len(tps):
            next_tp = tps[tp_idx]
            if should_advance_stop(direction, current_price, next_tp):
                next_tp_after = tps[tp_idx + 1] if tp_idx + 1 < len(tps) else None
                advance_trailing_stop(tid, direction, current_price, ema_20, tp_idx, next_tp_after)
                units_remaining = abs(int(t.get("currentUnits", 0)))
                close_units     = partial_close_size(units_remaining, tp_idx)
                if close_units > 0:
                    close_trade(tid, units=close_units)
                    logger.info("Partial close %d units at TP%d", close_units, tp_idx + 1)
                state["tp_idx"] += 1

        if direction == "long"  and current_price < ema_20:
            close_trade(tid)
            logger.info("EMA20 cross-back close: %s", tid)
            _active_trades.pop(tid, None)
        elif direction == "short" and current_price > ema_20:
            close_trade(tid)
            logger.info("EMA20 cross-back close: %s", tid)
            _active_trades.pop(tid, None)


def run_once_builtin(pairs: list[str], mode: str) -> None:
    """One iteration using the built-in six-filter strategy."""
    htf_gran, ltf_gran, _ = TF_MAP[mode]
    balance = get_account_balance()
    logger.info("Balance: %.2f", balance)

    for instrument in pairs:
        try:
            manage_open_trades(mode, instrument)

            htf_df = fetch_candles(instrument, htf_gran, count=200)
            ltf_df = fetch_candles(instrument, ltf_gran, count=200)

            signal = evaluate(instrument, htf_df, ltf_df, mode=mode)
            if signal is None:
                logger.info("[%s] No signal", instrument)
                continue

            logger.info("[%s] Signal: %s entry=%.5f sl=%.5f",
                        instrument, signal.direction, signal.entry_price, signal.stop_loss)

            lots = lot_size(balance, signal.entry_price, signal.stop_loss, instrument)
            if lots < 0.01:
                logger.warning("[%s] Lot size too small (%.4f), skipping", instrument, lots)
                continue

            units = units_from_lots(lots, instrument)
            if signal.direction == "short":
                units = -units

            response = place_market_order(
                instrument=instrument,
                units=units,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profits[0],
            )

            trade_id = (
                response.get("orderFillTransaction", {}).get("tradeOpened", {}).get("tradeID")
                or response.get("relatedTransactionIDs", [None])[0]
            )
            if trade_id:
                _active_trades[str(trade_id)] = {
                    "direction": signal.direction,
                    "tps": signal.take_profits,
                    "tp_idx": 0,
                    "units": abs(units),
                }

        except Exception as e:
            logger.error("[%s] Error: %s", instrument, e, exc_info=True)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Forex Bot Live / Paper Trader")
    parser.add_argument("--mode",    default="scalp", choices=["swing", "intraday", "scalp"])
    parser.add_argument("--pairs",   default=None,
                        help="Comma-separated instruments (default: GBP_USD in paper mode, "
                             "EUR_USD,GBP_USD,USD_JPY otherwise)")
    parser.add_argument("--paper-trade", action="store_true",
                        help="Run on OANDA practice account with RSI 2.5R plugin")
    parser.add_argument("--signals-module", default=None, metavar="PATH",
                        help="Path to plugin .py (default in paper mode: rsi_plugin_25r.py)")
    args = parser.parse_args()

    # ── Resolve pairs ─────────────────────────────────────────────────────────
    if args.pairs:
        pairs = [p.strip() for p in args.pairs.split(",")]
    elif args.paper_trade:
        pairs = DEFAULT_PAPER_PAIRS
    else:
        pairs = ["EUR_USD", "GBP_USD", "USD_JPY"]

    mode        = args.mode
    candle_secs = candle_seconds(mode)

    # ── Paper trade setup ─────────────────────────────────────────────────────
    if args.paper_trade:
        _acquire_pidfile()   # exits immediately if another instance is running

        plugin_path = args.signals_module or str(DEFAULT_PAPER_PLUGIN)
        plugin      = _load_plugin(plugin_path)

        import data, broker
        env = data.ENVIRONMENT
        if env != "practice":
            logger.warning(
                "OANDA_ENV is '%s' but --paper-trade expects 'practice'. "
                "Check your .env file.", env,
            )

        import subprocess as _sp
        try:
            _git_hash = _sp.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=Path(__file__).parent, text=True, stderr=_sp.DEVNULL,
            ).strip()
        except Exception:
            _git_hash = "unknown"

        _safe_print(_SEP)
        _safe_print("  FOREX BOT — PAPER TRADE MODE")
        _safe_print(f"  Plugin  : {Path(plugin_path).name}")
        _safe_print(f"  Pairs   : {', '.join(pairs)}")
        _safe_print(f"  Mode    : {mode}  (candle every {candle_secs}s)")
        _safe_print(f"  Account : {broker.ACCOUNT_ID}  [{env}]")
        _safe_print(f"  Commit  : {_git_hash}")
        _safe_print(f"  PID     : {os.getpid()}  (lockfile: {PIDFILE})")
        _safe_print(f"  Press Ctrl+C to stop")
        _safe_print(_SEP)

        try:
            while True:
                try:
                    run_once_paper(pairs, mode, plugin)
                except KeyboardInterrupt:
                    _safe_print("\n  Paper trade session ended.")
                    break
                except Exception as e:
                    logger.error("Loop error: %s", e, exc_info=True)
                sleep_until_next_candle(candle_secs)
        finally:
            _release_pidfile()

    # ── Built-in live strategy ────────────────────────────────────────────────
    else:
        logger.info("Starting live loop | mode=%s | pairs=%s | candle=%ds",
                    mode, pairs, candle_secs)
        while True:
            try:
                run_once_builtin(pairs, mode)
            except KeyboardInterrupt:
                logger.info("Shutting down.")
                break
            except Exception as e:
                logger.error("Loop error: %s", e, exc_info=True)
            sleep_until_next_candle(candle_secs)


if __name__ == "__main__":
    main()
