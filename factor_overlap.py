"""
Factor overlap map (handoff 2026-07-03): shared-losing-WEEK co-occurrence and
shared-losing-REGIME composition across the live+benched roster, from the
corrected f86d9f4 records. Co-occurrence of drawdown periods, NOT return
correlation.

Conventions (chosen before running):
- Losing week: ISO week (Friday-anchored) with net fixed-$80 P&L < 0. Fixed-
  risk P&L, not the compounding curve -- co-occurrence should be sizing-free.
- Weeks with no closed trades are NOT losing weeks (flat != loss).
- Matrix is ASYMMETRIC: M[A->B] = share of A's losing weeks in which B also
  lost. Read row A as "when A is bleeding, how often is B bleeding too."
- Regime clock: USD_JPY daily ER(20), quarterly mean, trending iff >= 0.20 --
  the Bot E regime-map convention, applied book-wide (USD_JPY is the primary
  instrument for 5 of the 7 strategies; a per-pair clock would fragment the
  question the map is asking: where does the BOOK co-lose).

One command:
    D:/rhyme/venv/Scripts/python.exe D:/rhyme/factor_overlap.py
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BT = Path(__file__).parent / "backtests"
ER_THRESHOLD = 0.20
ER_N = 20

ROSTER = {
    "intraday":   "corrected_f86d9f4_intraday_2021-2026ytd.csv",
    "scalp30":    "corrected_f86d9f4_scalp30_2021-2026ytd.csv",
    "pullback30": "corrected_f86d9f4_pullback30_2021-2026ytd.csv",
    "spread2b":   "corrected_f86d9f4_nzdcad_spread_2021-2026ytd.csv",
    "spread2a":   "corrected_f86d9f4_eurgbp_spread_2021-2026ytd.csv",
    "spread2c":   "corrected_f86d9f4_chfsgd_spread_2021-2026ytd.csv",
    "d_h4":       "corrected_f86d9f4_trend_origin_h4_2021-2026ytd.csv",
    # Gate-2 survivor (validated-but-benched 2026-07-09); record starts 2021-12
    # (MT5 data ceiling) -- absent weeks are handled by the flat != loss convention.
    "xau_pullback": "../gate2_XAUUSD_trend_origin_pullback_full.csv",
    # US500 Gate-2 passer (2026-07-09); record starts 2022-07 (Phase A ceiling).
    "spx_pullback": "../gate2_SPX_trend_origin_pullback_full.csv",
    # BTCUSD Gate-2 passer (2026-07-09, .sim data); record starts 2022-10.
    "btc_donchian": "../gate2sim_BTCUSD_donchian_full.csv",
    # Line B close-variant passers (2026-07-09); ORB deployment shortlist.
    "orb_spx": "../orb_SPX_close_full.csv",
    "orb_xau": "../orb_XAUUSD_close_full.csv",
    "orb_nq": "../orb_NQ_close_full.csv",
    # Campaign 2 Track B survivor (2026-07-09): vol-compression breakout, XAU.
    "volcomp_xau": "../volcomp_XAUUSD_full.csv",
    # Campaign 3 Track B full-window passers (2026-07-09): M15 rungs on gold.
    "xau_pb_m15": "../linec2_xau_pullback_m15_full.csv",
    "xau_don_m15": "../linec2_xau_donchian_m15_full.csv",
    # Campaign 6 survivors (2026-07-10): gap deployed, fomc benched.
    "eur_wkndgap": "../c6_wkndgap_EUR_USD.csv",
    "fomc_drift": "../c6_fomc_drift.csv",
    # trendline row removed 2026-07-10: record void (fractal look-ahead).
    # Classic-indicator screen validated passes (2026-07-11, reg 53610c6,
    # validator-v2 reproduced): candidates under passport evaluation.
    "jpy_adxgate": "../classicind_USD_JPY_adxgate_full.csv",
    "jpy_frama": "../classicind_USD_JPY_frama_full.csv",
}


def weekly_pnl(csv_name: str) -> pd.Series:
    df = pd.read_csv(BT / csv_name, parse_dates=["exit_time"])
    s = pd.Series(df["pnl"].values,
                  index=pd.DatetimeIndex(df["exit_time"]).tz_localize(None))
    return s.resample("W-FRI").sum()          # weeks with no trades absent -> NaN-free sum only over present weeks


def regime_by_quarter() -> pd.Series:
    """Quarterly USD_JPY ER(20) regime labels from OANDA daily candles."""
    import data
    df = data.fetch_candles("USD_JPY", "D",
                            from_time=datetime(2020, 11, 1, tzinfo=timezone.utc),
                            to_time=datetime(2026, 7, 1, tzinfo=timezone.utc))
    c = df["close"].copy()
    c.index = c.index.tz_localize(None)
    er = (c.diff(ER_N).abs() / c.diff().abs().rolling(ER_N).sum()).dropna()
    q = er.resample("QE").mean()
    q = q[q.index >= "2021-01-01"]
    return q.apply(lambda v: "trending" if v >= ER_THRESHOLD else "ranging")


def main() -> None:
    losing = {}
    for name, csv in ROSTER.items():
        wp = weekly_pnl(csv)
        losing[name] = set(wp[wp < 0].index)

    names = list(ROSTER)
    print("=" * 78)
    print("FACTOR OVERLAP MAP -- corrected f86d9f4 records, generated 2026-07-03")
    print("=" * 78)

    print("\n[1] SHARED-LOSING-WEEK MATRIX  (row A -> col B: % of A's losing weeks where B also lost)")
    print("    " + "".join(f"{n[:10]:>11s}" for n in names))
    for a in names:
        cells = []
        for b in names:
            if a == b:
                cells.append("       --  ")
            else:
                pct = 100 * len(losing[a] & losing[b]) / len(losing[a]) if losing[a] else 0.0
                cells.append(f"{pct:10.1f} ")
        print(f"{a[:10]:>10s} " + "".join(cells) + f"  (n={len(losing[a])})")

    regime = regime_by_quarter()
    qlabel = {q: lab for q, lab in regime.items()}

    def week_regime(w: pd.Timestamp) -> str:
        for q, lab in qlabel.items():
            if w <= q and w > q - pd.offsets.QuarterEnd(1):
                return lab
        return "?"

    print(f"\n[2] REGIME CLOCK (USD_JPY quarterly ER({ER_N}) mean, trending >= {ER_THRESHOLD}):")
    line = "    "
    for q, lab in regime.items():
        line += f"{q.year}Q{q.quarter}:{'T' if lab == 'trending' else 'r'}  "
    print(line)

    print("\n[3] LOSING-WEEK REGIME COMPOSITION (per strategy: % of its losing weeks in trending quarters)")
    for n in names:
        labs = [week_regime(w) for w in losing[n]]
        t = labs.count("trending")
        print(f"    {n:12s} trending {100 * t / len(labs):5.1f}%  ranging {100 * (len(labs) - t) / len(labs):5.1f}%  (n={len(labs)})")

    print("\n[4] TEMPORAL CLUSTERING -- weeks where >=4 of 7 strategies lost together:")
    all_weeks = sorted(set().union(*losing.values()))
    heavy = [(w, [n for n in names if w in losing[n]]) for w in all_weeks]
    heavy = [(w, ls) for w, ls in heavy if len(ls) >= 4]
    for w, ls in heavy:
        print(f"    {w.date()} [{week_regime(w):8s}] ({len(ls)}): {', '.join(ls)}")
    by_q = pd.Series([week_regime(w) for w, _ in heavy]).value_counts() if heavy else pd.Series(dtype=int)
    print(f"    -> {len(heavy)} such weeks; regime split: {dict(by_q)}")


if __name__ == "__main__":
    main()
