"""
Adjudication tables for the pre-2021 USD_JPY regime test (RESEARCH_LOG
registration approved 2026-07-11; runs graded by the frozen validator-v2).

Reads the six validator-produced CSVs and prints, per the registered
criteria: per-year net, per-direction net, ex-best-year check, the
2010-2012 yen-strengthening stretch standalone, and the 2012-2015
Abenomics decomposition -- at both spread levels. This script only
REPORTS; interpretation criteria (a)/(b)/(c) are applied in the log entry.

Run: D:/workspace/rhyme/venv/Scripts/python.exe pre2021_adjudicate.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BT = Path(__file__).parent / "backtests"

RUNS = {
    "donchian_scalp30  sp0.8": "backtest_USD_JPY_scalp30_pre2021_donchian_scalp30_sp08.validator-v2_2010-2019.csv",
    "donchian_scalp30  sp1.6": "backtest_USD_JPY_scalp30_pre2021_donchian_scalp30_sp16.validator-v2_2010-2019.csv",
    "donchian_intraday sp0.8": "backtest_USD_JPY_intraday_pre2021_donchian_intraday_sp08.validator-v2_2010-2019.csv",
    "donchian_intraday sp1.6": "backtest_USD_JPY_intraday_pre2021_donchian_intraday_sp16.validator-v2_2010-2019.csv",
    "pullback_parent   sp0.8": "backtest_USD_JPY_scalp30_pre2021_pullback_parent_sp08.validator-v2_2010-2019.csv",
    "pullback_parent   sp1.6": "backtest_USD_JPY_scalp30_pre2021_pullback_parent_sp16.validator-v2_2010-2019.csv",
}

YEN_STRENGTH = (2010, 2011)          # standalone falsifier-preview stretch (2010-01 .. 2011-12)
ABENOMICS = (2013, 2015)             # 2013-01 .. 2015-12 yen-weakening trend years


def report(name: str, csv: str) -> None:
    path = BT / csv
    if not path.exists():
        print(f"\n### {name}: MISSING ({csv})")
        return
    df = pd.read_csv(path, parse_dates=["time"])
    df["year"] = df["time"].dt.year
    df["win"] = df["pnl"] > 0

    net, n, wr = df["pnl"].sum(), len(df), df["win"].mean() * 100
    print(f"\n### {name}  --  n={n}, WR {wr:.1f}%, net {net:+,.2f}")

    yearly = df.groupby("year")["pnl"].agg(["sum", "count"])
    print("  per-year: " + "  ".join(f"{y}:{r['sum']:+,.0f}({int(r['count'])})"
                                     for y, r in yearly.iterrows()))
    pos_years = int((yearly["sum"] > 0).sum())
    print(f"  positive years: {pos_years}/{len(yearly)}")

    by_dir = df.groupby("direction")["pnl"].agg(["sum", "count"])
    print("  per-direction: " + "  ".join(f"{d}:{r['sum']:+,.0f}({int(r['count'])})"
                                          for d, r in by_dir.iterrows()))

    best_year = yearly["sum"].idxmax()
    ex_best = net - yearly.loc[best_year, "sum"]
    print(f"  ex-best-year ({best_year}): {ex_best:+,.2f}")

    ys = df[df["year"].between(*YEN_STRENGTH)]
    print(f"  2010-2011 yen-strengthening standalone: {ys['pnl'].sum():+,.2f} "
          f"(n={len(ys)}, WR {ys['win'].mean()*100 if len(ys) else 0:.1f}%)")

    ab = df[df["year"].between(*ABENOMICS)]
    print(f"  2013-2015 Abenomics standalone:        {ab['pnl'].sum():+,.2f} "
          f"(n={len(ab)}, WR {ab['win'].mean()*100 if len(ab) else 0:.1f}%)")


if __name__ == "__main__":
    print("PRE-2021 USD_JPY REGIME TEST -- adjudication tables (validator-v2 records)")
    print("Registered window 2010-01-01 .. 2019-12-31; $80 fixed risk; look-once dataset.")
    for name, csv in RUNS.items():
        report(name, csv)
