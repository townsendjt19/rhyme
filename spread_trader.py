"""
Stat-arb 2B spread trader — NZD_USD / USD_CAD, isolated account -003.

Implements the approved deployment design (RESEARCH_LOG 2026-07-02, commits
a8df3ed + e201c6f) on the Phase 2 validated mechanics (1149237): rolling-90
adaptive-beta z-spread, entry |z| >= 2.0 (with the §1a live-mid staleness
re-check at commitment), exit |z| <= 0.5, stop |z| >= 3.5, one idea at a
time, $80 trade-idea risk across both legs, atomic execution via
spread_execution, emergency hard SLs at 2x the spread-stop distance.

Operational notes:
- Exits are SOFTWARE-managed (this process must be alive); the broker-side
  emergency SLs are catastrophe bounds only. Crash recovery = logon-triggered
  scheduler task + startup orphan reconciliation.
- Signals evaluate once per completed daily candle; the loop wakes hourly.
- A NAKED_LEG incident suspends new entries persistently; clearing the
  suspension is a manual operator action (delete the flag in the state file
  after resolving the incident).

Usage (scheduler is the sole launch path, fleet convention):
    D:/rhyme/venv/Scripts/python.exe D:/rhyme/spread_trader.py --account 101-001-39634331-003
"""
from __future__ import annotations
import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "spread_state_2b.json"
PIDFILE = ROOT / "paper_trader_spread2b.pid"
EVENTS_CSV = ROOT / "paper_trades_spread2b.csv"

PAIR_Y, PAIR_X = "NZD_USD", "USD_CAD"   # leg 1 = NZD_USD (less liquid, fills first)
RISK_USD = 80.0
CYCLE_SEC = 3600
EMERGENCY_SL_MULT = 2.0                  # x the 1.5-sigma spread-stop distance

# Fleet timestamp convention (main.py's AM/PM local style with ,ms)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s,%(msecs)03d %(levelname)s %(message)s",
                    datefmt="%Y-%m-%d %I:%M:%S %p %Z")
log = logging.getLogger("spread2b")

# Operator alerting (2026-07-10): CRITICALs (naked leg, exit-close failure,
# equity floor, fleet halt) escalate to Telegram + toast. attach_once is
# idempotent -- importing main below attaches it too.
import alerts
alerts.attach_once()


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"idea": None, "suspended": False, "last_eval": None, "idea_seq": 0}


def save_state(st: dict) -> None:
    STATE_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def log_event(kind: str, detail: dict) -> None:
    import csv
    new = not EVENTS_CSV.exists()
    with EVENTS_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "kind", "detail"])
        w.writerow([datetime.now(timezone.utc).isoformat(), kind, json.dumps(detail)])


def pidfile_guard() -> None:
    """Fleet convention: remove a stale pidfile, refuse to double-run."""
    if PIDFILE.exists():
        old = int(PIDFILE.read_text().strip() or 0)
        alive = False
        if old:
            try:
                out = subprocess.run(["tasklist", "/FI", f"PID eq {old}"],
                                     capture_output=True, text=True, timeout=30).stdout
                alive = str(old) in out and "python" in out.lower()
            except Exception:
                alive = True   # can't verify -> assume alive, refuse to start
        if alive:
            log.error("another spread2b process (PID %s) is alive -- exiting", old)
            sys.exit(1)
        log.info("Stale pidfile (PID %s, mode=spread2b) no longer alive -- removing", old)
        PIDFILE.unlink()
    PIDFILE.write_text(str(os.getpid()))


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return "unknown"


def units_for_notional(instrument: str, notional_usd: float) -> int:
    import broker
    base = instrument.split("_")[0]
    usd_per_base = broker.convert_to_usd(1.0, base)
    return int(round(notional_usd / usd_per_base)) if usd_per_base > 0 else 0


def try_entry(st: dict, sig: dict) -> None:
    import broker
    from portfolio_state import (get_portfolio_state, check_spread_position_cap,
                                 check_spread_currency_exposure_cap)
    from risk import spread_trade_units
    from spread_signal import Z_ENTRY, Z_STOP, live_z, leg_signs
    import spread_execution as sx

    if abs(sig["z"]) < Z_ENTRY:
        log.info("  -- %s/%s  no entry  (z=%+.2f, inside ±%.1f)", PAIR_Y, PAIR_X, sig["z"], Z_ENTRY)
        return
    direction = "short" if sig["z"] > 0 else "long"   # of the SPREAD (y-leg side)
    sgn, x_sign = leg_signs(direction, sig["beta"])

    n_y_usd, n_x_usd = spread_trade_units(RISK_USD, sig["sigma"], Z_ENTRY, Z_STOP, sig["beta"])
    units_y = sgn * units_for_notional(PAIR_Y, n_y_usd)
    units_x = x_sign * units_for_notional(PAIR_X, n_x_usd)
    if units_y == 0 or units_x == 0:
        log.warning("  -- %s/%s  no entry  (sizing produced zero units, sigma %.5f)", PAIR_Y, PAIR_X, sig["sigma"])
        return
    legs = [(PAIR_Y, units_y), (PAIR_X, units_x)]

    # Joint gates -- the idea approves or rejects WHOLE.
    state = get_portfolio_state()
    ok, why = check_spread_position_cap(state, legs)
    if not ok:
        log.info("  -- %s/%s  no entry  (gated: %s)", PAIR_Y, PAIR_X, why)
        return
    ok, why = check_spread_currency_exposure_cap(state, legs)
    if not ok:
        log.info("  -- %s/%s  no entry  (gated: %s)", PAIR_Y, PAIR_X, why)
        return
    margin = sum(broker.required_margin_usd(i, abs(u)) for i, u in legs)
    free = broker.get_account_margin()[1]
    if margin > free * 0.9:
        log.info("  -- %s/%s  no entry  (gated: two-leg margin $%.0f vs free $%.0f)", PAIR_Y, PAIR_X, margin, free)
        return

    # §1a pre-flight staleness: same threshold, at the moment of commitment.
    y_mid, x_mid = broker._current_price(PAIR_Y), broker._current_price(PAIR_X)
    zl = live_z(sig, y_mid, x_mid)
    if abs(zl) < Z_ENTRY or (zl > 0) != (sig["z"] > 0):
        log.info("  -- %s/%s  no entry  (stale at execution: close-z %+.2f, live-z %+.2f)",
                 PAIR_Y, PAIR_X, sig["z"], zl)
        log_event("stale_skip", {"close_z": sig["z"], "live_z": zl})
        return

    # Emergency hard SLs at 2 x 1.5-sigma from current mids (catastrophe bound).
    dist = EMERGENCY_SL_MULT * (Z_STOP - Z_ENTRY) * sig["sigma"]
    sl_y = y_mid * (1 - dist) if units_y > 0 else y_mid * (1 + dist)
    sl_x = x_mid * (1 - dist) if units_x > 0 else x_mid * (1 + dist)

    st["idea_seq"] += 1
    idea_id = f"2B-{st['idea_seq']:04d}"
    leg1 = sx.SpreadLeg(PAIR_Y, units_y, round(sl_y, 5))
    leg2 = sx.SpreadLeg(PAIR_X, units_x, round(sl_x, 5))
    result = sx.execute_spread_idea(idea_id, leg1, leg2, sx.OandaSpreadOps())
    log_event("entry_attempt", {"idea": idea_id, "status": result["status"], "z": sig["z"],
                                "live_z": zl, "beta": sig["beta"], "sigma": sig["sigma"],
                                "legs": {PAIR_Y: units_y, PAIR_X: units_x},
                                "incidents": result["incidents"]})
    if result["status"] == "open":
        st["idea"] = {"id": idea_id, "direction": direction, "legs": result["legs"],
                      "entry_z": sig["z"], "beta": sig["beta"], "sigma": sig["sigma"],
                      "entry_date": str(sig["asof"].date())}
        log.info("  >> LEGS FILLED  %s: %s spread  %s %+d / %s %+d  (z=%+.2f, beta=%+.3f, sigma=%.5f)  trades=%s",
                 idea_id, direction.upper(), PAIR_Y, units_y, PAIR_X, units_x,
                 sig["z"], sig["beta"], sig["sigma"], result["legs"])
    elif result["status"] == "aborted_unwound":
        log.warning("  !! ENTRY ABORTED %s: leg 2 failed, leg 1 unwound cleanly", idea_id)
    elif result["status"] == "NAKED_LEG":
        st["suspended"] = True
        log.critical("  !! SUSPENDED after naked-leg incident on %s -- manual clear required", idea_id)
    save_state(st)


def try_exit(st: dict, sig: dict) -> None:
    from spread_signal import Z_EXIT, Z_STOP
    import spread_execution as sx
    idea = st["idea"]
    z = sig["z"]
    short = idea["direction"] == "short"
    hit_exit = abs(z) <= Z_EXIT
    hit_stop = (z >= Z_STOP) if short else (z <= -Z_STOP)
    if not (hit_exit or hit_stop):
        log.info("  -- holding %s  (z=%+.2f; exit at ±%.1f, stop at ±%.1f)",
                 idea["id"], z, Z_EXIT, Z_STOP)
        return
    reason = "exit_0.5s" if hit_exit else "stop_3.5s"
    ops = sx.OandaSpreadOps()
    failures = []
    for instrument, trade_id in list(idea["legs"].items()):
        if ops.close_trade(trade_id):
            del idea["legs"][instrument]
        else:
            failures.append(trade_id)
    log_event("exit", {"idea": idea["id"], "reason": reason, "z": z, "close_failures": failures})
    if failures:
        log.critical("  !! EXIT CLOSE FAILED for %s -- will retry next cycle; orphan reconciliation is the backstop", failures)
        save_state(st)
        return
    log.info("  >> LEGS CLOSED  %s (%s) at z=%+.2f", idea["id"], reason, z)
    st["idea"] = None
    save_state(st)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="101-001-39634331-003")
    args = ap.parse_args()

    import broker
    broker.set_account(args.account)
    from main import check_equity_floor, check_fleet_drawdown, _write_heartbeat, RESEARCH_ACCOUNTS
    import spread_execution as sx
    from spread_signal import current_signal, ROLL_W, Z_ENTRY, Z_EXIT, Z_STOP

    pidfile_guard()
    nav = broker.get_nav_for(args.account)   # refuse to start on a dead account
    log.info("=" * 70)
    log.info("Rhyme spread trader 2B | legs %s/%s | account %s (NAV $%.2f)",
             PAIR_Y, PAIR_X, args.account, nav)
    log.info("commit %s | PID %s | roll%d z-entry %.1f exit %.1f stop %.1f | $%.0f/idea",
             git_commit(), os.getpid(), ROLL_W, Z_ENTRY, Z_EXIT, Z_STOP, RISK_USD)
    log.info("=" * 70)

    st = load_state()
    inc = sx.reconcile_orphans(sx.OandaSpreadOps())
    for i in inc:
        log_event("reconcile", {"incident": i})

    floor_accounts = list(dict.fromkeys(RESEARCH_ACCOUNTS + [args.account]))
    while True:
        try:
            stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %I:%M:%S %p %Z")
            log.info("  SPREAD TRADE  |  %s  |  mode=spread2b", stamp)
            navs = []
            navs_complete = True
            for acct in floor_accounts:
                try:
                    navs.append((acct, broker.get_nav_for(acct)))
                except Exception as e:
                    # Fails CLOSED since 2026-07-10 (GOVERNANCE dated note,
                    # was fail-open): an account we can't see is a floor we
                    # can't verify -- entries skip this cycle; exits still run.
                    navs_complete = False
                    log.error("floor check: NAV unavailable for %s (%s) -- failing closed", acct, e)
            own_nav = dict(navs).get(args.account)
            ok, why = check_equity_floor(navs)
            # Fleet trailing drawdown halt (GOVERNANCE addendum 2026-07-10):
            # research-account NAVs only -- this process's -003 account is in
            # RESEARCH_ACCOUNTS, and the halt threshold is defined on the
            # fleet peak, so partial lists must not feed the peak math.
            dd_ok, dd_why = (check_fleet_drawdown([(a, n) for a, n in navs if a in RESEARCH_ACCOUNTS])
                             if navs_complete else (False, "fleet drawdown unverifiable (NAV fetch failed)"))

            # Entry blocks (fail-closed conversion + fleet halt, 2026-07-10).
            # Entries and exits are decided SEPARATELY now: exits are
            # software-managed (broker SLs are catastrophe-only), so an open
            # idea keeps being managed even while entries are suspended --
            # previously a floor breach paused exit management too, leaving
            # the position on emergency SLs alone.
            entries_blocked = ""
            if not navs_complete:
                entries_blocked = "NAV fetch incomplete -- failing closed"
                log.error("  !! %s -- entries suspended this cycle", entries_blocked)
            elif not ok:
                entries_blocked = why
                log.critical("  !! EQUITY FLOOR: %s -- entries suspended this cycle", why)
            elif not dd_ok:
                entries_blocked = dd_why
                log.critical("  !! FLEET HALT: %s -- entries suspended this cycle", dd_why)
            elif st.get("suspended"):
                entries_blocked = "suspended (naked-leg incident) -- manual clear required"
                log.warning("  !! %s -- no new entries", entries_blocked)

            if not entries_blocked or st["idea"] is not None:
                sig = current_signal(PAIR_Y, PAIR_X)
                idea = st["idea"]
                log.info("  Account : %s   NAV $%s   idea: %s   z=%+.2f  beta=%+.3f",
                         args.account,
                         f"{own_nav:,.2f}" if own_nav is not None else "?",
                         idea["id"] if idea else "none (flat)", sig["z"], sig["beta"])
                new_close = st.get("last_eval") != str(sig["asof"].date())
                if new_close:
                    st["last_eval"] = str(sig["asof"].date())
                    save_state(st)
                    log.info("  daily eval %s:", sig["asof"].date())
                    if st["idea"] is not None:
                        try_exit(st, sig)
                    elif not entries_blocked:
                        try_entry(st, sig)
                else:
                    log.info("  -- %s/%s  no eval  (no new daily close; last eval %s)",
                             PAIR_Y, PAIR_X, st.get("last_eval"))
        except Exception as e:
            log.error("cycle error: %s", e)
        _write_heartbeat("spread2b", CYCLE_SEC)
        wake = datetime.now(timezone.utc).astimezone() + timedelta(seconds=CYCLE_SEC)
        log.info("Next cycle at %s — sleeping %ds (daily eval fires when a new close appears)",
                 wake.strftime("%Y-%m-%d %I:%M:%S %p %Z"), CYCLE_SEC)
        time.sleep(CYCLE_SEC)


if __name__ == "__main__":
    main()
