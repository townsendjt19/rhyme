"""
Overshoot/reversion tradeability check — second falsification gate for the
NY-close/Sydney-open liquidity trough idea (pre-scoping triage, 2026-07-03).

Question: does the raw dislocation exceed raw execution cost? Strictly NOT a
strategy: no entry/exit rules, no sizing, no P&L sim.

Definitions (fixed before the run, reported in full — nothing tuned):
  Baseline B    : last mid close before 17:00 ET (the 16:55 bar) per ET day,
                  Mon-Thu only (Fri window doesn't exist; Sun = weekly open).
  Overshoot     : max excursion of window (17:00-19:00 ET) highs/lows from B
                  >= N x pair's FULL-SAMPLE median M5 bar range; N in {2,3,4}.
  Reversion     : pips recovered from the window extreme back toward B by the
                  20:55 ET close. Negative (= continuation) included.
  Cost          : 2 x that day's mean REAL bid/ask spread across window bars
                  (OANDA price="MBA" candles — actual quoted spread, not a
                  bar-range proxy).

Run: D:/rhyme/venv/Scripts/python.exe D:/rhyme/trough_overshoot_check.py
Output: trough_overshoot_check.png + console tables.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from data import get_client, _GRAN_SECONDS, _MAX_COUNT, _dt_to_rfc3339
from oandapyV20.endpoints.instruments import InstrumentsCandles

PAIRS = ["AUD_USD", "NZD_USD", "USD_JPY"]
START = datetime(2025, 7, 1, tzinfo=timezone.utc)
END = datetime(2026, 7, 1, tzinfo=timezone.utc)
ET = ZoneInfo("America/New_York")
N_GRID = [2, 3, 4]
MIN_WINDOW_BARS = 12  # skip holiday-thinned days (< half the 24 M5 bars)


def pip_size(pair: str) -> float:
    return 0.01 if pair.endswith("JPY") else 0.0001


def fetch_mba(instrument: str) -> pd.DataFrame:
    """Chunked M5 fetch with mid + bid + ask prices (same client as data.py)."""
    import time as _t
    gran_secs = _GRAN_SECONDS["M5"]
    chunk = timedelta(seconds=gran_secs * _MAX_COUNT)
    rows = []
    cursor = START
    while cursor < END:
        chunk_end = min(cursor + chunk, END)
        params = {"granularity": "M5", "price": "MBA",
                  "from": _dt_to_rfc3339(cursor), "to": _dt_to_rfc3339(chunk_end)}
        req = InstrumentsCandles(instrument=instrument, params=params)
        get_client().request(req)
        for c in req.response.get("candles", []):
            if not c.get("complete", True):
                continue
            mid, bid, ask = c["mid"], c["bid"], c["ask"]
            rows.append({
                "time": pd.Timestamp(c["time"]),
                "high": float(mid["h"]), "low": float(mid["l"]),
                "close": float(mid["c"]),
                "spread": float(ask["c"]) - float(bid["c"]),
            })
        cursor = chunk_end
        _t.sleep(0.1)
    df = pd.DataFrame(rows).set_index("time").sort_index()
    return df[~df.index.duplicated(keep="last")]


def day_events(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    """One row per eligible ET day: excursion, reversion, day's window cost."""
    ps = pip_size(pair)
    et = df.index.tz_convert(ET)
    df = df.copy()
    df["et_date"] = et.date
    df["mod"] = et.hour * 60 + et.minute
    df["wd"] = et.weekday
    median_range = float(((df["high"] - df["low"]) / ps).median())

    out = []
    for day, g in df[df["wd"] <= 3].groupby("et_date"):  # Mon-Thu ET days
        pre = g[(g["mod"] >= 15 * 60) & (g["mod"] < 17 * 60)]
        win = g[(g["mod"] >= 17 * 60) & (g["mod"] < 19 * 60)]
        post = g[(g["mod"] >= 19 * 60) & (g["mod"] < 21 * 60)]
        if pre.empty or post.empty or len(win) < MIN_WINDOW_BARS:
            continue
        B = pre["close"].iloc[-1]                      # 16:55 ET close
        up = (win["high"].max() - B) / ps
        dn = (B - win["low"].min()) / ps
        if up >= dn:                                    # dominant side
            exc, extreme, sign = up, win["high"].max(), +1
        else:
            exc, extreme, sign = dn, win["low"].min(), -1
        p21 = post["close"].iloc[-1]                    # 20:55 ET close
        reversion = sign * (extreme - p21) / ps         # + = came back toward B
        cost = 2 * win["spread"].mean() / ps            # round-trip, real spread
        out.append({"day": day, "excursion": exc, "reversion": reversion,
                    "cost": cost, "spread_pips": win["spread"].mean() / ps})
    ev = pd.DataFrame(out)
    ev.attrs["median_range"] = median_range
    return ev


def main():
    events, spread_curves = {}, {}
    for pair in PAIRS:
        print(f"Fetching {pair} M5 MBA {START.date()} -> {END.date()} ...")
        df = fetch_mba(pair)
        print(f"  {len(df)} bars")
        events[pair] = day_events(df, pair)
        # spread by minute-of-day (ET, Sundays excluded) for the plot
        et = df.index.tz_convert(ET)
        keep = et.weekday != 6
        spread_curves[pair] = (df["spread"][keep] / pip_size(pair)).groupby(
            (et.hour * 60 + et.minute)[keep]).mean()

    print("\n=== Per-pair summary (12mo, Mon-Thu ET days) ===")
    header = (f"{'pair':<9}{'N':>3}{'thresh(p)':>10}{'events':>8}{'ev/yr':>7}"
              f"{'mean exc':>9}{'mean rev':>9}{'med rev':>8}{'mean cost':>10}"
              f"{'rev/cost':>9}{'%rev>cost':>10}")
    results = {}
    for pair in PAIRS:
        ev = events[pair]
        mr = ev.attrs["median_range"]
        print(f"\n{pair}: eligible days={len(ev)}, median M5 range="
              f"{mr:.2f} pips, mean window spread={ev['spread_pips'].mean():.2f} pips")
        print(header)
        for N in N_GRID:
            thr = N * mr
            e = ev[ev["excursion"] >= thr]
            if len(e) == 0:
                print(f"{pair:<9}{N:>3}{thr:>10.1f}{0:>8}{0:>7.0f}")
                continue
            row = dict(
                n=len(e), per_yr=len(e), mean_exc=e["excursion"].mean(),
                mean_rev=e["reversion"].mean(), med_rev=e["reversion"].median(),
                mean_cost=e["cost"].mean(),
                ratio=e["reversion"].mean() / e["cost"].mean(),
                pct_clear=100 * (e["reversion"] > e["cost"]).mean(),
            )
            results[(pair, N)] = (e, row)
            print(f"{pair:<9}{N:>3}{thr:>10.1f}{row['n']:>8}{row['n']:>7}"
                  f"{row['mean_exc']:>9.1f}{row['mean_rev']:>9.1f}"
                  f"{row['med_rev']:>8.1f}{row['mean_cost']:>10.1f}"
                  f"{row['ratio']:>9.2f}{row['pct_clear']:>9.0f}%")

    # Plot: real spread by time of day + reversion-vs-cost scatter at N=3
    fig, axes = plt.subplots(2, 1, figsize=(13, 9))
    for pair in PAIRS:
        s = spread_curves[pair]
        axes[0].plot(s.index / 60, s, label=pair, lw=0.9)
    axes[0].axvspan(17, 19, color="red", alpha=0.12)
    axes[0].set_title("REAL mean bid/ask spread by time of day (pips, ET) — "
                      "OANDA MBA candles, ET Sundays excluded")
    axes[0].set_xlim(0, 24); axes[0].set_xticks(range(0, 25, 2))
    axes[0].legend(fontsize=8)

    for i, pair in enumerate(PAIRS):
        if (pair, 3) not in results:
            continue
        e, _ = results[(pair, 3)]
        axes[1].scatter(np.full(len(e), i) + np.random.uniform(-0.15, 0.15, len(e)),
                        e["reversion"] - e["cost"], s=12, alpha=0.6, label=pair)
    axes[1].axhline(0, color="red", lw=1)
    axes[1].set_xticks(range(len(PAIRS))); axes[1].set_xticklabels(PAIRS)
    axes[1].set_title("Per-event reversion MINUS round-trip cost (pips), N=3 — "
                      "above red line = room after real spread")
    fig.tight_layout()
    fig.savefig("trough_overshoot_check.png", dpi=110)
    print("\nSaved trough_overshoot_check.png")


if __name__ == "__main__":
    # np.random only jitters scatter x-positions for readability; seed for
    # reproducible output image
    np.random.seed(0)
    main()
