"""
FTMO trial forward test -- XAUUSD.sim challenge bot.

FTMO-TRIAL EXPERIMENT ONLY. Trades the validated trend-origin pullback
candidate (Gate 2 + factor overlap + Phase B cost gate, RESEARCH_LOG
2026-07-08/09) on the 14-day FTMO free trial (demo account 1600158217,
OANDA-Demo-1, $100k virtual). Isolated from the Rhyme fleet: no scheduler
task, not in RESEARCH_ACCOUNTS, invisible to portfolio_state and the audit.

Phase discipline (registered in the main RESEARCH_LOG before first armed
cycle): this collects EXECUTION MECHANICS (fills, slippage, spread paid,
SL/TP behavior) and a small honest forward record. ~8-10 trades in 14 days
concludes NOTHING about strategy performance.

Dry-run by default: every cycle logs the order it WOULD place, but no order
is sent unless launched with --armed.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/ftmo_trial/ftmo_gold_bot.py [--armed]
"""
from __future__ import annotations
import argparse
import logging
import math
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))          # for the plugin + indicators only

import MetaTrader5 as mt5

from trend_origin_pullback_plugin import generate_signal   # UNMODIFIED fleet plugin
from indicators import add_emas, detect_fractals           # fleet enrichment (personal-live lesson)

TERMINAL = r"C:\Program Files\OANDA MetaTrader 5\terminal64.exe"
EXPECTED_LOGIN = 1600158217
SYMBOL = "XAUUSD.sim"
MODE = "scalp30"                       # H4/M30, the validated configuration

INITIAL_BALANCE = 100_000.0
RISK_PCT = 0.005                       # 0.5% of current equity (operator-selected)
DAILY_HALT_USD = -2_000.0              # no new entries past -2% day P&L (closed+floating)
FLOOR_HALT_EQUITY = 93_000.0           # no new entries at/below (3% above FTMO's $90k line)

H4_COUNT = 230                         # >= 2x the plugin's 110-candle warm-up
M30_COUNT = 400
CYCLE_ALIGN_S = 1800

# Server clock: EET with European DST, measured 2026-07-09 (winter +2h, summer +3h)
WINTER_OFF, SUMMER_OFF = 2, 3

PIDFILE = HERE / "ftmo_gold_bot.pid"
LOGFILE = HERE / "ftmo_gold_bot.log"

_fmt = logging.Formatter("%(asctime)s,%(msecs)03d %(levelname)s %(message)s",
                         datefmt="%Y-%m-%d %I:%M:%S %p %Z")
_fh = logging.FileHandler(LOGFILE, encoding="utf-8")
_fh.setFormatter(_fmt)
_out = logging.StreamHandler(sys.stdout)
_out.setFormatter(_fmt)
_err = logging.StreamHandler(sys.stderr)
_err.setFormatter(_fmt)
_err.setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO, handlers=[_fh, _out, _err])
log = logging.getLogger("ftmo_trial")


def server_offset_hours(ts_utc: pd.Timestamp) -> int:
    """European DST: last Sunday of March 01:00 UTC -> last Sunday of October 01:00 UTC."""
    y = ts_utc.year
    def last_sunday(month):
        d = pd.Timestamp(y, month, 31)
        while d.month != month:
            d -= pd.Timedelta(days=1)
        return d if d.dayofweek == 6 else d - pd.Timedelta(days=d.dayofweek + 1)
    if last_sunday(3).replace(hour=1) <= ts_utc < last_sunday(10).replace(hour=1):
        return SUMMER_OFF
    return WINTER_OFF


def connect() -> None:
    if not mt5.initialize(path=TERMINAL, timeout=90_000):
        log.error("MT5 attach failed: %s", mt5.last_error())
        sys.exit(1)
    a = mt5.account_info()
    if a is None or a.login != EXPECTED_LOGIN:
        log.error("wrong account: %s (expected %s) -- refusing", a and a.login, EXPECTED_LOGIN)
        mt5.shutdown()
        sys.exit(1)
    if a.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        log.error("account %s is NOT demo (trade_mode=%s) -- refusing", a.login, a.trade_mode)
        mt5.shutdown()
        sys.exit(1)
    if not mt5.symbol_select(SYMBOL, True):
        log.error("symbol_select %s failed: %s", SYMBOL, mt5.last_error())
        sys.exit(1)


def fetch_frame(timeframe: int, count: int) -> pd.DataFrame:
    """Enriched OHLCV frame, exactly the shape the fleet hands its plugins.
    Drops the (possibly forming) last bar so only complete candles are seen."""
    r = mt5.copy_rates_from_pos(SYMBOL, timeframe, 0, count)
    if r is None or len(r) < 10:
        raise RuntimeError(f"copy_rates_from_pos {SYMBOL}: {mt5.last_error()}")
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    df = df[["time", "open", "high", "low", "close", "volume"]].set_index("time")
    df = df.iloc[:-1]
    return add_emas(detect_fractals(df))


def size_lots(equity: float, entry: float, stop: float) -> float:
    """0.5% of current equity; XAUUSD contract sizing from symbol_info."""
    info = mt5.symbol_info(SYMBOL)
    stop_dist = abs(entry - stop)
    if stop_dist <= 0:
        return 0.0
    risk = equity * RISK_PCT
    raw = risk / (stop_dist * info.trade_contract_size)
    step = info.volume_step or 0.01
    # round() on both sides of the floor: quotient dust (0.57/0.01 ->
    # 56.999...) and product dust (41*0.01 -> 0.41000...03) -- see risk._round_lots
    lots = round(math.floor(round(raw / step, 9)) * step, 8)
    return min(max(lots, 0.0), info.volume_max) if lots >= info.volume_min else 0.0


def day_pnl_usd() -> float:
    """Today's closed P&L (server day) + current floating P&L."""
    now_utc = pd.Timestamp.now(tz="UTC").tz_localize(None)
    off = server_offset_hours(now_utc)
    server_now = now_utc + pd.Timedelta(hours=off)
    server_midnight_utc = (server_now.normalize() - pd.Timedelta(hours=off)).to_pydatetime()
    deals = mt5.history_deals_get(server_midnight_utc, datetime.utcnow() + timedelta(hours=12)) or []
    closed = sum(d.profit + d.commission + d.swap for d in deals)
    a = mt5.account_info()
    floating = a.equity - a.balance
    return closed + floating


def place_order(direction: str, lots: float, sl: float, tp: float) -> dict | None:
    tick = mt5.symbol_info_tick(SYMBOL)
    is_long = direction == "long"
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": lots,
        "type": mt5.ORDER_TYPE_BUY if is_long else mt5.ORDER_TYPE_SELL,
        "price": tick.ask if is_long else tick.bid,
        "sl": round(sl, 3),
        "tp": round(tp, 3),
        "deviation": 50,
        "magic": 20260709,
        "comment": "ftmo_trial_xau",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        log.warning("order rejected: retcode=%s comment=%s",
                    res and res.retcode, res and res.comment)
        return None
    return {"price": res.price, "volume": res.volume, "order": res.order,
            "requested": req["price"], "spread_at_entry": tick.ask - tick.bid}


def open_position_count() -> int:
    return len(mt5.positions_get(symbol=SYMBOL) or [])


def pidfile_guard() -> None:
    if PIDFILE.exists():
        log.error("pidfile exists (%s) -- refusing to double-run; remove it if stale",
                  PIDFILE.read_text().strip())
        sys.exit(1)
    PIDFILE.write_text(str(os.getpid()))


def cycle(armed: bool) -> None:
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %I:%M:%S %p %Z")
    log.info("  FTMO TRIAL  |  %s  |  %s %s  [%s]", stamp, SYMBOL, MODE,
             "ARMED" if armed else "DRY-RUN")

    a = mt5.account_info()
    equity = a.equity

    if open_position_count() >= 1:
        log.info("  -- no scan  (one-position cap: position already open)")
        return
    day = day_pnl_usd()
    if day <= DAILY_HALT_USD:
        log.warning("  -- HALT  daily circuit breaker: day P&L $%.2f <= $%.2f", day, DAILY_HALT_USD)
        return
    if equity <= FLOOR_HALT_EQUITY:
        log.warning("  -- HALT  floor guard: equity $%.2f <= $%.2f", equity, FLOOR_HALT_EQUITY)
        return

    htf = fetch_frame(mt5.TIMEFRAME_H4, H4_COUNT)
    ltf = fetch_frame(mt5.TIMEFRAME_M30, M30_COUNT)
    signal = generate_signal(SYMBOL, htf, ltf, MODE)
    if signal is None:
        log.info("  -- %s  no signal", SYMBOL)
        return

    entry, sl, tp = signal.entry_price, signal.stop_loss, signal.take_profits[0]
    lots = size_lots(equity, entry, sl)
    if lots <= 0:
        log.info("  -- %s  no trade  (sizes below volume_min at %.2f%% of $%.2f)",
                 SYMBOL, RISK_PCT * 100, equity)
        return

    log.info("  >> SIGNAL  %s %s  entry~%.3f sl=%.3f tp=%.3f lots=%.2f  risk $%.0f of $%.2f",
             signal.direction.upper(), SYMBOL, entry, sl, tp, lots, equity * RISK_PCT, equity)
    if not armed:
        log.info("  >> DRY-RUN: order NOT placed (launch with --armed to trade)")
        return

    fill = place_order(signal.direction, lots, sl, tp)
    if fill:
        slippage = fill["price"] - fill["requested"]
        log.info("  >> FILLED  order=%s vol=%.2f @ %.3f (requested %.3f, slippage %+.3f, "
                 "spread at entry %.3f)", fill["order"], fill["volume"], fill["price"],
                 fill["requested"], slippage, fill["spread_at_entry"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--armed", action="store_true", help="place real demo orders; default dry-run")
    args = ap.parse_args()

    connect()
    pidfile_guard()
    a = mt5.account_info()

    log.info("=" * 64)
    log.info("  FTMO TRIAL FORWARD TEST  (isolated; not a Rhyme fleet bot)")
    log.info("  Mode    : %s  [%s]", MODE, "ARMED -- DEMO ORDERS" if args.armed else "DRY-RUN")
    log.info("  Symbol  : %s", SYMBOL)
    log.info("  Account : %s @ %s (%s)  equity $%.2f", a.login, a.server, a.company, a.equity)
    log.info("  Sizing  : %.2f%%/trade of current equity | daily halt $%.0f | floor $%.0f",
             RISK_PCT * 100, DAILY_HALT_USD, FLOOR_HALT_EQUITY)
    log.info("  Signal  : trend_origin_pullback_plugin.generate_signal (unmodified fleet import)")
    log.info("  PID     : %s  (lockfile: %s)", os.getpid(), PIDFILE)
    log.info("=" * 64)

    try:
        while True:
            try:
                cycle(args.armed)
            except Exception as e:
                log.error("cycle error: %s", e)
            sleep_s = CYCLE_ALIGN_S - (time.time() % CYCLE_ALIGN_S) + 5
            wake = datetime.now(timezone.utc).astimezone() + timedelta(seconds=sleep_s)
            log.info("Next candle at %s -- sleeping %ds",
                     wake.strftime("%Y-%m-%d %I:%M:%S %p %Z"), int(sleep_s))
            time.sleep(sleep_s)
    finally:
        if PIDFILE.exists():
            PIDFILE.unlink()


if __name__ == "__main__":
    main()
