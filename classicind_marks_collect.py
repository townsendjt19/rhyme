"""
Marks collection for the classic-indicator screen's two validated USD_JPY
cells (registration 53610c6): rerun the full window with collect_marks=True
and write the trades CSV + marks pkl under the corrected_f86d9f4_* naming
that prop_rules.py's loader expects (the prefix is the loader's de facto
format marker; these runs use the current harness, which includes f86d9f4).
Deterministic rerun of the adjudicated cells — same signal path, marks added.

Run:  venv/Scripts/python.exe classicind_marks_collect.py
"""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import backtest

HERE = Path(__file__).parent
BT = HERE / "backtests"
FULL = (datetime(2021, 7, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc))
CELLS = {
    "jpy_adxgate": "adx_gate_plugin.py",
    "jpy_frama": "frama_plugin.py",
}


def main() -> None:
    for name, plugin_file in CELLS.items():
        plugin = backtest._load_plugin(str(HERE / plugin_file))
        marks_out: list = []
        tr = backtest.run_backtest(
            instrument="USD_JPY", mode="scalp30", start=FULL[0], end=FULL[1],
            signal_plugin=plugin, fixed_risk=80.0,
            strategy_name=f"classicind_marks_{name}",
            collect_marks=True, marks_out=marks_out,
        )
        tr = tr.reset_index(drop=True)
        tr["trade_id"] = tr.index   # prop_rules.py join key to the marks frame
        tr.to_csv(BT / f"corrected_f86d9f4_{name}_2021-2026ytd.csv", index=False)
        mk = pd.DataFrame(
            [(tid, ts, mark) for tid, marks in enumerate(marks_out) for ts, mark in marks],
            columns=["trade_id", "time", "mark"],
        )
        mk.to_pickle(BT / f"corrected_f86d9f4_{name}_marks.pkl")
        print(f"{name}: {len(tr)} trades, {len(mk)} marks -> backtests/corrected_f86d9f4_{name}_*")


if __name__ == "__main__":
    main()
