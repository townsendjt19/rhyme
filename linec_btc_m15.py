"""
Line C cell 1 -- BTCUSD x donchian at M15 (registered 2026-07-09, committed
before results). Quick-check 2023; full window only if it clears.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/linec_btc_m15.py [full]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import backtest
import risk
from gate2_killtest import mt5_fetch_candles

HERE = Path(__file__).parent
CONV = {"pip_size": 1.00, "pip_value": 0.10, "spread_pips": 2.0}


def main():
    backtest.fetch_candles = mt5_fetch_candles
    risk._PIP_SIZE["BTCUSD"] = CONV["pip_size"]
    risk._PIP_VALUE_USD["BTCUSD"] = CONV["pip_value"]

    full = len(sys.argv) > 1 and sys.argv[1] == "full"
    start, end = ((datetime(2021, 12, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc))
                  if full else
                  (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)))
    plugin = backtest._load_plugin(str(HERE / "donchian_plugin.py"))
    name = f"linec_BTCUSD_donchian_m15_{'full' if full else '2023'}"
    print(f"\n########## {name} ##########")
    tr = backtest.run_backtest(
        instrument="BTCUSD", mode="scalp", start=start, end=end,
        signal_plugin=plugin, fixed_risk=80.0,
        spread_pips=CONV["spread_pips"], strategy_name=name,
    )
    tr.to_csv(HERE / f"{name}.csv", index=False)
    n = len(tr)
    net = tr["pnl"].sum() if n else 0.0
    exp = net / n if n else float("nan")
    med_stop = (tr["entry"] - tr["sl"]).abs().median() / CONV["pip_size"] if n else float("nan")
    verdict = "KILL" if n < 20 or exp < 0 or med_stop < 10 * CONV["spread_pips"] else "CLEAR"
    print(f"  n={n}  net=${net:.2f}  expectancy=${exp:.2f}/trade  "
          f"median_stop={med_stop:.0f} pips (floor {10*CONV['spread_pips']:.0f})  -> {verdict}")


if __name__ == "__main__":
    main()
