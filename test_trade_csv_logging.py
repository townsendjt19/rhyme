"""
Tests for the execution-quality columns in paper_trades.csv (2026-07-10):
signal_price, slippage_pips, spread_pips_at_fill, half_spread_cost -- plus
the one-time 11->15-column header migration.

Run: D:/workspace/rhyme/venv/Scripts/python.exe test_trade_csv_logging.py
"""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import main
from strategy import Signal


def _signal(direction: str, entry: float, sl: float, tp: float) -> Signal:
    return Signal(instrument="TEST", timeframe="M30", direction=direction,
                  entry_price=entry, stop_loss=sl, take_profits=[tp, tp, tp],
                  reason="test")


def _response(fill_price: str, bid: str = None, ask: str = None, half_spread: str = None) -> dict:
    fill = {"price": fill_price, "tradeOpened": {"tradeID": "42"}}
    if bid is not None:
        fill["fullPrice"] = {"bids": [{"price": bid}], "asks": [{"price": ask}]}
    if half_spread is not None:
        fill["halfSpreadCost"] = half_spread
    return {"orderFillTransaction": fill}


def _read(path: Path) -> list[list[str]]:
    with path.open("r", newline="") as fh:
        return list(csv.reader(fh))


def test_long_slippage_and_spread_jpy(tmp: Path) -> None:
    main.PAPER_TRADES_CSV = tmp / "pt1.csv"
    # Long USD_JPY: signal 155.000, filled 155.020 -> +2.0 pips adverse (pip 0.01)
    main._log_trade_csv("USD_JPY", _signal("long", 155.000, 154.500, 156.000),
                        1.0, 100000, _response("155.020", "155.015", "155.025", "0.75"),
                        "test_long")
    rows = _read(main.PAPER_TRADES_CSV)
    assert rows[0] == main._TRADE_CSV_COLUMNS
    r = dict(zip(rows[0], rows[1]))
    assert r["signal_price"] == "155.000"
    assert r["slippage_pips"] == "2.00", r["slippage_pips"]
    assert r["spread_pips_at_fill"] == "1.00", r["spread_pips_at_fill"]
    assert r["half_spread_cost"] == "0.75"
    print("PASS: long JPY slippage/spread computed correctly")


def test_short_slippage_sign(tmp: Path) -> None:
    main.PAPER_TRADES_CSV = tmp / "pt2.csv"
    # Short GBP_USD: signal 1.30000, filled 1.29990 -> filled LOWER than
    # intended on a short = adverse = +1.0 pips (pip 0.0001)
    main._log_trade_csv("GBP_USD", _signal("short", 1.30000, 1.30500, 1.29000),
                        1.0, -100000, _response("1.29990"), "test_short")
    r = dict(zip(*_read(main.PAPER_TRADES_CSV)[:2]))
    assert r["slippage_pips"] == "1.00", r["slippage_pips"]
    assert r["spread_pips_at_fill"] == "", "no fullPrice -> blank, no exception"
    assert r["half_spread_cost"] == ""
    print("PASS: short slippage sign correct; missing fullPrice degrades to blanks")


def test_migration_preserves_old_rows(tmp: Path) -> None:
    main.PAPER_TRADES_CSV = tmp / "pt3.csv"
    old_cols = main._TRADE_CSV_COLUMNS[:11]
    with main.PAPER_TRADES_CSV.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(old_cols)
        w.writerow(["2026-07-01 12:00:00", "USD_JPY", "donchian_plugin_scalp30", "long",
                    "155.100", "154.900", "155.600", "0.21", "21000", "37", "breakout"])
    main._log_trade_csv("USD_JPY", _signal("long", 155.000, 154.500, 156.000),
                        1.0, 100000, _response("155.020"), "test_new")
    rows = _read(main.PAPER_TRADES_CSV)
    assert rows[0] == main._TRADE_CSV_COLUMNS
    assert all(len(r) == len(main._TRADE_CSV_COLUMNS) for r in rows), "ragged rows after migration"
    assert rows[1][:11] == ["2026-07-01 12:00:00", "USD_JPY", "donchian_plugin_scalp30", "long",
                            "155.100", "154.900", "155.600", "0.21", "21000", "37", "breakout"]
    assert rows[1][11:] == ["", "", "", ""], "old row must be blank-padded"
    assert rows[2][0] != ""  # new row appended after migration
    # Idempotence: logging again must not re-migrate/duplicate anything
    main._log_trade_csv("USD_JPY", _signal("long", 155.000, 154.500, 156.000),
                        1.0, 100000, _response("155.020"), "test_new2")
    rows = _read(main.PAPER_TRADES_CSV)
    assert len(rows) == 4 and rows[0] == main._TRADE_CSV_COLUMNS
    print("PASS: 11->15 column migration preserves old rows, idempotent")


def test_fresh_file_gets_new_header(tmp: Path) -> None:
    main.PAPER_TRADES_CSV = tmp / "pt4.csv"
    main._log_trade_csv("GBP_USD", _signal("long", 1.30000, 1.29500, 1.31000),
                        1.0, 100000, _response("1.30000"), "test_fresh")
    rows = _read(main.PAPER_TRADES_CSV)
    assert rows[0] == main._TRADE_CSV_COLUMNS
    r = dict(zip(rows[0], rows[1]))
    assert r["slippage_pips"] == "0.00"
    print("PASS: fresh file written with the 15-column header")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_long_slippage_and_spread_jpy(tmp)
        test_short_slippage_sign(tmp)
        test_migration_preserves_old_rows(tmp)
        test_fresh_file_gets_new_header(tmp)
    print("ALL PASS: test_trade_csv_logging.py")
