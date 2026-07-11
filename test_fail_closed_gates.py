"""
Tests for the fail-closed gate conversion (2026-07-10, GOVERNANCE dated note).

Covers: _checked_equity_floor failing CLOSED on API error, the
_gate_exception escalation-to-alert at GATE_ALERT_AFTER consecutive
failures, and reset-on-success.

Run: D:/workspace/rhyme/venv/Scripts/python.exe test_fail_closed_gates.py
"""
from __future__ import annotations

import main
import alerts
from risk import GATE_ALERT_AFTER


def test_floor_fails_closed_on_api_error() -> None:
    orig = main.get_nav_for

    def boom(acct):
        raise RuntimeError("OANDA down")

    main.get_nav_for = boom
    main._gate_failure_counts.clear()
    try:
        ok, reason, navs = main._checked_equity_floor()
    finally:
        main.get_nav_for = orig
    assert ok is False, "floor must fail CLOSED on API error"
    assert "UNVERIFIABLE" in reason
    assert navs == [], "no NAVs on the fail-closed path"
    print("PASS: equity floor fails closed on API error")


def test_floor_passes_and_returns_navs() -> None:
    orig = main.get_nav_for
    main.get_nav_for = lambda acct: 4000.0
    main._gate_failure_counts.clear()
    try:
        ok, reason, navs = main._checked_equity_floor()
    finally:
        main.get_nav_for = orig
    assert ok is True and reason == ""
    assert len(navs) == len(main.RESEARCH_ACCOUNTS)
    assert all(nav == 4000.0 for _, nav in navs)
    print("PASS: healthy floor check passes and returns per-account NAVs")


def test_floor_breach_still_detected() -> None:
    orig = main.get_nav_for
    main.get_nav_for = lambda acct: 750.0   # below the $800 floor
    main._gate_failure_counts.clear()
    try:
        ok, reason, navs = main._checked_equity_floor()
    finally:
        main.get_nav_for = orig
    assert ok is False and "FLOOR BREACHED" in reason
    assert navs, "breach path must still return the NAVs (fleet-DD reuses them)"
    print("PASS: genuine floor breach still detected, NAVs returned")


def test_gate_exception_escalates_then_resets() -> None:
    calls = []
    orig = alerts.send_alert
    alerts.send_alert = lambda msg, level="critical", key=None: calls.append(msg)
    main._gate_failure_counts.clear()
    try:
        for _ in range(GATE_ALERT_AFTER - 1):
            main._gate_exception("margin", "boom")
        assert calls == [], f"alert fired before threshold: {calls}"
        main._gate_exception("margin", "boom")          # hits GATE_ALERT_AFTER
        assert len(calls) == 1, f"expected 1 alert at threshold, got {len(calls)}"
        main._gate_success("margin")                     # reset
        main._gate_exception("margin", "boom again")     # count restarts at 1
        assert len(calls) == 1, "alert re-fired without reaching threshold after reset"
    finally:
        alerts.send_alert = orig
        main._gate_failure_counts.clear()
    print("PASS: gate exceptions escalate at threshold and reset on success")


def test_gate_counters_are_per_gate() -> None:
    calls = []
    orig = alerts.send_alert
    alerts.send_alert = lambda msg, level="critical", key=None: calls.append(msg)
    main._gate_failure_counts.clear()
    try:
        for _ in range(GATE_ALERT_AFTER - 1):
            main._gate_exception("margin", "boom")
            main._gate_exception("currency_exposure", "boom")
        assert calls == [], "cross-gate counts must not pool into one threshold"
    finally:
        alerts.send_alert = orig
        main._gate_failure_counts.clear()
    print("PASS: failure counters are per-gate")


if __name__ == "__main__":
    test_floor_fails_closed_on_api_error()
    test_floor_passes_and_returns_navs()
    test_floor_breach_still_detected()
    test_gate_exception_escalates_then_resets()
    test_gate_counters_are_per_gate()
    print("ALL PASS: test_fail_closed_gates.py")
