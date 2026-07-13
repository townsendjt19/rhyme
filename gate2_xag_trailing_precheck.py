"""
Trailing-floor prop pre-check for the XAGUSD real-cost Gate-2 survivor:
trend_origin_pullback, full window, $80 fixed risk (registered 2026-07-13,
cost-correction entry; conventions from gate2_xag_realcost.py).

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/gate2_xag_trailing_precheck.py
"""
import json
from pathlib import Path

import pandas as pd

import backtest
import risk
from prop_rules import trailing_precheck
from gate2_killtest import mt5_fetch_candles
from gate2_xag_realcost import SYM, CONV, FULL, FIXED_RISK

HERE = Path(__file__).parent


def main():
    backtest.TF_MAP.setdefault("scalp30", ("H4", "M30"))
    backtest.fetch_candles = mt5_fetch_candles
    risk._PIP_SIZE[SYM] = CONV["pip_size"]
    risk._PIP_VALUE_USD[SYM] = CONV["pip_value"]

    plugin_fn = backtest._load_plugin(str(HERE / "trend_origin_pullback_plugin.py"))
    start, end = FULL
    marks_out = []
    tr = backtest.run_backtest(
        instrument=SYM, mode="scalp30", start=start, end=end,
        signal_plugin=plugin_fn, fixed_risk=FIXED_RISK,
        spread_pips=CONV["spread_pips"],
        strategy_name="gate2xagreal_trend_origin_pullback_full",
        collect_marks=True, marks_out=marks_out,
    )

    tr = tr.reset_index(drop=True)
    tr["trade_id"] = tr.index
    tr["R"] = tr["pnl"] / FIXED_RISK
    mk = pd.DataFrame(
        [(tid, ts, mark) for tid, marks in enumerate(marks_out) for ts, mark in marks],
        columns=["trade_id", "time", "mark"],
    )
    mk["R"] = mk["mark"] / FIXED_RISK

    result = trailing_precheck(tr, mk)
    print(json.dumps(result, indent=2, default=str))
    (HERE / "gate2_XAG_pullback_trailing_precheck.json").write_text(
        json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
