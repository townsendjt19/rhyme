"""
Trendline-break killtest (registration 16e41f8). XAUUSD + SPX on Phase A
data; USD_JPY on OANDA (the reopened door's verified cost). Mode scalp30.
Quick-check 2023 (grid criteria) -> full window.

Run:  venv/Scripts/python.exe trendline_killtest.py [full]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import backtest
import risk
from gate2_killtest import mt5_fetch_candles

HERE = Path(__file__).parent
OANDA_FETCH = backtest.fetch_candles          # default = data.fetch_candles

CELLS = {
    "XAUUSD": {"src": "mt5", "pip_size": 0.01, "pip_value": 0.10, "spread_pips": 30.0,
               "full": datetime(2021, 12, 1, tzinfo=timezone.utc)},
    "SPX":    {"src": "mt5", "pip_size": 0.10, "pip_value": 0.10, "spread_pips": 5.0,
               "full": datetime(2022, 7, 1, tzinfo=timezone.utc)},
    "USD_JPY": {"src": "oanda", "pip_size": 0.01, "pip_value": 6.8, "spread_pips": 0.9,
                "full": datetime(2021, 7, 1, tzinfo=timezone.utc)},
}


def main() -> None:
    full = len(sys.argv) > 1 and sys.argv[1] == "full"
    backtest.TF_MAP.setdefault("scalp30", ("H4", "M30"))   # the gate2 M30 mode
    for sym, cfg in CELLS.items():
        backtest.fetch_candles = mt5_fetch_candles if cfg["src"] == "mt5" else OANDA_FETCH
        risk._PIP_SIZE[sym] = cfg["pip_size"]
        risk._PIP_VALUE_USD[sym] = cfg["pip_value"]
        start, end = ((cfg["full"], datetime(2026, 7, 1, tzinfo=timezone.utc)) if full else
                      (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)))
        plugin = backtest._load_plugin(str(HERE / "trendline_plugin.py"))
        name = f"trendline_{sym}_{'full' if full else '2023'}"
        print(f"\n########## {name} ##########")
        tr = backtest.run_backtest(
            instrument=sym, mode="scalp30", start=start, end=end,
            signal_plugin=plugin, fixed_risk=80.0,
            spread_pips=cfg["spread_pips"], strategy_name=name,
        )
        tr.to_csv(HERE / f"{name}.csv", index=False)
        n = len(tr)
        net = tr["pnl"].sum() if n else 0.0
        exp = net / n if n else float("nan")
        med_stop = (tr["entry"] - tr["sl"]).abs().median() / cfg["pip_size"] if n else float("nan")
        verdict = "KILL" if n < 20 or exp <= 0 or med_stop < 10 * cfg["spread_pips"] else "CLEAR"
        print(f"  n={n}  net=${net:.2f}  exp=${exp:.2f}/tr  med_stop={med_stop:.0f}p "
              f"(floor {10 * cfg['spread_pips']:.0f})  -> {verdict}")
        if full and n:
            import pandas as pd
            yearly = tr.assign(t=pd.to_datetime(tr["time"])).set_index("t")["pnl"].resample("YE").sum()
            print("  yearly: " + " ".join(f"{t.year}:{v:+.0f}" for t, v in yearly.items()) +
                  f"  ex-best-year: {net - yearly.max():+.2f}")


if __name__ == "__main__":
    main()
