"""
One-position-cap replay (methods correction, 2026-07-10). The backtest
harness simulates EVERY signal as an independent trade (no open-position
tracking -- acknowledged as an approximation in the prop-rules study, its
P&L impact unquantified until now). Live slots cap at one position. This
tool replays a record chronologically keeping only trades whose entry is at
or after the previous kept trade's exit -- the greedy LOWER BOUND on what a
one-position slot realizes (live re-signaling after flat recovers some
skipped trades, so truth lies between record and replay).

Usage:  venv/Scripts/python.exe onecap_replay.py <record.csv> [more.csv ...]
Writes <record>_1cap.csv beside each input and prints both bounds.
"""
import sys

import pandas as pd


def onecap(path: str) -> None:
    df = pd.read_csv(path, parse_dates=["time", "exit_time"]).sort_values("time")
    t = pd.DatetimeIndex(df["time"])
    x = pd.DatetimeIndex(df["exit_time"])
    if t.tz is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    if x.tz is not None:
        x = x.tz_convert("UTC").tz_localize(None)
    df = df.assign(_t=t, _x=x)
    kept, last_exit = [], pd.Timestamp.min
    for _, r in df.iterrows():
        if r["_t"] >= last_exit:
            kept.append(r)
            last_exit = r["_x"]
    k = pd.DataFrame(kept).drop(columns=["_t", "_x"])
    out = path.replace(".csv", "_1cap.csv")
    k.to_csv(out, index=False)
    print(f"{path}: record n={len(df)} net={df['pnl'].sum():+.2f}  |  "
          f"1cap n={len(k)} net={k['pnl'].sum():+.2f}  -> {out}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        onecap(p)
