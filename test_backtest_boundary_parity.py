"""
Regression guard: per-year vs continuous backtest boundary parity.

This is the exact case that exposed the 2026-07-02 harness warm-up bug
(diagnosis at commit 631de22): USD_CAD 2022Q3-2023Q3 on range_fade_v2 read
+$851.09 continuous vs +$147.95 across a calendar-year split -- a $703 gap
made of (1) warm-up dead zones, because candles were fetched from `start`
with no prefix while the plugin needs 121 H4 candles before it can fire,
and (2) an end_of_data force-close of a trade still open at the segment end.

After the fix (warm-up prefix + exit simulation past `end`), a run split at
a year boundary and a continuous run over the same calendar window must
produce IDENTICAL trade lists: same entries, same pnl to the cent, same
exit reasons. This test must stay in the permanent suite.

Run (hits the OANDA practice API for candles; takes a few minutes):
    D:/rhyme/venv/Scripts/python.exe D:/rhyme/test_backtest_boundary_parity.py
"""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import backtest

backtest.TF_MAP.setdefault("scalp30", ("H4", "M30"))
if hasattr(backtest, "_TF_MAP_LABELS"):
    backtest._TF_MAP_LABELS.setdefault("scalp30", {"htf": "H4", "ltf": "M30"})

PLUGIN_PATH = str(Path(__file__).parent / "range_fade_v2_plugin.py")

WINDOW_START = datetime(2022, 7, 1, tzinfo=timezone.utc)
YEAR_SPLIT = datetime(2023, 1, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2023, 10, 1, tzinfo=timezone.utc)

COMPARE_COLS = ["direction", "entry", "sl", "tp1", "pnl", "exit_reason"]


def _run(start: datetime, end: datetime) -> pd.DataFrame:
    # Fresh plugin load per run -- module-level re-entry-guard state must not
    # leak between runs (same convention as the per-year runners).
    plugin = backtest._load_plugin(PLUGIN_PATH)
    return backtest.run_backtest(
        "USD_CAD", "scalp30", start, end, 10_000.0,
        config=backtest.StrategyConfig(),
        signal_plugin=plugin,
        strategy_name="range_fade_v2",
        fixed_risk=80.0,
        spread_pips=None,
    )


def test_boundary_parity():
    continuous = _run(WINDOW_START, WINDOW_END).set_index("time")
    seg1 = _run(WINDOW_START, YEAR_SPLIT)
    seg2 = _run(YEAR_SPLIT, WINDOW_END)
    split = pd.concat([seg1, seg2], ignore_index=True).set_index("time")

    only_cont = continuous.index.difference(split.index)
    only_split = split.index.difference(continuous.index)
    assert len(only_cont) == 0 and len(only_split) == 0, (
        f"entry sets differ: {len(only_cont)} only-continuous {list(only_cont)}, "
        f"{len(only_split)} only-split {list(only_split)}"
    )

    for t in continuous.index:
        rc, rs = continuous.loc[t], split.loc[t]
        for col in COMPARE_COLS:
            vc, vs = rc[col], rs[col]
            if col == "pnl":
                assert abs(vc - vs) <= 0.01, (
                    f"{t}: pnl differs -- continuous {vc:.2f} vs split {vs:.2f}"
                )
            else:
                assert vc == vs, f"{t}: {col} differs -- continuous {vc!r} vs split {vs!r}"

    assert abs(continuous["pnl"].sum() - split["pnl"].sum()) <= 0.01

    print(
        f"PASS: boundary parity -- {len(continuous)} trades identical across run shapes "
        f"(net {continuous['pnl'].sum():+.2f} both ways, "
        f"seg1 n={len(seg1)}, seg2 n={len(seg2)})"
    )


if __name__ == "__main__":
    test_boundary_parity()
