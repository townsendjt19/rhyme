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
    def __init__(self, equity=100_000.0, balance=100_000.0, margin=0.0):
        self.equity, self.balance, self.margin = equity, balance, margin


class FakeTick:
    ask, bid = 3300.1, 3300.0


# Margin-guard API defaults for the whole suite (no terminal attached):
# generous budget so pre-guard tests keep their behavior; the guard's own
# tests override these locally.
bot.mt5.symbol_info_tick = lambda s: FakeTick()
bot.mt5.order_calc_margin = lambda otype, s, lots, price: lots * 100.0


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
    _patch_shared(total_positions=bot.MAX_OPEN_POSITIONS)
    bot.fetch_frame = lambda *a: (_ for _ in ()).throw(AssertionError("scanned past cap"))
    bot.SLOTS = fresh_slots()
    try:
        bot.cycle(armed=True, wake_epoch=EPOCH_M30)
        assert all(sl["plugin"].calls == 0 for sl in bot.SLOTS)
        print(f"PASS: aggregate {bot.MAX_OPEN_POSITIONS}-position backstop stops all scanning")
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.fetch_frame, bot.SLOTS) = orig


def test_mixed_k_slot():
    """max_pos=2 slot: trades (at half risk) with 1 open, shadow-scans at 2."""
    placed = []
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.fetch_frame, bot.mt5.symbol_info, bot.place_order,
            bot.size_lots, bot.SLOTS)
    _patch_shared()
    sized = []
    bot.fetch_frame = lambda *a: pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1]})
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    bot.size_lots = lambda sym, eq, e, sl, rp: sized.append(rp) or 0.20
    bot.place_order = lambda slot, d, l, s, t: placed.append(slot["name"]) or None
    slot = {"name": "tl", "symbol": "USDJPY.sim", "plugin_file": bot.TRENDLINE,
            "long_only": False, "risk_pct": 0.005, "magic": 7, "plugin": FakePlugin(),
            "cycle_s": 1800, "tf": "M30", "needs_htf": False, "max_pos": 2}
    bot.SLOTS = [slot]
    try:
        bot.slot_position_count = lambda s: 1          # one open -> may still trade
        bot.cycle(armed=True, wake_epoch=EPOCH_M30)
        assert placed == ["tl"] and abs(sized[-1] - 0.0025) < 1e-12, (placed, sized)
        bot.slot_position_count = lambda s: 2          # at max_pos -> shadow only
        bot.cycle(armed=True, wake_epoch=EPOCH_M30 + 1800)
        assert placed == ["tl"], placed
        print("PASS: mixed-k slot trades at risk/k below max_pos, shadow-scans at max_pos")
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.fetch_frame, bot.mt5.symbol_info, bot.place_order,
         bot.size_lots, bot.SLOTS) = orig


def test_per_slot_position_cap():
    """xau has an open position: it SHADOW-scans (plugin called, capture-rate
    logging) but must NEVER place; jpy scans and may trade."""
    placed = []
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.fetch_frame, bot.mt5.symbol_info, bot.place_order, bot.SLOTS)
    _patch_shared()
    bot.slot_position_count = lambda slot: (1 if slot["name"] == "xau" else 0)
    bot.fetch_frame = lambda *a: pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1]})
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    bot.place_order = lambda slot, d, l, s, t: placed.append(slot["name"]) or None
    bot.SLOTS = fresh_slots()
    try:
        bot.cycle(armed=True, wake_epoch=EPOCH_M30)
        assert bot.SLOTS[0]["plugin"].calls == 1, "blocked slot did not shadow-scan"
        assert bot.SLOTS[1]["plugin"].calls == 1, "jpy did not scan"
        assert placed == ["jpy"], f"blocked slot must never place: {placed}"
        print("PASS: blocked slot shadow-scans (never places); open slot trades")
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


# -- appended 2026-07-09 (Campaign 2): volcomp plugin seam tests --

def _volcomp_frame(break_dir="up", early_break=False, compressed=True):
    """8 synthetic server days of M30 bars; day 7 is the compression candidate,
    day 8 ('today') has 3 bars whose last optionally breaks the range."""
    rows, idx = [], []
    for d in range(7):                       # completed days
        base = 3300.0 + d * 2
        wide = 20.0 if (d < 6 or not compressed) else 4.0   # last day narrow
        for b in range(10):
            idx.append(pd.Timestamp("2026-07-01") + pd.Timedelta(days=d, minutes=30 * b))
            rows.append({"open": base, "high": base + wide / 2,
                         "low": base - wide / 2, "close": base})
    comp_hi, comp_lo = 3312.0 + 2.0, 3312.0 - 2.0          # day-7 range (base 3312, wide 4)
    today = pd.Timestamp("2026-07-08")
    px = [3312.0, comp_hi + (5.0 if early_break else -1.0), 0.0]
    px[2] = (comp_hi + 3.0) if break_dir == "up" else (comp_lo - 3.0)
    for b, p in enumerate(px):
        idx.append(today + pd.Timedelta(minutes=30 * b))
        rows.append({"open": p, "high": p + 1.0, "low": p - 1.0, "close": p})
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


def test_volcomp_signal_and_levels():
    plug = bot.load_plugin_instance(bot.VOLCOMP)
    f = _volcomp_frame("up")
    sig = plug.generate_signal("XAUUSD.sim", f, f, bot.MODE)
    assert sig is not None and sig.direction == "long"
    assert sig.stop_loss == 3310.0                          # compression-day low
    risk = sig.entry_price - sig.stop_loss
    assert abs(sig.take_profits[0] - (sig.entry_price + 2.5 * risk)) < 1e-9
    # re-entry guard: same compression day never signals twice
    assert plug.generate_signal("XAUUSD.sim", f, f, bot.MODE) is None
    plug2 = bot.load_plugin_instance(bot.VOLCOMP)
    sig2 = plug2.generate_signal("XAUUSD.sim", None, _volcomp_frame("down"), bot.MODE)
    assert sig2 is not None and sig2.direction == "short" and sig2.stop_loss == 3314.0
    print("PASS: volcomp signals on the breaking close with killtest SL/TP levels + re-entry guard")


def test_volcomp_no_signal_cases():
    plug = bot.load_plugin_instance(bot.VOLCOMP)
    # no compression -> no signal
    assert plug.generate_signal("X", None, _volcomp_frame(compressed=False), bot.MODE) is None
    # an EARLIER bar today already broke the range -> day is spent, never chase
    plug2 = bot.load_plugin_instance(bot.VOLCOMP)
    assert plug2.generate_signal("X", None, _volcomp_frame(early_break=True), bot.MODE) is None
    # short history -> no signal
    plug3 = bot.load_plugin_instance(bot.VOLCOMP)
    assert plug3.generate_signal("X", None, _volcomp_frame()[:100].iloc[:50], bot.MODE) is None
    print("PASS: volcomp stays flat on no-compression, missed-break, and short-history frames")


# -- appended 2026-07-10 (Campaign 6): weekend-gap slot + timed-exit tests --

def _gap_frame(gap_up=True, monday_utc="2026-07-13 07:00"):
    """~23 ET days of M30 bars ending in the Monday 03:00-03:30 ET window
    (07:00 UTC in July = 03:00 EDT), with a weekend break before the last day."""
    rows, idx = [], []
    t = pd.Timestamp("2026-06-10 00:00")
    end_fri = pd.Timestamp("2026-07-10 20:00")
    while t <= end_fri:
        if t.dayofweek < 5:
            rows.append({"open": 1.1000, "high": 1.1050, "low": 1.0950, "close": 1.1000})
            idx.append(t)
        t += pd.Timedelta(minutes=30)
    mon = pd.Timestamp(monday_utc) - pd.Timedelta(minutes=90)   # a few bars into Monday
    px = 1.1080 if gap_up else 1.0920
    for b in range(3):
        idx.append(mon + pd.Timedelta(minutes=30 * b))
        rows.append({"open": px, "high": px + 0.001, "low": px - 0.001, "close": px})
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


def test_wkndgap_signal():
    plug = bot.load_plugin_instance(bot.WKNDGAP)
    f = _gap_frame(gap_up=True)
    sig = plug.generate_signal("EURUSD.sim", None, f, bot.MODE)
    assert sig is not None and sig.direction == "long", sig
    assert sig.stop_loss < sig.entry_price          # 1xATR below
    assert plug.generate_signal("EURUSD.sim", None, f, bot.MODE) is None  # one per Monday
    plug2 = bot.load_plugin_instance(bot.WKNDGAP)
    sig2 = plug2.generate_signal("EURUSD.sim", None, _gap_frame(gap_up=False), bot.MODE)
    assert sig2 is not None and sig2.direction == "short"
    # outside the Monday 03:00-03:30 ET window -> no signal (shift last bar)
    plug3 = bot.load_plugin_instance(bot.WKNDGAP)
    f3 = _gap_frame(monday_utc="2026-07-13 12:00")
    assert plug3.generate_signal("EURUSD.sim", None, f3, bot.MODE) is None
    print("PASS: wkndgap signals gap-direction in the Monday window only, one entry/Monday")


def test_timed_exit_rule():
    slot = {"timed_exit": True}
    # Monday 2026-07-13: 03:05 ET = 07:05 UTC -> position may live
    assert not bot.timed_exit_due(slot, pd.Timestamp("2026-07-13 07:05"))
    # Monday 16:00 ET = 20:00 UTC -> close
    assert bot.timed_exit_due(slot, pd.Timestamp("2026-07-13 20:00"))
    # Tuesday any time -> close (downtime recovery)
    assert bot.timed_exit_due(slot, pd.Timestamp("2026-07-14 09:00"))
    # non-timed slots never
    assert not bot.timed_exit_due({"name": "xau"}, pd.Timestamp("2026-07-13 20:00"))
    print("PASS: timed-exit rule (Monday-before-16:00-ET only; downtime recovery closes)")


def test_timed_exit_pass_runs_before_guards():
    closed = []
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.slot_position_count, bot.fetch_frame, bot.close_slot_position, bot.SLOTS)
    _patch_shared(day=-9_999.0)                      # breaker WOULD halt entries
    bot.slot_position_count = lambda slot: 1 if slot.get("timed_exit") else 0
    bot.close_slot_position = lambda slot, armed: closed.append(slot["name"])
    bot.fetch_frame = lambda *a: (_ for _ in ()).throw(AssertionError("scanned past breaker"))
    bot.SLOTS = fresh_slots() + [{"name": "gap", "symbol": "EURUSD.sim", "plugin_file": bot.WKNDGAP,
                                  "long_only": False, "risk_pct": 0.005, "magic": 9,
                                  "plugin": FakePlugin(), "cycle_s": 1800, "tf": "M30",
                                  "needs_htf": False, "timed_exit": True}]
    try:
        # Tuesday wake epoch: exit must fire even though the breaker halts scanning
        epoch = pd.Timestamp("2026-07-14 20:00").timestamp()
        bot.cycle(armed=True, wake_epoch=epoch)
        assert closed == ["gap"], closed
        print("PASS: timed-exit pass fires before (and despite) the daily breaker")
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.slot_position_count, bot.fetch_frame, bot.close_slot_position, bot.SLOTS) = orig


# -- appended 2026-07-10: dashboard heartbeat (write_state) --

def test_write_state_schema_and_atomicity():
    import json as _json
    import tempfile

    class FakePos:
        ticket, magic = 555, 1
        type = bot.mt5.POSITION_TYPE_BUY
        volume, price_open, sl, tp, profit = 0.41, 3300.0, 3288.0, 3330.0, 55.3
        time = 1_780_000_000

    orig = (bot.mt5.account_info, bot.mt5.positions_get, bot.day_pnl_usd,
            bot.open_position_count, bot.SLOTS, bot.STATE_FILE, bot.STATE_HISTORY)
    bot.mt5.account_info = lambda: FakeAccount(equity=92_000.0, balance=99_000.0)
    bot.mt5.positions_get = lambda symbol=None: [FakePos()]   # xau's magic only
    bot.day_pnl_usd = lambda: -2_500.0
    bot.open_position_count = lambda symbol=None: 1
    bot.SLOTS = fresh_slots()
    with tempfile.TemporaryDirectory() as td:
        bot.STATE_FILE = Path(td) / "state.json"
        bot.STATE_HISTORY = Path(td) / "state_history.ndjson"
        try:
            bot.write_state(armed=True)
            s = _json.loads(bot.STATE_FILE.read_text())
            for key in ("schema", "ts_utc", "ts_server", "pid", "armed", "equity",
                        "balance", "day_pnl", "guards", "open_positions_total", "slots"):
                assert key in s, key
            assert s["armed"] and s["equity"] == 92_000.0 and s["day_pnl"] == -2_500.0
            # both halted flags computed from the mocked values
            assert s["guards"]["daily_halted"] and s["guards"]["floor_halted"]
            # magic filter: the position lands under xau (magic 1), not jpy (magic 2)
            by_name = {sl["name"]: sl for sl in s["slots"]}
            assert len(by_name["xau"]["positions"]) == 1
            assert by_name["xau"]["positions"][0]["direction"] == "long"
            assert by_name["jpy"]["positions"] == []
            assert not bot.STATE_FILE.with_suffix(".json.tmp").exists()   # atomic, no litter
            lines = bot.STATE_HISTORY.read_text().splitlines()
            assert len(lines) == 1 and _json.loads(lines[0])["equity"] == 92_000.0
            print("PASS: write_state emits valid schema, halted flags, magic-filtered slots, atomically")
        finally:
            (bot.mt5.account_info, bot.mt5.positions_get, bot.day_pnl_usd,
             bot.open_position_count, bot.SLOTS, bot.STATE_FILE, bot.STATE_HISTORY) = orig


def test_write_state_failure_never_raises():
    orig = (bot.mt5.account_info, bot.STATE_FILE)
    try:
        bot.mt5.account_info = lambda: (_ for _ in ()).throw(RuntimeError("terminal gone"))
        bot.write_state(armed=True)                    # must swallow
        bot.mt5.account_info = lambda: FakeAccount()
        bot.STATE_FILE = Path("Z:/nonexistent/dir/state.json")   # unwritable path
        bot.write_state(armed=True)                    # must swallow
        print("PASS: write_state failures are swallowed (heartbeat can never kill the loop)")
    finally:
        bot.mt5.account_info, bot.STATE_FILE = orig


# -- appended 2026-07-10: trendline slot seam --

def test_trendline_signal_seam():
    """Manual fractal columns: rising lows -> break below the line = short."""
    n = 60
    df = pd.DataFrame({"open": [100.0] * n, "high": [101.0] * n,
                       "low": [99.0] * n, "close": [100.0] * n},
                      index=pd.date_range("2026-07-01", periods=n, freq="30min"))
    df["fractal_low"] = float("nan")
    df["fractal_high"] = float("nan")
    # anchors near the end so the projected line stays below the 100.0 closes
    # until the final bar (the first-break-only rule treats any earlier
    # close-below-line as a spent break)
    df.loc[df.index[30], "fractal_low"] = 99.0     # rising lows
    df.loc[df.index[50], "fractal_low"] = 99.6
    df.loc[df.index[40], "fractal_high"] = 101.5   # opposing fractal = SL
    df.loc[df.index[45], "fractal_high"] = 101.2
    df.iloc[-1, df.columns.get_loc("close")] = 99.0   # close below projected line
    plug = bot.load_plugin_instance(bot.TRENDLINE)
    sig = plug.generate_signal("USDJPY.sim", df, df, bot.MODE)
    assert sig is not None and sig.direction == "short", sig
    assert sig.stop_loss == 101.2                     # most recent opposing fractal
    assert plug.generate_signal("USDJPY.sim", df, df, bot.MODE) is None  # line consumed
    print("PASS: trendline seam (rising-lows break -> short, opposing-fractal SL, one per line)")


def _guard_env(equity=100_000.0, margin=0.0, calc=None):
    orig = (bot.mt5.account_info, bot.mt5.symbol_info, bot.mt5.symbol_info_tick,
            bot.mt5.order_calc_margin)
    bot.mt5.account_info = lambda: FakeAccount(equity=equity, margin=margin)
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    bot.mt5.symbol_info_tick = lambda s: FakeTick()
    if calc is not None:
        bot.mt5.order_calc_margin = calc
    return orig


def _guard_restore(orig):
    (bot.mt5.account_info, bot.mt5.symbol_info, bot.mt5.symbol_info_tick,
     bot.mt5.order_calc_margin) = orig


def test_margin_guard_within_budget_passthrough():
    # 2.0 lots at $100/lot = $200 needed vs $50k budget -> untouched
    orig = _guard_env(calc=lambda o, s, l, p: l * 100.0)
    try:
        lots, need = bot.margin_capped_lots("XAUUSD.sim", "long", 2.0)
        assert lots == 2.0 and need == 200.0, (lots, need)
    finally:
        _guard_restore(orig)
    print("PASS: margin guard passes within-budget entries through unchanged")


def test_margin_guard_downsizes_to_fit():
    # $30k/lot; budget = 50% x 100k - 20k used = $30k -> 2.0 lots ($60k) fits at 1.0
    orig = _guard_env(margin=20_000.0, calc=lambda o, s, l, p: l * 30_000.0)
    try:
        lots, need = bot.margin_capped_lots("XAUUSD.sim", "long", 2.0)
        assert lots == 1.0, lots
        assert abs(need - 30_000.0) < 1e-6, need
        # downsize is step-floored, never rounded up
        orig2 = _guard_env(margin=20_000.0, calc=lambda o, s, l, p: l * 40_000.0)
        lots2, _ = bot.margin_capped_lots("XAUUSD.sim", "long", 2.0)
        assert lots2 == 0.75, lots2
        _guard_restore(orig2)
    finally:
        _guard_restore(orig)
    print("PASS: margin guard downsizes to the largest step multiple that fits")


def test_margin_guard_skips_below_min():
    # even volume_min (0.01) needs $500 vs $100 budget -> skip (0.0)
    orig = _guard_env(margin=49_900.0, calc=lambda o, s, l, p: l * 50_000.0)
    try:
        lots, _ = bot.margin_capped_lots("XAUUSD.sim", "long", 1.0)
        assert lots == 0.0, lots
    finally:
        _guard_restore(orig)
    print("PASS: margin guard skips when even volume_min exceeds the budget")


def test_margin_guard_fails_closed():
    orig = _guard_env(calc=lambda o, s, l, p: None)
    try:
        lots, _ = bot.margin_capped_lots("XAUUSD.sim", "long", 1.0)
        assert lots == 0.0, lots
        bot.mt5.account_info = lambda: None
        lots2, _ = bot.margin_capped_lots("XAUUSD.sim", "long", 1.0)
        assert lots2 == 0.0, lots2
    finally:
        _guard_restore(orig)
    print("PASS: margin guard fails CLOSED on API failure (calc None / no account)")


def test_margin_guard_blocks_entry_in_scan():
    # end-to-end: a scan whose signal would trade gets SKIPPED by the guard
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.slot_position_count, bot.fetch_frame, bot.mt5.symbol_info,
            bot.place_order, bot.mt5.order_calc_margin, bot.mt5.symbol_info_tick)
    placed = []
    bot.mt5.account_info = lambda: FakeAccount(margin=49_999.0)
    bot.day_pnl_usd = lambda: 0.0
    bot.open_position_count = lambda symbol=None: 0
    bot.slot_position_count = lambda slot: 0
    bot.fetch_frame = lambda *a, **k: pd.DataFrame()
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    bot.mt5.symbol_info_tick = lambda s: FakeTick()
    bot.mt5.order_calc_margin = lambda o, s, l, p: l * 1_000_000.0   # nothing fits
    bot.place_order = lambda *a, **k: placed.append(a) or {"price": 1.0, "volume": 1.0,
                                                           "order": 1, "requested": 1.0,
                                                           "spread_at_entry": 0.0}
    slot = {"name": "t", "symbol": "XAUUSD.sim", "plugin": FakePlugin(), "long_only": False,
            "risk_pct": 0.005, "magic": 1, "cycle_s": 1800, "tf": "M30", "needs_htf": False}
    try:
        bot.scan_slot(slot, equity=100_000.0, armed=True)
        assert placed == [], placed
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.slot_position_count, bot.fetch_frame, bot.mt5.symbol_info,
         bot.place_order, bot.mt5.order_calc_margin, bot.mt5.symbol_info_tick) = orig
    print("PASS: margin guard blocks an otherwise-tradeable entry in the scan path")


def _m5_frame(end_utc: str, days: int = 26, closes=None):
    """Synthetic M5 frame ending at end_utc (exclusive of the forming bar)."""
    end = pd.Timestamp(end_utc)
    idx = pd.date_range(end - pd.Timedelta(days=days), end, freq="5min", inclusive="left")
    base = 1.30
    df = pd.DataFrame({"open": base, "high": base + 0.001, "low": base - 0.001,
                       "close": base, "volume": 100}, index=idx)
    if closes:
        for ts, px in closes.items():
            df.loc[pd.Timestamp(ts), "close"] = px
    return df


def test_boe_plugin_event_window_and_direction():
    import importlib, boe_drift_plugin as boe
    boe = importlib.reload(boe)
    # 2026-08-06 is BST: statement T = 11:00 UTC; entry window [12:00, 12:15) UTC
    frame = _m5_frame("2026-08-06 12:00",
                      closes={"2026-08-06 11:00": 1.30, "2026-08-06 11:50": 1.32})
    frame.loc[pd.Timestamp("2026-08-06 11:00"), "open"] = 1.30
    sig = boe.generate_signal("GBPUSD.sim", frame, frame)
    assert sig is not None and sig.direction == "long", sig
    assert sig.stop_loss < sig.entry_price < sig.take_profits[0]
    # one-per-event: second call same day is silent
    assert boe.generate_signal("GBPUSD.sim", frame, frame) is None
    # outside the window (13:00 wake) a fresh instance stays silent
    boe2 = importlib.reload(boe)
    late = _m5_frame("2026-08-06 13:00", closes={"2026-08-06 11:50": 1.32})
    assert boe2.generate_signal("GBPUSD.sim", late, late) is None
    # non-event day: silent
    boe3 = importlib.reload(boe)
    off = _m5_frame("2026-08-05 12:00", closes={"2026-08-05 11:50": 1.32})
    assert boe3.generate_signal("GBPUSD.sim", off, off) is None
    print("PASS: boe plugin fires once, in-window only, on event days, impulse-signed")


def test_boe_plugin_uk_dst():
    import boe_drift_plugin as boe
    # Aug = BST -> statement 11:00 UTC; Nov = GMT -> 12:00 UTC
    assert boe._statement_utc("2026-08-06") == pd.Timestamp("2026-08-06 11:00")
    assert boe._statement_utc("2026-11-05") == pd.Timestamp("2026-11-05 12:00")
    print("PASS: boe statement time honors the UK statutory DST rule")


def _boe_slot():
    return {"name": "boe", "symbol": "GBPUSD.sim", "plugin": FakePlugin("long"),
            "long_only": False, "risk_pct": 0.0025, "magic": 99, "cycle_s": 900,
            "tf": "M15", "needs_htf": False, "data_tf": "M5", "ltf_count": 6600,
            "shadow": True, "timed_exit": "entry_plus_20h"}


def test_shadow_slot_never_places_and_fetches_m5():
    orig = (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
            bot.slot_position_count, bot.fetch_frame, bot.mt5.symbol_info,
            bot.place_order)
    placed, fetches = [], []
    bot.mt5.account_info = lambda: FakeAccount()
    bot.day_pnl_usd = lambda: 0.0
    bot.open_position_count = lambda symbol=None: 0
    bot.slot_position_count = lambda slot: 0
    bot.fetch_frame = lambda s, tf, c: fetches.append((tf, c)) or pd.DataFrame()
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    bot.place_order = lambda *a, **k: placed.append(a)
    try:
        bot.scan_slot(_boe_slot(), equity=100_000.0, armed=True)
        assert placed == [], placed
        assert fetches == [(bot.mt5.TIMEFRAME_M5, 6600)], fetches
    finally:
        (bot.mt5.account_info, bot.day_pnl_usd, bot.open_position_count,
         bot.slot_position_count, bot.fetch_frame, bot.mt5.symbol_info,
         bot.place_order) = orig
    print("PASS: shadow slot fetches M5 at ltf_count and NEVER places while armed")


def test_timed_exit_entry_plus_20h():
    class FakePos:
        magic = 99
        def __init__(self, t): self.time = t
    slot = _boe_slot()
    now_utc = pd.Timestamp("2026-08-07 09:00")           # BST window: server = UTC+3
    off = bot.server_offset_hours(now_utc)
    orig = bot.mt5.positions_get
    try:
        # opened 21h ago (server-clock epoch) -> due
        opened = (now_utc - pd.Timedelta(hours=21)) + pd.Timedelta(hours=off)
        bot.mt5.positions_get = lambda symbol=None: [FakePos(int(opened.timestamp()))]
        assert bot.timed_exit_due(slot, now_utc) is True
        # opened 5h ago -> not due
        opened = (now_utc - pd.Timedelta(hours=5)) + pd.Timedelta(hours=off)
        bot.mt5.positions_get = lambda symbol=None: [FakePos(int(opened.timestamp()))]
        assert bot.timed_exit_due(slot, now_utc) is False
        # no positions -> not due
        bot.mt5.positions_get = lambda symbol=None: []
        assert bot.timed_exit_due(slot, now_utc) is False
    finally:
        bot.mt5.positions_get = orig
    print("PASS: entry_plus_20h rule converts server-clock open time and trips at 20h")


def test_keltner_cci_plugins_seam():
    """Standing 2026-07-10 rule: new plugins must pass a session-clock seam
    test (frames as the bot delivers them: UTC, enriched, forming bar
    dropped) + confirmed-indicator audit. Keltner/CCI use only completed-bar
    OHLC (no fractals, no future references) -- audit note in the log."""
    import importlib.util as ilu
    import numpy as np
    for fname, direction_px in (("keltner_breakout_plugin.py", 1.36),
                                ("cci_momentum_plugin.py", 1.36)):
        spec = ilu.spec_from_file_location("_seam_" + fname, Path(__file__).parent.parent / fname)
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # bot-shaped frame: 400 UTC M30 bars, enriched columns present
        idx = pd.date_range("2026-06-01", periods=400, freq="30min")
        base = 1.30 + np.linspace(0, 0.001, 400)
        df = pd.DataFrame({"open": base, "high": base + 0.0004, "low": base - 0.0004,
                           "close": base, "volume": 100, "ema_20": base,
                           "fractal_high": np.nan, "fractal_low": np.nan}, index=idx)
        # breakout on the last bar: push close far above the channel/threshold
        df.iloc[-1, df.columns.get_loc("close")] = direction_px
        df.iloc[-1, df.columns.get_loc("high")] = direction_px + 0.0004
        sig = mod.generate_signal("USDJPY.sim", df, df, bot.MODE)
        assert sig is not None and sig.direction == "long", (fname, sig)
        assert sig.stop_loss < sig.entry_price, fname
        # no-flip frame stays silent (state unchanged on last bar)
        df2 = df.copy()
        df2.iloc[-2, df2.columns.get_loc("close")] = direction_px
        df2.iloc[-2, df2.columns.get_loc("high")] = direction_px + 0.0004
        assert mod.generate_signal("USDJPY.sim", df2, df2, bot.MODE) is None, fname
    print("PASS: keltner/cci plugins pass the bot-frame seam test (flip-bar-only, no lookahead)")


if __name__ == "__main__":
    tests = [
        test_fetch_enrichment_feeds_real_signal_function,
        test_sizing, test_server_offset_dst,
        test_daily_circuit_breaker_halts_all_slots, test_floor_halt,
        test_aggregate_cap, test_mixed_k_slot, test_per_slot_position_cap, test_long_only_filter,
        test_dry_run_never_places, test_plugin_state_isolation,
        test_slot_scheduling, test_magic_filtered_slot_cap, test_orb_slot_fetch_path,
        test_volcomp_signal_and_levels, test_volcomp_no_signal_cases,
        test_wkndgap_signal, test_timed_exit_rule, test_timed_exit_pass_runs_before_guards,
        test_trendline_signal_seam,
        test_write_state_schema_and_atomicity, test_write_state_failure_never_raises,
        test_day_pnl_combines_closed_and_floating,
        test_margin_guard_within_budget_passthrough, test_margin_guard_downsizes_to_fit,
        test_margin_guard_skips_below_min, test_margin_guard_fails_closed,
        test_margin_guard_blocks_entry_in_scan,
        test_boe_plugin_event_window_and_direction, test_boe_plugin_uk_dst,
        test_shadow_slot_never_places_and_fetches_m5, test_timed_exit_entry_plus_20h,
        test_keltner_cci_plugins_seam,
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
