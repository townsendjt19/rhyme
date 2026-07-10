"""
London-open ORB plugin (Campaign 3 Track C, registration c1dd8c2). The US
ORB core's close-variant mechanics transplanted UNMODIFIED to the London
session clock — same OR construction, box-9 floor, 2x-height TP, single-use
(session, direction) identities, fire-and-forget:

  OR            = 08:00-08:30 London (two M15 bars)
  signal window = 08:30-14:00 London (OR end -> OR start + 6h, mirroring the
                  US construction: 09:30 OR start -> 15:30 window end)
  UK DST rule   = last Sunday of March 01:00 UTC -> last Sunday of October
                  01:00 UTC (statutory), implemented like the hand-verified
                  US rule. Boundary spot-check in the registration entry.

Kept as a deliberate copy of orb_plugin_core's logic (not a parameterized
core) so the deployed US plugins cannot drift from this experiment; the
shared constants (_SPREAD, _MIN_STOP_TO_SPREAD, _TP_MULT) are imported.
"""
import pandas as pd

from orb_plugin_core import _SPREAD, _MIN_STOP_TO_SPREAD, _TP_MULT
from strategy import Signal

_used: set = set()


def _uk_dst_offset(ts: pd.Timestamp) -> int:
    """UTC->London offset in hours: BST +1 between last Sunday of March
    01:00 UTC and last Sunday of October 01:00 UTC, else GMT +0."""
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    y = ts.year
    def last_sunday(month):
        d = pd.Timestamp(y, month, 31)
        while d.month != month:
            d -= pd.Timedelta(days=1)
        return d - pd.Timedelta(days=(d.dayofweek + 1) % 7)
    start = last_sunday(3) + pd.Timedelta(hours=1)
    end = last_sunday(10) + pd.Timedelta(hours=1)
    return 1 if start <= ts < end else 0


def _to_london(ts: pd.Timestamp) -> pd.Timestamp:
    return ts + pd.Timedelta(hours=_uk_dst_offset(ts))


def generate_signal(instrument, htf_df, ltf_df, mode) -> Signal | None:
    if len(ltf_df) < 3:
        return None
    now = ltf_df.index[-1]
    lon = _to_london(now)
    lon_minutes = lon.hour * 60 + lon.minute
    if not (510 <= lon_minutes < 840):          # 08:30-14:00 London
        return None

    session_date = lon.date()
    tail = ltf_df.iloc[-60:]
    day = tail[[_to_london(t).date() == session_date for t in tail.index]]
    mins = [(t, _to_london(t).hour * 60 + _to_london(t).minute) for t in day.index]
    or_bars = day.loc[[t for t, m in mins if 480 <= m < 510]]   # 08:00, 08:15
    if len(or_bars) < 2:
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
                      reason=f"ORB-london close h={height:.2f}")
    return None
