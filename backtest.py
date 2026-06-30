"""
Backtester — walk-forward simulation over historical data.

Default usage (built-in 6-filter strategy):
    python backtest.py --instrument EUR_USD --mode scalp --start 2023-01-01 --end 2024-01-01

External Python strategy plugin:
    python backtest.py --instrument EUR_USD --mode scalp --start 2023-01-01 --end 2024-01-01
                       --signals-module path/to/my_strategy.py

Pre-computed CSV signals:
    python backtest.py --instrument EUR_USD --start 2023-01-01 --end 2024-01-01
                       --signals-csv path/to/signals.csv

CSV format: time (ISO8601), instrument, direction (long/short),
            entry, sl, tp1, tp2 (opt), tp3 (opt)
"""
import argparse
import importlib.util
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

# Force UTF-8 output on Windows so unicode box-drawing chars don't crash
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from data import fetch_candles
from indicators import add_emas, detect_fractals
from strategy import evaluate, FILTER_STAGES, StrategyConfig, Signal
from risk import lot_size, units_from_lots, stop_distance_pips, partial_close_size

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    stream=sys.stdout)
logger = logging.getLogger(__name__)


# ── Run metadata ──────────────────────────────────────────────────────────────

# Plugin constants we know how to extract by name
_KNOWN_PLUGIN_PARAMS = {
    "_TP_R_MULTIPLE":   "tp_r_multiple",
    "_RSI_PERIOD":      "rsi_period",
    "_OVERSOLD":        "rsi_oversold",
    "_OVERBOUGHT":      "rsi_overbought",
    "_MACD_FAST":       "macd_fast",
    "_MACD_SLOW":       "macd_slow",
    "_MACD_SIGNAL":     "macd_signal",
    "_MIN_RANGE_PIPS":  "min_range_pips",
    "_ENTRY_START_MIN": "entry_start_min",
    "_ENTRY_END_MIN":   "entry_end_min",
}

_TF_MAP_LABELS = {
    "scalp":    {"htf": "H1",  "ltf": "M15"},
    "intraday": {"htf": "H4",  "ltf": "H1"},
    "swing":    {"htf": "D",   "ltf": "H4"},
}


def _git_hash() -> str:
    """Return the short HEAD commit hash, or 'no-git' if unavailable."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "-C", str(Path(__file__).parent), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip() if result.returncode == 0 else "no-git"
    except Exception:
        return "no-git"


def _extract_plugin_params(module) -> dict:
    """Introspect a loaded plugin module for known constant names."""
    params = {}
    for attr, label in _KNOWN_PLUGIN_PARAMS.items():
        val = getattr(module, attr, None)
        if val is not None:
            params[label] = val
    return params


def build_run_metadata(
    plugin_path: str | None,
    plugin_module,
    instrument: str,
    mode: str,
    start: datetime,
    end: datetime,
    balance: float,
    strategy_name: str,
    trailing_stop: bool,
    trail_distance: float,
) -> dict:
    tfs = _TF_MAP_LABELS.get(mode, {})
    meta = {
        "strategy_name":   strategy_name,
        "instrument":      instrument,
        "mode":            mode,
        "htf":             tfs.get("htf", "?"),
        "ltf":             tfs.get("ltf", "?"),
        "start":           start.strftime("%Y-%m-%d"),
        "end":             end.strftime("%Y-%m-%d"),
        "starting_balance": balance,
        "trailing_stop":   trailing_stop,
        "trail_distance_r": trail_distance,
        "git_commit":      _git_hash(),
        "plugin_path":     str(Path(plugin_path).resolve()) if plugin_path else "built-in",
        "plugin_params":   _extract_plugin_params(plugin_module) if plugin_module else {},
        "run_timestamp":   datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return meta


def print_run_header(meta: dict) -> None:
    """Print a self-documenting header before each backtest run."""
    W = 62
    plugin_params = meta.get("plugin_params", {})
    print(f"\n{'='*W}")
    print(f"  BACKTEST RUN")
    print(f"{'='*W}")
    print(f"  Strategy     : {meta['strategy_name']}")
    print(f"  Instrument   : {meta['instrument']}")
    print(f"  Mode         : {meta['mode']}  (HTF={meta['htf']}  LTF={meta['ltf']})")
    print(f"  Date range   : {meta['start']} → {meta['end']}")
    print(f"  Balance      : ${meta['starting_balance']:.2f}")
    print(f"  Trailing stop: {'yes  (BE@1R, trail@' + str(meta['trail_distance_r']) + 'R)' if meta['trailing_stop'] else 'no'}")
    print(f"  Git commit   : {meta['git_commit']}")
    print(f"  Plugin file  : {meta['plugin_path']}")
    if plugin_params:
        print(f"  Plugin params:")
        for k, v in plugin_params.items():
            print(f"    {k:<22}: {v}")
    print(f"  Run at (UTC) : {meta['run_timestamp']}")
    print(f"{'='*W}\n")


def write_meta_sidecar(out_path: Path, meta: dict) -> None:
    """Write a <name>.meta.json sidecar next to the CSV for full traceability."""
    import json
    sidecar = out_path.with_suffix(".meta.json")
    sidecar.write_text(json.dumps(meta, indent=2), encoding="utf-8")


# ── Signal provider loading ───────────────────────────────────────────────────

def _load_plugin(module_path: str) -> Callable:
    """
    Load an external strategy module and return its generate_signal function.

    The module must define:
        def generate_signal(instrument, htf_df, ltf_df, mode) -> Signal | None
    """
    path = Path(module_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Signal plugin not found: {path}")
    spec = importlib.util.spec_from_file_location("_external_strategy", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "generate_signal"):
        raise AttributeError(
            f"{path.name} must define generate_signal(instrument, htf_df, ltf_df, mode) -> Signal | None"
        )
    logger.info("Loaded external strategy plugin: %s", path.name)
    return mod.generate_signal


def _load_csv_signals(csv_path: str, instrument: str) -> pd.DataFrame:
    """
    Load pre-computed signals from a CSV file.

    Required columns : time, instrument, direction, entry, sl, tp1
    Optional columns : tp2, tp3
    """
    df = pd.read_csv(csv_path, parse_dates=["time"])
    required = {"time", "instrument", "direction", "entry", "sl", "tp1"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"signals CSV missing columns: {missing}")
    df = df[df["instrument"] == instrument].copy()
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df.set_index("time", inplace=True)
    df.sort_index(inplace=True)
    logger.info("Loaded %d CSV signals for %s", len(df), instrument)
    return df

# Timeframe map: mode -> (higher_tf granularity, trigger_tf granularity)
TF_MAP = {
    "swing":    ("D",   "H4"),
    "intraday": ("H4",  "H1"),
    "scalp":    ("H1",  "M15"),
}

SLIPPAGE_PIPS = 1.0  # simulated slippage per entry


def run_backtest(
    instrument: str,
    mode: str,
    start: datetime,
    end: datetime,
    account_balance: float = 10_000.0,
    config: StrategyConfig | None = None,
    signal_plugin: Callable | None = None,
    signals_csv: pd.DataFrame | None = None,
    trailing_stop: bool = False,
    trail_distance: float = 0.5,
    strategy_name: str | None = None,
) -> pd.DataFrame:
    """
    Run a walk-forward backtest.

    Signal source priority (first match wins):
      1. signals_csv  — pre-computed signals DataFrame (from --signals-csv)
      2. signal_plugin — external generate_signal() function (from --signals-module)
      3. built-in evaluate()  — default 6-filter strategy

    signal_plugin and signals_csv are mutually exclusive.
    """
    if signals_csv is not None:
        return _run_csv_backtest(instrument, start, end, account_balance, signals_csv)

    htf_gran, ltf_gran = TF_MAP[mode]

    logger.info("Fetching %s %s candles…", instrument, htf_gran)
    htf_all = fetch_candles(instrument, htf_gran, from_time=start, to_time=end)

    logger.info("Fetching %s %s candles…", instrument, ltf_gran)
    ltf_all = fetch_candles(instrument, ltf_gran, from_time=start, to_time=end)

    htf_all = add_emas(detect_fractals(htf_all))
    ltf_all = add_emas(detect_fractals(ltf_all))

    trades_log = []
    balance = account_balance
    min_candles = 110  # need enough for EMA 100 warm-up

    # Funnel counters — only populated for built-in strategy
    funnel: dict[str, int] = {s: 0 for s in FILTER_STAGES}
    candles_evaluated = 0
    using_plugin = signal_plugin is not None
    source_label = getattr(signal_plugin, "__module__", "plugin") if using_plugin else "built-in"
    _strategy_tag = strategy_name or (source_label if using_plugin else mode)
    if using_plugin:
        logger.info("Using external signal plugin: %s", source_label)

    for i in range(min_candles, len(ltf_all)):
        ltf_window = ltf_all.iloc[: i + 1]
        signal_time = ltf_all.index[i]

        htf_window = htf_all[htf_all.index <= signal_time]
        if len(htf_window) < min_candles:
            continue

        candles_evaluated += 1

        if using_plugin:
            # External plugin — receives enriched DataFrames, returns Signal | None
            try:
                signal = signal_plugin(instrument, htf_window, ltf_window, mode)
            except Exception as e:
                logger.error("Plugin error at %s: %s", signal_time, e)
                signal = None
            funnel["passed" if signal else "1_htf_ema_alignment"] += 1
        else:
            signal, stage = evaluate(
                instrument, htf_window, ltf_window, mode=mode, config=config
            )
            funnel[stage] += 1

        if signal is None:
            continue

        entry = signal.entry_price
        sl = signal.stop_loss
        tps = signal.take_profits

        if not tps:
            continue

        # Dynamic pip value for USD/JPY based on current entry price
        from risk import dynamic_pip_value
        pv = dynamic_pip_value(instrument, entry)
        lots = lot_size(balance, entry, sl, instrument, pip_value_usd=pv)
        if lots < 0.01:
            continue

        total_units = units_from_lots(lots, instrument)

        # Simulate trade outcome using future candles
        future = ltf_all.iloc[i + 1:]
        trade_result = _simulate_trade(
            signal.direction, entry, sl, tps, future, total_units, instrument,
            pip_value_usd=pv, trailing_stop=trailing_stop, trail_distance=trail_distance,
        )

        pnl = trade_result["pnl"]
        balance += pnl

        trades_log.append(
            {
                "time": signal_time,
                "instrument": instrument,
                "strategy": _strategy_tag,
                "direction": signal.direction,
                "entry": entry,
                "sl": sl,
                "tp1": tps[0] if len(tps) > 0 else None,
                "tp2": tps[1] if len(tps) > 1 else None,
                "tp3": tps[2] if len(tps) > 2 else None,
                "units": total_units,
                "pnl": pnl,
                "balance": balance,
                "exit_reason": trade_result["exit_reason"],
            }
        )
        logger.info(
            "[%s] %s %s entry=%.5f sl=%.5f pnl=%.2f balance=%.2f",
            signal_time, signal.direction, instrument, entry, sl, pnl, balance,
        )

    _print_funnel(funnel, candles_evaluated)
    return pd.DataFrame(trades_log)


def _print_funnel(funnel: dict[str, int], total: int) -> None:
    labels = {
        "1_htf_ema_alignment":  "1. HTF EMA aligned (20>50>100)",
        "2_ltf_ema_crossover":  "2. LTF EMA crossover (same candle)",
        "3_fractal_break":      "3. Williams Fractal break",
        "4_candlestick_filter": "4. Candlestick filter (no opposing pattern)",
        "5_volume_profile_lvn": "5. Volume Profile (not in LVN)",
        "6_fib_confirmation":   "6. Fibonacci retracement confirmation",
        "passed":               "   --> SIGNAL PASSED ALL FILTERS",
    }

    # Build cumulative survivors: each stage shows how many reached it
    survivors = total
    print(f"\n{'='*60}")
    print(f"SIGNAL FUNNEL  ({total} candles evaluated)")
    print("=" * 60)

    eliminated_by: dict[str, int] = {}
    for stage in FILTER_STAGES[:-1]:  # exclude "passed"
        eliminated_by[stage] = funnel.get(stage, 0)

    reached: dict[str, int] = {}
    running = total
    for stage in FILTER_STAGES[:-1]:
        reached[stage] = running
        running -= eliminated_by[stage]
    reached["passed"] = running

    for stage in FILTER_STAGES:
        label = labels.get(stage, stage)
        n = reached[stage]
        pct = n / total * 100 if total else 0
        eliminated = eliminated_by.get(stage, 0)

        if stage == "passed":
            print("-" * 60)
            print(f"  {label:<42} {n:>5}  ({pct:.1f}%)")
        else:
            print(f"  {label:<42} {n:>5}  ({pct:.1f}%)  -{eliminated} eliminated")

    print("=" * 60 + "\n")


def _simulate_trade(
    direction: str,
    entry: float,
    sl: float,
    tps: list[float],
    future: pd.DataFrame,
    total_units: int,
    instrument: str,
    pip_value_usd: float | None = None,
    trailing_stop: bool = False,
    trail_distance: float = 0.5,
) -> dict:
    """
    Walk future candles and simulate partial closes at each TP, SL if hit.

    trailing_stop:
        When True, once price moves 1R in profit the SL advances to breakeven
        (entry), then trails trail_distance×R behind the highest favourable
        price reached. TP levels still act as a ceiling — whichever is hit
        first wins.  A trailing SL above entry locks in profit; PnL is
        calculated from the actual exit price (current_sl), not the original SL.
    """
    from risk import pip_size, _PIP_VALUE_USD

    ps = pip_size(instrument)
    pv = pip_value_usd if pip_value_usd is not None else _PIP_VALUE_USD.get(instrument, 10.0)
    remaining_units = total_units
    pnl = 0.0
    tp_idx = 0

    initial_risk = abs(entry - sl)                    # 1R in price terms
    half_r       = initial_risk * trail_distance      # trail distance after activation
    trail_active = False
    current_sl   = sl                       # tracks moving stop when trailing

    def _pnl_for(units: int, price_diff: float, sign: int) -> float:
        return sign * units * (price_diff / ps) * pv / 100_000

    for _, row in future.iterrows():
        if remaining_units <= 0:
            break

        high = row["high"]
        low  = row["low"]

        # ── Update trailing stop ──────────────────────────────────────────────
        if trailing_stop and initial_risk > 0:
            if direction == "long":
                if not trail_active and high >= entry + initial_risk:
                    trail_active = True
                    current_sl = entry               # move SL to breakeven
                if trail_active:
                    current_sl = max(current_sl, high - half_r)
            else:
                if not trail_active and low <= entry - initial_risk:
                    trail_active = True
                    current_sl = entry
                if trail_active:
                    current_sl = min(current_sl, low + half_r)

        # ── Check TPs first (TP wins if same candle hits both) ────────────────
        while tp_idx < len(tps) and remaining_units > 0:
            tp = tps[tp_idx]
            tp_hit = (direction == "long" and high >= tp) or (direction == "short" and low <= tp)
            if tp_hit:
                close_units = partial_close_size(remaining_units, tp_idx)
                close_units = min(close_units, remaining_units)
                price_diff  = abs(tp - entry)
                sign        = 1 if direction == "long" else -1
                pnl += _pnl_for(close_units, price_diff, sign)
                remaining_units -= close_units
                tp_idx += 1
            else:
                break

        # ── Check SL (or trailing SL) for remaining units ────────────────────
        sl_hit = (
            (direction == "long"  and low  <= current_sl) or
            (direction == "short" and high >= current_sl)
        )
        if sl_hit and remaining_units > 0:
            # Exit price is current_sl — may be above entry (profitable trail)
            exit_diff = (current_sl - entry) if direction == "long" else (entry - current_sl)
            sign = 1 if exit_diff >= 0 else -1
            pnl += _pnl_for(remaining_units, abs(exit_diff), sign)
            remaining_units = 0
            reason = "trailing_sl" if (trailing_stop and trail_active) else "sl"
            return {"pnl": pnl, "exit_reason": reason}

    # Any remaining units closed at last seen price
    if remaining_units > 0 and not future.empty:
        last_close = future.iloc[-1]["close"]
        price_diff = last_close - entry if direction == "long" else entry - last_close
        sign = 1 if price_diff >= 0 else -1
        pnl += _pnl_for(remaining_units, abs(price_diff), sign)

    return {"pnl": pnl, "exit_reason": "tp_all" if tp_idx >= len(tps) else "end_of_data"}


def print_summary(df: pd.DataFrame, starting_balance: float) -> None:
    if df.empty:
        print("No trades taken.")
        return
    total = len(df)
    wins = len(df[df["pnl"] > 0])
    losses = len(df[df["pnl"] <= 0])
    win_rate = wins / total * 100
    net_pnl = df["pnl"].sum()
    avg_win = df[df["pnl"] > 0]["pnl"].mean() if wins else 0
    avg_loss = df[df["pnl"] <= 0]["pnl"].mean() if losses else 0
    rr = abs(avg_win / avg_loss) if avg_loss else float("inf")
    final_balance = df["balance"].iloc[-1]

    # Sanity check: final_balance must equal starting_balance + sum(pnl)
    expected = starting_balance + net_pnl
    if abs(final_balance - expected) > 0.01:
        raise ValueError(
            f"Balance integrity error: starting {starting_balance:.2f} + "
            f"net_pnl {net_pnl:.2f} = {expected:.2f}, "
            f"but final balance column shows {final_balance:.2f}. "
            f"These must match — check _simulate_trade pnl/balance accounting."
        )

    print(f"\n{'='*50}")
    print(f"Backtest Results — {df['instrument'].iloc[0]}")
    print(f"{'='*50}")
    print(f"Total trades            : {total}")
    print(f"Wins                    : {wins} ({win_rate:.1f}%)")
    print(f"Losses                  : {losses}")
    print(f"Avg win                 : ${avg_win:.2f}")
    print(f"Avg loss                : ${avg_loss:.2f}")
    print(f"Avg R:R                 : {rr:.2f}")
    print(f"Net P&L (sum of trades) : ${net_pnl:+.2f}")
    print(f"Starting balance        : ${starting_balance:.2f}")
    print(f"Final account balance   : ${final_balance:.2f}")
    print(f"{'='*50}\n")


def _run_csv_backtest(
    instrument: str,
    start: datetime,
    end: datetime,
    account_balance: float,
    signals_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Replay pre-computed signals from a CSV against real OANDA price data.

    Each row in signals_df defines entry/sl/tp levels; future candles
    are fetched (M15) to simulate trade outcome using the same _simulate_trade
    logic as the built-in strategy.
    """
    ltf_gran = "M15"
    logger.info("Fetching %s %s candles for CSV backtest…", instrument, ltf_gran)
    ltf_all = fetch_candles(instrument, ltf_gran, from_time=start, to_time=end)
    ltf_all = add_emas(detect_fractals(ltf_all))

    # Filter signals to date range
    mask = (signals_df.index >= pd.Timestamp(start)) & (signals_df.index <= pd.Timestamp(end))
    signals = signals_df[mask]
    logger.info("Replaying %d signals in date range", len(signals))

    trades_log = []
    balance = account_balance

    for signal_time, row in signals.iterrows():
        entry = float(row["entry"])
        sl = float(row["sl"])
        direction = str(row["direction"]).lower()
        tps = []
        for col in ["tp1", "tp2", "tp3"]:
            if col in row and pd.notna(row[col]):
                tps.append(float(row[col]))

        if not tps:
            logger.warning("Signal at %s has no TP levels — skipping", signal_time)
            continue

        from risk import dynamic_pip_value
        pv = dynamic_pip_value(instrument, entry)
        lots = lot_size(balance, entry, sl, instrument, pip_value_usd=pv)
        if lots < 0.01:
            continue

        total_units = units_from_lots(lots, instrument)
        future = ltf_all[ltf_all.index > signal_time]

        trade_result = _simulate_trade(
            direction, entry, sl, tps, future, total_units, instrument,
            pip_value_usd=pv, trailing_stop=trailing_stop, trail_distance=trail_distance,
        )

        pnl = trade_result["pnl"]
        balance += pnl

        trades_log.append({
            "time": signal_time,
            "instrument": instrument,
            "strategy": _strategy_tag,
            "direction": direction,
            "entry": entry,
            "sl": sl,
            "tp1": tps[0] if len(tps) > 0 else None,
            "tp2": tps[1] if len(tps) > 1 else None,
            "tp3": tps[2] if len(tps) > 2 else None,
            "units": total_units,
            "pnl": pnl,
            "balance": balance,
            "exit_reason": trade_result["exit_reason"],
        })
        logger.info(
            "[CSV] [%s] %s %s entry=%.5f pnl=%.2f balance=%.2f",
            signal_time, direction, instrument, entry, pnl, balance,
        )

    print(f"\n[CSV mode] Replayed {len(trades_log)} signals from external source")
    return pd.DataFrame(trades_log)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forex Bot Backtester")
    parser.add_argument("--instrument", default="EUR_USD")
    parser.add_argument("--mode", default="intraday", choices=["swing", "intraday", "scalp"])
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2024-01-01")
    parser.add_argument("--balance", type=float, default=10_000.0)
    parser.add_argument("--skip-wednesday", action="store_true",
                        help="Skip all entries on Wednesday (UTC)")
    parser.add_argument("--skip-382", action="store_true",
                        help="Skip 38.2%% fib entries — only allow 50%% and 61.8%%")
    parser.add_argument("--min-rr", type=float, default=0.0,
                        help="Minimum R:R required (measured TP3 vs SL). 0 = disabled.")
    parser.add_argument("--signals-module", default=None, metavar="PATH",
                        help="Path to external .py strategy module with generate_signal()")
    parser.add_argument("--signals-csv", default=None, metavar="PATH",
                        help="Path to pre-computed signals CSV (time,instrument,direction,entry,sl,tp1[,tp2,tp3])")
    parser.add_argument("--trailing-stop", action="store_true",
                        help="Enable trailing stop: BE at 1R, then trail at --trail-distance × R")
    parser.add_argument("--trail-distance", type=float, default=0.5, metavar="R",
                        help="Trail distance as a fraction of initial risk (default 0.5)")
    parser.add_argument("--strategy-name", default=None, metavar="NAME",
                        help="Tag written to the 'strategy' column of the output CSV (default: plugin stem or mode)")
    args = parser.parse_args()

    start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    plugin = None
    csv_signals = None

    if args.signals_module and args.signals_csv:
        parser.error("--signals-module and --signals-csv are mutually exclusive")

    if args.signals_module:
        plugin = _load_plugin(args.signals_module)

    if args.signals_csv:
        csv_signals = _load_csv_signals(args.signals_csv, args.instrument)

    cfg = StrategyConfig(
        skip_wednesday=args.skip_wednesday,
        skip_382_fib=args.skip_382,
        min_rr=args.min_rr,
    )

    active = []
    if args.signals_module:
        active.append(f"external-plugin={Path(args.signals_module).name}")
    elif args.signals_csv:
        active.append(f"csv-signals={Path(args.signals_csv).name}")
    else:
        if args.skip_wednesday:
            active.append("skip-wednesday")
        if args.skip_382:
            active.append("skip-38.2%-fib")
        if args.min_rr > 0:
            active.append(f"min-rr={args.min_rr}")
    if active:
        print(f"Active options: {', '.join(active)}")

    if args.trailing_stop:
        active.append(f"trailing-stop(BE@1R,trail@{args.trail_distance}R)")

    # Derive default strategy name from plugin stem or mode
    _default_name = (
        Path(args.signals_module).stem if args.signals_module
        else Path(args.signals_csv).stem if args.signals_csv
        else args.mode
    )
    strat_name = args.strategy_name or _default_name

    # Build and print self-documenting run header
    _plugin_module = None
    if args.signals_module and plugin is not None:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location("_hdr_plugin", args.signals_module)
        _plugin_module = _ilu.module_from_spec(_spec)
        try:
            _spec.loader.exec_module(_plugin_module)
        except Exception:
            _plugin_module = None

    run_meta = build_run_metadata(
        plugin_path=args.signals_module,
        plugin_module=_plugin_module,
        instrument=args.instrument,
        mode=args.mode,
        start=start_dt,
        end=end_dt,
        balance=args.balance,
        strategy_name=strat_name,
        trailing_stop=args.trailing_stop,
        trail_distance=args.trail_distance,
    )
    print_run_header(run_meta)

    # Build output filename: backtest_PAIR_MODE_STRATEGY_YEAR.csv
    if start_dt.year == end_dt.year:
        _year_label = f"{start_dt.year}ytd"
    elif end_dt.year == start_dt.year + 1 and end_dt.month == 1 and end_dt.day == 1:
        _year_label = str(start_dt.year)   # clean calendar year: 2023-01-01 -> 2024-01-01
    else:
        _year_label = f"{start_dt.year}-{end_dt.year}"
    _safe_strat = strat_name.replace("/", "-").replace("\\", "-").replace(" ", "_")
    out_path = Path(__file__).parent / f"backtest_{args.instrument}_{args.mode}_{_safe_strat}_{_year_label}.csv"

    if out_path.exists():
        print(f"WARNING: output file already exists and will NOT be overwritten:")
        print(f"  {out_path}")
        print(f"  Delete or rename it first, then re-run.")
        sys.exit(1)

    results = run_backtest(
        args.instrument, args.mode, start_dt, end_dt, args.balance,
        config=cfg,
        signal_plugin=plugin,
        signals_csv=csv_signals,
        trailing_stop=args.trailing_stop,
        trail_distance=args.trail_distance,
        strategy_name=strat_name,
    )
    print_summary(results, starting_balance=args.balance)

    results.to_csv(out_path, index=False)
    write_meta_sidecar(out_path, run_meta)
    print(f"Results saved to {out_path}")
    print(f"Metadata saved to {out_path.with_suffix('.meta.json')}")
