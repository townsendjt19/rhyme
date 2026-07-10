"""
One-position-cap replay (methods correction, 2026-07-10). The backtest
harness simulates EVERY signal as an independent trade (no open-position
tracking -- acknowledged as an approximation in the prop-rules study, its
P&L impact unquantified until now). Live slots cap at one position. This
tool replays a record chronologically keeping only trades whose entry is at
or after the previous kept trade's exit -- the greedy LOWER BOUND on what a
one-position slot realizes (live re-signaling after flat recovers some
skipped trades, so truth lies between record and replay).

Extended 2026-07-10 (operator-directed): a third QUEUED-RECOVERY mode — the
mechanistic middle. When the slot is occupied a signal queues; when the slot
frees, the earliest queued trade whose recorded exit is still in the future
(the zone/trade was still alive) is taken at its recorded outcome; dead
queued trades drop. This models the live bot's re-signal-after-flat
behavior. Implied recovery rate r = (recovered) / (skipped), and expected
P&L = lower + r_eff x (upper - lower).

Usage:  venv/Scripts/python.exe onecap_replay.py <record.csv> [more.csv ...]
Writes <record>_1cap.csv and <record>_queued.csv beside each input.
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


def queued(path: str) -> None:
    df = pd.read_csv(path, parse_dates=["time", "exit_time"]).sort_values("time")
    t = pd.DatetimeIndex(df["time"])
    x = pd.DatetimeIndex(df["exit_time"])
    if t.tz is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    if x.tz is not None:
        x = x.tz_convert("UTC").tz_localize(None)
    rows = df.assign(_t=t, _x=x).to_dict("records")

    kept, queue, busy_until = [], [], pd.Timestamp.min
    i = 0
    while i < len(rows) or queue:
        nxt = rows[i] if i < len(rows) else None
        if nxt is not None and nxt["_t"] < busy_until:
            queue.append(nxt)                       # slot occupied -> queue
            i += 1
            continue
        # slot frees at busy_until: recover the earliest queued trade still alive
        alive = [q for q in queue if q["_x"] > busy_until]
        if alive and (nxt is None or busy_until <= nxt["_t"]):
            take = alive[0]
            take = dict(take, recovered=True)
            kept.append(take)
            queue = [q for q in queue if q["_x"] > take["_x"]]  # drop dead + taken
            busy_until = take["_x"]
            continue
        queue = []                                  # nothing alive; clear
        if nxt is None:
            break
        kept.append(dict(nxt, recovered=False))
        busy_until = nxt["_x"]
        i += 1

    k = pd.DataFrame(kept)
    out = path.replace(".csv", "_queued.csv")
    k.drop(columns=["_t", "_x"]).to_csv(out, index=False)
    full_net, k_net = df["pnl"].sum(), k["pnl"].sum()
    n_rec = int(k["recovered"].sum())
    skipped = len(df) - (len(k) - n_rec)
    r = n_rec / skipped if skipped else 0.0
    print(f"{path}: queued-recovery n={len(k)} (recovered {n_rec}) net={k_net:+.2f}  "
          f"implied r={r:.2f}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        onecap(p)
        queued(p)
