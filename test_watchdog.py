"""
Tests for watchdog.py -- staleness detection, recovery alert, suspension
surfacing. Uses --heartbeat-dir-style injection (direct function calls with a
fixture dir) and a stubbed alert transport.

Run: D:/workspace/rhyme/venv/Scripts/python.exe test_watchdog.py
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import alerts
import watchdog


def _stub_alerts():
    calls = []
    orig = alerts.send_alert
    alerts.send_alert = lambda msg, level="critical", key=None: calls.append((msg, key))
    return calls, orig


def _write_hb(hb_dir: Path, mode: str, age_sec: float, interval: int = 1800) -> None:
    ts = datetime.now(tz=timezone.utc) - timedelta(seconds=age_sec)
    (hb_dir / f"{mode}.json").write_text(json.dumps({
        "ts": ts.isoformat(), "pid": 1234, "mode": mode, "interval_sec": interval,
    }), encoding="utf-8")


def test_fresh_heartbeat_no_alert(tmp: Path) -> None:
    calls, orig = _stub_alerts()
    hb = tmp / "hb1"; hb.mkdir()
    _write_hb(hb, "scalp30", age_sec=60)
    try:
        state = watchdog.check_heartbeats(hb, {"stale": []}, datetime.now(tz=timezone.utc))
    finally:
        alerts.send_alert = orig
    assert calls == [] and state["stale"] == []
    print("PASS: fresh heartbeat -> no alert")


def test_stale_heartbeat_alerts(tmp: Path) -> None:
    calls, orig = _stub_alerts()
    hb = tmp / "hb2"; hb.mkdir()
    # interval 1800 -> limit 2*1800+300 = 3900s; 4000s is stale
    _write_hb(hb, "scalp30", age_sec=4000)
    try:
        state = watchdog.check_heartbeats(hb, {"stale": []}, datetime.now(tz=timezone.utc))
    finally:
        alerts.send_alert = orig
    assert len(calls) == 1 and "stale" in calls[0][0]
    assert state["stale"] == ["scalp30"]
    print("PASS: stale heartbeat -> alert, tracked in state")


def test_boundary_not_stale(tmp: Path) -> None:
    calls, orig = _stub_alerts()
    hb = tmp / "hb3"; hb.mkdir()
    _write_hb(hb, "intraday", age_sec=3800)   # under the 3900s limit
    try:
        state = watchdog.check_heartbeats(hb, {"stale": []}, datetime.now(tz=timezone.utc))
    finally:
        alerts.send_alert = orig
    assert calls == [] and state["stale"] == []
    print("PASS: age under 2x interval + grace -> not stale")


def test_recovery_alert(tmp: Path) -> None:
    calls, orig = _stub_alerts()
    hb = tmp / "hb4"; hb.mkdir()
    _write_hb(hb, "scalp30", age_sec=60)      # now fresh again
    try:
        state = watchdog.check_heartbeats(hb, {"stale": ["scalp30"]}, datetime.now(tz=timezone.utc))
    finally:
        alerts.send_alert = orig
    assert len(calls) == 1 and "RECOVERED" in calls[0][0]
    assert state["stale"] == []
    print("PASS: previously-stale mode going fresh -> recovery alert")


def test_deleted_heartbeat_no_recovery_alert(tmp: Path) -> None:
    calls, orig = _stub_alerts()
    hb = tmp / "hb5"; hb.mkdir()              # no file for retired mode
    try:
        state = watchdog.check_heartbeats(hb, {"stale": ["swing"]}, datetime.now(tz=timezone.utc))
    finally:
        alerts.send_alert = orig
    assert calls == [], "a deleted (retired) heartbeat is not a recovery"
    print("PASS: deleted heartbeat file -> no spurious recovery alert")


def test_garbage_heartbeat_skipped(tmp: Path) -> None:
    calls, orig = _stub_alerts()
    hb = tmp / "hb6"; hb.mkdir()
    (hb / "broken.json").write_text("{not json", encoding="utf-8")
    _write_hb(hb, "pullback30", age_sec=60)
    try:
        state = watchdog.check_heartbeats(hb, {"stale": []}, datetime.now(tz=timezone.utc))
    finally:
        alerts.send_alert = orig
    assert calls == [] and state["stale"] == []
    print("PASS: unreadable heartbeat file skipped without crashing")


def test_suspension_alerts(tmp: Path) -> None:
    calls, orig = _stub_alerts()
    orig_spread, orig_halt = watchdog.SPREAD_STATE, watchdog.FLEET_HALT
    watchdog.SPREAD_STATE = tmp / "spread_state_2b.json"
    watchdog.FLEET_HALT = tmp / "fleet_halt.json"
    watchdog.SPREAD_STATE.write_text(json.dumps({"suspended": True}), encoding="utf-8")
    watchdog.FLEET_HALT.write_text(json.dumps({"halted": True}), encoding="utf-8")
    try:
        watchdog.check_suspensions()
    finally:
        alerts.send_alert = orig
        watchdog.SPREAD_STATE, watchdog.FLEET_HALT = orig_spread, orig_halt
    assert len(calls) == 2, f"expected suspension + halt alerts, got {calls}"
    assert any("SUSPENDED" in m for m, _ in calls) and any("HALTED" in m for m, _ in calls)
    print("PASS: suspended spread state and fleet halt both alert")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_fresh_heartbeat_no_alert(tmp)
        test_stale_heartbeat_alerts(tmp)
        test_boundary_not_stale(tmp)
        test_recovery_alert(tmp)
        test_deleted_heartbeat_no_recovery_alert(tmp)
        test_garbage_heartbeat_skipped(tmp)
        test_suspension_alerts(tmp)
    print("ALL PASS: test_watchdog.py")
