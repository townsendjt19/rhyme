"""
Campaign 6 (registration 4e370ab, committed before results): three FX-native
untested classes on EUR_USD / USD_JPY / GBP_USD at verified FTMO costs.

Track A: FOMC announcement drift  (spread-spike check -> impulse-sign hold to next day)
Track B: London->NY session-flow continuation (03:00->09:30 ET sign, held to 16:00)
Track C: weekend-gap continuation (Sunday-open gap sign, Monday London->NY close)

ET clock: the ORB core's hand-verified US statutory DST rule.
Run:  venv/Scripts/python.exe campaign6_killtest.py
"""
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import data
import orb_plugin_core as orb

HERE = Path(__file__).parent
PAIRS = {"EUR_USD": 0.7, "USD_JPY": 0.9, "GBP_USD": 0.8}
RISK_USD = 80.0
START = datetime(2021, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 7, 1, tzinfo=timezone.utc)
Q23 = (pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC"))

FOMC = [  # scheduled decision days (2026 from the Fed's published schedule)
 "2021-01-27","2021-03-17","2021-04-28","2021-06-16","2021-07-28","2021-09-22","2021-11-03","2021-12-15",
 "2022-01-26","2022-03-16","2022-05-04","2022-06-15","2022-07-27","2022-09-21","2022-11-02","2022-12-14",
 "2023-02-01","2023-03-22","2023-05-03","2023-06-14","2023-07-26","2023-09-20","2023-11-01","2023-12-13",
 "2024-01-31","2024-03-20","2024-05-01","2024-06-12","2024-07-31","2024-09-18","2024-11-07","2024-12-18",
 "2025-01-29","2025-03-19","2025-05-07","2025-06-18","2025-07-30","2025-09-17","2025-10-29","2025-12-10",
 "2026-01-28","2026-03-18","2026-04-29","2026-06-17"]


def pip(pair):
    return 0.01 if pair.endswith("JPY") else 0.0001


def et_frame(df):
    idx = pd.DatetimeIndex(df.index).tz_convert("UTC")
    naive = idx.tz_localize(None)
    off = pd.Series(naive).map(lambda t: orb._us_dst_offset(t)).values
    et = naive + pd.to_timedelta(off, unit="h")
    return df.assign(et_date=et.date, et_min=et.hour * 60 + et.minute, et_wd=et.weekday)


def atr20(df):
    rng = (df["high"].groupby(df["et_date"]).max() - df["low"].groupby(df["et_date"]).min())
    return rng.rolling(20).mean().shift(1)   # known before the day trades


def leg(bars, dirn, a, cost_px, meta):
    entry = bars["open"].iloc[0]
    sl = entry - dirn * a
    exit_px, reason, exit_t = None, "time", bars.index[-1]
    for t, b in bars.iterrows():
        if (dirn == 1 and b["low"] <= sl) or (dirn == -1 and b["high"] >= sl):
            exit_px, reason, exit_t = sl, "sl", t
            break
    if exit_px is None:
        exit_px = bars["close"].iloc[-1]
    r = (dirn * (exit_px - entry) - cost_px) / a
    return {**meta, "direction": "long" if dirn == 1 else "short", "entry": entry,
            "sl": sl, "pnl": RISK_USD * r, "exit_reason": reason,
            "time": bars.index[0], "exit_time": exit_t}


def adjudicate(df, label):
    for wlabel, g in [("2023", df[(df["time"] >= Q23[0]) & (df["time"] < Q23[1])]), ("full", df)]:
        n, net = len(g), g["pnl"].sum() if len(g) else 0.0
        exp = net / n if n else 0.0
        kill = exp <= 0 or n < 20
        print(f"  {label:12s} {wlabel:5s} n={n:4d} net={net:+9.2f} exp={exp:+7.2f}/tr "
              f"WR={100 * (g['pnl'] > 0).mean() if n else float('nan'):.1f}% -> {'KILL' if kill else 'clear'}")
    if len(df):
        yearly = df.set_index("time")["pnl"].resample("YE").sum()
        print("    yearly: " + " ".join(f"{t.year}:{v:+.0f}" for t, v in yearly.items()) +
              f"  ex-best-year: {df['pnl'].sum() - yearly.max():+.2f}")


def main() -> None:
    m30, m5 = {}, {}
    for p in PAIRS:
        m30[p] = et_frame(data.fetch_candles(p, "M30", from_time=START, to_time=END))
        print(f"fetched {p} M30: {len(m30[p])}")

    # ---------- Track A: FOMC ----------
    print("\n=== TRACK A: FOMC drift ===")
    fomc = set(pd.to_datetime(FOMC).date)
    for p in PAIRS:
        m5[p] = et_frame(data.fetch_candles(p, "M5", from_time=START, to_time=END))
    # spread-spike check at 15:00 ET on FOMC days (MBA, trailing sample)
    from oandapyV20.endpoints.instruments import InstrumentsCandles
    from data import get_client, _dt_to_rfc3339
    recent_fomc = [d for d in sorted(fomc) if d >= datetime(2024, 1, 1).date()]
    for p in PAIRS:
        rows = []
        for d in recent_fomc:
            day_utc = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            req = InstrumentsCandles(instrument=p, params={
                "granularity": "M5", "price": "MBA",
                "from": _dt_to_rfc3339(day_utc.replace(hour=17)),
                "to": _dt_to_rfc3339(day_utc.replace(hour=21, minute=30))})
            get_client().request(req)
            rows += [(pd.Timestamp(c["time"]), float(c["ask"]["c"]) - float(c["bid"]["c"]))
                     for c in req.response.get("candles", []) if c.get("complete")]
        s = et_frame(pd.DataFrame(rows, columns=["t", "spr"]).set_index("t"))
        at15 = s[(s["et_min"] >= 895) & (s["et_min"] < 905)]
        at14 = s[(s["et_min"] >= 840) & (s["et_min"] < 850)]
        print(f"  {p} FOMC-day spread: 14:00 ET {at14['spr'].median()/pip(p):.2f}p  "
              f"15:00 ET {at15['spr'].median()/pip(p):.2f}p  (session norm ~{PAIRS[p]-0.5:.1f}p)")
    # measured FOMC-day 15:00 ET spreads (this run's own measurement) replace
    # the session-norm costs for Track A -- the honest event-day charge
    FOMC_COST = {"EUR_USD": 1.6 + 0.5, "USD_JPY": 1.7 + 0.5, "GBP_USD": 1.9 + 0.5}
    trades = []
    for p, cost in FOMC_COST.items():
        df, a = m5[p], atr20(m30[p])
        for d in sorted(fomc):
            day = df[df["et_date"] == d]
            imp = day[(day["et_min"] >= 840) & (day["et_min"] < 895)]
            if len(imp) < 5:
                continue
            move = imp["close"].iloc[-1] - imp["open"].iloc[0]
            if move == 0 or a.get(d) is None or a.get(d) != a.get(d):
                continue
            dirn = 1 if move > 0 else -1
            start_t = day[day["et_min"] >= 900].index
            if not len(start_t):
                continue
            nxt = df[df.index >= start_t[0]]
            exit_mask = (pd.Index(nxt["et_date"]) > d) & (nxt["et_min"] >= 660)
            end_i = np.argmax(exit_mask.values) if exit_mask.any() else len(nxt) - 1
            bars = nxt.iloc[:end_i + 1]
            trades.append(leg(bars, dirn, a[d], cost * pip(p),
                              {"instrument": p, "strategy": "fomc_drift"}))
    fomc_tr = pd.DataFrame(trades)
    adjudicate(fomc_tr, "FOMC pooled")
    fomc_tr.to_csv(HERE / "c6_fomc_drift.csv", index=False)

    # ---------- Track B: London->NY handoff ----------
    print("\n=== TRACK B: London->NY continuation ===")
    for p, cost in PAIRS.items():
        df, a = m30[p], atr20(m30[p])
        trades = []
        for d, day in df.groupby("et_date"):
            lon = day[(day["et_min"] >= 180) & (day["et_min"] < 570)]
            ny = day[(day["et_min"] >= 570) & (day["et_min"] < 960)]
            if len(lon) < 8 or len(ny) < 8:
                continue
            move = lon["close"].iloc[-1] - lon["open"].iloc[0]
            av = a.get(d)
            if move == 0 or av is None or av != av:
                continue
            trades.append(leg(ny, 1 if move > 0 else -1, av, cost * pip(p),
                              {"instrument": p, "strategy": "handoff"}))
        adjudicate(pd.DataFrame(trades), p)
        pd.DataFrame(trades).to_csv(HERE / f"c6_handoff_{p}.csv", index=False)

    # ---------- Track C: weekend-gap continuation ----------
    print("\n=== TRACK C: weekend-gap continuation ===")
    for p, cost in PAIRS.items():
        df, a = m30[p], atr20(m30[p])
        days = sorted(df["et_date"].unique())
        trades = []
        for i in range(1, len(days)):
            d = days[i]
            if pd.Timestamp(d).weekday() != 0:      # Mondays only
                continue
            prev_day = df[df["et_date"] == days[i - 1]]
            mon = df[df["et_date"] == d]
            gap = mon["open"].iloc[0] - prev_day["close"].iloc[-1]
            av = a.get(d)
            if gap == 0 or av is None or av != av:
                continue
            window = mon[(mon["et_min"] >= 180) & (mon["et_min"] < 960)]
            if len(window) < 8:
                continue
            trades.append(leg(window, 1 if gap > 0 else -1, av, cost * pip(p),
                              {"instrument": p, "strategy": "wkndgap"}))
        adjudicate(pd.DataFrame(trades), p)
        pd.DataFrame(trades).to_csv(HERE / f"c6_wkndgap_{p}.csv", index=False)


if __name__ == "__main__":
    main()
