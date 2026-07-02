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
# Repointed 2026-07-02 at the corrected-harness record (warm-up fix 85e4b67,
# scope correction in RESEARCH_LOG same date); pre-fix catalog CSVs retained
# on disk but no longer the source of standing claims.
s30 = load_years("corrected_f86d9f4_scalp30_2021-2026ytd.csv")
art = "corrected_f86d9f4_scalp30_2021-2026ytd.csv"
check("scalp30 total net +$26,278.01 (corrected)", "GOVERNANCE passport", art, 26278.01, round(s30["pnl"].sum(), 2), TOL_DOLLARS)
check("scalp30 n=2,931 (corrected)", "GOVERNANCE passport", art, 2931, len(s30), 0)
check("scalp30 WR 32.7% (corrected)", "GOVERNANCE passport / monitoring baseline", art, 32.7, round(s30["win"].mean() * 100, 1), TOL_PCT)
for y, exp in [(2021, 6965.25), (2022, 14631.07), (2023, 2231.96), (2024, 7887.54), (2025, -2868.94), (2026, -2568.88)]:
    check(f"scalp30 {y} net {exp:+} (corrected)", "RESEARCH_LOG scope-correction entry / GOVERNANCE", art,
          exp, round(s30[s30["year"] == y]["pnl"].sum(), 2), TOL_DOLLARS)
wr_2025 = s30[s30["year"] == 2025]["win"].mean() * 100
check("scalp30 worst-full-year WR baseline 27.1% (2025, corrected)", "GOVERNANCE monitoring table", art, 27.1, round(wr_2025, 1), TOL_PCT)
check("scalp30 1%-compounding maxDD -68.8% (corrected)", "GOVERNANCE passport", art, -68.8, round(dd_1pct(s30), 1), TOL_PCT)

# ── intraday (Donchian H1/H4, 5 pairs) ───────────────────────────────────────
# Repointed 2026-07-02 at the corrected-harness record (see scalp30 note).
intr = load_years("corrected_f86d9f4_intraday_2021-2026ytd.csv")
art = "corrected_f86d9f4_intraday_2021-2026ytd.csv (5 pairs)"
check("intraday total net +$28,973.51 (corrected)", "GOVERNANCE passport", art, 28973.51, round(intr["pnl"].sum(), 2), TOL_DOLLARS)
check("intraday n=7,434 (corrected)", "GOVERNANCE passport", art, 7434, len(intr), 0)
check("intraday WR 31.0% (corrected)", "GOVERNANCE monitoring baseline", art, 31.0, round(intr["win"].mean() * 100, 1), TOL_PCT)
check("intraday USD_JPY share +$24,580.76 = 85% (corrected)", "GOVERNANCE passport", art, 24580.76,
      round(intr[intr["pair"] == "USD_JPY"]["pnl"].sum(), 2), TOL_DOLLARS)
check("intraday 2023 net -$4,308.58 (corrected; flipped negative)", "GOVERNANCE passport", art, -4308.58,
      round(intr[intr["year"] == 2023]["pnl"].sum(), 2), TOL_DOLLARS)
check("intraday 2026H1 net -$10,545.76 (corrected)", "GOVERNANCE monitoring table", art, -10545.76,
      round(intr[intr["year"] == 2026]["pnl"].sum(), 2), TOL_DOLLARS)
wr_2025 = intr[intr["year"] == 2025]["win"].mean() * 100
check("intraday worst-full-year WR baseline 27.7% (2025, corrected)", "GOVERNANCE monitoring table", art, 27.7, round(wr_2025, 1), TOL_PCT)
check("intraday 1%-compounding maxDD -92.0% (corrected)", "GOVERNANCE passport", art, -92.0, round(dd_1pct(intr), 1), TOL_PCT)

# ── swing USD_CAD (retired record) ───────────────────────────────────────────
sw = load_years("backtest_USD_CAD_swing_donchian_fixed_*.csv")
art = "backtest_USD_CAD_swing_donchian_fixed_*.csv"
check("swing USD_CAD total net +$292.53", "GOVERNANCE retired passport / RESEARCH_LOG retirement", art,
      292.53, round(sw["pnl"].sum(), 2), TOL_DOLLARS)
check("swing USD_CAD n=225", "GOVERNANCE retired passport", art, 225, len(sw), 0)
minn_fails = sum(1 for (_, _), g in sw.groupby(["year", "direction"]) if len(g) < 10)
check("swing USD_CAD min-N failing cells = 3", "GOVERNANCE retired passport", art, 3, minn_fails, 0)
check("swing USD_CAD 1%-compounding maxDD -20.3%", "GOVERNANCE retired passport", art, -20.3, round(dd_1pct(sw), 1), TOL_PCT)

# Corrected-harness swing record (2026-07-02 dated note on the retired
# passport + RESEARCH_LOG retirement addendum). The pre-fix claims above are
# preserved deliberately: they verify the record the decision was made on.
swc = load_years("corrected_f86d9f4_swing_2021-2026ytd.csv")
art = "corrected_f86d9f4_swing_2021-2026ytd.csv"
check("swing corrected net -$4,759.73 (sign flip)", "GOVERNANCE retired-passport dated note", art,
      -4759.73, round(swc["pnl"].sum(), 2), TOL_DOLLARS)
check("swing corrected n=376", "GOVERNANCE retired-passport dated note", art, 376, len(swc), 0)
check("swing corrected WR 24.7%", "GOVERNANCE retired-passport dated note", art, 24.7, round(swc["win"].mean() * 100, 1), TOL_PCT)
check("swing corrected 1%-compounding maxDD -56.5%", "RESEARCH_LOG retirement addendum", art, -56.5, round(dd_1pct(swc), 1), TOL_PCT)

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
# Overlap expecteds recomputed 2026-07-02 against the corrected records
# (were 99.7 / 97.3 / 28.4 on the pre-fix CSVs; conclusions unchanged).
ovl, same, _ = overlap_same_dir(intr_jpy, don30)
check("intraday/scalp30 USD_JPY overlap 99.5% of intraday days (corrected)", "GOVERNANCE passports", "both CSV sets", 99.5, round(ovl, 1), TOL_PCT)
check("intraday/scalp30 same-direction 97.0% (corrected)", "GOVERNANCE passports", "both CSV sets", 97.0, round(same, 1), TOL_PCT)

ovl, same, opp = overlap_same_dir(to, don30)
check("pullback30/scalp30 same-direction 68.1%", "GOVERNANCE passport", "both CSV sets", 68.1, round(same, 1), TOL_PCT)
check("pullback30/scalp30 opposite-direction 28.2% (corrected)", "GOVERNANCE passport", "both CSV sets", 28.2, round(opp, 1), TOL_PCT)

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

# ── Portfolio equity floor (per-account semantics) ───────────────────────────
from risk import EQUITY_FLOOR_USD
from main import check_equity_floor, RESEARCH_ACCOUNTS

check("equity floor constant $800", "GOVERNANCE Portfolio Risk Tolerance", "risk.py EQUITY_FLOOR_USD",
      800.0, EQUITY_FLOOR_USD, 0.001)

status = "PASS" if set(RESEARCH_ACCOUNTS) == {"101-001-39634331-001", "101-001-39634331-002"} else \
    f"DRIFT (RESEARCH_ACCOUNTS = {RESEARCH_ACCOUNTS})"
results.append(("floor covers both research accounts", "GOVERNANCE Portfolio Risk Tolerance",
                "main.py RESEARCH_ACCOUNTS", status))

# Semantics: single-account breach must suspend even when combined sum is healthy
ok, _ = check_equity_floor([("-001", 4000.0), ("-002", 799.99)])
status = "PASS" if not ok else "DRIFT (per-account semantics regressed: combined sum rescued a breached account)"
results.append(("floor semantics: single-account breach suspends fleet (per-account, not combined)",
                "GOVERNANCE Portfolio Risk Tolerance", "main.check_equity_floor()", status))

ok, _ = check_equity_floor([("-001", 800.0), ("-002", 4000.0)])
status = "PASS" if not ok else "DRIFT (exact-touch <=800 no longer breaches)"
results.append(("floor semantics: exact touch (==$800) breaches",
                "GOVERNANCE Portfolio Risk Tolerance", "main.check_equity_floor()", status))

# ── Monitoring-contract amendments present and unambiguous ───────────────────
# 2026-07-02: intraday review trigger shortened to 150 trades / 2026-08-15.
# Verifies the amended trigger is standing in GOVERNANCE.md AND the old
# trigger no longer appears as an active (un-annotated) value.
_gov = (ROOT / "GOVERNANCE.md").read_text(encoding="utf-8")
_has_new = "150 closed trades or 2026-08-15" in _gov
_has_note = "Contract amendment (2026-07-02): intraday review trigger shortened" in _gov
_old_active = re.search(r"300 closed trades or 2026-10-01(?![^|]*AMENDED)", _gov) is not None
status = "PASS" if (_has_new and _has_note and not _old_active) else \
    f"DRIFT (amended trigger present={_has_new}, amendment note={_has_note}, old trigger still active={_old_active})"
results.append(("intraday review trigger = 150 trades / 2026-08-15 (2026-07-02 amendment)",
                "GOVERNANCE monitoring table + contract amendment", "GOVERNANCE.md", status))

# ── Prop-firm compatibility line consistent (2026-07-02) ─────────────────────
# The GOVERNANCE matrix and passport rows must agree with prop_rules.py's
# encoded presets; presence-checked here (full re-derivation = running
# prop_rules.py, which is the manual-section step at review time).
_ok = ("Prop-firm compatibility (reference simulation line" in _gov
       and "deliberately not exhaustive" in _gov
       and (ROOT / "prop_rules.py").exists()
       and all(p in (ROOT / "prop_rules.py").read_text(encoding="utf-8")
               for p in ["FTMO_2STEP", "FTMO_1STEP", "5PERCENTERS_HIGH_STAKES_CLASSIC", "FUNDEDNEXT_FUTURES_LEGACY"]))
results.append(("prop-firm compatibility section + 4 sourced presets standing",
                "GOVERNANCE prop-firm section / prop_rules.py PRESETS",
                "GOVERNANCE.md + prop_rules.py",
                "PASS" if _ok else "DRIFT (section or preset inventory missing/renamed)"))

# ── Harness warm-up covers each plugin's history requirement ─────────────────
# Guards the 2026-07-02 boundary-parity fix (RESEARCH_LOG; diagnosis 631de22):
# for every strategy plugin, the warm-up the harness would derive (declared
# WARMUP_HTF_CANDLES, else backtest.DEFAULT_WARMUP_HTF_CANDLES) must be >= the
# plugin's own minimum-history guard, re-derived from its source -- otherwise
# per-year runs regrow silent dead zones at segment starts.
import importlib.util as _ilu
import backtest as _bt

for _plug in sorted(ROOT.glob("*_plugin.py")):
    _spec = _ilu.spec_from_file_location(f"_audit_{_plug.stem}", _plug)
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _src_text = _plug.read_text(encoding="utf-8")
    _m = re.search(r"len\(htf_df\)\s*<\s*(.+?)(?:\s+or\b|:)", _src_text)
    # Guard expressions may reference simple function-locals (e.g. `needed =
    # _FRACTAL_N * 2 + 2`); re-derive those assignments into the namespace.
    _ns = dict(vars(_mod))
    for _name, _expr in re.findall(r"^\s*(needed)\s*=\s*(.+?)\s*$", _src_text, re.MULTILINE):
        try:
            _ns[_name] = eval(_expr, dict(vars(_mod)))
        except Exception:
            pass
    _guard = int(eval(_m.group(1), _ns)) if _m else 0
    _declared = getattr(_mod, "WARMUP_HTF_CANDLES", None)
    _effective = int(_declared) if _declared is not None else _bt.DEFAULT_WARMUP_HTF_CANDLES
    _src = "declared WARMUP_HTF_CANDLES" if _declared is not None else "DEFAULT_WARMUP_HTF_CANDLES fallback"
    status = "PASS" if _effective >= _guard else \
        f"DRIFT (harness warm-up {_effective} < plugin history guard {_guard})"
    results.append((f"harness warm-up covers {_plug.name} history requirement ({_effective} >= guard {_guard})",
                    f"backtest.py warm-up derivation ({_src})", _plug.name, status))

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
  [ ] Prop-compatibility matrix still matches a fresh prop_rules.py run (re-run if any
      corrected_f86d9f4_* artifact or preset changed since 2026-07-02)
""")
sys.exit(1 if n_drift else 0)
