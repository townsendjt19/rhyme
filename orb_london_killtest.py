"""
Campaign 3 Track C: London-open ORB on XAUUSD (registration c1dd8c2,
committed before results). Line B kill-test criteria verbatim: both
stretches must pass (net-positive AND n >= 30) -> full window.
Cost: 30 pips-equiv commission-inclusive (25 real .sim spread + ~5 comm).
Pre-adjudicated: overlap lift >= 1.35x vs live oxau -> BENCH regardless.

Run:  venv/Scripts/python.exe orb_london_killtest.py [full]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import backtest
import risk
from gate2_killtest import mt5_fetch_candles

HERE = Path(__file__).parent
CONV = {"pip_size": 0.01, "pip_value": 0.10, "spread_pips": 30.0}
STRETCHES = {
    "A2023": (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)),
    "B24H2": (datetime(2024, 7, 1, tzinfo=timezone.utc), datetime(2025, 7, 1, tzinfo=timezone.utc)),
}
FULL = (datetime(2021, 12, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc))


def main() -> None:
    full = len(sys.argv) > 1 and sys.argv[1] == "full"
    backtest.fetch_candles = mt5_fetch_candles
    risk._PIP_SIZE["XAUUSD"] = CONV["pip_size"]
    risk._PIP_VALUE_USD["XAUUSD"] = CONV["pip_value"]
    stage = {"full": FULL} if full else STRETCHES
    for label, (start, end) in stage.items():
        plugin = backtest._load_plugin(str(HERE / "orb_london_plugin.py"))
        name = f"orb_london_XAUUSD_close_{label}"
        print(f"\n########## {name} ##########")
        tr = backtest.run_backtest(
            instrument="XAUUSD", mode="scalp", start=start, end=end,
            signal_plugin=plugin, fixed_risk=80.0,
            spread_pips=CONV["spread_pips"], strategy_name=name,
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
