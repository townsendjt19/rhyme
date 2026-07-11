"""
Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014) over the roster, using
failure_db.json as the search denominator.

Why this exists (expert-review action, 2026-07-10): the live flagships were
grandfathered before pre-registration began, and the killed-hypothesis ledger
shows the survivors emerged from a wide search (e.g. 8 pairs tested for
trend-origin, 8 rejected, USD_JPY sole survivor). When one candidate survives
N trials, part of its measured Sharpe is selection. DSR asks: what is the
probability the observed Sharpe exceeds the maximum Sharpe expected from N
skill-less trials?

Method (weekly returns from sortino.weekly_returns -- the registered box-8
convention, flat weeks = 0%):
  SR_hat   = mean(weekly) / std(weekly)                       (per-week, not annualized)
  SR0      = sqrt(1/T) * ((1-g)*z(1-1/N) + g*z(1-1/(N*e)))    (expected max of N null SRs;
             g = Euler-Mascheroni; null SR-estimator stdev approximated sqrt(1/T))
  DSR      = Phi( (SR_hat - SR0) * sqrt(T-1)
                  / sqrt(1 - skew*SR_hat + (kurt-1)/4 * SR_hat^2) )
DSR ~ 1.0: Sharpe unlikely to be a selection artifact. DSR < 0.95: cannot
rule out that the best of N junk trials looks this good.

MANDATORY CAVEATS (printed with every run):
- N is a FLOOR: failure_db has one entry per killed strategy/cell, but
  implicit trials (parameter probes, pair sweeps folded into one entry,
  ideas killed before registration existed) are undercounted. True N is
  higher, so true DSR is LOWER than printed.
- Trials are heterogeneous (different universes, timeframes, kill stages) --
  the iid-null max is an approximation, not an adjudication.
- The weekly flat-week convention flatters sparse strategies (the spreads),
  exactly as documented on the box-8 table.
This script RANKS and CONTEXTUALIZES; it does not adjudicate. No roster
action follows from it automatically.

Run: D:/workspace/rhyme/venv/Scripts/python.exe deflated_sharpe.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
from scipy.stats import kurtosis, norm, skew

from sortino import ROSTER, weekly_returns

ROOT = Path(__file__).parent
FAILURE_DB = ROOT / "failure_db.json"
EULER_GAMMA = 0.5772156649015329


def n_trials() -> tuple[int, str]:
    """Search denominator: killed hypotheses + everything on the roster
    (live, probation, benched -- each was itself a trial)."""
    db = json.loads(FAILURE_DB.read_text(encoding="utf-8"))
    n_killed = len(db["entries"])
    n_roster = len(ROSTER)
    n = n_killed + n_roster
    derivation = (f"N = {n_killed} failure_db entries + {n_roster} roster strategies "
                  f"= {n} trials (a FLOOR -- implicit trials undercounted)")
    return n, derivation


def expected_max_sharpe(n: int, t: int) -> float:
    """E[max SR] across n independent skill-less trials of length t, with the
    null SR-estimator stdev approximated as sqrt(1/t)."""
    if n < 1 or t < 2:
        return 0.0
    if n == 1:
        return 0.0
    return math.sqrt(1.0 / t) * (
        (1 - EULER_GAMMA) * norm.ppf(1 - 1.0 / n)
        + EULER_GAMMA * norm.ppf(1 - 1.0 / (n * math.e))
    )


def deflated_sharpe(weekly: pd.Series, n: int) -> dict:
    t = len(weekly)
    sd = weekly.std(ddof=1)
    if t < 3 or sd == 0 or math.isnan(sd):
        return {"weeks": t, "sr_wk": float("nan"), "sr0_wk": float("nan"),
                "dsr": float("nan")}
    sr = weekly.mean() / sd
    sr0 = expected_max_sharpe(n, t)
    g3 = float(skew(weekly))
    g4 = float(kurtosis(weekly, fisher=False))   # normal = 3
    denom = 1 - g3 * sr + (g4 - 1) / 4.0 * sr**2
    if denom <= 0:
        return {"weeks": t, "sr_wk": sr, "sr0_wk": sr0, "dsr": float("nan")}
    z = (sr - sr0) * math.sqrt(t - 1) / math.sqrt(denom)
    return {"weeks": t, "sr_wk": sr, "sr0_wk": sr0, "dsr": float(norm.cdf(z)),
            "skew": g3, "kurt": g4}


def table() -> pd.DataFrame:
    n, _ = n_trials()
    rows = []
    for name, csv in ROSTER.items():
        st = deflated_sharpe(weekly_returns(csv), n)
        rows.append({"strategy": name, **st})
    return pd.DataFrame(rows).sort_values("dsr", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    n, derivation = n_trials()
    t = table()
    print("Deflated Sharpe Ratio (Bailey & Lopez de Prado) -- ranked")
    print(f"  {derivation}")
    print("  CAVEATS: N is a floor (true DSR lower than printed); trials are")
    print("  heterogeneous; flat-week convention flatters sparse strategies.")
    print("  This table ranks and contextualizes -- it does NOT adjudicate.")
    for _, r in t.iterrows():
        print(f"  {r['strategy']:18s} DSR {r['dsr']:5.3f}   weekly SR {r['sr_wk']:+.3f} "
              f"vs E[max null SR] {r['sr0_wk']:.3f}   weeks {int(r['weeks']):3d}   "
              f"skew {r.get('skew', float('nan')):+.2f}  kurt {r.get('kurt', float('nan')):.1f}")
