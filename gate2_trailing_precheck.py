"""
Trailing-floor prop pre-check for the sole Gate-2 survivor:
trend_origin_pullback on XAUUSD, full window, $80 fixed risk.

Re-runs the registered full-window backtest with floating marks collected,
then applies prop_rules.trailing_precheck (amended-protocol requirement
before any prop-track claim). One-shot; conventions identical to
gate2_killtest.py.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/gate2_trailing_precheck.py
"""
import json
from pathlib import Path

import pandas as pd

import backtest
import risk
from prop_rules import trailing_precheck
from gate2_killtest import SYMBOLS, FULL_WINDOWS, FIXED_RISK, mt5_fetch_candles

HERE = Path(__file__).parent


def main():
    backtest.TF_MAP.setdefault("scalp30", ("H4", "M30"))
    backtest.fetch_candles = mt5_fetch_candles
    conv = SYMBOLS["XAUUSD"]
    risk._PIP_SIZE["XAUUSD"] = conv["pip_size"]
    risk._PIP_VALUE_USD["XAUUSD"] = conv["pip_value"]

    plugin_fn = backtest._load_plugin(str(HERE / "trend_origin_pullback_plugin.py"))
    start, end = FULL_WINDOWS["XAUUSD"]
    marks_out = []
    tr = backtest.run_backtest(
        instrument="XAUUSD", mode="scalp30", start=start, end=end,
        signal_plugin=plugin_fn, fixed_risk=FIXED_RISK,
        spread_pips=conv["spread_pips"],
        strategy_name="gate2_XAUUSD_trend_origin_pullback_full",
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
    (HERE / "gate2_XAUUSD_pullback_trailing_precheck.json").write_text(
        json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
