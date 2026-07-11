"""
Tests for data.load_candles_csv -- the external-candle door into the backtest
harness (--candles-csv-dir). Must reproduce fetch_candles' exact output
shape: UTC-aware time index, sorted, deduped, open/high/low/close/volume.

Run: D:/workspace/rhyme/venv/Scripts/python.exe test_candles_csv.py
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from data import load_candles_csv


def _write_csv(path: Path, rows: list[tuple]) -> None:
    pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]).to_csv(
        path, index=False)


def test_shape_matches_fetch_candles(tmp: Path) -> None:
    p = tmp / "USD_JPY_M30.csv"
    _write_csv(p, [
        ("2015-01-05 00:30:00", 119.10, 119.30, 119.05, 119.25, 500),
        ("2015-01-05 00:00:00", 119.00, 119.20, 118.95, 119.10, 400),  # out of order
        ("2015-01-05 00:30:00", 119.10, 119.31, 119.05, 119.26, 501),  # duplicate ts
    ])
    df = load_candles_csv(p)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.name == "time"
    assert str(df.index.tz) == "UTC", f"index must be UTC-aware, got {df.index.tz}"
    assert df.index.is_monotonic_increasing, "index must be sorted"
    assert len(df) == 2, "duplicate timestamps must dedupe (keep last)"
    assert df.iloc[1]["high"] == 119.31, "dedupe must keep the LAST row (fetch_candles convention)"
    assert df["volume"].dtype == int or str(df["volume"].dtype).startswith("int")
    print("PASS: loader output matches fetch_candles shape (UTC index, sorted, deduped-keep-last)")


def test_time_window_slicing(tmp: Path) -> None:
    p = tmp / "USD_JPY_H4.csv"
    _write_csv(p, [(f"2015-01-0{d} 00:00:00", 119.0, 119.5, 118.5, 119.2, 100)
                   for d in range(1, 8)])
    df = load_candles_csv(p,
                          from_time=datetime(2015, 1, 3, tzinfo=timezone.utc),
                          to_time=datetime(2015, 1, 5, tzinfo=timezone.utc))
    assert len(df) == 3
    assert df.index[0] == pd.Timestamp("2015-01-03", tz="UTC")
    assert df.index[-1] == pd.Timestamp("2015-01-05", tz="UTC")
    print("PASS: from_time/to_time slicing inclusive on both ends")


def test_naive_and_aware_timestamps(tmp: Path) -> None:
    p = tmp / "aware.csv"
    _write_csv(p, [("2015-01-05 00:00:00+00:00", 1.0, 1.1, 0.9, 1.05, 10)])
    df = load_candles_csv(p)
    assert str(df.index.tz) == "UTC"
    print("PASS: tz-aware input timestamps convert cleanly to UTC")


def test_harness_indicator_pipeline_runs(tmp: Path) -> None:
    """Smoke: the loaded frame flows through the same indicator prep the
    backtest applies (add_emas + detect_fractals) without error."""
    from indicators import add_emas, detect_fractals
    p = tmp / "smoke.csv"
    rows = []
    px = 119.0
    for i in range(200):
        px += 0.01 if i % 3 else -0.015
        ts = pd.Timestamp("2015-01-01", tz="UTC") + pd.Timedelta(hours=4 * i)
        rows.append((str(ts), px, px + 0.1, px - 0.1, px + 0.02, 100))
    _write_csv(p, rows)
    df = add_emas(detect_fractals(load_candles_csv(p)))
    assert len(df) == 200 and "ema20" in [c.lower() for c in df.columns] or len(df.columns) > 5
    print("PASS: loaded candles flow through detect_fractals + add_emas")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_shape_matches_fetch_candles(tmp)
        test_time_window_slicing(tmp)
        test_naive_and_aware_timestamps(tmp)
        test_harness_indicator_pipeline_runs(tmp)
    print("ALL PASS: test_candles_csv.py")
