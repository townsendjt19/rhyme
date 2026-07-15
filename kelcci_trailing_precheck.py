"""
Trailing pre-checks for the bench-deployment-sweep winners (registration
75492f4): keltner x USD_JPY and cci x USD_JPY, full window, marks collected,
prop_rules.trailing_precheck. OANDA data, megascreen conventions verbatim.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/kelcci_trailing_precheck.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import backtest
from prop_rules import trailing_precheck
from megascreen_killtest import make_plugin

HERE = Path(__file__).parent
FULL = (datetime(2021, 12, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc))
FIXED_RISK = 80.0


def main():
    backtest.TF_MAP.setdefault("scalp30", ("H4", "M30"))
    for family in ("keltner", "cci"):
        marks_out = []
        tr = backtest.run_backtest(
            instrument="USD_JPY", mode="scalp30", start=FULL[0], end=FULL[1],
            signal_plugin=make_plugin(family), fixed_risk=FIXED_RISK,
            spread_pips=0.9, strategy_name=f"precheck_{family}_jpy",
            collect_marks=True, marks_out=marks_out)
        tr = tr.reset_index(drop=True)
        tr["trade_id"] = tr.index
        tr["R"] = tr["pnl"] / FIXED_RISK
        mk = pd.DataFrame([(tid, ts, m) for tid, marks in enumerate(marks_out)
                           for ts, m in marks], columns=["trade_id", "time", "mark"])
        mk["R"] = mk["mark"] / FIXED_RISK
        result = trailing_precheck(tr, mk)
        print(f"===== {family} x USD_JPY =====", flush=True)
        print(json.dumps(result, indent=2, default=str), flush=True)
        (HERE / f"{family}_jpy_trailing_precheck.json").write_text(
            json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
