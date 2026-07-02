"""
Parameterized prop-firm rule checker over corrected-harness backtest data.

Post-processing only: consumes the trade series + stop-bounded worst-case
floating-PnL marks collected once per strategy at $80 fixed risk (R-multiples
and R-marks are sizing-invariant; fixed-fractional risk levels are exact
post-processing). See RESEARCH_LOG 2026-07-02 FTMO entries for conventions:
$100k notional, UTC day boundary, daily baseline = closed balance at day
start, conservative simultaneous-worst marking, historical same-instrument
stacking that live gates prohibit.

Three distinct drawdown mechanics (not parameter variants of each other):
  static        — floor fixed at initial*(1 - pct/100), set once at open
  trailing_eod  — floor = (1 - pct/100) * running peak EOD closed balance
  trailing_lock — floor = min(peak EOD closed balance - buffer, initial),
                  buffer = pct/100 * initial; trails up, LOCKS at initial
                  once accumulated profit equals the buffer (FundedNext MLL)

Preset sources are dated in each preset's `source` field — firm's own pages
only, per the 2026-07-02 verification rule. New presets are added when a
specific firm becomes relevant, not preemptively (GOVERNANCE.md, prop-firm
compatibility section).

Usage:
    D:/rhyme/venv/Scripts/python.exe D:/rhyme/prop_rules.py [strategy ...]
Requires backtests/corrected_f86d9f4_{strategy}_2021-2026ytd.csv and
backtests/corrected_f86d9f4_{strategy}_marks.pkl (regenerate with a
collect_marks=True per-year pass if absent).
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
BT = ROOT / "backtests"
INITIAL = 100_000.0
RISK_LEVELS = [0.0025, 0.005, 0.01]
STRATEGIES = ["intraday", "scalp30", "pullback30", "swing"]

PRESETS = {
    "FTMO_2STEP": {
        "daily_loss_pct": 5.0,
        "drawdown": ("static", 10.0),
        "target_pct": 10.0,       # Phase 1; Phase 2 is 5%, not separately simulated
        "consistency": None,       # none formally enforced
        "source": "FTMO account comparison page screenshots (user-provided), 2026-07-02",
    },
    "FTMO_1STEP": {
        "daily_loss_pct": 3.0,
        "drawdown": ("trailing_eod", 10.0),
        "target_pct": 10.0,
        "consistency": ("best_day_share", 50.0),
        "source": "FTMO account comparison page screenshots (user-provided), 2026-07-02",
    },
    "5PERCENTERS_HIGH_STAKES_CLASSIC": {
        "daily_loss_pct": 5.0,     # vs previous day's closing equity/balance (higher), 00:00 server
        "drawdown": ("static", 10.0),
        "target_pct": 8.0,         # CLASSIC High Stakes Phase 1 (New variant is 10%); Phase 2 5%
        "consistency": ("min_profitable_days", 3, 0.5),  # >=3 days with closed profit >=0.5% of initial
        # NOTE: the 30% single-day consistency cap does NOT apply to High
        # Stakes (it is a per-position rule in The5%ers FUTURES programs) —
        # verified before encoding, per the confirm-first instruction.
        "source": "help.the5ers.com 'general rules for the High Stakes Program' + drawdown FAQ, fetched 2026-07-02",
    },
    "FUNDEDNEXT_FUTURES_LEGACY": {
        "daily_loss_pct": None,    # Legacy has NO daily loss limit (Bolt does: $1,000/50K)
        "drawdown": ("trailing_lock", 3.0),   # $3,000 MLL on 100K, EOD-trailing, locks at initial
        "target_pct": 6.0,         # $6,000 on 100K
        "consistency": ("best_day_share", 40.0),  # challenge phase
        # Futures program: the drawdown MECHANIC is what is modeled; the
        # underlying data here is FX. Documented asset-class mismatch.
        "source": "fundednext.com/general-rules/futures/trading-objectives, fetched 2026-07-02",
    },
}


def load(strat: str):
    tr = pd.read_csv(BT / f"corrected_f86d9f4_{strat}_2021-2026ytd.csv",
                     parse_dates=["time", "exit_time"]).sort_values("time").reset_index(drop=True)
    tr["R"] = tr["pnl"] / 80.0
    mk = pd.read_pickle(BT / f"corrected_f86d9f4_{strat}_marks.pkl")
    mk["time"] = pd.to_datetime(mk["time"], utc=True)
    mk["R"] = mk["mark"] / 80.0
    return tr, mk


def build_curves(tr, mk, f, start=None, initial=INITIAL):
    """Fixed-fractional equity curves; rules-agnostic. Returns None if no trades."""
    t = tr if start is None else tr[tr["time"] >= start]
    if len(t) == 0:
        return None
    t = t.sort_values("time")

    entries = list(zip(t["time"], t["trade_id"], t["R"], t["exit_time"]))
    exits = sorted(((r[3], r[1], r[2]) for r in entries), key=lambda x: x[0])
    scale, bal, ei = {}, initial, 0
    for ent_time, tid, R, _ in entries:
        while ei < len(exits) and exits[ei][0] < ent_time:
            _, xid, xR = exits[ei]
            if xid in scale:
                bal += xR * scale[xid]
            ei += 1
        scale[tid] = f * bal

    m = mk[mk["trade_id"].isin(scale)].copy()
    m["fl"] = m["R"] * m["trade_id"].map(scale)
    fl_sum = m.groupby("time")["fl"].sum().sort_index()

    x = t.copy()
    x["pnl_f"] = x["R"] * x["trade_id"].map(scale)
    x = x.sort_values("exit_time")
    closed = x.set_index("exit_time")["pnl_f"].groupby(level=0).sum().cumsum()

    pos = closed.index.searchsorted(fl_sum.index, side="left")
    cum = np.concatenate([[0.0], closed.values])
    equity_low = pd.Series(initial + cum[pos] + fl_sum.values, index=fl_sum.index)
    return {"closed": closed, "cum": cum, "equity_low": equity_low, "trades": x, "initial": initial}


def check_preset(curves, preset, initial=INITIAL):
    closed, cum, equity_low = curves["closed"], curves["cum"], curves["equity_low"]
    dates = equity_low.index.tz_convert("UTC").normalize()
    day_min = equity_low.groupby(dates).min()
    days = day_min.index

    out = {}

    # Daily loss (baseline = closed balance at UTC day start; see conventions)
    if preset["daily_loss_pct"] is not None:
        pos_mid = closed.index.searchsorted(days, side="left")
        baseline = initial + cum[pos_mid]
        dd = (day_min.values - baseline) / baseline * 100
        lim = -preset["daily_loss_pct"]
        wi = int(np.argmin(dd))
        first = days[dd <= lim]
        out.update(worst_daily_pct=float(dd[wi]), worst_daily_date=str(days[wi].date()),
                   daily_breaches=int((dd <= lim).sum()),
                   first_daily=str(first[0].date()) if len(first) else None)
    else:
        out.update(worst_daily_pct=None, daily_breaches=0, first_daily=None)

    # Drawdown floor per mechanic
    mech, pct = preset["drawdown"]
    eod_pos = closed.index.searchsorted(days + pd.Timedelta(days=1), side="left")
    eod_bal = initial + cum[eod_pos]
    prior_peak = np.maximum.accumulate(np.concatenate([[initial], eod_bal]))[:-1]
    if mech == "static":
        floor = np.full(len(days), initial * (1 - pct / 100))
    elif mech == "trailing_eod":
        floor = (1 - pct / 100) * prior_peak
    elif mech == "trailing_lock":
        buffer = pct / 100 * initial
        floor = np.minimum(prior_peak - buffer, initial)
    else:
        raise ValueError(mech)
    breach = (day_min.values < floor) | (eod_bal < floor)
    firstf = days[breach]
    out.update(floor_mech=mech, floor_breaches=int(breach.sum()),
               first_floor=str(firstf[0].date()) if len(firstf) else None,
               worst_floor_gap_pct=float(np.min(np.minimum(day_min.values, eod_bal) - floor) / initial * 100))

    # Consistency (reported; gates passing/payout, not account survival)
    x = curves["trades"]
    day_pnl = x.groupby(x["exit_time"].dt.tz_convert("UTC").dt.normalize())["pnl_f"].sum()
    total = day_pnl.sum()
    c = preset["consistency"]
    if c is None:
        out["consistency"] = "n/a"
    elif c[0] == "best_day_share":
        share = day_pnl.max() / total * 100 if total > 0 else float("nan")
        out["consistency"] = f"best day {share:.1f}% vs {c[1]:.0f}% cap ({'ok' if share <= c[1] else 'VIOLATES'})" \
            if total > 0 else "n/a (net negative)"
    elif c[0] == "min_profitable_days":
        n_prof = int((day_pnl >= c[2] / 100 * initial).sum())
        out["consistency"] = f"{n_prof} profitable days vs min {c[1]} ({'ok' if n_prof >= c[1] else 'VIOLATES'})"

    out["survives"] = out["daily_breaches"] == 0 and out["floor_breaches"] == 0
    out["final_bal"] = initial + float(closed.iloc[-1])
    return out


# ── Cheap prop-shape pre-check (2026-07-02 process amendment) ─────────────────
# Run on a kill-test / crown-jewel-equivalent stretch BEFORE an expensive full
# window: worst trailing-floor-style peak-to-trough drawdown (peak = running
# max EOD closed balance, trough = worst intraday equity or EOD balance) at
# 0.25%/0.50%. "Prop-deprioritized" iff the margin is blown by more than
# WIDE_MARGIN_FACTOR x EVERY trailing preset's threshold at BOTH risk levels
# (thresholds: FTMO 1-Step 10%, FundedNext Legacy 3%; 2x the loosest = 20%
# is therefore the binding test). Deprioritized does NOT mean discarded --
# it gates research-time priority toward the prop track, not validity.
PRECHECK_RISK_LEVELS = [0.0025, 0.005]
TRAILING_THRESHOLDS = {"FTMO_1STEP trailing_eod": 10.0, "FUNDEDNEXT_FUTURES_LEGACY trailing_lock": 3.0}
WIDE_MARGIN_FACTOR = 2.0


def trailing_precheck(tr, mk, initial=INITIAL):
    out = {"levels": {}}
    blown_everywhere = True
    for f in PRECHECK_RISK_LEVELS:
        curves = build_curves(tr, mk, f)
        if curves is None:
            return {"verdict": "no-trades", "levels": {}}
        closed, cum, equity_low = curves["closed"], curves["cum"], curves["equity_low"]
        dates = equity_low.index.tz_convert("UTC").normalize()
        day_min = equity_low.groupby(dates).min()
        days = day_min.index
        eod_pos = closed.index.searchsorted(days + pd.Timedelta(days=1), side="left")
        eod_bal = initial + cum[eod_pos]
        prior_peak = np.maximum.accumulate(np.concatenate([[initial], eod_bal]))[:-1]
        trough = np.minimum(day_min.values, eod_bal)
        dd_pct = float(np.min((trough - prior_peak) / prior_peak) * 100)   # negative
        blown = {name: -dd_pct > WIDE_MARGIN_FACTOR * t for name, t in TRAILING_THRESHOLDS.items()}
        out["levels"][f] = {"worst_trailing_dd_pct": dd_pct, "blown_2x": blown}
        if not all(blown.values()):
            blown_everywhere = False
    out["verdict"] = "prop-deprioritized" if blown_everywhere else "proceed"
    return out


def main(strategies=None):
    strategies = strategies or STRATEGIES
    matrix = {}
    for strat in strategies:
        tr, mk = load(strat)
        for f in RISK_LEVELS:
            curves = build_curves(tr, mk, f)
            for pname, preset in PRESETS.items():
                r = check_preset(curves, preset)
                matrix[(strat, pname, f)] = r
                flag = "SURVIVES" if r["survives"] else "fails"
                daily = f"daily worst {r['worst_daily_pct']:+.2f}% ({r['daily_breaches']} breaches)" \
                    if r["worst_daily_pct"] is not None else "no daily rule"
                print(f"[{strat:10s}] {pname:32s} f={f*100:.2f}%: {daily}; "
                      f"floor[{r['floor_mech']}] {r['floor_breaches']} breach days "
                      f"(first {r['first_floor']}, worst gap {r['worst_floor_gap_pct']:+.2f}%); "
                      f"{r['consistency']}  ->  {flag}", flush=True)

    print("\n=== CROSS-PRESET SURVIVAL MATRIX (highest surviving risk level, drawdown rules) ===")
    header = f"{'strategy':<12}" + "".join(f"{p:<34}" for p in PRESETS)
    print(header)
    for strat in strategies:
        row = f"{strat:<12}"
        for pname in PRESETS:
            best = [f for f in RISK_LEVELS if matrix[(strat, pname, f)]["survives"]]
            row += f"{(f'{max(best)*100:.2f}%' if best else 'none'):<34}"
        print(row)
    return matrix


if __name__ == "__main__":
    import sys
    main(sys.argv[1:] or None)
