"""
Unit tests for the FTMO trial bot -- ALL MT5 CALLS MOCKED at the API
boundary; no terminal is attached and no order can fire from this suite.

Run: D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/ftmo_trial/test_ftmo_gold_bot.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

import pandas as pd

import ftmo_gold_bot as bot

# Test runs must NEVER write into the live observation log (personal-live
# 2026-07-03 regression guard): strip file handlers attached at import.
for h in list(bot.log.handlers) + list(logging.getLogger().handlers):
    if isinstance(h, logging.FileHandler):
        bot.log.removeHandler(h)
        logging.getLogger().removeHandler(h)


class FakeSymbolInfo:
    trade_contract_size = 100.0   # 1 lot = 100 oz
    volume_step = 0.01
    volume_min = 0.01
    volume_max = 100.0


class FakeAccount:
    def __init__(self, equity=100_000.0, balance=100_000.0):
        self.equity, self.balance = equity, balance


def fake_rates(n, base=3300.0):
    rows = []
    for i in range(n):
        px = base + (i % 9) * 1.5
        rows.append({"time": 1_780_000_000 + i * 1800, "open": px, "high": px + 2.0,
                     "low": px - 2.0, "close": px + 0.5, "tick_volume": 100,
                     "spread": 250, "real_volume": 0})
    return rows


def test_sizing():
    orig = bot.mt5.symbol_info
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    try:
        # $500 risk, $12 stop, $100/lot per $1 -> 0.4167 raw -> 0.41 floored
        assert bot.size_lots(100_000, 3300.0, 3288.0) == 0.41
        # zero stop distance -> 0
        assert bot.size_lots(100_000, 3300.0, 3300.0) == 0.0
        # stop so wide it sizes under volume_min -> 0 (skip, never an invalid order)
        assert bot.size_lots(100_000, 3300.0, 2700.0) == 0.0
        # adversarial float-dust values must land EXACTLY on the step grid
        for equity, entry, stop in ((100_000, 3300.0, 3291.2), (100_000, 3300.0, 3282.5)):
            lots = bot.size_lots(equity, entry, stop)
            assert lots == round(lots, 2), (equity, entry, stop, lots)
        print("PASS: sizing floors to volume_step, skips zero-distance and sub-minimum, no float dust")
    finally:
        bot.mt5.symbol_info = orig


def test_server_offset_dst():
    assert bot.server_offset_hours(pd.Timestamp("2026-01-15")) == 2
    assert bot.server_offset_hours(pd.Timestamp("2025-07-15")) == 3
    assert bot.server_offset_hours(pd.Timestamp("2026-03-29 00:59")) == 2  # DST flips 01:00 UTC Mar 29 2026
    assert bot.server_offset_hours(pd.Timestamp("2026-03-29 01:01")) == 3
    print("PASS: EET DST offset piecewise-correct incl. the spring boundary hour")


def _stub_cycle_env(equity=100_000.0, positions=0, day=0.0):
    """Patch everything cycle() touches before the scan stage."""
    bot.mt5.account_info = lambda: FakeAccount(equity=equity)
    bot.open_position_count = lambda: positions
    bot.day_pnl_usd = lambda: day
    bot.fetch_frame = lambda tf, n: (_ for _ in ()).throw(AssertionError("scanned past a guard"))


def test_one_position_cap():
    orig = (bot.mt5.account_info, bot.open_position_count, bot.day_pnl_usd, bot.fetch_frame)
    _stub_cycle_env(positions=1)
    try:
        bot.cycle(armed=True)
        print("PASS: one-position cap stops the cycle before candles are fetched")
    finally:
        bot.mt5.account_info, bot.open_position_count, bot.day_pnl_usd, bot.fetch_frame = orig


def test_daily_circuit_breaker():
    orig = (bot.mt5.account_info, bot.open_position_count, bot.day_pnl_usd, bot.fetch_frame)
    _stub_cycle_env(day=-2_500.0)
    try:
        bot.cycle(armed=True)
        print("PASS: -$2,500 day P&L halts new entries before any scan")
    finally:
        bot.mt5.account_info, bot.open_position_count, bot.day_pnl_usd, bot.fetch_frame = orig


def test_floor_halt():
    orig = (bot.mt5.account_info, bot.open_position_count, bot.day_pnl_usd, bot.fetch_frame)
    _stub_cycle_env(equity=92_999.0)
    try:
        bot.cycle(armed=True)
        print("PASS: equity at $92,999 (below the $93k buffer floor) halts before any scan")
    finally:
        bot.mt5.account_info, bot.open_position_count, bot.day_pnl_usd, bot.fetch_frame = orig


def _signal(direction="long"):
    from strategy import Signal
    return Signal(direction=direction, entry_price=3300.0, stop_loss=3288.0,
                  take_profits=[3330.0, 3330.0, 3330.0], instrument=bot.SYMBOL,
                  timeframe="t", reason="test")


def test_dry_run_never_places():
    orig = (bot.mt5.account_info, bot.open_position_count, bot.day_pnl_usd,
            bot.fetch_frame, bot.generate_signal, bot.place_order, bot.mt5.symbol_info)
    bot.mt5.account_info = lambda: FakeAccount()
    bot.open_position_count = lambda: 0
    bot.day_pnl_usd = lambda: 0.0
    bot.fetch_frame = lambda tf, n: pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1]})
    bot.generate_signal = lambda *a, **k: _signal()
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    bot.place_order = lambda *a, **k: (_ for _ in ()).throw(AssertionError("ORDER PLACED IN DRY-RUN"))
    try:
        bot.cycle(armed=False)
        print("PASS: dry-run runs the full pipeline and never reaches order placement")
    finally:
        (bot.mt5.account_info, bot.open_position_count, bot.day_pnl_usd,
         bot.fetch_frame, bot.generate_signal, bot.place_order, bot.mt5.symbol_info) = orig


def test_armed_places_correct_order():
    placed = {}
    orig = (bot.mt5.account_info, bot.open_position_count, bot.day_pnl_usd,
            bot.fetch_frame, bot.generate_signal, bot.place_order, bot.mt5.symbol_info)
    bot.mt5.account_info = lambda: FakeAccount()
    bot.open_position_count = lambda: 0
    bot.day_pnl_usd = lambda: 0.0
    bot.fetch_frame = lambda tf, n: pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1]})
    bot.generate_signal = lambda *a, **k: _signal("short")
    bot.mt5.symbol_info = lambda s: FakeSymbolInfo()
    def fake_place(direction, lots, sl, tp):
        placed.update(direction=direction, lots=lots, sl=sl, tp=tp)
        return None
    bot.place_order = fake_place
    try:
        bot.cycle(armed=True)
        assert placed["direction"] == "short" and placed["lots"] == 0.41, placed
        assert placed["sl"] == 3288.0 and placed["tp"] == 3330.0
        print(f"PASS: armed cycle places the mocked order correctly ({placed['lots']} lots short)")
    finally:
        (bot.mt5.account_info, bot.open_position_count, bot.day_pnl_usd,
         bot.fetch_frame, bot.generate_signal, bot.place_order, bot.mt5.symbol_info) = orig


def test_fetch_enrichment_feeds_real_signal_function():
    """Mock at the MT5 boundary, run the REAL plugin on fetch_frame output
    (the personal-live 2026-07-03 seam lesson)."""
    orig = bot.mt5.copy_rates_from_pos
    bot.mt5.copy_rates_from_pos = lambda sym, tf, pos, n: fake_rates(n)
    try:
        htf = bot.fetch_frame(0, bot.H4_COUNT)
        ltf = bot.fetch_frame(0, bot.M30_COUNT)
        assert "ema_20" in htf.columns and "fractal_high" in htf.columns, htf.columns.tolist()
        result = bot.generate_signal(bot.SYMBOL, htf, ltf, bot.MODE)   # must not raise
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
        assert bot.day_pnl_usd() == -604.0 + -400.0, bot.day_pnl_usd()
        print("PASS: day P&L = closed deals (profit+commission+swap) + floating (equity-balance)")
    finally:
        bot.mt5.history_deals_get, bot.mt5.account_info = orig


if __name__ == "__main__":
    test_fetch_enrichment_feeds_real_signal_function()
    test_sizing()
    test_server_offset_dst()
    test_one_position_cap()
    test_daily_circuit_breaker()
    test_floor_halt()
    test_dry_run_never_places()
    test_armed_places_correct_order()
    test_day_pnl_combines_closed_and_floating()
    print("\nALL TESTS PASSED")
