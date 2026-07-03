"""
Account-size feasibility checker — read-only analysis, places no orders,
touches no live credentials. Generalizes the 2026-07-02 manual scalp30
analysis (GOVERNANCE prop-section note) across the validated roster.

For a validated strategy's corrected trade record it computes, at a given
risk fraction and account balance:
  - per-trade required units at OANDA's true 1-unit granularity
    (units scale linearly from the $80-fixed-risk record: u = units_80 * riskS/80);
  - rounding-induced risk distortion (0.5/u worst-case per trade);
  - margin per position and for the strategy's typical concurrency.

VERDICT RULES (fixed here, not tuned per run):
  NOT WORKABLE  median trade sizes < 1 unit, OR one median-trade margin
                > 60% of balance (the fleet's utilization cap convention).
  DISTORTED     the wide-stop tail (5th-percentile units_80 trade) sizes
                < 25 whole units (> 2% rounding risk error), OR full typical
                concurrency margin > 60% of balance.
  VIABLE        tail >= 25 units AND typical-concurrency margin fits.

Margin assumes the LIVE-US 50:1 (2%) rate on majors — this checker feeds the
live-side Phase 2 funding decision (practice runs 20:1; margins there are
2.5x these figures). USD-per-base-unit uses analysis-grade approximations.

Usage:
    D:/rhyme/venv/Scripts/python.exe D:/rhyme/account_feasibility.py [risk_pct]
"""
from __future__ import annotations
import math
import sys
from pathlib import Path

import pandas as pd

BT = Path(__file__).parent / "backtests"
BALANCES = [99, 250, 500, 1000, 2000, 4000, 10000]
MARGIN_RATE = 0.02          # live US 50:1
MARGIN_CAP = 0.60           # fleet utilization-cap convention
TAIL_MIN_UNITS = 25         # 2% worst-case rounding error
USD_PER_BASE = {"USD": 1.00, "EUR": 1.08, "GBP": 1.27, "AUD": 0.66,
                "NZD": 0.60, "CAD": 0.73, "CHF": 1.24}

STRATEGIES = {
    "intraday":   {"csv": "corrected_f86d9f4_intraday_2021-2026ytd.csv", "concurrency": 5},
    "scalp30":    {"csv": "corrected_f86d9f4_scalp30_2021-2026ytd.csv", "concurrency": 1},
    "pullback30": {"csv": "corrected_f86d9f4_pullback30_2021-2026ytd.csv", "concurrency": 1},
}


def usd_per_unit(pair: str) -> float:
    return USD_PER_BASE.get(pair.split("_")[0], 1.0)


def donchian_family(name: str, cfg: dict, risk_pct: float) -> dict:
    df = pd.read_csv(BT / cfg["csv"])
    if "pair" not in df.columns:
        df["pair"] = "USD_JPY"
    df["notional_per_unit"] = df["pair"].map(usd_per_unit)
    rows = {}
    for bal in BALANCES:
        scale = (bal * risk_pct) / 80.0
        u = (df["units"] * scale)
        tail_u = u.quantile(0.05)
        med_u = u.median()
        med_margin = (u * df["notional_per_unit"]).median() * MARGIN_RATE
        conc_margin = med_margin * cfg["concurrency"]
        if med_u < 1 or med_margin > MARGIN_CAP * bal:
            verdict = "NOT WORKABLE"
        elif tail_u < TAIL_MIN_UNITS or conc_margin > MARGIN_CAP * bal:
            verdict = "DISTORTED"
        else:
            verdict = "VIABLE"
        rows[bal] = {"verdict": verdict, "tail_units": tail_u, "median_units": med_u,
                     "tail_err_pct": 50.0 / tail_u if tail_u > 0 else float("inf"),
                     "conc_margin_pct": conc_margin / bal * 100}
    # minimum viable balance: tail>=25 units AND concurrency margin fits
    u5_at_80 = df["units"].quantile(0.05)
    b_tail = TAIL_MIN_UNITS * 80.0 / (u5_at_80 * risk_pct)
    med_margin_frac = (df["units"] * df["notional_per_unit"]).median() * MARGIN_RATE \
        * cfg["concurrency"] * risk_pct / 80.0    # margin as a fraction of B is balance-INDEPENDENT
    b_min = b_tail if med_margin_frac <= MARGIN_CAP else float("inf")
    return {"rows": rows, "min_viable": b_min}


def spread2b(risk_pct: float) -> dict:
    df = pd.read_csv(BT / "corrected_f86d9f4_nzdcad_spread_2021-2026ytd.csv")
    # units column = y-leg USD notional at $80 risk; sigma/beta per trade.
    rows = {}
    for bal in BALANCES:
        scale = (bal * risk_pct) / 80.0
        y_notional = df["units"] * scale
        y_units = y_notional / 0.60                  # NZD_USD base
        x_notional = df["beta"].abs() * y_notional   # USD_CAD base = USD
        tail_u = min(y_units.quantile(0.05), x_notional.quantile(0.05))
        med_u = min(y_units.median(), x_notional.median())
        idea_margin = ((y_notional + x_notional) * MARGIN_RATE).median()
        if med_u < 1 or idea_margin > MARGIN_CAP * bal:
            verdict = "NOT WORKABLE"
        elif tail_u < TAIL_MIN_UNITS:
            verdict = "DISTORTED"
        else:
            verdict = "VIABLE"
        rows[bal] = {"verdict": verdict, "tail_units": tail_u, "median_units": med_u,
                     "tail_err_pct": 50.0 / tail_u if tail_u > 0 else float("inf"),
                     "conc_margin_pct": idea_margin / bal * 100}
    y5 = (df["units"].quantile(0.05)) / 0.60
    x5 = (df["beta"].abs() * df["units"]).quantile(0.05)
    b_min = TAIL_MIN_UNITS * 80.0 / (min(y5, x5) * risk_pct)
    return {"rows": rows, "min_viable": b_min}


def main(risk_pct: float = 0.01) -> None:
    print(f"=== Account feasibility at {risk_pct:.1%} risk/trade, 1-unit granularity, "
          f"live 50:1 margin, {MARGIN_CAP:.0%} utilization cap ===\n")
    results = {name: donchian_family(name, cfg, risk_pct) for name, cfg in STRATEGIES.items()}
    results["spread2b"] = spread2b(risk_pct)

    header = f"{'strategy':<12}" + "".join(f"{('$'+format(b, ',')):>12}" for b in BALANCES) + f"{'min viable':>14}"
    print(header)
    for name, r in results.items():
        line = f"{name:<12}"
        for b in BALANCES:
            line += f"{r['rows'][b]['verdict']:>12}"
        mv = r["min_viable"]
        line += f"{('$' + format(int(math.ceil(mv)), ',')) if mv != float('inf') else 'margin-bound':>14}"
        print(line)

    print("\n--- detail: tail units (5th pct) / worst rounding error / concurrency margin %% of balance ---")
    for name, r in results.items():
        print(f"\n{name}:")
        for b in BALANCES:
            d = r["rows"][b]
            print(f"  ${b:>6,}: tail {d['tail_units']:8.0f}u  err {d['tail_err_pct']:6.2f}%  "
                  f"concurrency margin {d['conc_margin_pct']:5.1f}%  -> {d['verdict']}")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.01)
