"""
Rhyme — Live / Paper Trading Loop
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
  python main.py --paper-trade --signals-module D:/rhyme/macd_rsi_plugin.py --pairs GBP_USD,USD_JPY

  # Live built-in strategy (original behaviour):
  python main.py --mode intraday --pairs EUR_USD,GBP_USD,USD_JPY
"""
from __future__ import annotations

import argparse
import contextlib
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
    RISK_PCT,
    GLOBAL_RISK_CAP_PCT,
    MAX_POSITIONS_PER_INSTRUMENT,
    MARGIN_UTILIZATION_CAP_PCT,
    EQUITY_FLOOR_USD,
    price_precision,
)
from broker import (
    get_account_balance,
    get_open_trades,
    place_market_order,
    close_trade,
    advance_trailing_stop,
    get_account_margin,
    get_account_nav,
    get_nav_for,
    required_margin_usd,
)
from portfolio_state import get_portfolio_state, check_currency_exposure_cap

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_FILE = Path(__file__).parent / "paper_trader.log"

# DISPLAY ONLY -- every scheduling/candle-boundary decision in this file
# (sleep_until_next_candle, TF_MAP intervals, etc.) runs on raw UTC epoch
# seconds via time.time(), which is timezone-agnostic and completely
# unaffected by anything below. This block only controls what gets PRINTED
# to the console/log file, never what gets computed.
#
# Originally forced to time.gmtime (see commit 7b04c7b) after discovering
# logging.Formatter defaults %(asctime)s to LOCAL time, which disagreed by
# exactly this system's UTC offset with the explicit datetime.now(tz=
# timezone.utc) banner in _print_cycle_header(). Switched back to local
# time here for console readability, but NOW EXPLICITLY (time.localtime,
# not the implicit default) with a dynamic %Z zone name via datefmt, so the
# label is always correct instead of a hardcoded, potentially-stale word --
# critically, %Z re-derives from the OS's DST rules at each record's own
# timestamp, so it correctly flips from "Eastern Daylight Time" to "Eastern
# Standard Time" across a DST transition in a long-running process, rather
# than baking in whatever was true at process-start. _print_cycle_header()
# and sleep_until_next_candle() were updated to match (both now display
# local time too, both still computed from an underlying UTC-aware value).
_fmt = logging.Formatter(
    "%(asctime)s,%(msecs)03d %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %I:%M:%S %p %Z",
)
_fmt.converter = time.localtime

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


def _pidfile_path(mode: str) -> Path:
    """Per-mode lockfile so swing/intraday/scalp instances can run concurrently
    as legitimately separate processes, while still blocking a duplicate launch
    of the *same* mode."""
    return Path(__file__).parent / f"paper_trader_{mode}.pid"


# ── Cross-mode trade decision lock ──────────────────────────────────────────────
#
# The per-mode pidfiles above only prevent two instances of the SAME mode from
# running together. They do nothing to stop two DIFFERENT modes (e.g. swing and
# intraday) from racing each other on the same pair: each is a separate OS
# process independently polling the same OANDA account, so both can call
# get_open_trades(), both see "no position open" for GBP_USD, and both place an
# order before either fill is visible to the other -- doubling the intended
# per-pair risk with no record of why.
#
# TRADE_LOCK_PATH is a single lockfile shared by every paper-trade process
# regardless of mode. It serializes the entire "is this pair already open? ->
# would this order breach the global exposure cap? -> place the order" decision
# across ALL concurrently running modes, so at most one process is ever
# mid-decision at a time. That also makes the global cap check below race-free:
# the open-trade count it reads is always the true, uncontested state.
TRADE_LOCK_PATH        = Path(__file__).parent / "trade_decision.lock"
TRADE_LOCK_TIMEOUT     = 30    # seconds to wait for the lock before giving up this instrument
TRADE_LOCK_STALE_AFTER = 120   # seconds after which a held lock is presumed abandoned (holder crashed)


@contextlib.contextmanager
def _trade_decision_lock(instrument: str):
    """Cross-process mutex around one instrument's open-check/cap-check/place sequence.

    Uses atomic exclusive file creation (O_CREAT|O_EXCL), which is atomic on
    both Windows and POSIX -- exactly one process can succeed at a time when
    the lockfile doesn't already exist. Stale-lock recovery mirrors the
    pidfile staleness handling elsewhere in this file: if a holder crashed
    without releasing, the lock is reclaimed after TRADE_LOCK_STALE_AFTER
    seconds rather than deadlocking forever.
    """
    deadline = time.time() + TRADE_LOCK_TIMEOUT
    acquired = False
    while time.time() < deadline:
        try:
            fd = os.open(str(TRADE_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as fh:
                fh.write(f"{os.getpid()} {instrument} {time.time()}")
            acquired = True
            break
        except FileExistsError:
            try:
                age = time.time() - TRADE_LOCK_PATH.stat().st_mtime
                if age > TRADE_LOCK_STALE_AFTER:
                    logger.warning(
                        "Trade decision lock stale (%.0fs old) -- reclaiming.", age,
                    )
                    TRADE_LOCK_PATH.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue  # released between our exists-check and stat() -- retry immediately
            time.sleep(0.25)

    if not acquired:
        raise TimeoutError(
            f"Could not acquire trade decision lock for {instrument} "
            f"within {TRADE_LOCK_TIMEOUT}s -- another process is holding it."
        )

    try:
        yield
    finally:
        TRADE_LOCK_PATH.unlink(missing_ok=True)


# ── Single-instance lock ───────────────────────────────────────────────────────

def _pid_alive(pid: int) -> bool:
    """Return True if the given PID is currently running (any process)."""
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


def _pid_is_paper_trader(pid: int) -> bool:
    """Return True only if pid is alive AND its command line matches main.py --paper-trade.

    Defends against Windows PID reuse: a killed bot's PID can be reassigned to an
    unrelated process, making _pid_alive() return True for the wrong process and
    causing a false "already running" block on the next startup.
    Falls back to _pid_alive() if the command-line query fails.
    """
    if not _pid_alive(pid):
        return False
    import subprocess
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["wmic", "process", "where", f"ProcessId={pid}",
                 "get", "CommandLine", "/format:csv"],
                capture_output=True, text=True, timeout=10,
            )
            cmdline = result.stdout
        else:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "args="],
                capture_output=True, text=True, timeout=10,
            )
            cmdline = result.stdout
        return "main.py" in cmdline and "--paper-trade" in cmdline
    except Exception as e:
        logger.warning(
            "Could not verify command line for PID %d (%s) — assuming it is the paper trader.",
            pid, e,
        )
        return True  # safe default: don't silently overwrite a potentially live bot


def _find_running_main_pids(exclude_pids: set[int], mode: str) -> list[int]:
    """Scan all python.exe processes for ones running main.py --paper-trade
    in the SAME mode. Mode-aware so swing/intraday/scalp instances running
    concurrently as separate, legitimate processes don't flag each other.

    This catches orphan instances that were started without writing the pidfile,
    which is the failure mode that allowed duplicate bots to run simultaneously.
    Falls back silently if the OS query fails (the pidfile check still runs).

    exclude_pids must include BOTH the caller's own PID and its PARENT's PID.
    A venv's Scripts/python.exe on Windows (CPython 3.8+'s venvlauncher.exe
    stub) is not a self-contained interpreter -- launching it starts a
    launcher-stub PROCESS which then spawns the real interpreter as a CHILD
    with a DIFFERENT PID, and both processes carry an identical command line
    (verified: os.getppid() inside the real interpreter equals the PID
    Start-Process reports for the launch). Excluding only os.getpid() means
    every venv-launched instance permanently finds its own launcher stub via
    this scan and refuses to start, misreporting a duplicate that doesn't
    exist. This never showed up when launching the base D:\\python.exe
    directly (single process, no stub), which is why it went unnoticed.
    """
    import re
    import subprocess
    found: list[int] = []
    # --mode may be omitted from the command line entirely, in which case it
    # defaults to "scalp" -- extract the effective mode rather than substring-
    # matching, so "--mode scalp" (explicit) and no flag at all (implicit) are
    # both correctly recognized as scalp.
    mode_re = re.compile(r"--mode[=\s]+(\S+)")

    def _effective_mode(cmdline: str) -> str:
        m = mode_re.search(cmdline)
        return m.group(1) if m else "scalp"

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
                if _effective_mode(line) != mode:
                    continue
                try:
                    pid = int(line.rsplit(",", 1)[-1].strip())
                except ValueError:
                    continue
                if pid not in exclude_pids:
                    found.append(pid)
        else:
            result = subprocess.run(
                ["pgrep", "-af", "main.py.*--paper-trade"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.splitlines():
                parts = line.split(None, 1)
                if len(parts) != 2:
                    continue
                pid_str, cmdline = parts
                if _effective_mode(cmdline) != mode:
                    continue
                try:
                    pid = int(pid_str)
                    if pid not in exclude_pids:
                        found.append(pid)
                except ValueError:
                    pass
    except Exception as e:
        logger.warning("Orphan process scan failed (%s) — relying on pidfile check only.", e)
    return found


def _acquire_pidfile(mode: str) -> None:
    """Write PID to a mode-specific lockfile. Exit if another instance running
    the SAME mode is already running -- a different mode is allowed to run
    concurrently as a separate process.

    Two-layer check:
    1. Scan all python processes for orphan main.py instances (same mode) not
       tracked by the pidfile.
    2. Check the pidfile for the instance that last registered itself.
    """
    my_pid  = os.getpid()
    pidfile = _pidfile_path(mode)

    # Layer 1: catch orphans the pidfile doesn't know about. Exclude our own
    # parent PID alongside our own -- see _find_running_main_pids' docstring
    # for why (venv launcher-stub processes on Windows share our command
    # line but run as a distinct parent PID, not a real duplicate instance).
    orphans = _find_running_main_pids(exclude_pids={my_pid, os.getppid()}, mode=mode)
    if orphans:
        pids_str = ", ".join(str(p) for p in orphans)
        print(f"ERROR: paper trader (mode={mode}) already running (unregistered PID(s): {pids_str}).")
        print(f"       These were started without writing the pidfile — kill them first:")
        for p in orphans:
            print(f"         Stop-Process -Id {p} -Force")
        sys.exit(1)

    # Layer 2: check the registered pidfile instance
    if pidfile.exists():
        try:
            existing_pid = int(pidfile.read_text().strip())
        except ValueError:
            existing_pid = None

        if existing_pid and existing_pid != my_pid:
            if _pid_is_paper_trader(existing_pid):
                print(f"ERROR: paper trader (mode={mode}) is already running as PID {existing_pid}.")
                print(f"       Kill it first:  Stop-Process -Id {existing_pid} -Force")
                print(f"       Or delete the lockfile: {pidfile}")
                sys.exit(1)
            elif _pid_alive(existing_pid):
                # PID is live but belongs to a different process — Windows reused the PID.
                logger.warning(
                    "Pidfile PID %d (mode=%s) is alive but is not main.py --paper-trade "
                    "(Windows reused the PID) — treating as stale.", existing_pid, mode,
                )
            else:
                logger.warning("Stale pidfile (PID %d, mode=%s) no longer alive — removing.", existing_pid, mode)

    pidfile.write_text(str(my_pid))


def _release_pidfile(mode: str) -> None:
    try:
        _pidfile_path(mode).unlink(missing_ok=True)
    except Exception:
        pass

TF_MAP = {
    "swing":    ("D",   "H4",  3600 * 4),
    "intraday": ("H4",  "H1",  3600),
    "scalp":    ("H1",  "M15", 900),
    # M30 signal / H4 HTF -- validated for USD_JPY specifically (see
    # RESEARCH_LOG.md). H4 chosen over H1 as HTF: an 8x gap gives real
    # trend-filter separation, matching intraday's H1(sig)/H4(htf) spacing;
    # H1 would only be 2x M30 and add little filtering value. NOT a general
    # M30/H4 recommendation -- GBP_USD and AUD_JPY were tested at this same
    # configuration and rejected (GBP_USD net negative, AUD_JPY spread-eaten).
    "scalp30":  ("H4",  "M30", 1800),
    # Identical timing to scalp30, distinct mode NAME so the Bot D slot's
    # process (trend_origin_pullback_long_plugin on USD_JPY) gets its own
    # per-mode pidfile/orphan-scan identity and can run alongside the
    # donchian scalp30 process without the duplicate-instance guards
    # colliding. Renamed from "botd" 2026-07-01 -- operational mode strings
    # describe the strategy/timeframe, portfolio-slot names live in
    # RESEARCH_LOG.md.
    "pullback30": ("H4", "M30", 1800),
}


# ── Portfolio equity floor (GOVERNANCE "Portfolio Risk Tolerance") ────────────

# Both research accounts, regardless of which one this process trades.
RESEARCH_ACCOUNTS = ["101-001-39634331-001", "101-001-39634331-002"]


def check_equity_floor(
    account_navs: list[tuple[str, float]], floor: float = EQUITY_FLOOR_USD
) -> tuple[bool, str]:
    """PER-ACCOUNT equity floor: each research account's marked-to-market
    NAV is checked independently against the floor. A breach on EITHER
    account suspends the ENTIRE fleet's new entries (not just that
    account's processes) pending full operator review -- a research
    vehicle hitting the floor is a portfolio-level event demanding full
    review regardless of where it happens. Corrected 2026-07-01 from an
    initial combined-equity implementation to match the decided intent
    (see GOVERNANCE Portfolio Risk Tolerance)."""
    breached = [(a, nav) for a, nav in account_navs if nav <= floor]
    if breached:
        detail = ", ".join(f"{a} NAV ${nav:,.2f}" for a, nav in breached)
        return False, (
            f"PORTFOLIO EQUITY FLOOR BREACHED (per-account): {detail} <= floor "
            f"${floor:,.2f} -- ENTIRE FLEET's new entries suspended pending full "
            f"review (GOVERNANCE Portfolio Risk Tolerance, 2026-07-01). Existing "
            f"positions remain managed by standing SL/TP."
        )
    return True, ""


# ── Cross-mode pre-trade gates (pure functions -- unit-testable) ─────────────

def check_instrument_position_cap(
    open_trades: list[dict],
    instrument: str,
    cap: int = MAX_POSITIONS_PER_INSTRUMENT,
) -> tuple[bool, str]:
    """Max open positions per instrument, counted across ALL modes.

    Replaces the previous blanket "any open position on this instrument
    blocks every mode" rule (a de-facto cap of 1). First-come-first-served:
    whichever modes' orders fill first hold the slots; position cap+1 and
    beyond are deterministically rejected until one closes.
    """
    n_open = sum(1 for t in open_trades if t.get("instrument") == instrument)
    if n_open >= cap:
        return False, (
            f"instrument position cap reached ({n_open} open on {instrument} "
            f">= cap {cap}, across all modes)"
        )
    return True, ""


def check_margin_utilization(
    nav: float,
    margin_used: float,
    required_margin: float,
    cap_pct: float = MARGIN_UTILIZATION_CAP_PCT,
) -> tuple[bool, str]:
    """Projected TOTAL margin utilization vs NAV, including the candidate
    order. Distinct from the marginAvailable check (which only asks "can
    this order be placed at all"): this bounds how deep into margin
    capacity the whole book may go, so a stack of individually-placeable
    positions can't walk utilization toward the closeout edge."""
    if nav <= 0:
        return False, f"cannot compute margin utilization (NAV={nav})"
    projected = margin_used + required_margin
    utilization = projected / nav
    if utilization > cap_pct:
        return False, (
            f"margin utilization cap would be breached (used ${margin_used:,.2f} "
            f"+ this order ${required_margin:,.2f} = ${projected:,.2f}, "
            f"{utilization:.0%} of NAV ${nav:,.2f} > {cap_pct:.0%} cap)"
        )
    return True, ""

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
    # Scheduling math is entirely raw UTC epoch seconds (time.time() and
    # modulo arithmetic) -- timezone-agnostic, DST-agnostic, unaffected by
    # anything below. next_candle/next_candle_local exist ONLY to produce a
    # human-readable log line; wait/time.sleep(wait) never touch them.
    now                 = int(time.time())
    seconds_into_candle = now % candle_secs
    wait                = (candle_secs - seconds_into_candle) + 5   # 5 s margin
    next_candle         = datetime.fromtimestamp(now + wait, tz=timezone.utc)
    next_candle_local   = next_candle.astimezone()
    logger.info(
        "Next candle at %s — sleeping %ds",
        next_candle_local.strftime("%Y-%m-%d %I:%M:%S %p %Z"),
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
    # Computed from the same UTC-aware instant as always (datetime.now(tz=
    # timezone.utc)) -- .astimezone() only changes what gets displayed, not
    # the underlying instant, so this carries no scheduling implications.
    now = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d %I:%M:%S %p %Z")
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
    prec = price_precision(instrument)
    _safe_print(f"  >> SIGNAL  {side}  {instrument}")
    _safe_print(f"     Entry : {signal.entry_price:.{prec}f}")
    _safe_print(f"     SL    : {signal.stop_loss:.{prec}f}  (risk {r_pct:.3f}%)")
    _safe_print(f"     TP    : {tp:.{prec}f}  (2.5R target)")
    _safe_print(f"     Size  : {lots:.2f} lots / {abs(units):,} units")
    if reason:
        _safe_print(f"     Reason: {reason}")


def _print_fill(instrument: str, response: dict) -> bool:
    """Report the true outcome of an order-create response. Returns True only
    if the order actually FILLED. OANDA can create-and-instantly-cancel an
    order in one response (e.g. FIFO_VIOLATION_SAFEGUARD_VIOLATION on a
    second same-instrument trade under NFA FIFO rules -- observed live
    2026-07-01 on Bot D's first order) -- the old version logged that as
    ">> FILLED @ ? trade_id=?", which is how a cancelled order masqueraded
    as a fill in the log."""
    fill = response.get("orderFillTransaction")
    if fill:
        fill_price = fill.get("price", "?")
        trade_id   = fill.get("tradeOpened", {}).get("tradeID", "?")
        _safe_print(f"  >> FILLED  {instrument}  @ {fill_price}  trade_id={trade_id}")
        return True

    cancel = response.get("orderCancelTransaction")
    if cancel:
        reason = cancel.get("reason", "unknown")
        # Same funnel visibility as every other gate rejection.
        _print_no_signal(instrument, f"order CANCELLED by broker: {reason}")
        logger.warning("[%s] Order cancelled by broker: %s", instrument, reason)
        return False

    _safe_print(f"  >> ORDER OUTCOME UNKNOWN  {instrument}  (no fill or cancel transaction in response)")
    logger.warning("[%s] Order response had neither fill nor cancel transaction: %s", instrument, response)
    return False


def _print_no_signal(instrument: str, reason: str = "") -> None:
    suffix = f"  ({reason})" if reason else ""
    _safe_print(f"  -- {instrument}  no signal{suffix}")


def _log_trade_csv(instrument: str, signal: Signal, lots: float, units: int, response: dict,
                    strategy_tag: str) -> None:
    """Append one filled trade row to paper_trades.csv.

    strategy_tag identifies both the plugin AND the mode (e.g. "donchian_plugin_swing"
    vs "donchian_plugin_intraday") so concurrent multi-mode runs land in distinct
    dashboard.py strategy-panel rows without any dashboard changes needed.
    """
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
        prec = price_precision(instrument)
        w.writerow([
            now,
            instrument,
            strategy_tag,
            signal.direction,
            fill_px,
            f"{signal.stop_loss:.{prec}f}",
            f"{signal.take_profits[0]:.{prec}f}",
            f"{lots:.2f}",
            abs(units),
            trade_id,
            signal.reason or "",
        ])


# ── Paper trade loop ──────────────────────────────────────────────────────────

def run_once_paper(pairs: list[str], mode: str, plugin: Callable) -> None:
    """One iteration of the paper trade loop using an external signal plugin."""
    htf_gran, ltf_gran, _ = TF_MAP[mode]
    strategy_tag = f"{getattr(plugin, '__module__', 'plugin')}_{mode}"

    try:
        balance     = get_account_balance()
        open_trades = get_open_trades()
    except Exception as e:
        logger.error("Could not fetch account data: %s", e)
        return

    _print_cycle_header(balance, open_trades, mode, pairs)

    # ── Portfolio equity floor: checked once per cycle, before any scanning.
    # COMBINED marked-to-market equity across BOTH research accounts; a
    # breach suspends this cycle's entries entirely (and every other
    # process's, since each runs the same check). Fails OPEN on API error
    # (a transient NAV-fetch failure should not halt trading), matching the
    # error convention of the per-trade gates.
    try:
        account_navs = [(a, get_nav_for(a)) for a in RESEARCH_ACCOUNTS]
        floor_ok, floor_reason = check_equity_floor(account_navs)
    except Exception as e:
        logger.error("Could not check portfolio equity floor (%s) -- proceeding without the check", e)
        floor_ok, floor_reason = True, ""

    if not floor_ok:
        _safe_print(f"  !! {floor_reason}")
        logger.critical(floor_reason)
        return

    for instrument in pairs:
        # Cheap pre-check against the once-per-cycle snapshot -- avoids paying
        # for a candle fetch + signal evaluation on a pair that was obviously
        # already at its position cap as of the top of this cycle. The
        # authoritative check happens fresh, under the lock, right before
        # placing an order.
        pre_ok, pre_reason = check_instrument_position_cap(open_trades, instrument)
        if not pre_ok:
            _print_no_signal(instrument, pre_reason)
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

        # ── Critical section: re-check open-ness, enforce the global exposure
        # cap, and place the order -- all under the cross-mode lock so no
        # other concurrently running mode can race this decision.
        try:
            with _trade_decision_lock(instrument):
                fresh_open_trades = get_open_trades()

                # Per-instrument position cap (max MAX_POSITIONS_PER_INSTRUMENT
                # across all modes, first-come-first-served). This REPLACES the
                # previous blanket "any open position on the instrument blocks
                # every mode" rule -- a deliberate loosening from a de-facto
                # cap of 1 to a policy cap of 2 (decision 2026-07-01, see
                # RESEARCH_LOG.md's Bot D stacked-exposure section).
                cap_ok, cap_reason = check_instrument_position_cap(fresh_open_trades, instrument)
                if not cap_ok:
                    _print_no_signal(instrument, cap_reason)
                    continue

                n_open = len(fresh_open_trades)
                projected_exposure = (n_open + 1) * RISK_PCT
                if projected_exposure > GLOBAL_RISK_CAP_PCT:
                    _print_no_signal(
                        instrument,
                        f"global risk cap would be breached "
                        f"({n_open} open + this trade = {projected_exposure:.0%} > {GLOBAL_RISK_CAP_PCT:.0%} cap)",
                    )
                    continue

                # ── Margin check: a SEPARATE constraint from the risk cap above.
                # GLOBAL_RISK_CAP_PCT bounds potential LOSS; this bounds the
                # CAPITAL REQUIRED to hold the position at all -- a low-risk-%
                # trade can still exceed available margin if the position size
                # (driven by a tight SL under fixed-risk sizing) is large enough
                # and the instrument's margin rate is high. Checked fresh here,
                # under the same lock, rather than letting OANDA reject it after
                # the fact.
                try:
                    margin_available, margin_used = get_account_margin()
                    required_margin = required_margin_usd(instrument, units)
                except Exception as e:
                    logger.error("[%s] Could not check margin (%s) -- proceeding without the check", instrument, e)
                    required_margin = None

                if required_margin is not None and required_margin > margin_available:
                    _print_no_signal(
                        instrument,
                        f"insufficient margin (need ${required_margin:,.2f}, "
                        f"available ${margin_available:,.2f}, used ${margin_used:,.2f})",
                    )
                    continue

                # ── Margin UTILIZATION cap: distinct from the availability
                # check above. That one asks "can this order be placed at
                # all"; this bounds how deep into total margin capacity the
                # whole book may go (projected used / NAV), so a stack of
                # individually-placeable positions can't walk utilization to
                # the closeout edge. Same lock, fresh NAV.
                if required_margin is not None:
                    try:
                        nav = get_account_nav()
                        util_ok, util_reason = check_margin_utilization(
                            nav, margin_used, required_margin,
                        )
                    except Exception as e:
                        logger.error(
                            "[%s] Could not check margin utilization (%s) -- proceeding without the check",
                            instrument, e,
                        )
                        util_ok, util_reason = True, ""

                    if not util_ok:
                        _print_no_signal(instrument, util_reason)
                        continue

                # ── Currency-factor exposure cap: a THIRD separate constraint,
                # distinct from both the risk cap above (bounds potential LOSS)
                # and the margin check above (bounds CAPITAL REQUIRED). A
                # portfolio can pass both of those and still be dangerously
                # concentrated in one currency -- e.g. long USD_JPY, long
                # EUR_USD, long GBP_USD open at once look like three
                # diversified pairs but are actually one large short-USD bet.
                # portfolio_state.py is the single source of truth for net
                # exposure per currency across every mode/process; queried
                # fresh here, under the same lock, so this candidate trade is
                # judged against the true current state, not a stale one.
                try:
                    portfolio_state = get_portfolio_state()
                    exposure_ok, exposure_reason = check_currency_exposure_cap(
                        portfolio_state, instrument, units,
                    )
                except Exception as e:
                    logger.error(
                        "[%s] Could not check currency exposure cap (%s) -- proceeding without the check",
                        instrument, e,
                    )
                    exposure_ok, exposure_reason = True, ""

                if not exposure_ok:
                    _print_no_signal(instrument, exposure_reason)
                    continue

                _print_signal(instrument, signal, units, lots)

                try:
                    response = place_market_order(
                        instrument=instrument,
                        units=units,
                        stop_loss=signal.stop_loss,
                        take_profit=tp,
                        client_extensions={"comment": signal.reason[:128] if signal.reason else ""},
                    )
                    filled = _print_fill(instrument, response)
                    if filled:
                        # Only genuinely FILLED orders belong in paper_trades.csv --
                        # a broker-cancelled order (e.g. FIFO safeguard) never
                        # opened a trade and must not pollute the trade log.
                        _log_trade_csv(instrument, signal, lots, units, response, strategy_tag)
                except Exception as e:
                    logger.error("[%s] Order failed: %s", instrument, e)
        except TimeoutError as e:
            logger.error("[%s] %s", instrument, e)


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
                advance_trailing_stop(tid, inst, direction, current_price, ema_20, tp_idx, next_tp_after)
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

            _prec = price_precision(instrument)
            logger.info(f"[%s] Signal: %s entry=%.{_prec}f sl=%.{_prec}f",
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
    parser = argparse.ArgumentParser(description="Rhyme Live / Paper Trader")
    parser.add_argument("--mode",    default="scalp", choices=["swing", "intraday", "scalp", "scalp30", "pullback30"])
    parser.add_argument("--pairs",   default=None,
                        help="Comma-separated instruments (default: GBP_USD in paper mode, "
                             "EUR_USD,GBP_USD,USD_JPY otherwise)")
    parser.add_argument("--paper-trade", action="store_true",
                        help="Run on OANDA practice account with RSI 2.5R plugin")
    parser.add_argument("--signals-module", default=None, metavar="PATH",
                        help="Path to plugin .py (default in paper mode: rsi_plugin_25r.py)")
    parser.add_argument("--account", default=None, metavar="ACCOUNT_ID",
                        help="OANDA account ID override for this process (token/env stay "
                             "shared from .env). Used to isolate a mode onto its own practice "
                             "sub-account -- e.g. Bot D, whose second-position USD_JPY orders "
                             "are otherwise broker-cancelled by the NFA FIFO safeguard.")
    args = parser.parse_args()

    # Apply the account override FIRST, before any broker call anywhere in
    # this process (the startup header, cycle headers, and every gate then
    # all consistently reflect the overridden account).
    if args.account:
        import broker as _broker
        _broker.set_account(args.account)

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
        _acquire_pidfile(mode)   # exits immediately if another SAME-mode instance is running

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
        _safe_print("  Rhyme — Paper Trade Mode")
        _safe_print(f"  Plugin  : {Path(plugin_path).name}")
        _safe_print(f"  Pairs   : {', '.join(pairs)}")
        _safe_print(f"  Mode    : {mode}  (candle every {candle_secs}s)")
        _safe_print(f"  Account : {broker.ACCOUNT_ID}  [{env}]")
        _safe_print(f"  Commit  : {_git_hash}")
        _safe_print(f"  PID     : {os.getpid()}  (lockfile: {_pidfile_path(mode)})")
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
            _release_pidfile(mode)

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
