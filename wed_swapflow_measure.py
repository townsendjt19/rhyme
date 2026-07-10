"""
Campaign 4 Track C: Wednesday pre-rollover swap-flow MEASUREMENT
(registration 1e1d1b1; no strategy code unless a signed effect is found).

Hypothesis: carry positioning adjusts in the session hours BEFORE Wednesday's
triple-swap rollover, producing a signed Wednesday-specific return in
carry-heavy pairs, absent in the control pair and on control days.

Window: 12:00-17:00 ET (pre-rollover afternoon), Wednesdays vs Mon/Tue/Thu.
Pairs: AUD_JPY, USD_JPY, EUR_JPY, GBP_JPY (carry) + EUR_USD (control).
Data: OANDA H1 mids, 2021-07 -> 2026-07. ET via the ORB core's hand-verified
US statutory DST rule.

Run:  venv/Scripts/python.exe wed_swapflow_measure.py
"""
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import data
import orb_plugin_core as orb

PAIRS = ["AUD_JPY", "USD_JPY", "EUR_JPY", "GBP_JPY", "EUR_USD"]
START = datetime(2021, 7, 1, tzinfo=timezone.utc)
END = datetime(2026, 7, 1, tzinfo=timezone.utc)


def pip(pair):
    return 0.01 if pair.endswith("JPY") else 0.0001


def main() -> None:
    print("=== TRACK C: Wednesday 12:00-17:00 ET pre-rollover return, by weekday (registration 1e1d1b1) ===")
    for pair in PAIRS:
        df = data.fetch_candles(pair, "H1", from_time=START, to_time=END)
        idx = pd.DatetimeIndex(df.index).tz_convert("UTC")
        et = idx + pd.Series(idx, index=df.index).map(
            lambda t: pd.Timedelta(hours=orb._us_dst_offset(pd.Timestamp(t).tz_localize(None)))).values
        df = df.assign(et_date=pd.DatetimeIndex(et).date, et_hour=pd.DatetimeIndex(et).hour,
                       wd=pd.DatetimeIndex(et).weekday)
        win = df[(df["et_hour"] >= 12) & (df["et_hour"] < 17)]
        rows = []
        for (d, w), g in win.groupby(["et_date", "wd"]):
            if len(g) < 4:
                continue
            rows.append({"wd": w, "ret_pips": (g["close"].iloc[-1] - g["open"].iloc[0]) / pip(pair)})
        r = pd.DataFrame(rows)
        line = f"{pair:8s}"
        for wd, name in [(0, "Mon"), (1, "Tue"), (2, "WED"), (3, "Thu")]:
            s = r[r["wd"] == wd]["ret_pips"]
            t = s.mean() / (s.std() / np.sqrt(len(s))) if len(s) > 2 else float("nan")
            line += f"  {name} {s.mean():+6.2f}p(n={len(s)},t={t:+.1f})"
        print(line)


if __name__ == "__main__":
    main()
