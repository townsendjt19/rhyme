"""
USD_JPY x trend-origin pullback x M15 cell (registered 2026-07-15 BEFORE
this script). H4 HTF / M15 LTF (the grid cell-3 family pattern), OANDA data,
$80 fixed risk, 0.9-pip verified FTMO all-in cost, plugin verbatim.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/jpy_pullback_m15_killtest.py [full]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import backtest

HERE = Path(__file__).parent

PAIR = "USD_JPY"
SPREAD_PIPS = 0.9          # verified all-in FTMO cost (Campaign 5)
FIXED_RISK = 80.0
QUICK = (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc))
FULL = (datetime(2021, 1, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc))
PIP = 0.01
STOP_FLOOR_PIPS = 10 * SPREAD_PIPS   # box-9


def main():
    full = len(sys.argv) > 1 and sys.argv[1] == "full"
    # Registered mapping: H4 filter, M15 trigger (cell-3 family pattern)
    backtest.TF_MAP["scalp15"] = ("H4", "M15")
    plugin_fn = backtest._load_plugin(str(HERE / "trend_origin_pullback_plugin.py"))
    start, end = FULL if full else QUICK
    name = f"jpym15_pullback_{'full' if full else '2023'}"
    print(f"\n########## {name} ##########")
    tr = backtest.run_backtest(
        instrument=PAIR, mode="scalp15", start=start, end=end,
        signal_plugin=plugin_fn, fixed_risk=FIXED_RISK,
        spread_pips=SPREAD_PIPS, strategy_name=name,
    )
    tr.to_csv(HERE / f"{name}.csv", index=False)
    n = len(tr)
    net = tr["pnl"].sum() if n else 0.0
    exp = net / n if n else float("nan")
    med_stop = (tr["entry"] - tr["sl"]).abs().median() / PIP if n else float("nan")
    verdict = "KILL" if (n < 20 or exp <= 0 or med_stop < STOP_FLOOR_PIPS) else "CLEAR"
    print(f"  n={n}  net=${net:.2f}  expectancy=${exp:.2f}/trade  "
          f"median_stop={med_stop:.1f}p (floor {STOP_FLOOR_PIPS:.0f}p)  -> {verdict}")
    if full and n:
        yearly = tr.set_index(tr["time"].map(lambda t: t.year))["pnl"].groupby(level=0).sum() \
            if not hasattr(tr["time"].iloc[0], "year") else tr.groupby(tr["time"].map(lambda t: t.year))["pnl"].sum()
        print("  yearly: " + "  ".join(f"{int(y)}:{v:+.0f}" for y, v in yearly.items()))
        print(f"  ex-best-year: {net - yearly.max():+.2f}")


if __name__ == "__main__":
    main()
