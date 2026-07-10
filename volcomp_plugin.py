"""
Volatility-compression breakout plugin (Campaign 2 Track B survivor,
validated 2026-07-09, XAUUSD). Mechanism EXACTLY as killtested
(volcomp_killtest.py): the last COMPLETED daily bar is an inside day OR the
narrowest range of the last 5 days -> the first M30 close of the NEXT day
beyond that compression bar's high/low enters; SL at its opposite extreme;
TP 2.5R; fire-and-forget.

Daily bars are built by resampling the M30 frame to UTC+2 calendar days --
EXACTLY the validated record's Phase A convention. (Code-review fix
2026-07-10: the bot's fetch seam now delivers UTC frames; the +2h shift
below reproduces the record's day boundaries precisely, removing the old
accepted 1h summer drift.)

Interface: generate_signal(instrument, htf_df, ltf_df, mode) -- htf ignored.
Module-global re-entry state (one signal per compression day), same property
as the fleet plugins; per-slot module instances isolate it.
"""
from types import SimpleNamespace

RR = 2.5
_used_days: set = set()   # compression-day identities already signalled


def generate_signal(instrument, htf_df, ltf_df, mode="scalp30"):
    df = ltf_df
    if df is None or len(df) < 60:
        return None
    import pandas as pd
    day_key = (df.index + pd.Timedelta(hours=2)).normalize()   # Phase A UTC+2 days
    days = df.groupby(day_key).agg(
        high=("high", "max"), low=("low", "min"))
    if len(days) < 7:
        return None
    today = days.index[-1]
    d1 = days.iloc[:-1]                    # completed days only
    if len(d1) < 6:
        return None
    rng = d1["high"] - d1["low"]
    comp = d1.iloc[-1]
    inside = comp["high"] < d1["high"].iloc[-2] and comp["low"] > d1["low"].iloc[-2]
    nr5 = rng.iloc[-1] == rng.iloc[-5:].min()
    if not (inside or nr5):
        return None
    comp_day = d1.index[-1]
    if comp_day in _used_days:
        return None

    bars = df[day_key == today]
    if bars.empty:
        return None
    # the LAST completed bar must be the FIRST of the day to close beyond
    # the compression range (killtest semantics: enter on the breaking close,
    # never mid-move on a later scan)
    prior = bars.iloc[:-1]
    if len(prior) and ((prior["close"] > comp["high"]) | (prior["close"] < comp["low"])).any():
        _used_days.add(comp_day)           # missed it; day is spent
        return None
    last = bars.iloc[-1]
    if last["close"] > comp["high"]:
        direction, sl = "long", comp["low"]
    elif last["close"] < comp["low"]:
        direction, sl = "short", comp["high"]
    else:
        return None

    entry = float(last["close"])
    risk = abs(entry - float(sl))
    if risk <= 0:
        return None
    tp = entry + (RR * risk if direction == "long" else -RR * risk)
    _used_days.add(comp_day)
    return SimpleNamespace(direction=direction, entry_price=entry,
                           stop_loss=float(sl), take_profits=[tp, tp, tp])
