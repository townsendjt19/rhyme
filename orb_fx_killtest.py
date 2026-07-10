"""
Campaign 5 Track B: US-open ORB (close variant) x FTMO FX (registration
ed31277). Mechanics verbatim from the live index design via orb_close_plugin;
OANDA M15 data (the harness default fetch -- no MT5 patch); verified all-in
FTMO costs as spread_pips. Line-B criteria: both stretches net-positive AND
n>=30 -> full window.

Run:  venv/Scripts/python.exe orb_fx_killtest.py [full]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import backtest
import risk

HERE = Path(__file__).parent
PAIRS = {
    "EUR_USD": {"pip_size": 0.0001, "pip_value": 10.0, "spread_pips": 0.7},
    "USD_JPY": {"pip_size": 0.01, "pip_value": 6.8, "spread_pips": 0.9},
    "GBP_USD": {"pip_size": 0.0001, "pip_value": 10.0, "spread_pips": 0.8},
}
STRETCHES = {
    "A2023": (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)),
    "B24H2": (datetime(2024, 7, 1, tzinfo=timezone.utc), datetime(2025, 7, 1, tzinfo=timezone.utc)),
}
FULL = (datetime(2021, 7, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc))


def main() -> None:
    full = len(sys.argv) > 1 and sys.argv[1] == "full"
    for pair, conv in PAIRS.items():
        stage = {"full": FULL} if full else STRETCHES
        for label, (start, end) in stage.items():
            plugin = backtest._load_plugin(str(HERE / "orb_close_plugin.py"))
            name = f"orbfx_{pair}_close_{label}"
            print(f"\n########## {name} ##########")
            tr = backtest.run_backtest(
                instrument=pair, mode="scalp", start=start, end=end,
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
