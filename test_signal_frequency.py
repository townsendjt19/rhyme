"""
Tests for signal_frequency.py -- synthetic ledger + synthetic backtest CSV
produce known rates/ratios; min-weeks gating; torn NDJSON lines skipped.

Run: D:/workspace/rhyme/venv/Scripts/python.exe test_signal_frequency.py
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import signal_frequency as sf

NOW = datetime(2026, 7, 10, tzinfo=timezone.utc)


def _synthetic_backtest_csv(tmp: Path, name: str, trades_per_week: int, weeks: int = 50) -> None:
    """One backtest CSV with a uniform trades/week rate."""
    times = []
    start = NOW - timedelta(weeks=weeks + 10)
    for w in range(weeks):
        for k in range(trades_per_week):
            times.append(start + timedelta(weeks=w, hours=k * 5 + 1))
    pd.DataFrame({"time": times, "exit_time": times, "pair": "USD_JPY",
                  "direction": "long", "pnl": 10.0}).to_csv(tmp / name, index=False)


def _ledger_line(ts: datetime, mode: str, signal: bool) -> str:
    return json.dumps({"ts": ts.isoformat(), "mode": mode,
                       "instrument": "USD_JPY", "signal": signal})


def test_baseline_rate(tmp: Path) -> None:
    sf.BT = tmp
    _synthetic_backtest_csv(tmp, "bt10.csv", trades_per_week=10)
    rate = sf.baseline_weekly_rate("bt10.csv")
    assert 9.0 <= rate <= 11.0, f"expected ~10/wk, got {rate}"
    print(f"PASS: baseline weekly rate ~10 (got {rate:.2f})")


def test_forward_rate_and_ratio(tmp: Path) -> None:
    # 6 weeks of ledger; in the trailing 4 weeks: 8 signal=true lines -> 2/wk
    ledger_path = tmp / "ledger1.ndjson"
    lines = [_ledger_line(NOW - timedelta(weeks=6), "scalp30", False)]  # coverage anchor
    for d in range(8):
        lines.append(_ledger_line(NOW - timedelta(days=2 + d * 3), "scalp30", True))
    for d in range(20):
        lines.append(_ledger_line(NOW - timedelta(days=1 + d), "scalp30", False))
    lines.append(_ledger_line(NOW - timedelta(days=3), "othermode", True))  # ignored
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ledger = sf.load_ledger(ledger_path)
    fwd, coverage = sf.forward_weekly_rate(ledger, "scalp30", now=NOW)
    assert fwd == 2.0, f"expected 2.0/wk, got {fwd}"
    assert 5.9 <= coverage <= 6.1, f"expected ~6 weeks coverage, got {coverage}"
    print("PASS: forward rate 2.0/wk over 4-week window, coverage ~6 weeks")


def test_torn_lines_skipped(tmp: Path) -> None:
    ledger_path = tmp / "ledger2.ndjson"
    good = _ledger_line(NOW - timedelta(days=1), "scalp30", True)
    ledger_path.write_text(good + "\n{torn line no clos\n" + good + "\n", encoding="utf-8")
    ledger = sf.load_ledger(ledger_path)
    assert len(ledger) == 2, f"expected 2 parsed rows, got {len(ledger)}"
    print("PASS: torn NDJSON line skipped")


def test_flag_logic(tmp: Path) -> None:
    sf.BT = tmp
    _synthetic_backtest_csv(tmp, "bt_flag.csv", trades_per_week=10)
    sf.ROSTER = {"scalp30": "bt_flag.csv"}

    # Case 1: coverage < 4 weeks -> never flags, even at zero forward signals
    ledger_path = tmp / "ledger3.ndjson"
    ledger_path.write_text(_ledger_line(NOW - timedelta(weeks=2), "scalp30", False) + "\n",
                           encoding="utf-8")
    sf.LEDGER = ledger_path
    t = sf.table(now=NOW)
    assert not t.iloc[0]["flag"], "must not flag with <4 weeks of ledger"

    # Case 2: 6 weeks coverage, forward 2/wk vs baseline 10/wk = 20% < 25% -> flag
    lines = [_ledger_line(NOW - timedelta(weeks=6), "scalp30", False)]
    for d in range(8):
        lines.append(_ledger_line(NOW - timedelta(days=2 + d * 3), "scalp30", True))
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    t = sf.table(now=NOW)
    assert t.iloc[0]["flag"], f"20% of baseline must flag: {t.iloc[0].to_dict()}"

    # Case 3: forward 3/wk = 30% > 25% -> no flag
    lines = [_ledger_line(NOW - timedelta(weeks=6), "scalp30", False)]
    for d in range(12):
        lines.append(_ledger_line(NOW - timedelta(days=1 + d * 2), "scalp30", True))
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    t = sf.table(now=NOW)
    assert not t.iloc[0]["flag"], f"30% of baseline must not flag: {t.iloc[0].to_dict()}"
    print("PASS: flag fires below 25% ratio with >=4 weeks coverage, not otherwise")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_baseline_rate(tmp)
        test_forward_rate_and_ratio(tmp)
        test_torn_lines_skipped(tmp)
        test_flag_logic(tmp)
    print("ALL PASS: test_signal_frequency.py")
