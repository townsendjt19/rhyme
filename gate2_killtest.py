"""
Gate 2 quick-check runner — prop-firm multi-asset expansion.

Spec pre-registered in RESEARCH_LOG.md (2026-07-08) BEFORE this script was
written. Runs the two live-validated trend mechanisms (donchian,
trend_origin_pullback), unmodified, on XAUUSD and NQ over calendar 2023,
through the corrected backtest.py harness fed by MT5 Phase A data
(broker time -> UTC via the Gate-1-verified fixed -2h offset).

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/gate2_killtest.py
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import backtest
import risk
from mt5_client import get_history

HERE = Path(__file__).parent

# Registered conventions (RESEARCH_LOG 2026-07-08): pip conventions are
# arbitrary-but-self-consistent, chosen so 0.01-lot rounding distorts
# $80 fixed risk by <=~2%. Spread from the Gate-1 indicative snapshot.
SYMBOLS = {
    "XAUUSD": {"pip_size": 0.01, "pip_value": 0.10, "spread_pips": 37.0},
    "NQ":     {"pip_size": 1.00, "pip_value": 0.10, "spread_pips": 5.8},
}
PLUGINS = ["donchian_plugin.py", "trend_origin_pullback_plugin.py"]

START = datetime(2023, 1, 1, tzinfo=timezone.utc)
END = datetime(2024, 1, 1, tzinfo=timezone.utc)
FIXED_RISK = 80.0

BROKER_UTC_OFFSET = timedelta(hours=2)  # fixed year-round, verified Gate 1


def mt5_fetch_candles(instrument, granularity, count=500, from_time=None, to_time=None):
    """Drop-in for data.fetch_candles serving MT5 Phase A data in UTC."""
    df = get_history(instrument, granularity,
                     (from_time + BROKER_UTC_OFFSET).replace(tzinfo=None),
                     (to_time + BROKER_UTC_OFFSET).replace(tzinfo=None))
    df.index = (df.index - BROKER_UTC_OFFSET).tz_localize("UTC")
    return df[["open", "high", "low", "close", "volume"]]


def main():
    backtest.TF_MAP.setdefault("scalp30", ("H4", "M30"))
    backtest.fetch_candles = mt5_fetch_candles
    for sym, conv in SYMBOLS.items():
        risk._PIP_SIZE[sym] = conv["pip_size"]
        risk._PIP_VALUE_USD[sym] = conv["pip_value"]  # $ per lot per pip

    for sym, conv in SYMBOLS.items():
        for plug in PLUGINS:
            plugin_fn = backtest._load_plugin(str(HERE / plug))
            name = f"gate2_{sym}_{plug.replace('_plugin.py', '')}_2023"
            print(f"\n########## {name} ##########")
            trades = backtest.run_backtest(
                instrument=sym, mode="scalp30", start=START, end=END,
                signal_plugin=plugin_fn, fixed_risk=FIXED_RISK,
                spread_pips=conv["spread_pips"], strategy_name=name,
            )
            out = HERE / f"{name}.csv"
            trades.to_csv(out, index=False)
            n = len(trades)
            net = trades["pnl"].sum() if n else 0.0
            exp = net / n if n else float("nan")
            med_stop = (trades["entry"] - trades["sl"]).abs().median() / conv["pip_size"] if n else float("nan")
            stop_floor = 10 * conv["spread_pips"]
            verdict = ("KILL" if n < 20 or exp < 0 or med_stop < stop_floor else "CLEAR")
            print(f"  n={n}  net=${net:.2f}  expectancy=${exp:.2f}/trade  "
                  f"median_stop={med_stop:.0f} pips (floor {stop_floor:.0f})  -> {verdict}")


if __name__ == "__main__":
    main()
