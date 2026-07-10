"""
Combined-book FTMO prop simulation (registered 2026-07-09, committed before
results). Joint weekly block bootstrap of the four deployed trial slots
through FTMO 2-Step mechanics. See RESEARCH_LOG registration for the spec.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/book_prop_sim.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
RNG = np.random.default_rng(20260709)   # seed = registration date, chosen not tuned

STREAMS = {
    "xau": ("gate2_XAUUSD_trend_origin_pullback_full.csv", 0.005),
    "jpy": ("backtests/corrected_f86d9f4_pullback30_2021-2026ytd.csv", 0.005),
    "spx": ("gate2_SPX_trend_origin_pullback_full.csv", 0.005),
    # btc stream removed 2026-07-09: commission correction voided the record
    # ORB close-variant slots (2026-07-09 deployment, pre-checks `proceed` at 0.5%)
    "ospx": ("orb_SPX_close_full.csv", 0.005),
    "oxau": ("orb_XAUUSD_close_full.csv", 0.005),
    # Campaign 2 Track B (2026-07-09): vol-compression breakout, XAU, deployed.
    "vxau": ("volcomp_XAUUSD_full.csv", 0.005),
    # gap (weekend gap) demoted to benched-weak 2026-07-10 (fixed re-run);
    # tl (trendline) RETIRED 2026-07-10 -- record was fractal-lookahead artifact.
}
COMMON_START, COMMON_END = "2022-10-01", "2026-07-01"
INITIAL = 100_000.0
DAILY_FLOOR = -0.05 * INITIAL          # per calendar day, vs initial (FTMO_2STEP)
MAX_LOSS_EQUITY = 0.90 * INITIAL
N_PATHS = 10_000


def load_streams(haircut=0.0):
    """{week_key: {day_of_week: [(slot, R), ...]}} over the common window."""
    weeks = {}
    for slot, (path, _risk) in STREAMS.items():
        df = pd.read_csv(HERE / path, parse_dates=["time"])
        t = pd.DatetimeIndex(df["time"])
        if t.tz is not None:
            t = t.tz_convert("UTC").tz_localize(None)
        df["t"] = t
        df = df[(df["t"] >= COMMON_START) & (df["t"] < COMMON_END)]
        r = df["pnl"].values / 80.0
        if haircut:
            r = r - haircut * r.mean()
        iso = df["t"].dt.isocalendar()
        for (y, w), dow, R in zip(zip(iso["year"], iso["week"]), df["t"].dt.dayofweek, r):
            weeks.setdefault((y, w), {}).setdefault(int(dow), []).append((slot, float(R)))
    return list(weeks.values())


def run_paths(week_bank, target_pct, horizon_days, risk):
    hits = breaches = 0
    days_to_target = []
    target = INITIAL * (1 + target_pct)
    for _ in range(N_PATHS):
        equity, day_count, done = INITIAL, 0, None
        while day_count < horizon_days and done is None:
            week = week_bank[RNG.integers(len(week_bank))]
            week_equity = equity
            for dow in range(7):
                if day_count >= horizon_days:
                    break
                day_pnl = 0.0
                for slot, R in week.get(dow, []):
                    day_pnl += R * risk[slot] * week_equity
                equity += day_pnl
                day_count += 1
                if day_pnl <= DAILY_FLOOR or equity <= MAX_LOSS_EQUITY:
                    done = "breach"
                    break
                if equity >= target:
                    done = "target"
                    days_to_target.append(day_count)
                    break
        if done == "target":
            hits += 1
        elif done == "breach":
            breaches += 1
    return {
        "P_target": hits / N_PATHS,
        "P_breach": breaches / N_PATHS,
        "P_timeout": 1 - (hits + breaches) / N_PATHS,
        "median_days_to_target": float(np.median(days_to_target)) if days_to_target else None,
    }


def run_paths_1step(week_bank, risk, horizon_days=365):
    """FTMO 1-Step mechanics (registered 2026-07-10, ftmo.com published rules):
    10% target, 3% daily loss, 10% TRAILING max loss from highest EOD balance
    (ratchets up only), 50% best-day rule as a pass CONDITION (path keeps
    trading until satisfied). Day-granular like run_paths: intraday drawdown
    is invisible, so breach is understated -- more so here (3% is tighter)."""
    hits = breaches = 0
    days_to_target = []
    target = INITIAL * 1.10
    daily_floor = -0.03 * INITIAL
    for _ in range(N_PATHS):
        equity, day_count, done = INITIAL, 0, None
        loss_floor = INITIAL - 0.10 * INITIAL
        best_day, pos_sum = 0.0, 0.0
        while day_count < horizon_days and done is None:
            week = week_bank[RNG.integers(len(week_bank))]
            week_equity = equity
            for dow in range(7):
                if day_count >= horizon_days:
                    break
                day_pnl = sum(R * risk[slot] * week_equity
                              for slot, R in week.get(dow, []))
                equity += day_pnl
                day_count += 1
                if day_pnl > 0:
                    pos_sum += day_pnl
                    best_day = max(best_day, day_pnl)
                if day_pnl <= daily_floor or equity <= loss_floor:
                    done = "breach"
                    break
                loss_floor = max(loss_floor, equity - 0.10 * INITIAL)  # EOD ratchet
                if equity >= target and best_day <= 0.5 * pos_sum:
                    done = "target"
                    days_to_target.append(day_count)
                    break
        if done == "target":
            hits += 1
        elif done == "breach":
            breaches += 1
    return {
        "P_target": hits / N_PATHS,
        "P_breach": breaches / N_PATHS,
        "P_timeout": 1 - (hits + breaches) / N_PATHS,
        "median_days_to_target": float(np.median(days_to_target)) if days_to_target else None,
    }


def main():
    risk = {slot: r for slot, (_p, r) in STREAMS.items()}
    out = {}
    for label, haircut in (("as-measured", 0.0), ("haircut-25", 0.25), ("haircut-50", 0.50)):
        bank = load_streams(haircut)
        out[label] = {
            "challenge_10pct_90d": run_paths(bank, 0.10, 90, risk),
            "trial_5pct_13d": run_paths(bank, 0.05, 13, risk),
            "onestep_10pct_365d": run_paths_1step(bank, risk),
        }
        print(label, json.dumps(out[label], indent=1))
    (HERE / "book_prop_sim_results.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
