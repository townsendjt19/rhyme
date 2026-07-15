"""
BoE decision-drift plugin (validated-weak 2026-07-15, registration f1ecf62;
shadow-slot deployment registration cf60a25). Mechanism EXACTLY as
adjudicated in cbdrift_BOE.csv: on BoE decision days, at the first M15 wake
>= T+60m (T = 12:00 Europe/London), direction = sign of the M5 impulse
close(T+55) - open(T); SL = 1x ATR(20 completed ET days, Sunday-free);
NO real take-profit -- the exit is TIMED (entry+20h, the bot's
entry_plus_20h rule); broker-side TP parked at 5x ATR (order path).

Needs ~22 trading days of M5 history (the slot passes ltf_count ~6600).
Module-global one-signal-per-event guard; per-slot instances.
"""
from types import SimpleNamespace

import pandas as pd

from orb_plugin_core import _us_dst_offset

# BoE MPC decision dates, 2026 H2 (published schedule; cross-confirmed via
# the 2026-07-13 centralbank.watch fetch). Extend when the 2027 calendar is
# adopted -- an empty upcoming list makes the plugin silently inert.
BOE_DATES = {"2026-08-06", "2026-09-17", "2026-11-05", "2026-12-17"}

WARMUP_HTF_CANDLES = 12   # session-anchored; no HTF requirement of its own

_used_events: set = set()


def _uk_offset_hours(ts_utc: pd.Timestamp) -> int:
    """UK statutory clock: BST (+1) between last Sunday of March 01:00 UTC
    and last Sunday of October 01:00 UTC, else GMT (+0)."""
    y = ts_utc.year
    def last_sunday(month):
        d = pd.Timestamp(y, month, 31)
        while d.month != month:
            d -= pd.Timedelta(days=1)
        return d - pd.Timedelta(days=(d.dayofweek + 1) % 7)
    start = last_sunday(3) + pd.Timedelta(hours=1)
    end = last_sunday(10) + pd.Timedelta(hours=1)
    return 1 if start <= ts_utc < end else 0


def _statement_utc(date_str: str) -> pd.Timestamp:
    noon_utc_guess = pd.Timestamp(f"{date_str} 12:00")
    return noon_utc_guess - pd.Timedelta(hours=_uk_offset_hours(noon_utc_guess))


def _to_et(ts: pd.Timestamp) -> pd.Timestamp:
    return ts + pd.Timedelta(hours=_us_dst_offset(ts))


def generate_signal(instrument, htf_df, ltf_df, mode="scalp30"):
    df = ltf_df
    if df is None or len(df) < 3000:
        return None
    now = df.index[-1] + pd.Timedelta(minutes=5)       # ~current wall clock
    date_str = str(now.date())
    if date_str not in BOE_DATES or date_str in _used_events:
        return None
    t = _statement_utc(date_str)
    # first M15 wake at/after T+60m: window [T+60m, T+75m)
    if not (t + pd.Timedelta(minutes=60) <= now < t + pd.Timedelta(minutes=75)):
        return None

    # impulse EXACTLY as killtested: M5 bars in [T, T+55)
    imp = df[(df.index >= t) & (df.index < t + pd.Timedelta(minutes=55))]
    if len(imp) < 5:
        return None
    move = float(imp["close"].iloc[-1] - imp["open"].iloc[0])
    if move == 0:
        return None

    # ATR(20d) over completed ET days (exclude today; drop partial sessions)
    et_dates = pd.Series([_to_et(x).date() for x in df.index])
    prior = et_dates != _to_et(now).date()
    g = df[prior.values].groupby(et_dates[prior].values)
    rng = g.agg(h=("high", "max"), l=("low", "min"))
    rng = rng[g.size() >= 240]       # Sunday partials out (M5: ~276 bars/day)
    if len(rng) < 20:
        return None
    a = float((rng["h"] - rng["l"]).iloc[-20:].mean())
    if a <= 0:
        return None

    direction = "long" if move > 0 else "short"
    entry = float(df["close"].iloc[-1])
    sl = entry - a if direction == "long" else entry + a
    tp = entry + 5 * a if direction == "long" else entry - 5 * a
    _used_events.add(date_str)
    return SimpleNamespace(direction=direction, entry_price=entry,
                           stop_loss=sl, take_profits=[tp, tp, tp])
