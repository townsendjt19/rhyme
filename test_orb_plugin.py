"""
Line B unit tests -- run BEFORE any backtest (standing convention).

Run: D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/test_orb_plugin.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

import orb_plugin_core as core


def frame(bars):
    """bars: list of (utc_str, o, h, l, c)."""
    idx = pd.DatetimeIndex([pd.Timestamp(t) for t, *_ in bars])
    df = pd.DataFrame([{"open": o, "high": h, "low": l, "close": c, "volume": 100}
                       for _, o, h, l, c in bars], index=idx)
    return df


# January 2026: EST, ET = UTC-5. 09:30 ET = 14:30 UTC.
OR_BARS = [("2026-01-15 14:30", 100, 104, 99, 101),
           ("2026-01-15 14:45", 101, 105, 100, 102)]   # OR: high 105, low 99, height 6 (> box-9 floor 5)


def fresh():
    core._used.clear()


def test_dst_offsets():
    assert core._us_dst_offset(pd.Timestamp("2026-01-15 12:00")) == -5
    assert core._us_dst_offset(pd.Timestamp("2025-07-15 12:00")) == -4
    # 2nd Sunday of March 2026 = Mar 8; switch at 07:00 UTC
    assert core._us_dst_offset(pd.Timestamp("2026-03-08 06:59")) == -5
    assert core._us_dst_offset(pd.Timestamp("2026-03-08 07:01")) == -4
    # 1st Sunday of Nov 2026 = Nov 1; switch at 06:00 UTC
    assert core._us_dst_offset(pd.Timestamp("2026-11-01 05:59")) == -4
    assert core._us_dst_offset(pd.Timestamp("2026-11-01 06:01")) == -5
    print("PASS: US DST offsets incl. both boundary hours")


def test_close_breakout_long():
    fresh()
    ltf = frame(OR_BARS + [("2026-01-15 15:00", 102, 106.5, 101.5, 106)])  # close 106 > 105
    s = core.generate_signal("SPX", ltf, ltf, "scalp", "close")
    assert s and s.direction == "long" and s.entry_price == 106
    assert s.stop_loss == 99 and s.take_profits[0] == 106 + 2 * 6
    print("PASS: close-variant long fires at close with OR stop and 2x-height TP")


def test_touch_fires_where_close_does_not():
    fresh()
    # bar pokes above 103 but closes back inside
    bars = OR_BARS + [("2026-01-15 15:00", 102, 105.5, 101.5, 104.5)]
    ltf = frame(bars)
    assert core.generate_signal("SPX", ltf, ltf, "scalp", "close") is None
    fresh()
    s = core.generate_signal("SPX", ltf, ltf, "scalp", "touch")
    assert s and s.direction == "long" and s.entry_price == 105  # AT the level
    print("PASS: touch-variant fills at the OR level on a poke the close-variant ignores")


def test_one_per_day_direction():
    fresh()
    ltf1 = frame(OR_BARS + [("2026-01-15 15:00", 102, 106.5, 101.5, 106)])
    assert core.generate_signal("SPX", ltf1, ltf1, "scalp", "close") is not None
    ltf2 = frame(OR_BARS + [("2026-01-15 15:00", 102, 106.5, 101.5, 106),
                            ("2026-01-15 15:15", 106, 107.5, 105.5, 107)])
    assert core.generate_signal("SPX", ltf2, ltf2, "scalp", "close") is None
    print("PASS: one trade per (session, direction) -- identity consumed")


def test_window_gating():
    fresh()
    # 09:45 ET bar (14:45 UTC) is inside the OR window -> no signal
    ltf = frame([OR_BARS[0], ("2026-01-15 14:45", 101, 106, 100, 105)])
    assert core.generate_signal("SPX", ltf, ltf, "scalp", "close") is None
    # 15:45 ET (20:45 UTC) is past the 15:30 window end
    fresh()
    ltf = frame(OR_BARS + [("2026-01-15 20:45", 102, 106.5, 101.5, 106)])
    assert core.generate_signal("SPX", ltf, ltf, "scalp", "close") is None
    print("PASS: signal window [10:00, 15:30) ET enforced on both sides")


def test_box9_floor():
    fresh()
    # OR height 2 < 10 x 0.5 spread -> floored, no signal ever
    bars = [("2026-01-15 14:30", 100, 101, 99.5, 100.5),
            ("2026-01-15 14:45", 100.5, 101.5, 99.5, 101),
            ("2026-01-15 15:00", 101, 103, 100.5, 102.8)]
    ltf = frame(bars)
    assert core.generate_signal("SPX", ltf, ltf, "scalp", "close") is None
    print("PASS: box-9 floor rejects sub-10x-spread opening ranges")


def test_incomplete_or_skipped():
    fresh()
    ltf = frame([OR_BARS[0], ("2026-01-15 15:00", 102, 104.5, 101.5, 104)])  # only one OR bar
    assert core.generate_signal("SPX", ltf, ltf, "scalp", "close") is None
    print("PASS: holiday/half-day sessions with an incomplete OR are skipped")


if __name__ == "__main__":
    tests = [test_dst_offsets, test_close_breakout_long, test_touch_fires_where_close_does_not,
             test_one_per_day_direction, test_window_gating, test_box9_floor,
             test_incomplete_or_skipped]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ERROR {t.__name__}: {e}")
            failed += 1
    print(f"\nResults: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
