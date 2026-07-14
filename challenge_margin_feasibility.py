"""
Challenge-prep Phases 2+3 (approved plan 2026-07-13; Phase-1 rules verified
and cited in RESEARCH_LOG the same day). Committed before results.

Section A — holding-profile audit: per deployed slot's validated record,
the share of trades (and of net P&L) closed same ET day / overnight /
crossing a weekend. Evidence base for what funded-Standard's weekend-flat
rule would cost.

Section B — margin feasibility: per-trade notional = risk$ x entry/|entry-sl|
(exact for USD-quoted linear instruments and USD-base FX; contract
conventions cancel). Margin distributions at the VERIFIED per-class
leverage, worst-case aggregate-cap-4 stacks, vs a conservative <=50%
utilization target at the $93k equity floor (FTMO publishes no fixed
stop-out; RESEARCH_LOG Phase-1 entry).

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/challenge_margin_feasibility.py
"""
from pathlib import Path

import pandas as pd

from orb_friday_killtest import friday_deadline_utc

HERE = Path(__file__).parent
INITIAL = 100_000.0
EQUITY_FLOOR = 93_000.0          # the bot's own floor guard
UTIL_TARGET = 0.50               # conservative stop-out headroom target

# Verified leverage (RESEARCH_LOG 2026-07-13 Phase-1 entry): XAU pairs
# 1:50/1:15 since 2026-02-01; indices 1:50/1:15; non-XAU metals 1:30/1:9;
# FX 1:100/1:30. (standard, swing)
LEVERAGE = {
    "XAUUSD": (50, 15), "US500": (50, 15), "XAGUSD": (30, 9), "USDJPY": (100, 30),
}

# Slot -> (record CSV, per-POSITION risk fraction of initial, instrument)
SLOTS = {
    "xau":  ("gate2_XAUUSD_trend_origin_pullback_full.csv", 0.005, "XAUUSD"),
    "jpy":  ("backtests/corrected_f86d9f4_pullback30_2021-2026ytd.csv", 0.005, "USDJPY"),
    # mixed-k (2026-07-10): spx runs max_pos 3 at risk/3 per position
    "spx":  ("gate2_SPX_trend_origin_pullback_full.csv", 0.005 / 3, "US500"),
    "ospx": ("orb_SPX_close_full.csv", 0.005, "US500"),
    "oxau": ("orb_XAUUSD_close_full.csv", 0.005, "XAUUSD"),
    "vxau": ("volcomp_XAUUSD_full.csv", 0.005, "XAUUSD"),
    # benched candidate, included for the deployment-decision table
    "xag":  ("gate2xagreal_trend_origin_pullback_full.csv", 0.0025, "XAGUSD"),
}


def load(rel):
    df = pd.read_csv(HERE / rel, parse_dates=["time", "exit_time"])
    for c in ("time", "exit_time"):
        if df[c].dt.tz is None:
            df[c] = df[c].dt.tz_localize("UTC")
    return df.dropna(subset=["exit_time"])


def holding_profile(df):
    et_entry = df["time"].dt.tz_convert("America/New_York")
    et_exit = df["exit_time"].dt.tz_convert("America/New_York")
    same_day = et_entry.dt.date == et_exit.dt.date
    deadline = df["time"].map(friday_deadline_utc)
    weekend = df["exit_time"] >= deadline
    overnight = ~same_day & ~weekend
    net = df["pnl"].sum()
    out = {}
    for label, mask in (("same_day", same_day), ("overnight", overnight), ("weekend", weekend)):
        out[label] = (mask.mean() * 100, df.loc[mask, "pnl"].sum(),
                      100 * df.loc[mask, "pnl"].sum() / net if net else float("nan"))
    return out, net


def main():
    print("=== Section A: holding profile (share of trades / P&L share of net) ===")
    margins = {}
    for slot, (rel, riskf, inst) in SLOTS.items():
        df = load(rel)
        prof, net = holding_profile(df)
        cells = "  ".join(f"{k}: {v[0]:4.1f}% of trades, ${v[1]:+8.0f} ({v[2]:+5.1f}% of net)"
                          for k, v in prof.items())
        print(f"  {slot:5s} n={len(df):4d} net=${net:+9.0f}  {cells}")

        # Section B inputs: notional at deployed risk on $100k
        risk_usd = riskf * INITIAL
        stop = (df["entry"] - df["sl"]).abs()
        notional = risk_usd * df["entry"] / stop
        margins[slot] = (inst, notional)

    print(f"\n=== Section B: margin at deployed risk on ${INITIAL:,.0f} "
          f"(notional = risk x entry/stop) ===")
    print(f"  {'slot':5s} {'inst':7s} {'risk$':>6s}   {'notional p50/p90/max':>32s}   "
          f"{'STD margin p90/max':>22s}   {'SWG margin p90/max':>22s}")
    rows = {}
    for slot, (inst, notional) in margins.items():
        lev_s, lev_w = LEVERAGE[inst]
        p50, p90, mx = notional.quantile(0.5), notional.quantile(0.9), notional.max()
        risk_usd = SLOTS[slot][1] * INITIAL
        rows[slot] = {"std_p90": p90 / lev_s, "std_max": mx / lev_s,
                      "swg_p90": p90 / lev_w, "swg_max": mx / lev_w,
                      "notional": notional, "lev": (lev_s, lev_w)}
        print(f"  {slot:5s} {inst:7s} {risk_usd:6.0f}   "
              f"${p50/1e3:6.0f}k ${p90/1e3:6.0f}k ${mx/1e3:7.0f}k   "
              f"${p90/lev_s/1e3:7.1f}k ${mx/lev_s/1e3:8.1f}k   "
              f"${p90/lev_w/1e3:7.1f}k ${mx/lev_w/1e3:8.1f}k")

    print("\n=== Worst-case stacks (aggregate cap 4 positions) ===")
    # deployed-book worst combination: the four largest p90 single-position
    # margins (spx counts up to 3 of its per-position margins)
    for label, key in (("p90", "p90"), ("max", "max")):
        cands = []
        for slot, r in rows.items():
            if slot == "xag":
                continue
            reps = 3 if slot == "spx" else 1
            cands += [(slot, r[f"std_{key}"], r[f"swg_{key}"])] * reps
        for acct, idx in (("STANDARD", 1), ("SWING", 2)):
            top = sorted(cands, key=lambda x: -x[idx])[:4]
            tot = sum(x[idx] for x in top)
            util = tot / EQUITY_FLOOR * 100
            names = "+".join(x[0] for x in top)
            print(f"  {label:3s} {acct:8s}: {names:24s} margin ${tot/1e3:6.1f}k "
                  f"= {util:5.1f}% of ${EQUITY_FLOOR/1e3:.0f}k floor equity "
                  f"({'OK' if util <= UTIL_TARGET*100 else 'EXCEEDS 50% TARGET'})")

    print("\n=== Margin-guard cost (share of historical trades whose SINGLE-position "
          "margin exceeds 25% of floor equity) ===")
    budget = 0.25 * EQUITY_FLOOR
    for slot, r in rows.items():
        lev_s, lev_w = r["lev"]
        n = len(r["notional"])
        std = (r["notional"] / lev_s > budget).mean() * 100
        swg = (r["notional"] / lev_w > budget).mean() * 100
        print(f"  {slot:5s}: STANDARD {std:5.1f}%   SWING {swg:5.1f}%   (n={n})")


if __name__ == "__main__":
    main()
