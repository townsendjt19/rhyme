"""
Track D (Campaign 2, registration 9d510ee): liquidity-trough REOPEN attempt
against the registered bar (failure_db `liquidity_trough_nyclose_sydneyopen`):
"cross-pair tradeable residual after real spread cost, with reversion measured
from an EXECUTABLE entry (not the window extreme), clearing cost on AUD_USD
or NZD_USD."

Executable redesign (structural; original 2026-07-03 conventions kept where
not superseded): baseline B = 16:55 ET close; signal = dominant window
(17:00-19:00 ET) excursion >= N x full-sample median M5 range, read at window
END (no mid-window peeking); ENTRY = first M5 bar OPEN at/after 19:00 ET,
fading toward B -- after the rollover spread spike has normalized, which is
the entire redesign: trade less of the reversion at a fraction of the cost;
EXIT = 20:55 ET close (original convention). Cost = real quoted half-spread
at the entry bar + half-spread at the exit bar (MBA candles). N grid {2,3,4}
reported in full, N=3 the registered center. 24 months, Mon-Thu ET days.

Run: venv/Scripts/python.exe trough_reopen_check.py
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from data import get_client, _GRAN_SECONDS, _MAX_COUNT, _dt_to_rfc3339
from oandapyV20.endpoints.instruments import InstrumentsCandles

PAIRS = ["AUD_USD", "NZD_USD", "USD_JPY"]     # bar adjudicates on AUD/NZD; JPY reference
START = datetime(2024, 7, 1, tzinfo=timezone.utc)
END = datetime(2026, 7, 1, tzinfo=timezone.utc)
ET = ZoneInfo("America/New_York")
N_GRID = [2, 3, 4]
MIN_WINDOW_BARS = 12


def pip_size(pair: str) -> float:
    return 0.01 if pair.endswith("JPY") else 0.0001


def fetch_mba(instrument: str) -> pd.DataFrame:
    import time as _t
    chunk = timedelta(seconds=_GRAN_SECONDS["M5"] * _MAX_COUNT)
    rows, cursor = [], START
    while cursor < END:
        chunk_end = min(cursor + chunk, END)
        params = {"granularity": "M5", "price": "MBA",
                  "from": _dt_to_rfc3339(cursor), "to": _dt_to_rfc3339(chunk_end)}
        req = InstrumentsCandles(instrument=instrument, params=params)
        get_client().request(req)
        for c in req.response.get("candles", []):
            if not c.get("complete", True):
                continue
            mid = c["mid"]
            rows.append({"time": pd.Timestamp(c["time"]),
                         "open": float(mid["o"]), "high": float(mid["h"]),
                         "low": float(mid["l"]), "close": float(mid["c"]),
                         "spread": float(c["ask"]["c"]) - float(c["bid"]["c"])})
        cursor = chunk_end
        _t.sleep(0.1)
    df = pd.DataFrame(rows).set_index("time").sort_index()
    return df[~df.index.duplicated(keep="last")]


def day_trades(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    ps = pip_size(pair)
    et = df.index.tz_convert(ET)
    df = df.copy()
    df["et_date"] = et.date
    df["mod"] = et.hour * 60 + et.minute
    df["wd"] = et.weekday
    median_range = float(((df["high"] - df["low"]) / ps).median())

    out = []
    for day, g in df[df["wd"] <= 3].groupby("et_date"):
        pre = g[(g["mod"] >= 15 * 60) & (g["mod"] < 17 * 60)]
        win = g[(g["mod"] >= 17 * 60) & (g["mod"] < 19 * 60)]
        post = g[(g["mod"] >= 19 * 60) & (g["mod"] < 21 * 60)]
        if pre.empty or post.empty or len(win) < MIN_WINDOW_BARS:
            continue
        B = pre["close"].iloc[-1]
        up = (win["high"].max() - B) / ps
        dn = (B - win["low"].min()) / ps
        exc, sign = (up, +1) if up >= dn else (dn, -1)   # fade the dominant side
        entry_bar = post.iloc[0]                          # first bar at/after 19:00 ET
        exit_close, exit_spread = post["close"].iloc[-1], post["spread"].iloc[-1]
        captured = sign * (entry_bar["open"] - exit_close) / ps   # + = reverted toward B
        cost = (entry_bar["spread"] / 2 + exit_spread / 2) / ps
        out.append({"day": day, "excursion": exc, "captured": captured,
                    "cost": cost, "entry_spread": entry_bar["spread"] / ps})
    ev = pd.DataFrame(out)
    ev.attrs["median_range"] = median_range
    return ev


def main() -> None:
    print("=== TRACK D: liquidity-trough reopen, EXECUTABLE entry (registration 9d510ee) ===")
    for pair in PAIRS:
        print(f"\nFetching {pair} M5 MBA {START.date()} -> {END.date()} ...")
        ev = day_trades(fetch_mba(pair), pair)
        mr = ev.attrs["median_range"]
        print(f"{pair}: eligible days={len(ev)}, median M5 range={mr:.2f} pips, "
              f"mean 19:00 entry spread={ev['entry_spread'].mean():.2f} pips")
        print(f"{'N':>3}{'thresh(p)':>10}{'events':>8}{'mean capt':>10}"
              f"{'med capt':>9}{'mean cost':>10}{'net/ev':>8}{'%>cost':>8}")
        for N in N_GRID:
            e = ev[ev["excursion"] >= N * mr]
            if not len(e):
                print(f"{N:>3}{N * mr:>10.1f}{0:>8}")
                continue
            net = e["captured"].mean() - e["cost"].mean()
            print(f"{N:>3}{N * mr:>10.1f}{len(e):>8}{e['captured'].mean():>10.2f}"
                  f"{e['captured'].median():>9.2f}{e['cost'].mean():>10.2f}"
                  f"{net:>8.2f}{100 * (e['captured'] > e['cost']).mean():>7.0f}%")


if __name__ == "__main__":
    main()
