"""
Signal-frequency monitor -- the pre-registered leading indicator for the
"edge-to-zero" failure mode (RESEARCH_LOG registration 2026-07-10, written
BEFORE any forward ledger data existed).

The trend family's documented failure mode is not drawdown but signal
starvation: when the dominant trend structure stops forming (HH/HL flatline,
EUR_JPY 2025-2026 being the live preview), signals and P&L go to zero and no
drawdown trigger ever fires -- only the probation calendar catches it, months
late. This script turns that into a fast flag:

  forward signal rate (rolling window, from signal_stats.ndjson, written by
  main._log_signal_stat each cycle)   vs   backtest baseline trades/week
  (backtests/corrected_f86d9f4_*.csv, resampled W-FRI like sortino.py)

REGISTERED THRESHOLD (fixed before data): rolling 4-week forward signal rate
below 25% of the backtest baseline -> review FLAG. Flag only -- suspend/
retire decisions remain the operator's per GOVERNANCE.

MEASUREMENT BIAS, stated up front: the backtest baseline counts FILLED
trades (post-gate), while the forward ledger counts RAW plugin signals
(pre-gate: position caps, margin, exposure gates all sit between a signal
and a fill). The forward rate is therefore biased HIGH relative to baseline,
so a ratio falling below the threshold is EXTRA meaningful, and a healthy
ratio must not be over-read.

Report:  D:/workspace/rhyme/venv/Scripts/python.exe signal_frequency.py
Check :  ... signal_frequency.py --check     (alerts on breach; watchdog-safe)
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
BT = ROOT / "backtests"
LEDGER = ROOT / "signal_stats.ndjson"

# Live modes with entry-signal backtest records. spread2b is excluded: its
# ledger writes come from spread_trader (different granularity, ~4 signals
# a YEAR by design -- a weekly-rate monitor is structurally uninformative).
ROSTER = {
    "intraday":   "corrected_f86d9f4_intraday_2021-2026ytd.csv",
    "scalp30":    "corrected_f86d9f4_scalp30_2021-2026ytd.csv",
    "pullback30": "corrected_f86d9f4_pullback30_2021-2026ytd.csv",
}

SIGNAL_FREQ_ALERT_RATIO = 0.25   # registered 2026-07-10, fixed before data
SIGNAL_FREQ_MIN_WEEKS = 4        # no flag before this much forward ledger


def baseline_weekly_rate(csv_name: str) -> float:
    """Mean trades/week over the full backtest record (flat weeks included,
    same W-FRI convention as sortino.py)."""
    df = pd.read_csv(BT / csv_name, parse_dates=["time"]).sort_values("time")
    idx = pd.DatetimeIndex(df["time"]).tz_localize(None)
    weekly = pd.Series(1, index=idx).resample("W-FRI").sum()
    return float(weekly.mean()) if len(weekly) else 0.0


def load_ledger(path: Path | None = None) -> pd.DataFrame:
    """Parse the NDJSON ledger, skipping torn/garbage lines (4 concurrent
    writers -- a torn tail line is expected and harmless). `path` resolves
    to the module-level LEDGER at call time (tests repoint it)."""
    path = path if path is not None else LEDGER
    rows = []
    if not path.exists():
        return pd.DataFrame(columns=["ts", "mode", "instrument", "signal"])
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    df = pd.DataFrame(rows)
    if len(df):
        df["ts"] = pd.to_datetime(df["ts"], format="ISO8601", utc=True)
    return df


def forward_weekly_rate(ledger: pd.DataFrame, mode: str, weeks: int = SIGNAL_FREQ_MIN_WEEKS,
                        now: datetime | None = None) -> tuple[float, float]:
    """(signals/week over the trailing window, weeks of ledger coverage for
    this mode). Coverage is measured from the mode's first ledger line."""
    now = now or datetime.now(tz=timezone.utc)
    sub = ledger[ledger["mode"] == mode] if len(ledger) else ledger
    if not len(sub):
        return 0.0, 0.0
    coverage_weeks = (now - sub["ts"].min()).total_seconds() / (7 * 86400)
    window = sub[sub["ts"] >= now - timedelta(weeks=weeks)]
    n_signals = int(window["signal"].sum())
    return n_signals / weeks, coverage_weeks


def table(now: datetime | None = None) -> pd.DataFrame:
    ledger = load_ledger()
    rows = []
    for mode, csv in ROSTER.items():
        base = baseline_weekly_rate(csv)
        fwd, coverage = forward_weekly_rate(ledger, mode, now=now)
        ratio = fwd / base if base > 0 else float("nan")
        rows.append({"mode": mode, "baseline_sig_wk": base, "fwd_4wk_sig_wk": fwd,
                     "ratio": ratio, "coverage_weeks": coverage,
                     "flag": coverage >= SIGNAL_FREQ_MIN_WEEKS and ratio < SIGNAL_FREQ_ALERT_RATIO})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="alert (via alerts.py) on any flagged mode; used by watchdog")
    args = ap.parse_args()

    t = table()
    print("Signal-frequency monitor (registered threshold: 4-week forward rate < "
          f"{SIGNAL_FREQ_ALERT_RATIO:.0%} of backtest baseline -> review flag)")
    print("BIAS NOTE: baseline counts post-gate FILLS, forward counts pre-gate raw")
    print("signals -- forward is biased high, so a low ratio is extra meaningful.")
    for _, r in t.iterrows():
        cov = (f"{r['coverage_weeks']:.1f} wks ledger"
               if r["coverage_weeks"] > 0 else "no ledger data")
        status = "FLAG" if r["flag"] else ("--" if r["coverage_weeks"] >= SIGNAL_FREQ_MIN_WEEKS
                                           else "insufficient forward weeks")
        print(f"  {r['mode']:12s} baseline {r['baseline_sig_wk']:6.1f}/wk   "
              f"fwd 4wk {r['fwd_4wk_sig_wk']:6.1f}/wk   ratio {r['ratio']:5.2f}   "
              f"[{cov}]  {status}")

    if args.check:
        import alerts
        for _, r in t[t["flag"]].iterrows():
            alerts.send_alert(
                f"signal-frequency review flag: {r['mode']} forward rate "
                f"{r['fwd_4wk_sig_wk']:.1f}/wk is {r['ratio']:.0%} of backtest baseline "
                f"{r['baseline_sig_wk']:.1f}/wk (registered threshold "
                f"{SIGNAL_FREQ_ALERT_RATIO:.0%}) -- possible edge-to-zero regime; "
                f"operator review (flag only, no automatic action)",
                key=f"sigfreq:{r['mode']}",
            )


if __name__ == "__main__":
    main()
