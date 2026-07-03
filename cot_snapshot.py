"""
COT instrumentation snapshot — MONITORING ONLY (Phase 2 resolution, RESEARCH_LOG
2026-07-03): no gate, no order path, no strategy status, and explicitly
NOT a validation path for the deferred positioning-filter option.

Net non-commercial positioning percentile (156-week trailing window — Phase
1's exact measure) for the seven mapped currencies, from CFTC's free public
API, cached locally and refreshed when the cache is older than the weekly
release cycle.

One-command report:
    D:/rhyme/venv/Scripts/python.exe D:/rhyme/cot_snapshot.py
Also consumed by review_dossier.py as a standing context block.
"""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
CACHE = Path(__file__).parent / "backtests" / "cot_snapshot.csv"
PCTL_W = 156
MAX_AGE_DAYS = 8   # weekly release cadence

# (currency, name variants, spot mapping note) -- JPY first: yen prominent.
CONTRACTS = [
    ("JPY", ["JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"], "USD_JPY inverted"),
    ("EUR", ["EURO FX - CHICAGO MERCANTILE EXCHANGE"], "EUR_USD direct"),
    ("GBP", ["BRITISH POUND - CHICAGO MERCANTILE EXCHANGE",
             "BRITISH POUND STERLING - CHICAGO MERCANTILE EXCHANGE"], "GBP_USD direct"),
    ("AUD", ["AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"], "AUD_USD direct"),
    ("NZD", ["NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE",
             "NEW ZEALAND DOLLAR - CHICAGO MERCANTILE EXCHANGE"], "NZD_USD direct"),
    ("CAD", ["CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"], "USD_CAD inverted"),
    ("CHF", ["SWISS FRANC - CHICAGO MERCANTILE EXCHANGE"], "USD_CHF inverted"),
]


def _q(params: dict) -> list:
    url = BASE + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.loads(r.read().decode())


def _fetch() -> pd.DataFrame:
    rows = []
    for ccy, names, mapping in CONTRACTS:
        frames = []
        for name in names:
            data = _q({"$select": "report_date_as_yyyy_mm_dd, noncomm_positions_long_all, noncomm_positions_short_all",
                       "$where": f"market_and_exchange_names='{name}' AND report_date_as_yyyy_mm_dd>'2017-12-31'",
                       "$order": "report_date_as_yyyy_mm_dd", "$limit": "5000"})
            if data:
                frames.append(pd.DataFrame(data))
        df = pd.concat(frames, ignore_index=True)
        df["date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"])
        df["net"] = df["noncomm_positions_long_all"].astype(int) - df["noncomm_positions_short_all"].astype(int)
        s = df.sort_values("date").drop_duplicates("date").set_index("date")["net"]
        window = s.iloc[-PCTL_W:]
        pctl = float((window <= s.iloc[-1]).mean() * 100)
        prev4 = float(s.iloc[-5]) if len(s) >= 5 else float("nan")
        rows.append({"ccy": ccy, "mapping": mapping, "report_date": s.index[-1].date().isoformat(),
                     "net": int(s.iloc[-1]), "pctl_156w": round(pctl, 1),
                     "net_4w_ago": int(prev4), "chg_4w": int(s.iloc[-1] - prev4)})
    out = pd.DataFrame(rows)
    out["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return out


def get_snapshot(max_age_days: int = MAX_AGE_DAYS) -> pd.DataFrame:
    """Cached snapshot; refreshes from the API when stale. Raises on first-run
    fetch failure; callers embedding this as context should try/except."""
    if CACHE.exists():
        cached = pd.read_csv(CACHE)
        age = (datetime.now(timezone.utc)
               - datetime.fromisoformat(cached["fetched_at"].iloc[0])).days
        if age < max_age_days:
            return cached
    fresh = _fetch()
    fresh.to_csv(CACHE, index=False)
    return fresh


def format_block(df: pd.DataFrame) -> str:
    lines = ["[COT] Net non-commercial positioning, 156w percentile (instrumentation only -- "
             "no gate, no order path):"]
    for _, r in df.iterrows():
        flag = ""
        if r["pctl_156w"] >= 90:
            flag = "  << extreme LONG (fuel mark, not a signal)"
        elif r["pctl_156w"] <= 10:
            flag = "  << extreme SHORT (fuel mark, not a signal)"
        lines.append(f"    {r['ccy']}: net {r['net']:+,} ({r['pctl_156w']:.0f}th pctl, "
                     f"4w chg {r['chg_4w']:+,})  [{r['mapping']}]  report {r['report_date']}{flag}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_block(get_snapshot()))
