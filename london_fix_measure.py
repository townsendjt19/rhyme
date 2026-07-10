"""
Campaign 4 Track D: London 4pm fix MEASUREMENT (registration 1e1d1b1;
no strategy code unless a signed, liquid-window flow effect is found).

Windows (London clock via orb_london_plugin._uk_dst_offset, 8/8 verified):
pre-fix 15:30-16:00, post-fix 16:00-16:30, controls 14:00-14:30 + 14:30-15:00.
Pre-registered breakdown: month-end (last trading day of month) vs ordinary.
Reported: mean |return| (activity), mean signed return (flow), and post-fix
reversal beta vs the pre-fix move. Pairs: EUR_USD, GBP_USD, USD_JPY.
Data: OANDA M5 mids 2022-07 -> 2026-07.

Run:  venv/Scripts/python.exe london_fix_measure.py
"""
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import data
from orb_london_plugin import _uk_dst_offset

PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY"]
START = datetime(2022, 7, 1, tzinfo=timezone.utc)
END = datetime(2026, 7, 1, tzinfo=timezone.utc)
WINDOWS = {"pre_fix": (930, 960), "post_fix": (960, 990),
           "ctl_A": (840, 870), "ctl_B": (870, 900)}


def pip(pair):
    return 0.01 if pair.endswith("JPY") else 0.0001


def window_returns(df, pair):
    idx = pd.DatetimeIndex(df.index).tz_convert("UTC")
    lon = idx + pd.Series(idx, index=df.index).map(
        lambda t: pd.Timedelta(hours=_uk_dst_offset(pd.Timestamp(t).tz_localize(None)))).values
    lon = pd.DatetimeIndex(lon)
    df = df.assign(d=lon.date, m=lon.hour * 60 + lon.minute, wd=lon.weekday)
    df = df[df["wd"] <= 4]
    out = {}
    for name, (lo, hi) in WINDOWS.items():
        g = df[(df["m"] >= lo) & (df["m"] < hi)].groupby("d")
        r = (g["close"].last() - g["open"].first()) / pip(pair)
        out[name] = r
    return pd.DataFrame(out).dropna()


def month_end_mask(dates):
    di = pd.DatetimeIndex(pd.to_datetime(list(dates)))
    s = pd.Series(di, index=di).groupby([di.year, di.month]).max()
    return pd.Index(dates).isin(set(s.dt.date if hasattr(s, "dt") else [x.date() for x in s]))


def report(label, w):
    for name in WINDOWS:
        s = w[name]
        t = s.mean() / (s.std() / np.sqrt(len(s))) if len(s) > 2 else float("nan")
        print(f"    {label:9s} {name:8s} n={len(s):4d}  |ret| {s.abs().mean():5.2f}p  "
              f"signed {s.mean():+5.2f}p (t={t:+.1f})")
    if len(w) > 5:
        beta = np.polyfit(w["pre_fix"], w["post_fix"], 1)[0]
        print(f"    {label:9s} post-fix beta vs pre-fix move: {beta:+.3f} "
              f"(negative = reversal)")


def main() -> None:
    print("=== TRACK D: London 4pm fix windows (registration 1e1d1b1) ===")
    for pair in PAIRS:
        print(f"\n{pair}:")
        df = data.fetch_candles(pair, "M5", from_time=START, to_time=END)
        w = window_returns(df, pair)
        me = month_end_mask(w.index)
        report("ALL", w)
        report("MONTH-END", w[me])
        report("ordinary", w[~me])


if __name__ == "__main__":
    main()
