"""Unit tests for the friday-close deadline (registered 2026-07-13) — run BEFORE any backtest.

Run: D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/test_orb_friday_killtest.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from orb_friday_killtest import friday_deadline_utc
from orb_plugin_core import _us_dst_offset


def _utc(s):
    return pd.Timestamp(s, tz="UTC")


def test_midweek_entry_summer():
    # Wed 2026-07-08 14:15 UTC = 10:15 EDT -> Friday 2026-07-10 17:00 EDT = 21:00 UTC
    assert friday_deadline_utc(_utc("2026-07-08 14:15")) == _utc("2026-07-10 21:00")


def test_midweek_entry_winter():
    # Tue 2023-01-10 15:00 UTC = 10:00 EST -> Friday 2023-01-13 17:00 EST = 22:00 UTC
    assert friday_deadline_utc(_utc("2023-01-10 15:00")) == _utc("2023-01-13 22:00")


def test_friday_entry_same_day():
    # Fri 2026-07-10 18:12 UTC = 14:12 EDT (the live ospx entry) -> same day 17:00 EDT
    assert friday_deadline_utc(_utc("2026-07-10 18:12")) == _utc("2026-07-10 21:00")


def test_friday_entry_after_close_rolls_forward():
    # Fri 22:00 UTC = 18:00 EDT, past the boundary -> next Friday
    assert friday_deadline_utc(_utc("2026-07-10 22:00")) == _utc("2026-07-17 21:00")


def test_march_dst_transition_week():
    # Mon 2023-03-06 15:00 UTC = 10:00 EST (EDT starts Sun 03-12) ->
    # Friday 2023-03-10 is still EST: 17:00 EST = 22:00 UTC
    assert friday_deadline_utc(_utc("2023-03-06 15:00")) == _utc("2023-03-10 22:00")


def test_november_dst_transition_week():
    # Mon 2023-10-30 14:00 UTC = 10:00 EDT (EST starts Sun 11-05) ->
    # Friday 2023-11-03 is still EDT: 17:00 EDT = 21:00 UTC
    assert friday_deadline_utc(_utc("2023-10-30 14:00")) == _utc("2023-11-03 21:00")


def test_iana_matches_statutory_rule_across_window():
    # The registration allows IANA America/New_York only because it agrees
    # with the plugin's statutory rule over the whole data window.
    for ts in pd.date_range("2021-12-01", "2026-07-01", freq="6h", tz="UTC"):
        iana = ts.tz_convert("America/New_York").utcoffset().total_seconds() / 3600
        assert iana == _us_dst_offset(ts), f"divergence at {ts}"


def test_deadline_strictly_after_entry_and_is_friday_17_et():
    for ts in pd.date_range("2023-01-01", "2024-01-01", freq="7h", tz="UTC"):
        d = friday_deadline_utc(ts)
        assert d > ts
        et = d.tz_convert("America/New_York")
        assert (et.weekday(), et.hour, et.minute) == (4, 17, 0)
        assert d - ts <= pd.Timedelta(days=7)


if __name__ == "__main__":
    tests = [test_midweek_entry_summer, test_midweek_entry_winter,
             test_friday_entry_same_day, test_friday_entry_after_close_rolls_forward,
             test_march_dst_transition_week, test_november_dst_transition_week,
             test_iana_matches_statutory_rule_across_window,
             test_deadline_strictly_after_entry_and_is_friday_17_et]
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
