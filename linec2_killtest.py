"""
Campaign 3 Track B — Line C continuation: M15 rungs (mode `scalp`, H1 confirm /
M15 trigger) of the validated mechanisms on gold/indices (registration c1dd8c2,
committed before results). Cells: XAUUSD x pullback, SPX x pullback,
XAUUSD x donchian (the pre-stated long shot). Quick-check 2023 per cell;
full window only for survivors.

Costs, commission-inclusive per the standing lesson: XAUUSD 30 pips-equiv
(25 real .sim spread + ~5 commission at $2.50/side); SPX 5.0 pips ($0 comm).

Run:  venv/Scripts/python.exe linec2_killtest.py [full] [cell=<name>]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import backtest
import risk
from gate2_killtest import mt5_fetch_candles

HERE = Path(__file__).parent

CELLS = {
    "xau_pullback_m15": {"instrument": "XAUUSD", "plugin": "trend_origin_pullback_plugin.py",
                         "pip_size": 0.01, "pip_value": 0.10, "spread_pips": 30.0},
    "spx_pullback_m15": {"instrument": "SPX", "plugin": "trend_origin_pullback_plugin.py",
                         "pip_size": 0.10, "pip_value": 0.10, "spread_pips": 5.0},
    "xau_donchian_m15": {"instrument": "XAUUSD", "plugin": "donchian_plugin.py",
                         "pip_size": 0.01, "pip_value": 0.10, "spread_pips": 30.0},
}
FULL_START = {"XAUUSD": datetime(2021, 12, 1, tzinfo=timezone.utc),
              "SPX": datetime(2022, 7, 1, tzinfo=timezone.utc)}


def run_cell(name: str, cfg: dict, full: bool) -> None:
    backtest.fetch_candles = mt5_fetch_candles
    risk._PIP_SIZE[cfg["instrument"]] = cfg["pip_size"]
    risk._PIP_VALUE_USD[cfg["instrument"]] = cfg["pip_value"]
    start, end = ((FULL_START[cfg["instrument"]], datetime(2026, 7, 1, tzinfo=timezone.utc))
                  if full else
                  (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)))
    plugin = backtest._load_plugin(str(HERE / cfg["plugin"]))
    run_name = f"linec2_{name}_{'full' if full else '2023'}"
    print(f"\n########## {run_name} ##########")
    tr = backtest.run_backtest(
        instrument=cfg["instrument"], mode="scalp", start=start, end=end,
        signal_plugin=plugin, fixed_risk=80.0,
        spread_pips=cfg["spread_pips"], strategy_name=run_name,
    )
    tr.to_csv(HERE / f"{run_name}.csv", index=False)
    n = len(tr)
    net = tr["pnl"].sum() if n else 0.0
    exp = net / n if n else float("nan")
    med_stop = (tr["entry"] - tr["sl"]).abs().median() / cfg["pip_size"] if n else float("nan")
    verdict = "KILL" if n < 20 or exp < 0 or med_stop < 10 * cfg["spread_pips"] else "CLEAR"
    print(f"  n={n}  net=${net:.2f}  expectancy=${exp:.2f}/trade  "
          f"median_stop={med_stop:.0f} pips (floor {10 * cfg['spread_pips']:.0f})  -> {verdict}")
    if full and n:
        import pandas as pd
        yearly = tr.assign(t=pd.to_datetime(tr["time"])).set_index("t")["pnl"].resample("YE").sum()
        print("  yearly: " + " ".join(f"{t.year}:{v:+.0f}" for t, v in yearly.items()) +
              f"  ex-best-year: {net - yearly.max():+.2f}")


def main() -> None:
    full = "full" in sys.argv[1:]
    only = next((a.split("=")[1] for a in sys.argv[1:] if a.startswith("cell=")), None)
    for name, cfg in CELLS.items():
        if only and name != only:
            continue
        run_cell(name, cfg, full)


if __name__ == "__main__":
    main()
