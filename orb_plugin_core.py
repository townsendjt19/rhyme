"""
Opening-range breakout core (Line B, registered 2026-07-09 BEFORE this file).

Session-anchored momentum: OR = 09:30-10:00 ET high/low; entry beyond the OR
extreme inside 10:00-15:30 ET; stop = opposite OR extreme (box-9 floor);
TP = 2x OR height; one trade per (session, direction); fire-and-forget.

Two entry variants (registered A/B), selected by the wrapper module:
  "close" -- first M15 CLOSE beyond the OR extreme
  "touch" -- entry AT the OR extreme on the first bar crossing it

Frames arrive in UTC (the gate2 fetch seam); ET is derived by the US
statutory DST rule (second Sunday of March / first Sunday of November).
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal

_TP_MULT = 2.0
_MIN_STOP_TO_SPREAD = 10.0

# Real .sim median spreads, price units (registered)
_SPREAD = {"SPX": 0.5, "US500.sim": 0.5, "YM": 2.0, "US30.sim": 2.0,
           "XAUUSD": 0.25, "XAUUSD.sim": 0.25}

WARMUP_HTF_CANDLES = 12   # session-anchored; needs only today's bars

_used: set = set()        # (date, direction) single-use identities


def _us_dst_offset(ts: pd.Timestamp) -> int:
    """UTC->ET offset (negative hours): EDT -4 between 2nd Sun Mar 07:00 UTC
    and 1st Sun Nov 06:00 UTC, else EST -5. Accepts naive-UTC or tz-aware
    timestamps (harness frames are tz-aware; comparing those against naive
    boundary stamps raised TypeError, which the backtest harness silently
    swallows as 'no signal' -- caught 2026-07-09, 12 zero-trade cells)."""
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    y = ts.year
    def nth_sunday(month, n):
        d = pd.Timestamp(y, month, 1)
        d += pd.Timedelta(days=(6 - d.dayofweek) % 7)   # first Sunday
        return d + pd.Timedelta(days=7 * (n - 1))
    start = nth_sunday(3, 2) + pd.Timedelta(hours=7)    # 02:00 EST = 07:00 UTC
    end = nth_sunday(11, 1) + pd.Timedelta(hours=6)     # 02:00 EDT = 06:00 UTC
    return -4 if start <= ts < end else -5


def _to_et(ts: pd.Timestamp) -> pd.Timestamp:
    return ts + pd.Timedelta(hours=_us_dst_offset(ts))


def generate_signal(instrument, htf_df, ltf_df, mode, entry_style="close") -> Signal | None:
    if len(ltf_df) < 3:
        return None
    now = ltf_df.index[-1]
    et = _to_et(now)
    # Signal window: bar CLOSE time is bar open + 15m; act on bars whose ET
    # open is within [10:00, 15:30).
    et_minutes = et.hour * 60 + et.minute
    if not (600 <= et_minutes < 930):
        return None

    session_date = et.date()
    day = ltf_df[[_to_et(t).date() == session_date for t in ltf_df.index]]
    et_mins = [(t, _to_et(t).hour * 60 + _to_et(t).minute) for t in day.index]
    or_bars = day.loc[[t for t, m in et_mins if 570 <= m < 600]]   # 09:30, 09:45
    if len(or_bars) < 2:
        return None   # incomplete opening range (holiday/half-day)
    or_high, or_low = or_bars["high"].max(), or_bars["low"].min()
    height = or_high - or_low
    if height <= 0:
        return None

    spread = _SPREAD.get(instrument, 0.5)
    if height < _MIN_STOP_TO_SPREAD * spread:
        return None   # box-9: the structural stop IS the OR height class

    bar = ltf_df.iloc[-1]
    for direction, level, stop in (("long", or_high, or_low), ("short", or_low, or_high)):
        key = (session_date, direction)
        if key in _used:
            continue
        if entry_style == "close":
            hit = bar["close"] > level if direction == "long" else bar["close"] < level
            entry = bar["close"]
        else:  # touch
            hit = bar["high"] >= level if direction == "long" else bar["low"] <= level
            entry = level
        if not hit:
            continue
        if abs(entry - stop) < _MIN_STOP_TO_SPREAD * spread:
            _used.add(key)   # identity consumed even when floored (single-use)
            continue
        tp = entry + _TP_MULT * height * (1 if direction == "long" else -1)
        _used.add(key)
        return Signal(direction=direction, entry_price=float(entry),
                      stop_loss=float(stop), take_profits=[float(tp)] * 3,
                      instrument=instrument, timeframe="M15",
                      reason=f"ORB {entry_style} h={height:.2f}")
    return None
