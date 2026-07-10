"""
EUR weekend-gap continuation plugin (Campaign 6 Track C survivor, validated
2026-07-10, registration 4e370ab). Mechanism EXACTLY as killtested:
direction = sign of (Sunday-open first bar open - Friday last close);
enter in the Monday 03:00-03:30 ET window (London, liquid); SL = 1x ATR(20d);
NO take-profit -- the exit is TIMED (Monday 16:00 ET), handled by the bot's
timed-exit pass, not by the plugin. The broker-side TP is parked at 5x ATR
(structurally unreachable intraday) because the order path requires one.

Needs ~21 trading days of M30 history for the ATR (the slot passes a larger
ltf_count). Module-global one-entry-per-Monday guard; per-slot instances.
"""
from types import SimpleNamespace

import pandas as pd

from orb_plugin_core import _us_dst_offset

_used_mondays: set = set()


def _to_et(ts: pd.Timestamp) -> pd.Timestamp:
    return ts + pd.Timedelta(hours=_us_dst_offset(ts))


def generate_signal(instrument, htf_df, ltf_df, mode="scalp30"):
    df = ltf_df
    if df is None or len(df) < 400:
        return None
    now = df.index[-1] + pd.Timedelta(minutes=30)      # ~current wall clock
    et = _to_et(now)
    if et.weekday() != 0 or not (180 <= et.hour * 60 + et.minute < 210):
        return None                                     # Monday 03:00-03:30 ET only
    monday = et.date()
    if monday in _used_mondays:
        return None

    et_idx = [_to_et(t) for t in df.index]
    dates = pd.Series([e.date() for e in et_idx])
    days = dates.unique()
    if len(days) < 22:
        return None
    # ATR(20d) over completed ET days (exclude today)
    prior = dates != monday
    g = df[prior.values].groupby(dates[prior].values)
    rng = g.agg(h=("high", "max"), l=("low", "min"))
    rng = rng[g.size() >= 24]        # drop Sunday partial sessions from the ATR
    if len(rng) < 20:
        return None
    a = float((rng["h"] - rng["l"]).iloc[-20:].mean())
    if a <= 0:
        return None

    # weekend gap: last close before the weekend break vs first open after
    idx = df.index
    breaks = idx.to_series().diff() > pd.Timedelta(hours=24)
    if not breaks.any():
        return None
    pos = [i for i, v in enumerate(breaks.values) if v]   # last weekend break
    if not pos:
        return None
    i = pos[-1]
    gap = float(df["open"].iloc[i] - df["close"].iloc[i - 1])
    if gap == 0:
        return None

    direction = "long" if gap > 0 else "short"
    entry = float(df["close"].iloc[-1])
    sl = entry - a if direction == "long" else entry + a
    tp = entry + 5 * a if direction == "long" else entry - 5 * a
    _used_mondays.add(monday)
    return SimpleNamespace(direction=direction, entry_price=entry,
                           stop_loss=sl, take_profits=[tp, tp, tp])
