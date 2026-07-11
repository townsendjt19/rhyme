"""
Fleet watchdog -- runs every 15 minutes via the \\Rhyme\\Rhyme-Watchdog
scheduled task (see scheduler/). Added 2026-07-10: before this, process
death and suspensions were only ever discovered forensically
(OPERATIONS_LOG's 4.8-day outage is the reference case).

Checks, all read-only, all alert-only (no gate -- a gate would change
trading behavior without registration):
1. Heartbeat staleness: each fleet process writes heartbeats/<mode>.json
   every cycle (main._write_heartbeat); stale = age > 2x its own cycle
   interval + 5min. Alerts once (deduped by alerts.py), and sends a
   "recovered" alert when a previously-stale mode comes back -- recovery
   tracking lives in watchdog_state.json.
2. spread_state_2b.json 'suspended' flag (naked-leg incident standing).
3. fleet_halt.json 'halted' flag (belt-and-braces for the trigger alert).
4. Correlation clusters: any cluster spanning >= 3 open positions
   (portfolio_state computes these but nothing enforced or surfaced them).

Run:  D:/workspace/rhyme/venv/Scripts/python.exe watchdog.py
Test: watchdog.py --heartbeat-dir <dir>  (point at a fixture dir)
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import alerts

ROOT = Path(__file__).parent
HEARTBEAT_DIR = ROOT / "heartbeats"
STATE_FILE = ROOT / "watchdog_state.json"
SPREAD_STATE = ROOT / "spread_state_2b.json"
FLEET_HALT = ROOT / "fleet_halt.json"
STALE_GRACE_SEC = 300           # on top of 2x the mode's own interval
CLUSTER_ALERT_MIN = 3           # open positions sharing a currency cluster

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s,%(msecs)03d %(levelname)s %(message)s",
                    datefmt="%Y-%m-%d %I:%M:%S %p %Z")
log = logging.getLogger("watchdog")


def _load_state(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"stale": []}


def check_heartbeats(hb_dir: Path, state: dict, now: datetime) -> dict:
    """Returns updated state; alerts on newly-stale and newly-recovered."""
    previously_stale = set(state.get("stale", []))
    currently_stale: set[str] = set()

    for hb_file in sorted(hb_dir.glob("*.json")):
        try:
            hb = json.loads(hb_file.read_text(encoding="utf-8"))
            ts = datetime.fromisoformat(hb["ts"])
            interval = int(hb.get("interval_sec", 3600))
            age = (now - ts).total_seconds()
        except Exception as e:
            log.warning("unreadable heartbeat %s (%s) -- skipping", hb_file.name, e)
            continue
        mode = hb.get("mode", hb_file.stem)
        limit = interval * 2 + STALE_GRACE_SEC
        if age > limit:
            currently_stale.add(mode)
            log.warning("%s heartbeat STALE: %.0fs old (limit %.0fs)", mode, age, limit)
            alerts.send_alert(
                f"{mode} heartbeat stale: {age:,.0f}s since last cycle "
                f"(limit {limit:,.0f}s) -- process likely dead or hung",
                key=f"hb:{mode}",
            )
        else:
            log.info("%s heartbeat ok (%.0fs old, limit %.0fs)", mode, age, limit)

    for mode in sorted(previously_stale - currently_stale):
        # Only celebrate recovery for modes whose heartbeat file still exists
        # (a retired mode's deleted heartbeat is not a recovery).
        if (hb_dir / f"{mode}.json").exists():
            alerts.send_alert(f"{mode} heartbeat RECOVERED", level="info", key=f"hb-rec:{mode}")

    state["stale"] = sorted(currently_stale)
    return state


def check_suspensions() -> None:
    try:
        if SPREAD_STATE.exists() and json.loads(SPREAD_STATE.read_text(encoding="utf-8")).get("suspended"):
            alerts.send_alert(
                "spread2b is SUSPENDED (naked-leg incident) -- manual clear required "
                "(spread_state_2b.json)",
                key="wd:spread-suspended",
            )
    except Exception as e:
        log.warning("could not read spread state: %s", e)
    try:
        if FLEET_HALT.exists() and json.loads(FLEET_HALT.read_text(encoding="utf-8")).get("halted"):
            alerts.send_alert(
                "fleet is HALTED (trailing drawdown) -- operator review + manual clear "
                "required (fleet_halt.json)",
                key="wd:fleet-halted",
            )
    except Exception as e:
        log.warning("could not read fleet halt state: %s", e)


def check_correlation_clusters() -> None:
    """Surface (alert-only) any currency cluster spanning >= CLUSTER_ALERT_MIN
    open positions -- portfolio_state computes clusters but nothing surfaced
    them before 2026-07-10. Needs the OANDA API; degrades to a log line."""
    try:
        from portfolio_state import get_portfolio_state
        state = get_portfolio_state()
        # state.clusters: list[list[OpenPosition]] (shared-currency union-find)
        for cluster in state.clusters or []:
            if len(cluster) >= CLUSTER_ALERT_MIN:
                desc = ", ".join(f"{p.instrument} {p.direction} ({p.strategy})" for p in cluster)
                alerts.send_alert(
                    f"correlation cluster spans {len(cluster)} open positions: {desc} -- "
                    f"review concentration (alert-only, no gate)",
                    key=f"wd:cluster:{desc[:60]}",
                )
    except Exception as e:
        log.warning("cluster check unavailable (%s) -- skipped", e)


def check_signal_frequency(now: datetime) -> None:
    """Weekly (Mondays 00:00-01:00 UTC): run the pre-registered signal-
    frequency review flag. Its alerts are deduped inside signal_frequency
    via alerts.py; a flag repeats weekly until reviewed, by design."""
    if now.weekday() != 0 or now.hour != 0:
        return
    try:
        import subprocess
        import sys
        subprocess.run([sys.executable, str(ROOT / "signal_frequency.py"), "--check"],
                       timeout=300, cwd=str(ROOT))
    except Exception as e:
        log.warning("signal-frequency check failed (%s) -- skipped", e)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heartbeat-dir", default=str(HEARTBEAT_DIR))
    ap.add_argument("--state-file", default=str(STATE_FILE))
    ap.add_argument("--skip-api", action="store_true",
                    help="skip checks needing the OANDA API (cluster check)")
    args = ap.parse_args()

    hb_dir = Path(args.heartbeat_dir)
    state_file = Path(args.state_file)
    now = datetime.now(tz=timezone.utc)

    state = _load_state(state_file)
    if hb_dir.exists():
        state = check_heartbeats(hb_dir, state, now)
    else:
        log.info("no heartbeat dir yet (%s) -- fleet not restarted on new code?", hb_dir)
    check_suspensions()
    if not args.skip_api:
        check_correlation_clusters()
        check_signal_frequency(now)

    try:
        state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("could not persist watchdog state: %s", e)
    log.info("watchdog sweep complete")


if __name__ == "__main__":
    main()
