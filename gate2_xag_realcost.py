"""
XAGUSD Gate-2 re-run at MEASURED real cost (registered 2026-07-13 BEFORE
this script was written; see the cost-correction entry).

The 2026-07-09 kill priced a 58-pip Phase A indicative spread; the real
.sim median is 9.5 pips (+1 pip commission-equivalent). One variable
changes vs the voided runs: spread 58.0 -> 10.5. Plugins, harness, data
source, and all other conventions verbatim. gate2_killtest.py stays at
its committed 58-pip state for the audit trail.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/gate2_xag_realcost.py [full]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import backtest
import risk
from gate2_killtest import mt5_fetch_candles

HERE = Path(__file__).parent

SYM = "XAGUSD"
CONV = {"pip_size": 0.001, "pip_value": 0.10, "spread_pips": 10.5}
PLUGINS = ["donchian_plugin.py", "trend_origin_pullback_plugin.py"]

QUICK = (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc))
FULL = (datetime(2021, 12, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc))
FIXED_RISK = 80.0


def main():
    full = len(sys.argv) > 1 and sys.argv[1] == "full"
    backtest.TF_MAP.setdefault("scalp30", ("H4", "M30"))
    backtest.fetch_candles = mt5_fetch_candles
    risk._PIP_SIZE[SYM] = CONV["pip_size"]
    risk._PIP_VALUE_USD[SYM] = CONV["pip_value"]

    start, end = FULL if full else QUICK
    for plug in PLUGINS:
        plugin_fn = backtest._load_plugin(str(HERE / plug))
        name = f"gate2xagreal_{plug.replace('_plugin.py', '')}_{'full' if full else '2023'}"
        print(f"\n########## {name} ##########")
        trades = backtest.run_backtest(
            instrument=SYM, mode="scalp30", start=start, end=end,
            signal_plugin=plugin_fn, fixed_risk=FIXED_RISK,
            spread_pips=CONV["spread_pips"], strategy_name=name,
        )
        trades.to_csv(HERE / f"{name}.csv", index=False)
        n = len(trades)
        net = trades["pnl"].sum() if n else 0.0
        exp = net / n if n else float("nan")
        med_stop = (trades["entry"] - trades["sl"]).abs().median() / CONV["pip_size"] if n else float("nan")
        stop_floor = 10 * CONV["spread_pips"]
        verdict = ("KILL" if n < 20 or exp < 0 or med_stop < stop_floor else "CLEAR")
        print(f"  n={n}  net=${net:.2f}  expectancy=${exp:.2f}/trade  "
              f"median_stop={med_stop:.0f} pips (floor {stop_floor:.0f})  -> {verdict}")


if __name__ == "__main__":
    main()
