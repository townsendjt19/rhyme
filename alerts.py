"""
Operator alerting — Telegram (primary) + Windows toast (best-effort local).

Added 2026-07-10 with the fail-closed gate conversion (see GOVERNANCE.md dated
note): the fleet previously had NO off-box notification path — every incident
in OPERATIONS_LOG.md was discovered forensically, including a 4.8-day outage.

Design constraints:
- send_alert() is the ONLY public send entry point and MUST NEVER RAISE or
  block a trading cycle. Every transport failure degrades to a log line.
- Zero new dependencies: Telegram via urllib, toast via a fire-and-forget
  PowerShell WinRT call.
- Dedupe is cross-process and restart-surviving (alerts_sent.json at repo
  root, shared by all 5 fleet processes): the same `key` is suppressed for
  ALERT_DEDUPE_SEC. Races on that file are benign (worst case one duplicate).
- Config: env RHYME_TG_TOKEN / RHYME_TG_CHAT, else the untracked
  alerts_config.json {"telegram_bot_token": ..., "telegram_chat_id": ...}.
  Missing config -> alerts degrade to log-only, never an error.

AlertingHandler forwards log records >= CRITICAL to send_alert, so the
existing logger.critical() call sites (equity floor, naked leg, exit-close
failure) alert with zero call-site changes. Attach via attach_once() -- the
guard matters because spread_trader imports main, so both may try to attach.

Manual test:  D:/workspace/rhyme/venv/Scripts/python.exe alerts.py --test
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG_FILE = ROOT / "alerts_config.json"      # untracked; holds the bot secret
DEDUPE_FILE = ROOT / "alerts_sent.json"
ALERT_DEDUPE_SEC = 3600

logger = logging.getLogger("alerts")

# Reentrancy guard: send_alert logs its own failures; if AlertingHandler is
# attached to the root logger, a CRITICAL emitted *while sending* must not
# recurse back into send_alert.
_sending = False
_handler_attached = False


def _load_config() -> dict:
    token = os.environ.get("RHYME_TG_TOKEN")
    chat = os.environ.get("RHYME_TG_CHAT")
    if token and chat:
        return {"telegram_bot_token": token, "telegram_chat_id": chat}
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("alerts config unreadable (%s) -- alerts degrade to log-only", e)
    return {}


def _send_telegram(text: str) -> bool:
    cfg = _load_config()
    token = cfg.get("telegram_bot_token")
    chat = cfg.get("telegram_chat_id")
    if not token or not chat:
        return False
    body = json.dumps({"chat_id": chat, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return 200 <= resp.status < 300


def _send_toast(title: str, text: str) -> bool:
    # WinRT toast via PowerShell, fire-and-forget (never waited on): the
    # trading cycle must not stall on a UI call. Single-quote escaping keeps
    # arbitrary alert text safe inside the -Command string.
    t, b = title.replace("'", "''"), text.replace("'", "''")
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] | Out-Null; "
        "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        "$n = $x.GetElementsByTagName('text'); "
        f"$n.Item(0).AppendChild($x.CreateTextNode('{t}')) | Out-Null; "
        f"$n.Item(1).AppendChild($x.CreateTextNode('{b}')) | Out-Null; "
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        "'Rhyme')."
        "Show([Windows.UI.Notifications.ToastNotification]::new($x))"
    )
    subprocess.Popen(
        ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
         "-Command", script],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return True


def _dedupe_ok(key: str, now: float) -> bool:
    """True if this key hasn't fired inside the suppression window. Updates
    the shared dedupe file (read-modify-write; races benign)."""
    sent: dict = {}
    try:
        if DEDUPE_FILE.exists():
            sent = json.loads(DEDUPE_FILE.read_text(encoding="utf-8"))
    except Exception:
        sent = {}
    last = sent.get(key, 0)
    if now - last < ALERT_DEDUPE_SEC:
        return False
    # Prune anything already outside the window so the file can't grow forever.
    sent = {k: v for k, v in sent.items() if now - v < ALERT_DEDUPE_SEC}
    sent[key] = now
    try:
        DEDUPE_FILE.write_text(json.dumps(sent), encoding="utf-8")
    except Exception:
        pass  # dedupe failure -> worst case a duplicate alert, never a miss
    return True


def send_alert(msg: str, level: str = "critical", key: str | None = None) -> None:
    """Fire an operator alert. Never raises; never blocks beyond the 10s
    Telegram timeout. `key` groups repeats: identical keys are suppressed
    for ALERT_DEDUPE_SEC across all fleet processes and restarts."""
    global _sending
    if _sending:
        return
    _sending = True
    try:
        now = time.time()
        if key is not None and not _dedupe_ok(key, now):
            return
        text = f"[rhyme {level.upper()}] {msg}"
        tg_ok = False
        try:
            tg_ok = _send_telegram(text)
        except Exception as e:
            logger.error("telegram alert failed (%s): %s", e, msg)
        try:
            _send_toast(f"Rhyme {level.upper()}", msg)
        except Exception as e:
            logger.error("toast alert failed (%s): %s", e, msg)
        logger.info("ALERT %s (telegram=%s): %s", level.upper(), "sent" if tg_ok else "log-only", msg)
    except Exception:
        pass  # alerting must never break a trading cycle
    finally:
        _sending = False


class AlertingHandler(logging.Handler):
    """Forwards records >= CRITICAL to send_alert, so existing
    logger.critical() call sites alert without modification. Dedupe key is
    the message head, so a repeating CRITICAL (e.g. equity floor, every
    cycle) alerts once per ALERT_DEDUPE_SEC, not per cycle."""

    def __init__(self) -> None:
        super().__init__(level=logging.CRITICAL)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            send_alert(msg, key=f"log:{msg[:120]}")
        except Exception:
            pass


def attach_once(target: logging.Logger | None = None) -> None:
    """Attach the CRITICAL-forwarding handler to the root logger exactly once
    per process (spread_trader imports main -- both call this)."""
    global _handler_attached
    if _handler_attached:
        return
    (target or logging.getLogger()).addHandler(AlertingHandler())
    _handler_attached = True


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="send a live test alert")
    args = ap.parse_args()
    if args.test:
        logging.basicConfig(level=logging.INFO)
        send_alert("test alert -- alerting pipeline is live", level="info")
        print("test alert dispatched (check Telegram + toast; log line above shows transport status)")
