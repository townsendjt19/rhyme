"""
Tests for the fleet trailing drawdown halt (GOVERNANCE addendum 2026-07-10).

Run: D:/workspace/rhyme/venv/Scripts/python.exe test_fleet_halt.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import main
import alerts

NAVS_4K = [("a-001", 4000.0), ("a-002", 4000.0), ("a-003", 4000.0)]  # fleet 12,000


def _setup(tmp: Path):
    main.FLEET_HALT_FILE = tmp / "fleet_halt.json"
    calls = []
    orig = alerts.send_alert
    alerts.send_alert = lambda msg, level="critical", key=None: calls.append(msg)
    return calls, orig


def test_peak_ratchets_up_never_down(tmp: Path) -> None:
    calls, orig = _setup(tmp)
    try:
        ok, _ = main.check_fleet_drawdown(NAVS_4K)
        assert ok and json.loads(main.FLEET_HALT_FILE.read_text())["nav_peak"] == 12000.0
        ok, _ = main.check_fleet_drawdown([("a", 13000.0)])
        assert ok and json.loads(main.FLEET_HALT_FILE.read_text())["nav_peak"] == 13000.0
        ok, _ = main.check_fleet_drawdown([("a", 12500.0)])   # below peak, above threshold
        assert ok and json.loads(main.FLEET_HALT_FILE.read_text())["nav_peak"] == 13000.0
    finally:
        alerts.send_alert = orig
        main.FLEET_HALT_FILE.unlink(missing_ok=True)
    print("PASS: peak ratchets up, never down")


def test_halt_boundary(tmp: Path) -> None:
    calls, orig = _setup(tmp)
    try:
        main.check_fleet_drawdown([("a", 10000.0)])           # peak = 10,000
        ok, _ = main.check_fleet_drawdown([("a", 7501.0)])    # 74.99% DD side: fine
        assert ok, "75.01% of peak must NOT halt"
        ok, reason = main.check_fleet_drawdown([("a", 7500.0)])  # exactly -25%
        assert not ok and "TRAILING DRAWDOWN HALT" in reason
        assert len(calls) == 1, "halt must alert exactly once at trigger"
    finally:
        alerts.send_alert = orig
        main.FLEET_HALT_FILE.unlink(missing_ok=True)
    print("PASS: halts at exactly -25% from peak, not before; alert fires")


def test_halt_is_sticky_until_manual_clear(tmp: Path) -> None:
    calls, orig = _setup(tmp)
    try:
        main.check_fleet_drawdown([("a", 10000.0)])
        main.check_fleet_drawdown([("a", 7000.0)])            # trip the halt
        ok, reason = main.check_fleet_drawdown([("a", 11000.0)])  # full recovery
        assert not ok and "HALTED since" in reason, "NAV recovery must not un-halt"
        # Manual operator clear:
        st = json.loads(main.FLEET_HALT_FILE.read_text())
        st["halted"] = False
        main.FLEET_HALT_FILE.write_text(json.dumps(st))
        ok, _ = main.check_fleet_drawdown([("a", 11000.0)])
        assert ok, "manual clear must resume entries"
    finally:
        alerts.send_alert = orig
        main.FLEET_HALT_FILE.unlink(missing_ok=True)
    print("PASS: halt sticky through recovery, cleared only manually")


def test_empty_navs_fail_closed(tmp: Path) -> None:
    calls, orig = _setup(tmp)
    try:
        ok, reason = main.check_fleet_drawdown([])
        assert not ok and "UNVERIFIABLE" in reason
    finally:
        alerts.send_alert = orig
        main.FLEET_HALT_FILE.unlink(missing_ok=True)
    print("PASS: empty NAV list fails closed")


def test_interleaved_writers_keep_max_peak(tmp: Path) -> None:
    calls, orig = _setup(tmp)
    try:
        # Writer A sees 12,000; writer B (a sibling process) writes a higher
        # peak to disk between A's read and A's write. A's monotonic-max
        # re-read must preserve B's 15,000.
        main.check_fleet_drawdown(NAVS_4K)                    # peak 12,000 on disk
        st = json.loads(main.FLEET_HALT_FILE.read_text())
        st["nav_peak"] = 15000.0                              # sibling's newer peak
        main.FLEET_HALT_FILE.write_text(json.dumps(st))
        main.check_fleet_drawdown([("a", 12000.0)])           # A re-checks at 12,000
        final = json.loads(main.FLEET_HALT_FILE.read_text())["nav_peak"]
        assert final == 15000.0, f"sibling's higher peak lost: {final}"
    finally:
        alerts.send_alert = orig
        main.FLEET_HALT_FILE.unlink(missing_ok=True)
    print("PASS: interleaved writers preserve the max peak")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_peak_ratchets_up_never_down(tmp)
        test_halt_boundary(tmp)
        test_halt_is_sticky_until_manual_clear(tmp)
        test_empty_navs_fail_closed(tmp)
        test_interleaved_writers_keep_max_peak(tmp)
    print("ALL PASS: test_fleet_halt.py")
