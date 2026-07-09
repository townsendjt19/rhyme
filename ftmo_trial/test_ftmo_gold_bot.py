"""
Unit tests for the multi-slot FTMO trial bot -- ALL MT5 CALLS MOCKED at the
API boundary; no terminal is attached and no order can fire from this suite.

Run: D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/ftmo_trial/test_ftmo_gold_bot.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

import pandas as pd

import ftmo_gold_bot as bot
_REAL_SLOT_COUNT = bot.slot_position_count

# Test runs must NEVER write into the live observation log (personal-live
# 2026-07-03 regression guard): strip file handlers attached at import.
for h in list(bot.log.handlers) + list(logging.getLogger().handlers):
    if isinstance(h, logging.FileHandler):
        bot.log.removeHandler(h)
        logging.getLogger().removeHandler(h)


class FakeSymbolInfo:
    # XAUUSD-shaped: tick 0.001 worth $0.10/lot -> $100 per 1.0 price move
    trade_contract_size = 100.0
    trade_tick_size = 0.001
    trade_tick_value = 0.10
    volume_step = 0.01
    volume_min = 0.01
    volume_max = 100.0
    digits = 3


class FakeJpySymbolInfo(FakeSymbolInfo):
    # USDJPY-shaped: tick 0.001 worth ~$0.683/lot -> ~$683 per 1.0 price move
    trade_contract_size = 100_000.0
    trade_tick_value = 0.683


class FakeAccount:
    def __init__(self, equity=100_000.0, balance=100_000.0):
        self.equity, self.balance = equity, balance


def _signal(direction="long"):
    from strategy import Signal
    return Signal(direction=direction, entry_price=3300.0, stop_loss=3288.0,
                  take_profits=[3330.0, 3330.0, 3330.0], instrument="XAUUSD.sim",
                  timeframe="t", reason="test")


class FakePlugin:
    def __init__(self, direction="long"):
        self.direction = direction
        self.calls = 0
    def generate_signal(self, *a, **k):
        self.calls += 1
        return _signal(self.direction)


EPOCH_M30 = 1800 * 1_000_000   # a wake where every slot is due
EPOCH_M15 = EPOCH_M30 + 900    # a wake where only M15 slots are due


def fresh_slots(directions=("long", "long")):
    return [
        {"name": "xau", "symbol": "XAUUSD.sim", "plugin_file": bot.PULLBACK, "long_only": False,
         "risk_pct": 0.005, "magic": 1, "plugin": FakePlugin(directions[0]),
         "cycle_s": 1800, "tf": "M30", "needs_htf": True},
        {"name": "jpy", "symbol": "USDJPY.sim", "plugin_file": bot.PULLBACK, "long_only": True,
         "risk_pct": 0.005, "magic": 2, "plugin": FakePlugin(directions[1]),
         "cycle_s": 1800, "tf": "M30", "needs_htf": True},
    ]


def orb_slot(direction="long"):
    return {"name": "oxau", "symbol": "XAUUSD.sim", "plugin_file": bot.ORB_CLOSE,
            "long_only": False, "risk_pct": 0.005, "magic": 3,
            "plugin": FakePlugin(direction), "cycle_s": 900, "tf": "M15", "needs_htf": False}


def test_sizing():
    orig = bot.mt5.symbol_info
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    try:
        assert bot.size_lots("XAUUSD.sim", 100_000, 3300.0, 3288.0, 0.005) == 0.41
        assert bot.size_lots("XAUUSD.sim", 100_000, 3300.0, 3300.0, 0.005) == 0.0
        assert bot.size_lots("XAUUSD.sim", 100_000, 3300.0, 2700.0, 0.005) == 0.0
        for stop in (3291.2, 3282.5):
            lots = bot.size_lots("XAUUSD.sim", 100_000, 3300.0, stop, 0.005)
            assert lots == round(lots, 2), (stop, lots)
        # USDJPY-shaped tick economics: $500 risk, 0.6-yen stop, $683/unit/lot
        # -> 500/(0.6*683) = 1.22 lots. The old contract_size formula gave
        # 0.008 -> 0 (the live bug this guards against).
        bot.mt5.symbol_info = lambda s: FakeJpySymbolInfo()
        assert bot.size_lots("USDJPY.sim", 100_000, 146.0, 145.4, 0.005) == 1.22
        print("PASS: sizing uses tick economics (JPY-quoted symbols size correctly), no float dust")
    finally:
        bot.mt5.symbol_info = orig


def test_server_offset_dst():
    assert bot.server_offset_hours(pd.Timestamp("2026-01-15")) == 2
    assert bot.server_offset_hours(pd.Timestamp("2025-07-15")) == 3
    assert bot.server_offset_hours(pd.Timestamp("2026-03-29 00:59")) == 2
    assert bot.server_offset_hours(pd.Timestamp("2026-03-29 01:01")) == 3
    print("PASS: EET DST offset piecewise-correct incl. the spring boundary hour")


def _patch_shared(equity=100_000.0, day=0.0, total_positions=0):
    bot.mt5.account_info = lambda: FakeAccount(equity=equity)
    bot.day_pnl_usd = lambda: day
    bot.open_position_count = lambda symbol=None: total_positions
    bot.slot_position_count = lambda slot: 0


def test_daily_circuit_breaker_halts_all_slots():
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.fetch_frame, bot.SLOTS)
    _patch_shared(day=-2_500.0)
    bot.fetch_frame = lambda *a: (_ for _ in ()).throw(AssertionError("scanned past breaker"))
    bot.SLOTS = fresh_slots()
    try:
        bot.cycle(armed=True, wake_epoch=EPOCH_M30)
        assert all(s["plugin"].calls == 0 for s in bot.SLOTS)
        print("PASS: daily breaker halts BOTH slots before any scan")
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.fetch_frame, bot.SLOTS) = orig


def test_floor_halt():
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.fetch_frame, bot.SLOTS)
    _patch_shared(equity=92_999.0)
    bot.fetch_frame = lambda *a: (_ for _ in ()).throw(AssertionError("scanned past floor"))
    bot.SLOTS = fresh_slots()
    try:
        bot.cycle(armed=True, wake_epoch=EPOCH_M30)
        print("PASS: equity floor halts all slots before any scan")
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.fetch_frame, bot.SLOTS) = orig


def test_aggregate_cap():
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.fetch_frame, bot.SLOTS)
    _patch_shared(total_positions=4)
    bot.fetch_frame = lambda *a: (_ for _ in ()).throw(AssertionError("scanned past cap"))
    bot.SLOTS = fresh_slots()
    try:
        bot.cycle(armed=True, wake_epoch=EPOCH_M30)
        assert all(sl["plugin"].calls == 0 for sl in bot.SLOTS)
        print("PASS: aggregate 4-position cap stops all scanning")
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.fetch_frame, bot.SLOTS) = orig


def test_per_slot_position_cap():
    """xau has an open position; jpy must still scan."""
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.fetch_frame, bot.mt5.symbol_info, bot.place_order, bot.SLOTS)
    _patch_shared()
    bot.slot_position_count = lambda slot: (1 if slot["name"] == "xau" else 0)
    bot.fetch_frame = lambda *a: pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1]})
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    bot.place_order = lambda *a, **k: None
    bot.SLOTS = fresh_slots()
    try:
        bot.cycle(armed=False, wake_epoch=EPOCH_M30)
        assert bot.SLOTS[0]["plugin"].calls == 0, "xau scanned despite open position"
        assert bot.SLOTS[1]["plugin"].calls == 1, "jpy did not scan"
        print("PASS: per-slot cap blocks only the slot with the open position")
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.fetch_frame, bot.mt5.symbol_info, bot.place_order, bot.SLOTS) = orig


def test_long_only_filter():
    """jpy slot must skip SHORT signals; xau slot must trade them."""
    placed = []
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.fetch_frame, bot.mt5.symbol_info, bot.place_order, bot.SLOTS)
    _patch_shared()
    bot.fetch_frame = lambda *a: pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1]})
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    bot.place_order = lambda slot, d, l, s, t: placed.append((slot["name"], d)) or None
    bot.SLOTS = fresh_slots(directions=("short", "short"))
    try:
        bot.cycle(armed=True, wake_epoch=EPOCH_M30)
        assert placed == [("xau", "short")], placed
        print("PASS: long-only filter blocks jpy shorts; xau shorts still trade")
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.fetch_frame, bot.mt5.symbol_info, bot.place_order, bot.SLOTS) = orig


def test_dry_run_never_places():
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.fetch_frame, bot.mt5.symbol_info, bot.place_order, bot.SLOTS)
    _patch_shared()
    bot.fetch_frame = lambda *a: pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1]})
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    bot.place_order = lambda *a, **k: (_ for _ in ()).throw(AssertionError("ORDER PLACED IN DRY-RUN"))
    bot.SLOTS = fresh_slots()
    try:
        bot.cycle(armed=False, wake_epoch=EPOCH_M30)
        print("PASS: dry-run runs both slots' full pipeline, never places")
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.fetch_frame, bot.mt5.symbol_info, bot.place_order, bot.SLOTS) = orig


def test_plugin_state_isolation():
    """Two slots must get two DISTINCT module objects (re-entry state)."""
    a, b = bot.load_plugin_instance(), bot.load_plugin_instance()
    assert a is not b
    a._last_used_pair_id = ("x",)
    assert b._last_used_pair_id is None
    d = bot.load_plugin_instance(bot.DONCHIAN)
    assert hasattr(d, "generate_signal") and hasattr(d, "_long_armed")
    print("PASS: per-slot plugin instances hold independent re-entry state (both plugin files)")


def test_fetch_enrichment_feeds_real_signal_function():
    """Mock at the MT5 boundary, run the REAL plugin on fetch_frame output."""
    def fake_rates(sym, tf, pos, n):
        rows = []
        for i in range(n):
            px = 3300.0 + (i % 9) * 1.5
            rows.append({"time": 1_780_000_000 + i * 1800, "open": px, "high": px + 2.0,
                         "low": px - 2.0, "close": px + 0.5, "tick_volume": 100,
                         "spread": 250, "real_volume": 0})
        return rows
    orig = bot.mt5.copy_rates_from_pos
    bot.mt5.copy_rates_from_pos = fake_rates
    try:
        htf = bot.fetch_frame("XAUUSD.sim", 0, bot.H4_COUNT)
        ltf = bot.fetch_frame("XAUUSD.sim", 0, bot.M30_COUNT)
        assert "ema_20" in htf.columns and "fractal_high" in htf.columns
        plugin = bot.load_plugin_instance()
        result = plugin.generate_signal("XAUUSD.sim", htf, ltf, bot.MODE)   # must not raise
        assert result is None or hasattr(result, "direction")
        print("PASS: fetch_frame output feeds the REAL plugin without KeyError (seam covered)")
    finally:
        bot.mt5.copy_rates_from_pos = orig


def test_day_pnl_combines_closed_and_floating():
    class Deal:
        profit, commission, swap = -300.0, -2.0, 0.0
    orig = (bot.mt5.history_deals_get, bot.mt5.account_info)
    bot.mt5.history_deals_get = lambda a, b: [Deal(), Deal()]
    bot.mt5.account_info = lambda: FakeAccount(equity=99_500.0, balance=99_900.0)
    try:
        assert bot.day_pnl_usd() == -604.0 + -400.0
        print("PASS: day P&L = closed deals + floating (account-wide)")
    finally:
        bot.mt5.history_deals_get, bot.mt5.account_info = orig


# -- appended 2026-07-09: per-slot cadence / magic caps / ORB slot tests --

def test_slot_scheduling():
    """M30 slots skip the :15/:45 wakes; M15 slots scan every wake."""
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.slot_position_count, bot.fetch_frame, bot.mt5.symbol_info,
            bot.place_order, bot.SLOTS)
    _patch_shared()
    bot.slot_position_count = lambda slot: 0
    bot.fetch_frame = lambda *a: pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1]})
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    bot.place_order = lambda *a, **k: None
    bot.SLOTS = fresh_slots() + [orb_slot()]
    try:
        bot.cycle(armed=False, wake_epoch=EPOCH_M15)   # M15-only boundary
        assert bot.SLOTS[0]["plugin"].calls == 0 and bot.SLOTS[1]["plugin"].calls == 0
        assert bot.SLOTS[2]["plugin"].calls == 1
        bot.cycle(armed=False, wake_epoch=EPOCH_M30)   # everyone due
        assert bot.SLOTS[0]["plugin"].calls == 1 and bot.SLOTS[2]["plugin"].calls == 2
        print("PASS: M30 slots skip M15-only wakes; M15 slots scan every wake")
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.slot_position_count, bot.fetch_frame, bot.mt5.symbol_info,
         bot.place_order, bot.SLOTS) = orig


def test_magic_filtered_slot_cap():
    """A pullback-xau position must NOT block the orb-xau slot (same symbol)."""
    class Pos:
        def __init__(self, magic): self.magic = magic
    orig = bot.mt5.positions_get
    bot.mt5.positions_get = lambda symbol=None: [Pos(1)]   # xau pullback's magic
    try:
        assert _REAL_SLOT_COUNT({"symbol": "XAUUSD.sim", "magic": 1}) == 1
        assert _REAL_SLOT_COUNT({"symbol": "XAUUSD.sim", "magic": 3}) == 0
        print("PASS: per-slot cap is magic-filtered; shared-symbol slots don't block each other")
    finally:
        bot.mt5.positions_get = orig


def test_orb_slot_fetch_path():
    """needs_htf=False slots fetch a single M15 frame passed as both frames."""
    fetches = []
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.slot_position_count, bot.fetch_frame, bot.mt5.symbol_info,
            bot.place_order, bot.SLOTS)
    _patch_shared()
    bot.slot_position_count = lambda slot: 0
    def fake_fetch(sym, tf, count):
        fetches.append((tf, count))
        return pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1]})
    bot.fetch_frame = fake_fetch
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    bot.place_order = lambda *a, **k: None
    bot.SLOTS = [orb_slot()]
    try:
        bot.cycle(armed=False, wake_epoch=EPOCH_M15)
        assert fetches == [(bot.mt5.TIMEFRAME_M15, bot.M15_COUNT)], fetches
        print("PASS: ORB slot fetches exactly one M15 frame (no H4)")
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.slot_position_count, bot.fetch_frame, bot.mt5.symbol_info,
         bot.place_order, bot.SLOTS) = orig


if __name__ == "__main__":
    tests = [
        test_fetch_enrichment_feeds_real_signal_function,
        test_sizing, test_server_offset_dst,
        test_daily_circuit_breaker_halts_all_slots, test_floor_halt,
        test_aggregate_cap, test_per_slot_position_cap, test_long_only_filter,
        test_dry_run_never_places, test_plugin_state_isolation,
        test_slot_scheduling, test_magic_filtered_slot_cap, test_orb_slot_fetch_path,
        test_day_pnl_combines_closed_and_floating,
    ]
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
