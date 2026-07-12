"""
Passport-box computations for the classic-indicator screen's two validated
USD_JPY cells (registration 53610c6). Boxes 2/3/4/5/8/9 numbers from the
adjudicated full-window CSVs; box 5 overlap vs the live USD_JPY strategies
per the standard convention (trading-day overlap %, same-direction % on
shared days, median entry-time gap). Box 8 imports sortino.py's registered
convention functions unchanged.

Run:  venv/Scripts/python.exe classicind_passport_stats.py
"""
from __future__ import annotations
from pathlib import Path

import pandas as pd

from sortino import weekly_returns, sortino

HERE = Path(__file__).parent
RISK = 80.0
PIP = 0.01  # USD_JPY

CANDS = {
    "jpy_adxgate": "classicind_USD_JPY_adxgate_full.csv",
    "jpy_frama": "classicind_USD_JPY_frama_full.csv",
}
LIVE = {  # USD_JPY live strategies (intraday filtered to USD_JPY)
    "scalp30": ("backtests/corrected_f86d9f4_scalp30_2021-2026ytd.csv", None),
    "intraday(JPY)": ("backtests/corrected_f86d9f4_intraday_2021-2026ytd.csv", "USD_JPY"),
    "pullback30": ("backtests/corrected_f86d9f4_pullback30_2021-2026ytd.csv", None),
}


def load(path: str, instrument: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(HERE / path, parse_dates=["time", "exit_time"])
    if instrument:
        df = df[df["instrument"] == instrument]
    return df.sort_values("time").reset_index(drop=True)


def daily_dir(df: pd.DataFrame) -> pd.Series:
    """Net direction per UTC trading day: sign of (longs - shorts) entered."""
    d = df.assign(day=df["time"].dt.date,
                  dirn=(df["direction"] == "long").astype(int) * 2 - 1)
    return d.groupby("day")["dirn"].sum()


def overlap(cand: pd.DataFrame, live: pd.DataFrame) -> str:
    cd, ld = daily_dir(cand), daily_dir(live)
    shared = cd.index.intersection(ld.index)
    day_ov = len(shared) / len(cd) * 100
    both = pd.DataFrame({"c": cd.loc[shared], "l": ld.loc[shared]})
    both = both[(both["c"] != 0) & (both["l"] != 0)]
    same = ((both["c"] > 0) == (both["l"] > 0)).mean() * 100 if len(both) else float("nan")
    lt = live["time"].sort_values().reset_index(drop=True)
    idx = lt.searchsorted(cand["time"])
    gaps = []
    for t, i in zip(cand["time"], idx):
        prev = abs((t - lt.iloc[i - 1]).total_seconds()) if i > 0 else float("inf")
        nxt = abs((lt.iloc[i] - t).total_seconds()) if i < len(lt) else float("inf")
        gaps.append(min(prev, nxt) / 3600)
    med_gap = pd.Series(gaps).median()
    return f"{day_ov:.1f}% trading-day overlap, {same:.1f}% same-direction (directional shared days), {med_gap:.1f}h median entry gap"


def report(name: str, csv: str) -> None:
    tr = load(csv)
    print(f"\n{'='*70}\n{name}  ({csv})\n{'='*70}")
    yr = tr["time"].dt.year

    # Box 2: min-N per year x direction
    cells = tr.groupby([yr, "direction"]).size()
    fails = cells[cells < 10]
    print(f"[box2] year x direction cells: {len(cells)}, failing (<10): {len(fails)}")
    print(cells.unstack(fill_value=0).to_string())

    # Box 3: top-5 win concentration per profitable year; ex-best-year
    yearly = tr.groupby(yr)["pnl"].sum()
    print(f"[box3] yearly: " + "  ".join(f"{y}:{v:+.0f}" for y, v in yearly.items()))
    for y, v in yearly[yearly > 0].items():
        wins = tr[(yr == y) & (tr["pnl"] > 0)]["pnl"].sort_values(ascending=False)
        print(f"       {y}: top-5 wins = {wins.head(5).sum() / wins.sum() * 100:.1f}% of gross wins (n wins={len(wins)})")
    print(f"       net={yearly.sum():+.2f}  ex-best-year={yearly.sum() - yearly.max():+.2f}  ex-top-2={yearly.sum() - yearly.nlargest(2).sum():+.2f}")

    # Box 4: drawdowns, both models
    t2 = tr.sort_values("exit_time")
    fixed = t2["pnl"].cumsum()
    dd_fixed = (fixed - fixed.cummax()).min()
    eq = (1 + 0.01 * t2["pnl"] / RISK).cumprod()
    dd_pct = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    print(f"[box4] fixed-$80 maxDD: {dd_fixed:+.2f}   1%-compounding maxDD: {dd_pct:.1f}%   final multiple: {eq.iloc[-1]:.2f}x")

    # Box 5: overlap vs each live strategy
    for lname, (lpath, instr) in LIVE.items():
        print(f"[box5] vs {lname}: {overlap(tr, load(lpath, instr))}")

    # Box 8: Sortino per registered convention
    st = sortino(weekly_returns(f"../{csv}"))
    print(f"[box8] Sortino {st['sortino']:.2f}  mean wk {st['mean_wk_bps']:+.1f} bps  "
          f"downside {st['downside_wk_bps']:.1f} bps  weeks {st['weeks']} (losing {st['loss_weeks']})")

    # Box 9: stop-distance floor (observed; no floor is enforced in the plugin)
    stops = (tr["entry"] - tr["sl"]).abs() / PIP
    print(f"[box9] stop distance pips: min={stops.min():.1f}  p1={stops.quantile(0.01):.1f}  "
          f"p5={stops.quantile(0.05):.1f}  median={stops.median():.1f}  (spread 0.8p; no floor enforced in plugin)")


if __name__ == "__main__":
    for n, c in CANDS.items():
        report(n, c)
