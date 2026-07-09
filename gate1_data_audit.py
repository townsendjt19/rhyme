"""
Gate 1 data-quality + indicative-cost audit — prop-firm multi-asset expansion.

Spec pre-registered in RESEARCH_LOG.md (2026-07-08) BEFORE this script was
written. Runs against the MT5 Phase A source (mt5_client) plus OANDA
(data.py) for the two FX cross-check instruments. Draws NO strategy
conclusions and NO trustworthy cost conclusions (Phase A fidelity contract:
price OK, spreads indicative-only).

Output: gate1_data_audit.csv + printed verdict table.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/gate1_data_audit.py
"""
import csv
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

from mt5_client import connect, get_history, SOURCE_TAG
from data import fetch_candles as oanda_fetch

WINDOW_END = datetime(2026, 7, 1)
HISTORY_START = datetime(2018, 1, 1)  # generous probe floor
COST_WINDOW_START = datetime(2025, 7, 1)

# Registered universe (RESEARCH_LOG 2026-07-08): 11 indices, 4 metals, 2 energy
UNIVERSE = {
    "SPX": "indices", "NQ": "indices", "YM": "indices", "FDAX": "indices",
    "CAC": "indices", "FTSE": "indices", "SX5E": "indices", "IBEX35": "indices",
    "NI225": "indices", "ASX200": "indices", "HK50": "indices",
    "XAUUSD": "metals", "XAGUSD": "metals", "XPTUSD": "metals", "XPDUSD": "metals",
    "XNGUSD": "energy", "UKBRENT": "energy",
}

# Source-wide clock verification: MT5 symbol -> OANDA instrument
CROSS_CHECKS = {"EURUSD": "EUR_USD", "USDJPY": "USD_JPY"}
OFFSETS_H = [0, 1, 2, 3]
# One winter month and one summer month to expose DST behavior
CLOCK_MONTHS = [
    ("winter", datetime(2026, 1, 5), datetime(2026, 1, 31)),
    ("summer", datetime(2025, 7, 7), datetime(2025, 8, 2)),
]

# Registered thresholds
MIN_YEARS = 3.0
DEFICIENT_WEEK_FRAC = 0.80     # week is deficient below 80% of modal weekly bars
MAX_DEFICIENT_SHARE = 0.05     # >5% deficient weeks -> quality exclude
MIN_CLOCK_CORR = 0.999
COST_RATIO_LIMIT = 0.25        # indicative spread >= 25% of median M30 range


def weekly_completeness(df: pd.DataFrame) -> tuple[float, int]:
    """Return (share of deficient weeks, modal weekly bar count).
    First and last calendar weeks are dropped (partial by construction)."""
    iso = df.index.isocalendar()
    key = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    weeks = df.groupby(key.values).size()
    first_bar = df.groupby(key.values).apply(lambda g: g.index.min()).sort_values()
    weeks = weeks.reindex(first_bar.index)
    if len(weeks) <= 2:
        return 0.0, int(weeks.max() if len(weeks) else 0)
    weeks = weeks.iloc[1:-1]
    modal = int(weeks.mode().iloc[0])
    deficient = int((weeks < DEFICIENT_WEEK_FRAC * modal).sum())
    return deficient / len(weeks), modal


def verify_clock() -> dict:
    """Source-wide broker-clock offset vs OANDA UTC, winter and summer."""
    out = {}
    for label, start, end in CLOCK_MONTHS:
        month_results = {}
        for sym, inst in CROSS_CHECKS.items():
            mdf = get_history(sym, "M30", start, end)
            odf = oanda_fetch(inst, "M30", from_time=start.replace(tzinfo=timezone.utc),
                              to_time=end.replace(tzinfo=timezone.utc))
            oser = odf["close"]
            if oser.index.tz is not None:
                oser.index = oser.index.tz_convert("UTC").tz_localize(None)
            best_off, best_corr = None, -1.0
            for off in OFFSETS_H:
                mser = mdf["close"].copy()
                mser.index = mser.index - pd.Timedelta(hours=off)
                joined = pd.concat([mser.rename("mt5"), oser.rename("oanda")],
                                   axis=1, join="inner")
                if len(joined) < 100:
                    continue
                corr = joined["mt5"].corr(joined["oanda"])
                if corr > best_corr:
                    best_off, best_corr = off, corr
            month_results[sym] = (best_off, round(best_corr, 6))
        offs = {v[0] for v in month_results.values()}
        corrs = [v[1] for v in month_results.values()]
        out[label] = {
            "offset": offs.pop() if len(offs) == 1 else None,  # must agree across symbols
            "min_corr": min(corrs),
            "detail": month_results,
        }
    return out


def audit_symbol(sym: str, asset_class: str) -> dict:
    df = get_history(sym, "M30", HISTORY_START, WINDOW_END)
    earliest = df.index.min()
    years = (WINDOW_END - earliest.to_pydatetime()).days / 365.25
    deficient_share, modal = weekly_completeness(df)

    recent = df[df.index >= COST_WINDOW_START]
    median_range = float((recent["high"] - recent["low"]).median())
    info = mt5.symbol_info(sym)
    spread_price = info.spread * info.point if info else float("nan")
    cost_ratio = spread_price / median_range if median_range else float("nan")

    if years < MIN_YEARS:
        verdict = "EXCLUDE_window"
    elif deficient_share > MAX_DEFICIENT_SHARE:
        verdict = "EXCLUDE_quality"
    elif cost_ratio >= COST_RATIO_LIMIT:
        verdict = "PROVISIONAL_EXCLUDE_cost"
    else:
        verdict = "PASS"

    return {
        "symbol": sym, "asset_class": asset_class, "source": SOURCE_TAG,
        "earliest_m30_broker_time": earliest.isoformat(), "usable_years": round(years, 2),
        "modal_weekly_bars": modal, "deficient_week_share": round(deficient_share, 4),
        "median_m30_range": median_range,
        "indicative_spread": spread_price,
        "spread_pct_median_range": round(100 * cost_ratio, 2),
        "verdict": verdict,
    }


def main() -> None:
    connect()

    print("== Source-level clock verification ==")
    clock = verify_clock()
    source_ok = True
    for label, r in clock.items():
        print(f"  {label}: offset=+{r['offset']}h  min_corr={r['min_corr']}  {r['detail']}")
        if r["offset"] is None or r["min_corr"] < MIN_CLOCK_CORR:
            source_ok = False
    if not source_ok:
        print("SOURCE-LEVEL FAIL: no unique >0.999 offset — Phase A source unfit; aborting per registration.")
        return

    rows = [audit_symbol(sym, cls) for sym, cls in UNIVERSE.items()]
    out = Path(__file__).parent / "gate1_data_audit.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\n== Gate 1 verdicts ({len(rows)} symbols) -> {out.name} ==")
    for r in sorted(rows, key=lambda r: (r["verdict"], r["symbol"])):
        print(f"  {r['symbol']:<8} {r['asset_class']:<8} {r['usable_years']:>5}y  "
              f"def_weeks={r['deficient_week_share']:.1%}  "
              f"spread={r['spread_pct_median_range']:>6.2f}% of median range  {r['verdict']}")


if __name__ == "__main__":
    main()
