"""
PERSONAL LIVE-ACCOUNT EXPERIMENT — NOT A RHYME STRATEGY.

No passport, no probation, no monitoring contract, no prop evaluation. NOT
covered by fleet monitoring, audit_governance.py, or the $800 fleet floor —
excluded by design. This account ID must NEVER be added to RESEARCH_ACCOUNTS
or any list the fleet's suspension/audit logic iterates over. Not launchable
via main.py's mode system or any scheduler task: manual console launch ONLY.

Purpose: observing LIVE execution mechanics (fills, slippage, spread) on a
$99 account, using scalp30's Donchian signal UNMODIFIED (imported, not
forked). Sizing is file-local: whole units at OANDA's true 1-unit
granularity, 1% of live equity per trade — deliberately NOT risk.py's
0.01-lot flooring, and never to be merged into the fleet's risk layer.

Safety rails: one open position max; personal floor $50 (below it: CRITICAL
log, no new entries); SL/TP placed broker-side at entry (fire-and-forget --
positions stay protected if this process dies); margin pre-check per trade.

ARMING: dry-run by default -- the full pipeline runs and logs the exact
order it WOULD place, but no order is sent unless launched with --armed.

Usage (manual console only):
    D:/rhyme/venv/Scripts/python.exe D:/rhyme/personal_live/personal_live_scalp.py            # dry-run
    D:/rhyme/venv/Scripts/python.exe D:/rhyme/personal_live/personal_live_scalp.py --armed    # live orders
"""
from __future__ import annotations
import argparse
import logging
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))          # for donchian_plugin + strategy.Signal only

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from donchian_plugin import generate_signal   # UNMODIFIED fleet signal function

PAIR = "USD_JPY"
MODE = "scalp30"
RISK_PCT = 0.01            # 1% of live equity -- NOT the fleet's 2%
PERSONAL_FLOOR = 50.0      # this experiment's own floor; unrelated to the fleet's $800
CANDLE_COUNT = 210
CYCLE_ALIGN_S = 1800       # M30 cadence

PIDFILE = HERE / "personal_live.pid"
LOGFILE = HERE / "personal_live.log"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.FileHandler(LOGFILE, encoding="utf-8"),
                              logging.StreamHandler()])
log = logging.getLogger("personal_live")


# ── Own live-host client: PERSONAL_LIVE_* credentials, never OANDA_* ─────────

def live_client():
    import oandapyV20
    token = os.getenv("PERSONAL_LIVE_ACCESS_TOKEN", "")
    if not token:
        log.error("PERSONAL_LIVE_ACCESS_TOKEN missing from .env -- cannot start")
        sys.exit(1)
    return oandapyV20.API(access_token=token, environment="live")


ACCOUNT = os.getenv("PERSONAL_LIVE_ACCOUNT_ID", "")


def account_summary(api) -> dict:
    from oandapyV20.endpoints import accounts
    req = accounts.AccountSummary(ACCOUNT)
    api.request(req)
    return req.response["account"]


def fetch_frame(api, granularity: str) -> pd.DataFrame:
    from oandapyV20.endpoints import instruments
    req = instruments.InstrumentsCandles(PAIR, params={
        "granularity": granularity, "count": CANDLE_COUNT, "price": "M"})
    api.request(req)
    rows, idx = [], []
    for c in req.response["candles"]:
        if not c.get("complete"):
            continue
        m = c["mid"]
        rows.append({"open": float(m["o"]), "high": float(m["h"]),
                     "low": float(m["l"]), "close": float(m["c"]),
                     "volume": int(c.get("volume", 0))})
        idx.append(pd.Timestamp(c["time"]))
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


def open_trade_count(api) -> int:
    from oandapyV20.endpoints import trades
    req = trades.TradesList(ACCOUNT)
    api.request(req)
    return len(req.response.get("trades", []))


# ── File-local sizing: whole units, 1-unit granularity, 1% of live equity ────

def size_units(equity: float, entry: float, stop: float,
               risk_pct: float = RISK_PCT) -> int:
    """floor(risk_dollars / (stop_pips * pip_value_per_unit)); 0 = skip.
    USD_JPY: pip 0.01, pip value per unit = 0.01/price USD."""
    risk_dollars = equity * risk_pct
    stop_pips = abs(entry - stop) / 0.01
    if stop_pips <= 0:
        return 0
    pip_value_per_unit = 0.01 / entry
    return math.floor(risk_dollars / (stop_pips * pip_value_per_unit))


def place_order(api, units: int, sl: float, tp: float) -> dict | None:
    """Market order with broker-side SL/TP (single TP at the plugin's tp[0] --
    documented execution simplification vs the backtest's partial ladder)."""
    from oandapyV20.endpoints import orders
    data = {"order": {
        "type": "MARKET", "instrument": PAIR, "units": str(units),
        "timeInForce": "FOK",
        "stopLossOnFill": {"price": f"{sl:.3f}"},
        "takeProfitOnFill": {"price": f"{tp:.3f}"},
        "clientExtensions": {"tag": "personal_live_experiment"},
    }}
    req = orders.OrderCreate(ACCOUNT, data=data)
    api.request(req)
    fill = req.response.get("orderFillTransaction")
    if not fill:
        cancel = req.response.get("orderCancelTransaction", {})
        log.warning("order not filled: %s", cancel.get("reason", "unknown"))
        return None
    return fill


def pidfile_guard() -> None:
    if PIDFILE.exists():
        log.error("pidfile exists (%s) -- refusing to double-run; remove it if stale",
                  PIDFILE.read_text().strip())
        sys.exit(1)
    PIDFILE.write_text(str(os.getpid()))


def cycle(api, armed: bool) -> None:
    acct = account_summary(api)
    nav = float(acct["NAV"])
    margin_avail = float(acct.get("marginAvailable", 0))

    if nav < PERSONAL_FLOOR:
        log.critical("PERSONAL FLOOR: NAV $%.2f < $%.2f -- no new entries", nav, PERSONAL_FLOOR)
        return
    if open_trade_count(api) >= 1:
        log.info("position already open -- one-position cap, skipping scan")
        return

    htf = fetch_frame(api, "H4")
    ltf = fetch_frame(api, "M30")
    signal = generate_signal(PAIR, htf, ltf, MODE)
    if signal is None:
        log.info("no signal (NAV $%.2f)", nav)
        return

    entry, sl = signal.entry_price, signal.stop_loss
    tp = signal.take_profits[0]
    units = size_units(nav, entry, sl)
    if units < 1:
        log.info("signal present but sizes to 0 units at 1%% of $%.2f -- skip", nav)
        return
    if signal.direction == "short":
        units = -units
    est_margin = abs(units) * entry / 154.0 * 0.02 if PAIR == "USD_JPY" else abs(units) * 0.02
    # margin estimate refined by the API's own rejection if wrong; pre-check vs available:
    if est_margin > margin_avail * 0.9:
        log.info("margin pre-check: est $%.2f > 90%% of available $%.2f -- skip", est_margin, margin_avail)
        return

    log.info("SIGNAL %s %s: entry~%.3f sl=%.3f tp=%.3f units=%+d (risk $%.2f = 1%% of $%.2f)",
             signal.direction, PAIR, entry, sl, tp, units, nav * RISK_PCT, nav)
    if not armed:
        log.info("DRY-RUN: order NOT placed (launch with --armed to trade live)")
        return
    fill = place_order(api, units, sl, tp)
    if fill:
        log.info("FILLED @ %s trade_id=%s", fill.get("price"),
                 fill.get("tradeOpened", {}).get("tradeID"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--armed", action="store_true",
                    help="place real orders; default is dry-run")
    args = ap.parse_args()

    if not ACCOUNT:
        log.error("PERSONAL_LIVE_ACCOUNT_ID missing from .env -- cannot start")
        sys.exit(1)

    api = live_client()
    acct = account_summary(api)   # auth + account verification before anything else
    pidfile_guard()
    log.info("=" * 66)
    log.info("PERSONAL LIVE EXPERIMENT (not a Rhyme strategy) | %s",
             "ARMED -- REAL ORDERS" if args.armed else "DRY-RUN")
    log.info("account %s (live host) | NAV $%.2f | %s %s | 1%%/trade, floor $%.0f",
             ACCOUNT, float(acct["NAV"]), PAIR, MODE, PERSONAL_FLOOR)
    log.info("PID %s | signal: donchian_plugin.generate_signal (unmodified fleet import)", os.getpid())
    log.info("=" * 66)

    try:
        while True:
            try:
                cycle(api, args.armed)
            except Exception as e:
                log.error("cycle error: %s", e)
            sleep_s = CYCLE_ALIGN_S - (time.time() % CYCLE_ALIGN_S) + 5
            time.sleep(sleep_s)
    finally:
        if PIDFILE.exists():
            PIDFILE.unlink()


if __name__ == "__main__":
    main()
