"""
Box-8 Sortino — computed EXACTLY per the GOVERNANCE convention registered
2026-07-03 (before any Sortino existed): 1%-compounding curve in exit_time
order, ISO-week (Friday-anchored) returns with flat weeks as 0%, MAR=0
full-sample downside deviation, sqrt(52) annualization.

One-command ranked table over the live+benched roster:
    D:/rhyme/venv/Scripts/python.exe D:/rhyme/sortino.py
"""
from __future__ import annotations
import math
from pathlib import Path

import pandas as pd

BT = Path(__file__).parent / "backtests"
RISK = 80.0

ROSTER = {
    "intraday":    "corrected_f86d9f4_intraday_2021-2026ytd.csv",
    "scalp30":     "corrected_f86d9f4_scalp30_2021-2026ytd.csv",
    "pullback30":  "corrected_f86d9f4_pullback30_2021-2026ytd.csv",
    "spread2b":    "corrected_f86d9f4_nzdcad_spread_2021-2026ytd.csv",
    "spread2a":    "corrected_f86d9f4_eurgbp_spread_2021-2026ytd.csv",
    "spread2c":    "corrected_f86d9f4_chfsgd_spread_2021-2026ytd.csv",
    "trend_origin_d_h4": "corrected_f86d9f4_trend_origin_h4_2021-2026ytd.csv",
}


def weekly_returns(csv_name: str) -> pd.Series:
    """Weekly returns of the 1%-compounding curve, flat weeks included as 0%."""
    df = pd.read_csv(BT / csv_name, parse_dates=["exit_time"]).sort_values("exit_time")
    r = 1 + 0.01 * (df["pnl"] / RISK)
    eq = pd.Series(r.values, index=pd.DatetimeIndex(df["exit_time"]).tz_localize(None)).cumprod()
    # last equity value per ISO week (Friday anchor), forward-filled over flat weeks
    wk = eq.resample("W-FRI").last().ffill()
    return wk.pct_change().fillna(wk.iloc[0] - 1.0 if len(wk) else 0.0)


def sortino(weekly: pd.Series) -> dict:
    mean = weekly.mean()
    downside = math.sqrt((weekly.clip(upper=0.0) ** 2).mean())   # MAR=0, full-sample denom
    s = (mean / downside) * math.sqrt(52) if downside > 0 else float("inf")
    return {"weeks": len(weekly), "loss_weeks": int((weekly < 0).sum()),
            "mean_wk_bps": mean * 1e4, "downside_wk_bps": downside * 1e4, "sortino": s}


def table() -> pd.DataFrame:
    rows = []
    for name, csv in ROSTER.items():
        st = sortino(weekly_returns(csv))
        rows.append({"strategy": name, **st})
    return pd.DataFrame(rows).sort_values("sortino", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    t = table()
    print("Box-8 Sortino (GOVERNANCE convention 2026-07-03) -- ranked")
    print("NOTE: flat weeks count as 0%; sparse strategies (spreads) are flattered by this;")
    print("      read next to trade counts, not instead of them.")
    for _, r in t.iterrows():
        print(f"  {r['strategy']:18s} Sortino {r['sortino']:6.2f}   "
              f"mean wk {r['mean_wk_bps']:+7.1f} bps   downside dev {r['downside_wk_bps']:6.1f} bps   "
              f"weeks {int(r['weeks']):3d} (losing {int(r['loss_weeks']):3d})")
