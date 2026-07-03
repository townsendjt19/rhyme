"""
Monitoring-review dossiers — standing artifacts, one command each:

    D:/rhyme/venv/Scripts/python.exe D:/rhyme/review_dossier.py intraday
    D:/rhyme/venv/Scripts/python.exe D:/rhyme/review_dossier.py scalp30

Each assembles the forward record against its own contract (GOVERNANCE
monitoring table, corrected baselines 52fea33; intraday review amended
126ea3b) with the pre-registered action ladder inline — review day is
execution against a prepared document, not assembly under pressure.

Supersedes intraday_review_dossier.py (760dcf8) by generalization.
"""
from __future__ import annotations
import math
import sys
from datetime import datetime, timezone

import pandas as pd

FORWARD_START = pd.Timestamp("2026-07-01")

CONTRACTS = {
    "intraday": {
        "attr": "donchian_plugin_intraday",
        "review_date": pd.Timestamp("2026-08-15"),
        "trade_trigger": 150,
        "wr_floor": 27.7,
        "dd_trigger_pct": 20.0,
        "ladder": ("net<=0 -> REDUCE to top-2 pairs by forward P&L; net<=0 AND rolling WR < 27.7% "
                   "-> SUSPEND; second consecutive failure -> RETIRE. Early-kill: forward 1%-curve DD > 20%."),
        "per_pair": True,
        "expectancy_baseline": None,
        "context": [
            "Grid (July 2026): USD_JPY is the ONLY pair in this family's records with demonstrated",
            "cross-year persistence; every other pair's record is windfall-shaped. Bears directly",
            "on any REDUCE-to-top-2 choice.",
            "Corrected baseline: +$28,973.51/7,434 trades; 2023 negative; USD_JPY = 85% of net.",
        ],
    },
    "scalp30": {
        "attr": "donchian_plugin_scalp30",
        "review_date": pd.Timestamp("2026-09-15"),
        "trade_trigger": 100,
        "wr_floor": 27.1,
        "dd_trigger_pct": 15.0,
        "ladder": ("net<=0 AND rolling WR < 27.1% -> SUSPEND; second consecutive failed review after "
                   "reinstatement -> RETIRE. Early-kill: forward 1%-curve DD > 15%."),
        "per_pair": False,   # single pair (USD_JPY)
        # Viability-floor context (GOVERNANCE note f02e0e2): for a strategy just
        # above its cost floor, EXPECTANCY DECAY is the leading indicator.
        "expectancy_baseline": 4.25,   # the grid gradient's M30 2023 cell ($/trade)
        "context": [
            "Gradient context note (GOVERNANCE, input to this review): family edge crosses zero",
            "between M15 (-$0.47/trade) and M30 (+$4.25/trade, scalp30's own 2023) -- scalp30",
            "sits just above the family's viability floor. Expectancy decay leads WR decay here.",
            "Corrected baseline: +$26,278.01/2,931 trades (6yr expectancy +$8.97/trade);",
            "2025 -$2,869 and 2026H1 -$2,569 -- already ~18 months into the negative stretch.",
        ],
    },
}


def main(which: str) -> None:
    cfg = CONTRACTS[which]
    import broker
    broker.set_account("101-001-39634331-002")

    pt = pd.read_csv(r"D:\rhyme\paper_trades.csv", parse_dates=["time"])
    fwd = pt[(pt["strategy"] == cfg["attr"]) & (pt["time"] >= FORWARD_START)].copy()

    closed_raw = {str(t.get("id")): t for t in broker.get_closed_trades()}
    open_ids = {str(t.get("id")) for t in broker.get_open_trades()}

    rows, pending = [], []
    for _, r in fwd.iterrows():
        tid = str(r["trade_id"]).split(".")[0] if pd.notna(r["trade_id"]) else ""
        if tid and tid in closed_raw:
            t = closed_raw[tid]
            rows.append({"trade_id": tid, "pair": r["pair"], "direction": r["direction"],
                         "close_time": pd.Timestamp(t.get("closeTime", "")),
                         "pnl": float(t.get("realizedPL", 0.0))})
        elif tid and tid in open_ids:
            pending.append((tid, r["pair"], r["direction"], str(r["time"])))
        elif tid:
            pending.append((tid, r["pair"], r["direction"], f"{r['time']} (id not found -- check attribution)"))

    df = pd.DataFrame(rows)
    now = datetime.now(timezone.utc)
    days_left = (cfg["review_date"].tz_localize("UTC") - pd.Timestamp(now)).days

    print("=" * 72)
    print(f"  {which.upper()} REVIEW DOSSIER  |  generated {now:%Y-%m-%d %H:%M} UTC")
    print(f"  Contract: {cfg['trade_trigger']} closed trades or {cfg['review_date'].date()} ({days_left} days out)")
    print("=" * 72)

    n = len(df)
    print(f"\n[1] TRIGGER PROGRESS: {n}/{cfg['trade_trigger']} forward closed trades since {FORWARD_START.date()}")
    print(f"    Open/pending (not counted): {len(pending)}")
    for p in pending:
        print(f"      trade {p[0]} {p[1]} {p[2]} opened {p[3]}")

    if n == 0:
        print(f"\n[2] WR vs {cfg['wr_floor']}% floor: n/a -- no closed forward trades yet")
        print(f"[3] Forward 1%-curve DD vs {cfg['dd_trigger_pct']:.0f}%: n/a")
        if cfg["expectancy_baseline"] is not None:
            print(f"[4] Forward expectancy vs +${cfg['expectancy_baseline']:.2f}/trade baseline: n/a")
        if cfg["per_pair"]:
            print("[4] Per-pair forward breakdown: n/a")
    else:
        wr = (df["pnl"] > 0).mean() * 100
        band = 200 * math.sqrt((wr / 100) * (1 - wr / 100) / n)
        print(f"\n[2] FORWARD WR: {wr:.1f}% on n={n}  (2-sigma band ±{band:.1f} -> "
              f"[{max(0, wr - band):.1f}, {min(100, wr + band):.1f}])  floor {cfg['wr_floor']}%")
        print("    Small-n honesty note applies: WR breach alone is weak evidence; every")
        print("    ladder action requires the conjunction with forward net P&L.")

        df = df.sort_values("close_time")
        eq = (1 + 0.01 * (df["pnl"] / 80.0)).cumprod()
        dd = float((eq / eq.cummax() - 1).min() * 100)
        net = df["pnl"].sum()
        print(f"\n[3] FORWARD NET: ${net:+,.2f} | 1%-curve DD from forward peak: {dd:.1f}% "
              f"(trigger {cfg['dd_trigger_pct']:.0f}%)")

        sec = 4
        if cfg["expectancy_baseline"] is not None:
            expct = df["pnl"].mean()
            base = cfg["expectancy_baseline"]
            print(f"\n[{sec}] FORWARD EXPECTANCY (the leading indicator at the viability floor):")
            print(f"    ${expct:+.2f}/trade  vs gradient baseline +${base:.2f}/trade "
                  f"(M15 family floor: -$0.47/trade)")
            print(f"    Distance to cost floor: ${expct - (-0.47):+.2f}/trade of the baseline's ${base + 0.47:.2f}")
            sec += 1
        if cfg["per_pair"]:
            print(f"\n[{sec}] PER-PAIR FORWARD BREAKDOWN (REDUCE ranks by forward P&L):")
            by_pair = df.groupby("pair").agg(n=("pnl", "size"), net=("pnl", "sum"),
                                             wr=("pnl", lambda s: (s > 0).mean() * 100))
            for pair, r in by_pair.sort_values("net", ascending=False).iterrows():
                print(f"    {pair:8s} n={int(r['n']):3d}  WR={r['wr']:5.1f}%  net=${r['net']:+9.2f}")
            top2 = by_pair.sort_values("net", ascending=False).head(2).index.tolist()
            print(f"    -> top-2 on forward evidence today: {top2}")
            sec += 1

    print(f"\n[{5 if n == 0 else 'CTX'}] STANDING CONTEXT (review input, not triggers):")
    for line in cfg["context"]:
        print(f"    {line}")

    # COT instrumentation block (Phase 2 resolution: monitoring only).
    try:
        from cot_snapshot import get_snapshot, format_block
        print()
        print(format_block(get_snapshot()))
    except Exception as e:
        print(f"\n[COT] snapshot unavailable ({e}) -- instrumentation only, dossier unaffected")

    print(f"\n[LADDER] PRE-COMMITTED ACTIONS (unchanged): {cfg['ladder']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "intraday")
