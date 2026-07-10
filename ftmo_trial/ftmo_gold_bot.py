"""
FTMO trial forward test -- multi-slot challenge bot (XAUUSD + USDJPY).

FTMO-TRIAL EXPERIMENT ONLY. One process, one terminal connection, N slots:
each slot is a (symbol, plugin, direction-filter, risk%) row trading the
14-day FTMO free trial (demo 1600158217, OANDA-Demo-1, $100k virtual).
Isolated from the Rhyme fleet: no scheduler task, not in RESEARCH_ACCOUNTS,
invisible to portfolio_state and the audit.

Slots (campaign Track 2 registration, main RESEARCH_LOG 2026-07-09):
  xau  -- XAUUSD.sim, trend-origin pullback, both directions (the Gate-2/
          cost-gate validated candidate; the original single-slot deployment)
  jpy  -- USDJPY.sim, trend-origin pullback LONG-ONLY (pullback30's fleet-
          probation variant; best prop-preset profile on the board)

Each slot gets its OWN plugin module instance (importlib, the harness's
_load_plugin pattern) because the plugin's re-entry guard is module-global
state -- sharing one module across symbols lets interleaved trades wipe
each other's zone identity.

Shared account-level guards (FTMO rules are account-wide): daily circuit
breaker, equity floor, aggregate open-position cap. Per-slot: one position.

Dry-run by default; --armed places real demo orders.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/ftmo_trial/ftmo_gold_bot.py [--armed]
"""
from __future__ import annotations
import argparse
import importlib.util
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
sys.path.insert(0, str(ROOT))          # for strategy/indicators imports

import MetaTrader5 as mt5

from indicators import add_emas, detect_fractals   # fleet enrichment (personal-live lesson)

TERMINAL = r"C:\Program Files\OANDA MetaTrader 5\terminal64.exe"
EXPECTED_LOGIN = 1600158217

INITIAL_BALANCE = 100_000.0
DAILY_HALT_USD = -2_000.0              # no new entries past -2% day P&L (closed+floating)
FLOOR_HALT_EQUITY = 93_000.0           # no new entries at/below (3% above FTMO's $90k line)
MAX_OPEN_POSITIONS = 4                 # aggregate, across all slots (6 slots, 2026-07-09)

H4_COUNT = 230                         # >= 2x the plugin's 110-candle warm-up
M30_COUNT = 400
M15_COUNT = 120                        # ORB needs only the current session's bars
CYCLE_ALIGN_S = 900                    # main loop wakes every M15 boundary
MODE = "scalp30"                       # passed to plugins (ORB ignores it)

# Server clock: EET with European DST, measured 2026-07-09 (winter +2h, summer +3h)
WINTER_OFF, SUMMER_OFF = 2, 3

PULLBACK = ROOT / "trend_origin_pullback_plugin.py"
DONCHIAN = ROOT / "donchian_plugin.py"
ORB_CLOSE = ROOT / "orb_close_plugin.py"
VOLCOMP = ROOT / "volcomp_plugin.py"
WKNDGAP = ROOT / "wkndgap_plugin.py"

# Slot fields: tf/cycle_s = the slot's trigger timeframe and scan cadence
# (main loop wakes every 15m; M30 slots scan every other wake);
# needs_htf = whether the plugin reads an H4 frame (ORB ignores HTF).
SLOTS = [
    {"name": "xau", "symbol": "XAUUSD.sim", "plugin_file": PULLBACK, "long_only": False,
     "risk_pct": 0.005, "magic": 20260709, "cycle_s": 1800, "tf": "M30", "needs_htf": True},
    {"name": "jpy", "symbol": "USDJPY.sim", "plugin_file": PULLBACK, "long_only": True,
     "risk_pct": 0.005, "magic": 20260710, "cycle_s": 1800, "tf": "M30", "needs_htf": True},
    # Track 3 (2026-07-09): US500 x trend-origin pullback, Gate-2 pass +
    # factor-overlap (cleanest on the map) + trailing pre-check `proceed`.
    {"name": "spx", "symbol": "US500.sim", "plugin_file": PULLBACK, "long_only": False,
     "risk_pct": 0.005, "magic": 20260711, "cycle_s": 1800, "tf": "M30", "needs_htf": True},
    # btc slot RETIRED 2026-07-09 (same day): the measured $20.57/side/lot
    # commission voids the Gate-2 pass (ex-best-year collapses to +$300 --
    # windfall shape). Open position runs off broker-side per the retirement
    # convention. See RESEARCH_LOG correction entry.
    # Line B (2026-07-09): ORB close-variant slots, M15 cadence. Risk set from
    # the trailing pre-checks per the registered sizing rule (see RESEARCH_LOG
    # deployment registration).
    {"name": "ospx", "symbol": "US500.sim", "plugin_file": ORB_CLOSE, "long_only": False,
     "risk_pct": 0.005, "magic": 20260713, "cycle_s": 900, "tf": "M15", "needs_htf": False},
    {"name": "oxau", "symbol": "XAUUSD.sim", "plugin_file": ORB_CLOSE, "long_only": False,
     "risk_pct": 0.005, "magic": 20260714, "cycle_s": 900, "tf": "M15", "needs_htf": False},
    # Campaign 2 Track B (2026-07-09): volatility-compression breakout, XAU.
    # Full passport pass, lifts <=1.31x, marks-bound pre-check -6.2% @ 0.5%.
    {"name": "vxau", "symbol": "XAUUSD.sim", "plugin_file": VOLCOMP, "long_only": False,
     "risk_pct": 0.005, "magic": 20260715, "cycle_s": 1800, "tf": "M30", "needs_htf": False},
    # Campaign 6 Track C survivor (2026-07-10): EUR weekend-gap continuation.
    # Cleanest overlap on the map (lifts 0.59-1.11x vs whole roster). Entry
    # Monday 03:00 ET window; TIMED exit Monday 16:00 ET (timed_exit pass);
    # broker-side SL 1xATR(20d); TP parked at 5xATR (order-path requirement).
    # ltf_count 1100 so the plugin sees ~23 trading days for its ATR.
    {"name": "gap", "symbol": "EURUSD.sim", "plugin_file": WKNDGAP, "long_only": False,
     "risk_pct": 0.005, "magic": 20260716, "cycle_s": 1800, "tf": "M30", "needs_htf": False,
     "ltf_count": 1100, "timed_exit": True},
]

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


def load_plugin_instance(path=PULLBACK) -> object:
    """Fresh module object per slot -- isolates the plugin's module-global
    re-entry state (same pattern as backtest._load_plugin)."""
    spec = importlib.util.spec_from_file_location(f"_slot_plugin_{id(object())}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
    for slot in SLOTS:
        if not mt5.symbol_select(slot["symbol"], True):
            log.error("symbol_select %s failed: %s", slot["symbol"], mt5.last_error())
            sys.exit(1)


def fetch_frame(symbol: str, timeframe: int, count: int) -> pd.DataFrame:
    """Enriched OHLCV frame, exactly the shape the fleet hands its plugins.
    Drops the (possibly forming) last bar so only complete candles are seen."""
    r = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if r is None or len(r) < 10:
        raise RuntimeError(f"copy_rates_from_pos {symbol}: {mt5.last_error()}")
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    df = df[["time", "open", "high", "low", "close", "volume"]].set_index("time")
    df = df.iloc[:-1]
    return add_emas(detect_fractals(df))


def size_lots(symbol: str, equity: float, entry: float, stop: float, risk_pct: float) -> float:
    """risk_pct of current equity. Dollar value of a 1.0 price move per lot
    comes from tick economics (trade_tick_value/trade_tick_size, already in
    account currency) -- contract_size alone is wrong for non-USD-quoted
    symbols (USDJPY: 1 lot x 1.0 move = 100,000 JPY, ~$680, not $100,000;
    caught live 2026-07-09, first jpy cycle sized to zero)."""
    info = mt5.symbol_info(symbol)
    stop_dist = abs(entry - stop)
    if stop_dist <= 0 or not info.trade_tick_size or not info.trade_tick_value:
        return 0.0
    value_per_unit_per_lot = info.trade_tick_value / info.trade_tick_size
    risk = equity * risk_pct
    raw = risk / (stop_dist * value_per_unit_per_lot)
    step = info.volume_step or 0.01
    # round() on both sides of the floor: quotient dust (0.57/0.01 ->
    # 56.999...) and product dust (41*0.01 -> 0.41000...03) -- see risk._round_lots
    lots = round(math.floor(round(raw / step, 9)) * step, 8)
    return min(max(lots, 0.0), info.volume_max) if lots >= info.volume_min else 0.0


def day_pnl_usd() -> float:
    """Today's closed P&L (server day) + current floating P&L. Account-wide."""
    now_utc = pd.Timestamp.now(tz="UTC").tz_localize(None)
    off = server_offset_hours(now_utc)
    server_now = now_utc + pd.Timedelta(hours=off)
    server_midnight_utc = (server_now.normalize() - pd.Timedelta(hours=off)).to_pydatetime()
    deals = mt5.history_deals_get(server_midnight_utc, datetime.utcnow() + timedelta(hours=12)) or []
    closed = sum(d.profit + d.commission + d.swap for d in deals)
    a = mt5.account_info()
    floating = a.equity - a.balance
    return closed + floating


def place_order(slot: dict, direction: str, lots: float, sl: float, tp: float) -> dict | None:
    symbol = slot["symbol"]
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    is_long = direction == "long"
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lots,
        "type": mt5.ORDER_TYPE_BUY if is_long else mt5.ORDER_TYPE_SELL,
        "price": tick.ask if is_long else tick.bid,
        "sl": round(sl, info.digits),
        "tp": round(tp, info.digits),
        "deviation": 50,
        "magic": slot["magic"],
        "comment": f"ftmo_trial_{slot['name']}",
        "type_time": mt5.ORDER_TIME_GTC,
        # Filling mode from the symbol's own supported flags (IOC was
        # rejected live with retcode 10030 on this server, 2026-07-09)
        "type_filling": (mt5.ORDER_FILLING_IOC if info.filling_mode & 2
                         else mt5.ORDER_FILLING_FOK if info.filling_mode & 1
                         else mt5.ORDER_FILLING_RETURN),
    }
    res = mt5.order_send(req)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        log.warning("[%s] order rejected: retcode=%s comment=%s",
                    slot["name"], res and res.retcode, res and res.comment)
        return None
    # This server returns price=0.0 on the order result (observed live
    # 2026-07-09) -- the real fill price lives on the opened position.
    fill_price = res.price
    if not fill_price:
        pos = mt5.positions_get(symbol=symbol)
        fill_price = pos[-1].price_open if pos else req["price"]
    return {"price": fill_price, "volume": res.volume, "order": res.order,
            "requested": req["price"], "spread_at_entry": tick.ask - tick.bid}


def open_position_count(symbol: str | None = None) -> int:
    if symbol:
        return len(mt5.positions_get(symbol=symbol) or [])
    return len(mt5.positions_get() or [])


def slot_position_count(slot: dict) -> int:
    """Per-slot cap counts only THIS slot's positions (magic-filtered):
    two slots can share a symbol (orb-xau + pullback-xau) without blocking
    each other."""
    return sum(1 for p in (mt5.positions_get(symbol=slot["symbol"]) or [])
               if p.magic == slot["magic"])


def close_slot_position(slot: dict, armed: bool) -> None:
    """Market-close this slot's open position (timed-exit slots only)."""
    for p in (mt5.positions_get(symbol=slot["symbol"]) or []):
        if p.magic != slot["magic"]:
            continue
        if not armed:
            log.info("  [%s] DRY-RUN timed exit: would close %.2f lots", slot["name"], p.volume)
            continue
        tick = mt5.symbol_info_tick(slot["symbol"])
        info = mt5.symbol_info(slot["symbol"])
        is_long = p.type == mt5.POSITION_TYPE_BUY
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": slot["symbol"],
               "volume": p.volume, "position": p.ticket,
               "type": mt5.ORDER_TYPE_SELL if is_long else mt5.ORDER_TYPE_BUY,
               "price": tick.bid if is_long else tick.ask,
               "deviation": 50, "magic": slot["magic"],
               "comment": f"ftmo_trial_{slot['name']}_texit",
               "type_time": mt5.ORDER_TIME_GTC,
               "type_filling": (mt5.ORDER_FILLING_IOC if info.filling_mode & 2
                                else mt5.ORDER_FILLING_FOK if info.filling_mode & 1
                                else mt5.ORDER_FILLING_RETURN)}
        res = mt5.order_send(req)
        if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
            log.warning("  [%s] timed-exit close REJECTED: retcode=%s", slot["name"],
                        res and res.retcode)
        else:
            log.info("  [%s] >> TIMED EXIT closed %.2f lots (order=%s)",
                     slot["name"], p.volume, res.order)


def timed_exit_due(slot: dict, now_utc: pd.Timestamp) -> bool:
    """gap-slot rule: a position may live ONLY during Monday before 16:00 ET
    (entries happen Monday 03:00 ET). Any other time an open position exists
    -- including after downtime -- it is closed at the first wake."""
    if not slot.get("timed_exit"):
        return False
    from orb_plugin_core import _us_dst_offset   # the hand-verified US statutory rule
    et = now_utc + pd.Timedelta(hours=_us_dst_offset(now_utc))
    return not (et.dayofweek == 0 and (et.hour * 60 + et.minute) < 960)


def pidfile_guard() -> None:
    if PIDFILE.exists():
        log.error("pidfile exists (%s) -- refusing to double-run; remove it if stale",
                  PIDFILE.read_text().strip())
        sys.exit(1)
    PIDFILE.write_text(str(os.getpid()))


def scan_slot(slot: dict, equity: float, armed: bool) -> None:
    name, symbol = slot["name"], slot["symbol"]
    if slot_position_count(slot) >= 1:
        log.info("  [%s] no scan  (one-position cap: slot position already open)", name)
        return

    if slot["tf"] == "M15":
        ltf = fetch_frame(symbol, mt5.TIMEFRAME_M15, M15_COUNT)
        htf = ltf if not slot["needs_htf"] else fetch_frame(symbol, mt5.TIMEFRAME_H4, H4_COUNT)
    elif not slot["needs_htf"]:
        ltf = fetch_frame(symbol, mt5.TIMEFRAME_M30, slot.get("ltf_count", M30_COUNT))
        htf = ltf
    else:
        htf = fetch_frame(symbol, mt5.TIMEFRAME_H4, H4_COUNT)
        ltf = fetch_frame(symbol, mt5.TIMEFRAME_M30, slot.get("ltf_count", M30_COUNT))
    signal = slot["plugin"].generate_signal(symbol, htf, ltf, MODE)
    if signal is None:
        log.info("  [%s] %s  no signal", name, symbol)
        return
    if slot["long_only"] and signal.direction != "long":
        log.info("  [%s] %s  %s signal SKIPPED (long-only slot)", name, symbol, signal.direction)
        return

    entry, sl, tp = signal.entry_price, signal.stop_loss, signal.take_profits[0]
    lots = size_lots(symbol, equity, entry, sl, slot["risk_pct"])
    if lots <= 0:
        log.info("  [%s] %s  no trade  (sizes below volume_min at %.2f%% of $%.2f)",
                 name, symbol, slot["risk_pct"] * 100, equity)
        return

    log.info("  [%s] >> SIGNAL  %s %s  entry~%.3f sl=%.3f tp=%.3f lots=%.2f  risk $%.0f",
             name, signal.direction.upper(), symbol, entry, sl, tp, lots,
             equity * slot["risk_pct"])
    if not armed:
        log.info("  [%s] >> DRY-RUN: order NOT placed (launch with --armed to trade)", name)
        return

    fill = place_order(slot, signal.direction, lots, sl, tp)
    if fill:
        slippage = fill["price"] - fill["requested"]
        log.info("  [%s] >> FILLED  order=%s vol=%.2f @ %.3f (requested %.3f, "
                 "slippage %+.3f, spread at entry %.3f)", name, fill["order"],
                 fill["volume"], fill["price"], fill["requested"], slippage,
                 fill["spread_at_entry"])


def cycle(armed: bool, wake_epoch: float | None = None) -> None:
    """One wake of the main loop. Slots scan only on their own cadence:
    wakes land ~5s past each M15 boundary; a slot is due when the boundary
    epoch is a multiple of its cycle_s."""
    if wake_epoch is None:
        wake_epoch = time.time()
    boundary = int(wake_epoch) - (int(wake_epoch) % CYCLE_ALIGN_S)

    # Timed-exit pass runs EVERY wake, before guards (it reduces risk and
    # must fire even when entry guards would halt scanning)
    now_utc = pd.Timestamp(wake_epoch, unit="s")
    for s in SLOTS:
        if timed_exit_due(s, now_utc) and slot_position_count(s) > 0:
            close_slot_position(s, armed)

    due = [s for s in SLOTS if boundary % s["cycle_s"] == 0]
    if not due:
        return

    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %I:%M:%S %p %Z")
    log.info("  FTMO TRIAL  |  %s  |  %d/%d slots due  [%s]", stamp, len(due), len(SLOTS),
             "ARMED" if armed else "DRY-RUN")

    a = mt5.account_info()
    equity = a.equity

    # Shared account-level guards (FTMO rules are account-wide)
    day = day_pnl_usd()
    if day <= DAILY_HALT_USD:
        log.warning("  -- HALT  daily circuit breaker: day P&L $%.2f <= $%.2f", day, DAILY_HALT_USD)
        return
    if equity <= FLOOR_HALT_EQUITY:
        log.warning("  -- HALT  floor guard: equity $%.2f <= $%.2f", equity, FLOOR_HALT_EQUITY)
        return
    if open_position_count() >= MAX_OPEN_POSITIONS:
        log.info("  -- no scan  (aggregate cap: %d positions open)", MAX_OPEN_POSITIONS)
        return

    for slot in due:
        try:
            scan_slot(slot, equity, armed)
        except Exception as e:
            log.error("  [%s] slot error: %s", slot["name"], e)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--armed", action="store_true", help="place real demo orders; default dry-run")
    args = ap.parse_args()

    connect()
    pidfile_guard()
    for slot in SLOTS:
        slot["plugin"] = load_plugin_instance(slot["plugin_file"])
    a = mt5.account_info()

    log.info("=" * 64)
    log.info("  FTMO TRIAL FORWARD TEST  (isolated; not a Rhyme fleet bot)")
    log.info("  Mode    : %s multi-slot  [%s]", MODE, "ARMED -- DEMO ORDERS" if args.armed else "DRY-RUN")
    for slot in SLOTS:
        log.info("  Slot    : %-4s %s %s %s  %.2f%%/trade", slot["name"], slot["symbol"],
                 slot["tf"], "LONG-ONLY" if slot["long_only"] else "long+short",
                 slot["risk_pct"] * 100)
    log.info("  Account : %s @ %s (%s)  equity $%.2f", a.login, a.server, a.company, a.equity)
    log.info("  Guards  : daily halt $%.0f | floor $%.0f | aggregate cap %d | 1/slot",
             DAILY_HALT_USD, FLOOR_HALT_EQUITY, MAX_OPEN_POSITIONS)
    log.info("  Signal  : per-slot fleet plugins (unmodified; fresh module per slot)")
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
