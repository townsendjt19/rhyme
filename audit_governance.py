"""
Governance reconciliation audit — re-derives every standing quantitative
claim in GOVERNANCE.md / strategies.json from the source artifacts
(backtest CSVs + meta.json + scheduler XMLs), never from prior log prose,
and reports PASS/DRIFT per claim.

Cadence (per GOVERNANCE.md): at every monitoring review trigger, and no
less than monthly regardless. Output feeds a dated reconciliation entry
in RESEARCH_LOG.md; any DRIFT is corrected at source with a dated note
(same convention as the 2026-07-01 scalp30 "no negative years" fix).

Usage:
    D:/rhyme/venv/Scripts/python.exe D:/rhyme/audit_governance.py
"""
from __future__ import annotations
import glob
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
BT = ROOT / "backtests"

TOL_DOLLARS = 0.01
TOL_PCT = 0.1     # percentage points
TOL_HOURS = 0.05

results: list[tuple[str, str, str, str]] = []   # (claim, source, artifact, PASS/DRIFT + detail)


def check(claim: str, source: str, artifact: str, expected, actual, tol) -> None:
    ok = abs(actual - expected) <= tol
    status = "PASS" if ok else f"DRIFT (claimed {expected}, artifact says {actual})"
    results.append((claim, source, artifact, status))


def load_years(pattern: str) -> pd.DataFrame:
    frames = [pd.read_csv(f, parse_dates=["time"]) for f in sorted(glob.glob(str(BT / pattern)))]
    df = pd.concat(frames, ignore_index=True).sort_values("time").reset_index(drop=True)
    df["year"] = df["time"].dt.year
    df["win"] = df["pnl"] > 0
    return df


def dd_1pct(df: pd.DataFrame) -> float:
    """Max drawdown (% of equity) on the 1%-compounding model, R = pnl/$80."""
    eq = (1 + 0.01 * (df.sort_values("time")["pnl"] / 80.0)).cumprod()
    return float((eq / eq.cummax() - 1).min() * 100)


# ── scalp30 (Donchian M30/H4, USD_JPY) ───────────────────────────────────────
s30 = load_years("backtest_USD_JPY_scalp30_donchian_m30_*.csv")
art = "backtest_USD_JPY_scalp30_donchian_m30_*.csv"
check("scalp30 total net +$28,000.34", "strategies.json / GOVERNANCE passport", art, 28000.34, round(s30["pnl"].sum(), 2), TOL_DOLLARS)
check("scalp30 n=2,719", "strategies.json / GOVERNANCE passport", art, 2719, len(s30), 0)
check("scalp30 WR 33.5%", "strategies.json / GOVERNANCE passport", art, 33.5, round(s30["win"].mean() * 100, 1), TOL_PCT)
for y, exp in [(2021, 6906.18), (2022, 15413.14), (2023, 3375.76), (2024, 6571.85), (2025, -942.81), (2026, -3323.79)]:
    check(f"scalp30 {y} net {exp:+}", "RESEARCH_LOG validation entry / GOVERNANCE", art,
          exp, round(s30[s30["year"] == y]["pnl"].sum(), 2), TOL_DOLLARS)
wr_2025 = s30[s30["year"] == 2025]["win"].mean() * 100
check("scalp30 worst-full-year WR baseline 28.5% (2025)", "GOVERNANCE monitoring table", art, 28.5, round(wr_2025, 1), TOL_PCT)
check("scalp30 1%-compounding maxDD -68.9%", "GOVERNANCE passport", art, -68.9, round(dd_1pct(s30), 1), TOL_PCT)

# ── intraday (Donchian H1/H4, 5 pairs) ───────────────────────────────────────
frames = []
INTRADAY_PAIRS = ["GBP_USD", "EUR_USD", "USD_JPY", "AUD_JPY", "EUR_JPY"]
for p in INTRADAY_PAIRS:
    d = load_years(f"backtest_{p}_intraday_donchian_fixed_*.csv")
    d["pair"] = p
    frames.append(d)
intr = pd.concat(frames, ignore_index=True).sort_values("time").reset_index(drop=True)
art = "backtest_{pair}_intraday_donchian_fixed_*.csv (5 pairs)"
check("intraday total net +$39,116.41", "GOVERNANCE passport", art, 39116.41, round(intr["pnl"].sum(), 2), TOL_DOLLARS)
check("intraday n=6,884", "GOVERNANCE passport", art, 6884, len(intr), 0)
check("intraday WR 32.0%", "GOVERNANCE monitoring table", art, 32.0, round(intr["win"].mean() * 100, 1), TOL_PCT)
check("intraday USD_JPY share +$26,406.24", "GOVERNANCE passport", art, 26406.24,
      round(intr[intr["pair"] == "USD_JPY"]["pnl"].sum(), 2), TOL_DOLLARS)
check("intraday 2026H1 net -$10,865.76", "GOVERNANCE monitoring table", art, -10865.76,
      round(intr[intr["year"] == 2026]["pnl"].sum(), 2), TOL_DOLLARS)
wr_2025 = intr[intr["year"] == 2025]["win"].mean() * 100
check("intraday worst-full-year WR baseline 28.8% (2025)", "GOVERNANCE monitoring table", art, 28.8, round(wr_2025, 1), TOL_PCT)
check("intraday 1%-compounding maxDD -90.7%", "GOVERNANCE passport", art, -90.7, round(dd_1pct(intr), 1), TOL_PCT)

# ── swing USD_CAD (retired record) ───────────────────────────────────────────
sw = load_years("backtest_USD_CAD_swing_donchian_fixed_*.csv")
art = "backtest_USD_CAD_swing_donchian_fixed_*.csv"
check("swing USD_CAD total net +$292.53", "GOVERNANCE retired passport / RESEARCH_LOG retirement", art,
      292.53, round(sw["pnl"].sum(), 2), TOL_DOLLARS)
check("swing USD_CAD n=225", "GOVERNANCE retired passport", art, 225, len(sw), 0)
minn_fails = sum(1 for (_, _), g in sw.groupby(["year", "direction"]) if len(g) < 10)
check("swing USD_CAD min-N failing cells = 3", "GOVERNANCE retired passport", art, 3, minn_fails, 0)
check("swing USD_CAD 1%-compounding maxDD -20.3%", "GOVERNANCE retired passport", art, -20.3, round(dd_1pct(sw), 1), TOL_PCT)

# ── pullback30 (trend-origin long side, parent backtest) ─────────────────────
to = load_years("backtest_USD_JPY_scalp30_trend_origin_pullback_2021-2026ytd.csv")
lo = to[to["direction"] == "long"]
art = "backtest_USD_JPY_scalp30_trend_origin_pullback_2021-2026ytd.csv"
check("pullback30 parent total +$14,136.28 (n=1,185)", "RESEARCH_LOG / GOVERNANCE passport", art,
      14136.28, round(to["pnl"].sum(), 2), TOL_DOLLARS)
check("pullback30 long side +$18,863.69", "GOVERNANCE passport", art, 18863.69, round(lo["pnl"].sum(), 2), TOL_DOLLARS)
check("pullback30 long n=689", "GOVERNANCE passport", art, 689, len(lo), 0)
check("pullback30 long WR 40.2%", "GOVERNANCE passport", art, 40.2, round(lo["win"].mean() * 100, 1), TOL_PCT)
neg_long_years = sum(1 for _, g in lo.groupby("year") if g["pnl"].sum() <= 0)
check("pullback30 long positive EVERY year (0 negative years)", "GOVERNANCE passport", art, 0, neg_long_years, 0)
check("pullback30 long 1%-compounding maxDD -30.5%", "GOVERNANCE passport", art, -30.5, round(dd_1pct(lo), 1), TOL_PCT)

# ── Overlap claims ────────────────────────────────────────────────────────────
def overlap_same_dir(a: pd.DataFrame, b: pd.DataFrame) -> tuple[float, float, float]:
    """(overlap days as % of a's days, same-dir % of overlap days, opposite %)."""
    a = a.copy(); b = b.copy()
    a["date"] = a["time"].dt.date; b["date"] = b["time"].dt.date
    a_days, b_days = set(a["date"]), set(b["date"])
    ov = a_days & b_days
    same = opp = 0
    for d in ov:
        da, db = set(a[a["date"] == d]["direction"]), set(b[b["date"] == d]["direction"])
        if len(da) == 1 and len(db) == 1:
            if da == db: same += 1
            else: opp += 1
    return len(ov) / len(a_days) * 100, same / len(ov) * 100, opp / len(ov) * 100

don30 = s30
intr_jpy = intr[intr["pair"] == "USD_JPY"]
ovl, same, _ = overlap_same_dir(intr_jpy, don30)
check("intraday/scalp30 USD_JPY overlap 99.7% of intraday days", "GOVERNANCE passports", "both CSV sets", 99.7, round(ovl, 1), TOL_PCT)
check("intraday/scalp30 same-direction 97.3%", "GOVERNANCE passports", "both CSV sets", 97.3, round(same, 1), TOL_PCT)

ovl, same, opp = overlap_same_dir(to, don30)
check("pullback30/scalp30 same-direction 68.1%", "GOVERNANCE passport", "both CSV sets", 68.1, round(same, 1), TOL_PCT)
check("pullback30/scalp30 opposite-direction 28.4%", "GOVERNANCE passport", "both CSV sets", 28.4, round(opp, 1), TOL_PCT)

# ── Pair lists / accounts: strategies.json vs scheduler XMLs ─────────────────
strat = json.load(open(ROOT / "strategies.json", encoding="utf-8"))["strategies"]

def xml_args(name: str) -> str:
    p = ROOT / "scheduler" / f"{name}.xml"
    if not p.exists():
        return ""
    return open(p, encoding="utf-16").read()

for sname, task in [("donchian_plugin_intraday", "Rhyme-Intraday"),
                    ("donchian_plugin_scalp30", "Rhyme-Scalp30"),
                    ("trend_origin_pullback_long", "Rhyme-Pullback30")]:
    doc_pairs = set(strat[sname]["pairs"])
    xml = xml_args(task)
    m = re.search(r"--pairs\s+(\S+)", xml)
    xml_pairs = set(m.group(1).split(",")) if m else set()
    status = "PASS" if doc_pairs == xml_pairs else f"DRIFT (strategies.json {sorted(doc_pairs)} vs task XML {sorted(xml_pairs)})"
    results.append((f"{sname} pair list matches live task config", "strategies.json vs scheduler XML", f"{task}.xml", status))

m = re.search(r"--account\s+(\S+?)\s", xml_args("Rhyme-Pullback30") + " ")
acct = m.group(1) if m else "none"
status = "PASS" if acct == "101-001-39634331-001" else f"DRIFT (XML says {acct})"
results.append(("pullback30 isolated on account -001", "strategies.json / RESEARCH_LOG", "Rhyme-Pullback30.xml", status))

swing_task_exists = (ROOT / "scheduler" / "Rhyme-Swing.xml").exists()
status = "PASS (XML remains in repo as record; task deletion is registry-side)" if swing_task_exists else "PASS"
results.append(("swing retired (no live relaunch path expected)", "GOVERNANCE roster", "scheduler/", status))

# ── Report ────────────────────────────────────────────────────────────────────
n_drift = sum(1 for *_, s in results if s.startswith("DRIFT"))
print(f"GOVERNANCE RECONCILIATION AUDIT — {len(results)} claims checked, {n_drift} DRIFT\n")
w = max(len(r[0]) for r in results)
for claim, source, artifact, status in results:
    print(f"{'[DRIFT]' if status.startswith('DRIFT') else '[ OK  ]'} {claim}")
    if status.startswith("DRIFT"):
        print(f"         source: {source}")
        print(f"         artifact: {artifact}")
        print(f"         {status}")

print("""
MANUAL SECTION (claims that don't reduce to a number -- confirm by eye each audit):
  [ ] Factor-dependence prose still matches the latest hypothesis state
      (currently: persistent-macro-trend reframe, yen-strengthening falsifier for pullback30)
  [ ] Retirement records match reality (swing: process absent, task deleted, run-off position status)
  [ ] Probation clock arithmetic (pullback30 trade count / calendar position vs terms)
  [ ] Monitoring-table review dates not yet passed without a review having occurred
  [ ] Guiding principle / roster status labels consistent with RESEARCH_LOG's latest entries
""")
sys.exit(1 if n_drift else 0)
