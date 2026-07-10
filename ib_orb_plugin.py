"""
IB-width ORB variant plugin (Campaign 4 Track A, registration 1e1d1b1).
The live ORB close-variant with ONE constant changed, declared as a variant
comparison: OR = 09:30-10:30 ET (four M15 bars) instead of 09:30-10:00;
signal window 10:30-15:30 ET. Everything else verbatim from orb_plugin_core:
close entry, opposite-extreme stop, TP 2x OR height, 10x-spread floor,
one trade/(session, direction), fire-and-forget.
"""
from orb_plugin_core import _SPREAD, _MIN_STOP_TO_SPREAD, _TP_MULT, _us_dst_offset
import pandas as pd

from strategy import Signal

_used: set = set()


def _to_et(ts: pd.Timestamp) -> pd.Timestamp:
    return ts + pd.Timedelta(hours=_us_dst_offset(ts))


def generate_signal(instrument, htf_df, ltf_df, mode) -> Signal | None:
    if len(ltf_df) < 5:
        return None
    now = ltf_df.index[-1]
    et = _to_et(now)
    et_minutes = et.hour * 60 + et.minute
    if not (630 <= et_minutes < 930):           # 10:30-15:30 ET
        return None

    session_date = et.date()
    tail = ltf_df.iloc[-60:]
    day = tail[[_to_et(t).date() == session_date for t in tail.index]]
    mins = [(t, _to_et(t).hour * 60 + _to_et(t).minute) for t in day.index]
    or_bars = day.loc[[t for t, m in mins if 570 <= m < 630]]   # 09:30..10:15 opens
    if len(or_bars) < 4:
        return None
    or_high, or_low = or_bars["high"].max(), or_bars["low"].min()
    height = or_high - or_low
    if height <= 0:
        return None

    spread = _SPREAD.get(instrument, 0.5)
    if height < _MIN_STOP_TO_SPREAD * spread:
        return None

    bar = ltf_df.iloc[-1]
    for direction, level, stop in (("long", or_high, or_low), ("short", or_low, or_high)):
        key = (session_date, direction)
        if key in _used:
            continue
        hit = bar["close"] > level if direction == "long" else bar["close"] < level
        if not hit:
            continue
        entry = bar["close"]
        if abs(entry - stop) < _MIN_STOP_TO_SPREAD * spread:
            _used.add(key)
            continue
        tp = entry + _TP_MULT * height * (1 if direction == "long" else -1)
        _used.add(key)
        return Signal(direction=direction, entry_price=float(entry),
                      stop_loss=float(stop), take_profits=[float(tp)] * 3,
                      instrument=instrument, timeframe="M15",
                      reason=f"IB-ORB close h={height:.2f}")
    return None
