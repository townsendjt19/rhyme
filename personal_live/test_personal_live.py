"""
Unit tests for the personal live experiment -- ORDER PLACEMENT MOCKED, no
live order can fire from this suite (no client is ever constructed).

Run: D:/rhyme/venv/Scripts/python.exe D:/rhyme/personal_live/test_personal_live.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import personal_live_scalp as pl


def test_sizing_unit_granularity():
    # $99 equity, 1% = $0.99 risk; USD_JPY entry 155.000, stop 37.6 pips away.
    units = pl.size_units(99.0, 155.000, 154.624)
    # pip value/unit = 0.01/155 = 6.4516e-5; 0.99/(37.6*6.4516e-5) = 408.1 -> 408
    assert units == 408, units
    print(f"PASS: median scalp30 trade sizes to {units} whole units at $99/1% (no lot flooring)")


def test_sizing_wide_stop_still_places():
    units = pl.size_units(99.0, 155.000, 153.967)   # 103.3-pip stop (95th pct)
    assert 1 <= units < 408, units
    print(f"PASS: 95th-percentile stop still sizes ({units} units) -- 1-unit granularity keeps it tradeable")


def test_sizing_zero_guard():
    assert pl.size_units(99.0, 155.000, 155.000) == 0
    assert pl.size_units(0.10, 155.000, 154.624) == 0   # microscopic equity -> 0 units -> skip
    print("PASS: zero stop distance and dust equity size to 0 (skip), never a negative/invalid order")


class FakeApi:
    """Never talks to any host; asserts nothing reaches order placement."""
    def request(self, req):
        raise AssertionError("network request attempted in a mocked test")


def test_floor_blocks_entries(monkey=None):
    calls = {"scan": 0}
    orig_summary, orig_count = pl.account_summary, pl.open_trade_count
    pl.account_summary = lambda api: {"NAV": "49.99", "marginAvailable": "40"}
    pl.open_trade_count = lambda api: (_ for _ in ()).throw(AssertionError("scan past floor"))
    try:
        pl.cycle(object(), armed=True)   # armed=True: the floor must stop it before ANY scan
        print("PASS: NAV below the $50 personal floor blocks the cycle before any scan or order")
    finally:
        pl.account_summary, pl.open_trade_count = orig_summary, orig_count


def test_one_position_cap():
    orig_summary, orig_count, orig_fetch = pl.account_summary, pl.open_trade_count, pl.fetch_frame
    pl.account_summary = lambda api: {"NAV": "99.0", "marginAvailable": "80"}
    pl.open_trade_count = lambda api: 1
    pl.fetch_frame = lambda api, g: (_ for _ in ()).throw(AssertionError("fetched candles past the cap"))
    try:
        pl.cycle(object(), armed=True)
        print("PASS: one-open-position cap stops the cycle before candles are even fetched")
    finally:
        pl.account_summary, pl.open_trade_count, pl.fetch_frame = orig_summary, orig_count, orig_fetch


def test_dry_run_never_places():
    import pandas as pd
    from strategy import Signal
    orig = (pl.account_summary, pl.open_trade_count, pl.fetch_frame, pl.generate_signal, pl.place_order)
    pl.account_summary = lambda api: {"NAV": "99.0", "marginAvailable": "80"}
    pl.open_trade_count = lambda api: 0
    pl.fetch_frame = lambda api, g: pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1]})
    pl.generate_signal = lambda *a, **k: Signal(
        direction="long", entry_price=155.000, stop_loss=154.624,
        take_profits=[155.9, 155.9, 155.9], instrument="USD_JPY",
        timeframe="t", reason="test")
    pl.place_order = lambda *a, **k: (_ for _ in ()).throw(AssertionError("ORDER PLACED IN DRY-RUN"))
    try:
        pl.cycle(object(), armed=False)
        print("PASS: dry-run (unarmed) runs the full pipeline and NEVER reaches order placement")
    finally:
        (pl.account_summary, pl.open_trade_count, pl.fetch_frame, pl.generate_signal, pl.place_order) = orig


def test_armed_places_with_correct_order():
    import pandas as pd
    from strategy import Signal
    placed = {}
    orig = (pl.account_summary, pl.open_trade_count, pl.fetch_frame, pl.generate_signal, pl.place_order)
    pl.account_summary = lambda api: {"NAV": "99.0", "marginAvailable": "80"}
    pl.open_trade_count = lambda api: 0
    pl.fetch_frame = lambda api, g: pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1]})
    pl.generate_signal = lambda *a, **k: Signal(
        direction="short", entry_price=155.000, stop_loss=155.376,
        take_profits=[154.1, 154.1, 154.1], instrument="USD_JPY",
        timeframe="t", reason="test")
    def fake_place(api, units, sl, tp):
        placed.update(units=units, sl=sl, tp=tp)
        return {"price": "155.0", "tradeOpened": {"tradeID": "mock"}}
    pl.place_order = fake_place
    try:
        pl.cycle(object(), armed=True)
        assert placed["units"] == -408, placed   # short -> negative units, 37.6p stop at $99
        assert placed["sl"] == 155.376 and placed["tp"] == 154.1
        print(f"PASS: armed cycle places the mocked order with correct signed units ({placed['units']}), SL, TP")
    finally:
        (pl.account_summary, pl.open_trade_count, pl.fetch_frame, pl.generate_signal, pl.place_order) = orig


if __name__ == "__main__":
    test_sizing_unit_granularity()
    test_sizing_wide_stop_still_places()
    test_sizing_zero_guard()
    test_floor_blocks_entries()
    test_one_position_cap()
    test_dry_run_never_places()
    test_armed_places_with_correct_order()
    print("\nALL 7 TESTS PASSED")
