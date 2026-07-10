"""
Campaign 4 Track A: IB-width ORB variant on SPX + XAUUSD (registration
1e1d1b1). Line-B criteria verbatim (both stretches net-positive AND n>=30)
-> full window. Disposition is pre-adjudicated swap-or-bench vs the live
30-minute-OR slots -- never a parallel deployment.

Run:  venv/Scripts/python.exe ib_killtest.py [full]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import backtest
import risk
from gate2_killtest import mt5_fetch_candles

HERE = Path(__file__).parent
SYMBOLS = {
    "SPX":    {"pip_size": 0.10, "pip_value": 0.10, "spread_pips": 5.0},
    "XAUUSD": {"pip_size": 0.01, "pip_value": 0.10, "spread_pips": 30.0},  # incl. ~5p commission
}
STRETCHES = {
    "A2023": (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)),
    "B24H2": (datetime(2024, 7, 1, tzinfo=timezone.utc), datetime(2025, 7, 1, tzinfo=timezone.utc)),
}
FULL_WINDOWS = {
    "SPX":    (datetime(2022, 7, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc)),
    "XAUUSD": (datetime(2021, 12, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc)),
}


def main() -> None:
    full = len(sys.argv) > 1 and sys.argv[1] == "full"
    backtest.fetch_candles = mt5_fetch_candles
    for sym, conv in SYMBOLS.items():
        risk._PIP_SIZE[sym] = conv["pip_size"]
        risk._PIP_VALUE_USD[sym] = conv["pip_value"]
    for sym, conv in SYMBOLS.items():
        stage = {"full": FULL_WINDOWS[sym]} if full else STRETCHES
        for label, (start, end) in stage.items():
            plugin = backtest._load_plugin(str(HERE / "ib_orb_plugin.py"))
            name = f"ib_{sym}_close_{label}"
            print(f"\n########## {name} ##########")
            tr = backtest.run_backtest(
                instrument=sym, mode="scalp", start=start, end=end,
                signal_plugin=plugin, fixed_risk=80.0,
                spread_pips=conv["spread_pips"], strategy_name=name,
            )
            tr.to_csv(HERE / f"{name}.csv", index=False)
            n = len(tr)
            net = tr["pnl"].sum() if n else 0.0
            wr = (tr["pnl"] > 0).mean() * 100 if n else float("nan")
            print(f"  n={n}  net=${net:.2f}  WR={wr:.1f}%  -> {'PASS' if net > 0 and n >= 30 else 'FAIL'}")
            if full and n:
                import pandas as pd
                yearly = tr.assign(t=pd.to_datetime(tr["time"])).set_index("t")["pnl"].resample("YE").sum()
                print("  yearly: " + " ".join(f"{t.year}:{v:+.0f}" for t, v in yearly.items()) +
                      f"  ex-best-year: {net - yearly.max():+.2f}")


if __name__ == "__main__":
    main()
