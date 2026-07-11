"""
Tests for alerts.py -- the hard requirement is "never raises, never blocks
trading": every failure mode must degrade silently.

Run: D:/workspace/rhyme/venv/Scripts/python.exe test_alerts.py
"""
from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

import alerts


def _fresh_dedupe(tmp: Path) -> None:
    alerts.DEDUPE_FILE = tmp / "alerts_sent.json"


def test_no_config_does_not_raise(tmp: Path) -> None:
    _fresh_dedupe(tmp)
    alerts.CONFIG_FILE = tmp / "nonexistent.json"   # and no env vars in test run
    alerts.send_alert("no config present")           # must simply not raise
    print("PASS: send_alert with no config does not raise")


def test_transport_raise_swallowed(tmp: Path) -> None:
    _fresh_dedupe(tmp)
    orig_tg, orig_toast = alerts._send_telegram, alerts._send_toast

    def boom(*a, **k):
        raise RuntimeError("transport down")

    alerts._send_telegram = boom
    alerts._send_toast = boom
    try:
        alerts.send_alert("transports exploding")    # must not raise
    finally:
        alerts._send_telegram, alerts._send_toast = orig_tg, orig_toast
    print("PASS: transport exceptions are swallowed")


def test_dedupe(tmp: Path) -> None:
    _fresh_dedupe(tmp)
    calls = []
    orig_tg, orig_toast = alerts._send_telegram, alerts._send_toast
    alerts._send_telegram = lambda text: calls.append(text) or True
    alerts._send_toast = lambda title, text: True
    try:
        alerts.send_alert("first", key="k1")
        alerts.send_alert("second same key", key="k1")   # suppressed
        alerts.send_alert("different key", key="k2")
        alerts.send_alert("no key always sends")
        alerts.send_alert("no key always sends")
    finally:
        alerts._send_telegram, alerts._send_toast = orig_tg, orig_toast
    assert len(calls) == 4, f"expected 4 sends, got {len(calls)}: {calls}"
    print("PASS: dedupe suppresses repeated keys, keyless always sends")


def test_dedupe_window_expiry(tmp: Path) -> None:
    _fresh_dedupe(tmp)
    now = time.time()
    assert alerts._dedupe_ok("kx", now) is True
    assert alerts._dedupe_ok("kx", now + 10) is False
    assert alerts._dedupe_ok("kx", now + alerts.ALERT_DEDUPE_SEC + 1) is True
    print("PASS: dedupe window expires after ALERT_DEDUPE_SEC")


def test_handler_fires_on_critical_only(tmp: Path) -> None:
    _fresh_dedupe(tmp)
    calls = []
    orig_tg, orig_toast = alerts._send_telegram, alerts._send_toast
    alerts._send_telegram = lambda text: calls.append(text) or True
    alerts._send_toast = lambda title, text: True

    lg = logging.getLogger("test_alerts_handler")
    lg.addHandler(alerts.AlertingHandler())
    lg.setLevel(logging.DEBUG)
    try:
        lg.error("an error -- should NOT alert")
        lg.critical("a critical -- SHOULD alert")
        lg.critical("a critical -- SHOULD alert")   # same message -> deduped
    finally:
        alerts._send_telegram, alerts._send_toast = orig_tg, orig_toast
    assert len(calls) == 1, f"expected 1 send, got {len(calls)}: {calls}"
    assert "SHOULD alert" in calls[0]
    print("PASS: AlertingHandler fires on CRITICAL only, deduped")


def test_attach_once(tmp: Path) -> None:
    _fresh_dedupe(tmp)
    lg = logging.getLogger("test_attach_once_target")
    before = len(lg.handlers)
    alerts._handler_attached = False
    alerts.attach_once(lg)
    alerts.attach_once(lg)   # second call must be a no-op
    assert len(lg.handlers) == before + 1, "attach_once attached more than once"
    print("PASS: attach_once attaches exactly one handler")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_no_config_does_not_raise(tmp)
        test_transport_raise_swallowed(tmp)
        test_dedupe(tmp)
        test_dedupe_window_expiry(tmp)
        test_handler_fires_on_critical_only(tmp)
        test_attach_once(tmp)
    print("ALL PASS: test_alerts.py")
