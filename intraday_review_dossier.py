"""
Intraday 2026-08-15 review dossier — standing artifact, one command to refresh:

    D:/rhyme/venv/Scripts/python.exe D:/rhyme/intraday_review_dossier.py

Assembles the forward record against the AMENDED contract (126ea3b: review at
150 closed trades or 2026-08-15; corrected baselines 52fea33: WR floor 27.7%,
forward 1%-curve DD suspend at 20%) and the per-pair breakdown the REDUCE
action needs. Pre-committed ladder (unchanged, GOVERNANCE): forward net <= 0
-> REDUCE to top-2 pairs by forward P&L; net <= 0 AND WR < floor -> SUSPEND;
second consecutive failure -> RETIRE.

Standing context baked in (not recomputed): the July 2026 grid found USD_JPY
is the only pair in this family's records with demonstrated cross-year
persistence; the timeframe gradient puts the family's edge floor between M15
and M30. Both are REVIEW INPUT, not triggers.
"""
from __future__ import annotations
import math
from datetime import datetime, timezone

import pandas as pd

FORWARD_START = pd.Timestamp("2026-07-01")
REVIEW_DATE = pd.Timestamp("2026-08-15")
TRADE_TRIGGER = 150
WR_FLOOR = 27.7          # corrected worst-full-year baseline (52fea33)
DD_SUSPEND_PCT = 20.0    # forward 1%-curve early-kill/suspend trigger
ACCOUNT = "101-001-39634331-002"


def main() -> None:
    import broker
    broker.set_account(ACCOUNT)

    pt = pd.read_csv(r"D:\rhyme\paper_trades.csv", parse_dates=["time"])
    fwd = pt[(pt["strategy"].str.contains("intraday", na=False))
             & (pt["time"] >= FORWARD_START)].copy()

    closed_raw = {str(t.get("id")): t for t in broker.get_closed_trades()}
    open_ids = {str(t.get("id")) for t in broker.get_open_trades()}

    rows = []
    pending = []
    for _, r in fwd.iterrows():
        tid = str(r["trade_id"]) if pd.notna(r["trade_id"]) else ""
        tid = tid.split(".")[0]   # float-cell artifact guard
        if tid and tid in closed_raw:
            t = closed_raw[tid]
            rows.append({"trade_id": tid, "pair": r["pair"], "direction": r["direction"],
                         "open_time": r["time"], "close_time": pd.Timestamp(t.get("closeTime", "")),
                         "pnl": float(t.get("realizedPL", 0.0))})
        elif tid and tid in open_ids:
            pending.append((tid, r["pair"], r["direction"], str(r["time"])))
        elif tid:
            pending.append((tid, r["pair"], r["direction"], f"{r['time']} (id not found -- check attribution)"))

    df = pd.DataFrame(rows)
    now = datetime.now(timezone.utc)
    days_left = (REVIEW_DATE.tz_localize("UTC") - pd.Timestamp(now)).days

    print("=" * 72)
    print(f"  INTRADAY REVIEW DOSSIER  |  generated {now:%Y-%m-%d %H:%M} UTC")
    print(f"  Contract: 150 closed trades or 2026-08-15 ({days_left} days out), amended 126ea3b")
    print("=" * 72)

    n = len(df)
    print(f"\n[1] TRIGGER PROGRESS: {n}/{TRADE_TRIGGER} forward closed trades since {FORWARD_START.date()}")
    print(f"    Open/pending (not counted): {len(pending)}")
    for p in pending:
        print(f"      trade {p[0]} {p[1]} {p[2]} opened {p[3]}")

    if n == 0:
        print("\n[2] WR vs floor: n/a -- no closed forward trades yet")
        print(f"[3] Forward 1%-curve DD vs {DD_SUSPEND_PCT:.0f}% suspend: n/a")
        print("[4] Per-pair forward breakdown: n/a")
    else:
        wr = (df["pnl"] > 0).mean() * 100
        band = 200 * math.sqrt((wr / 100) * (1 - wr / 100) / n)
        print(f"\n[2] FORWARD WR: {wr:.1f}% on n={n}  (2-sigma band ±{band:.1f} pts -> "
              f"[{max(0, wr - band):.1f}, {min(100, wr + band):.1f}])")
        print(f"    Corrected floor: {WR_FLOOR}%. At small n the band dominates -- the contract's")
        print(f"    honesty note applies: WR breach alone is weak evidence; action requires net<=0 too.")

        df = df.sort_values("close_time")
        eq = (1 + 0.01 * (df["pnl"] / 80.0)).cumprod()
        dd = float((eq / eq.cummax() - 1).min() * 100)
        net = df["pnl"].sum()
        print(f"\n[3] FORWARD NET: ${net:+,.2f} | 1%-curve DD from forward peak: {dd:.1f}% "
              f"(suspend trigger {DD_SUSPEND_PCT:.0f}%)")

        print(f"\n[4] PER-PAIR FORWARD BREAKDOWN (REDUCE action ranks by forward P&L):")
        by_pair = df.groupby("pair").agg(n=("pnl", "size"), net=("pnl", "sum"),
                                         wr=("pnl", lambda s: (s > 0).mean() * 100))
        for pair, r in by_pair.sort_values("net", ascending=False).iterrows():
            print(f"    {pair:8s} n={int(r['n']):3d}  WR={r['wr']:5.1f}%  net=${r['net']:+9.2f}")
        top2 = by_pair.sort_values("net", ascending=False).head(2).index.tolist()
        print(f"    -> top-2 on forward evidence today: {top2}")

    print(f"\n[5] STANDING CONTEXT (review input, not triggers):")
    print(f"    - Grid (July 2026): USD_JPY is the only pair in this family's records with")
    print(f"      demonstrated cross-year persistence; every other pair's record is a")
    print(f"      windfall-year shape. Bears directly on any REDUCE-to-top-2 choice.")
    print(f"    - Gradient: family edge crosses zero between M15 and M30 (scalp30 context")
    print(f"      note, GOVERNANCE) -- the H1 rung sits above the floor but the family's")
    print(f"      cushion is thinner than the pre-correction records suggested.")
    print(f"    - Corrected baseline: +$28,973.51/7,434, 2023 negative, USD_JPY = 85% of net.")
    print(f"\n[6] PRE-COMMITTED LADDER (unchanged): net<=0 -> REDUCE to top-2 by forward P&L;")
    print(f"    net<=0 AND rolling WR < {WR_FLOOR}% -> SUSPEND; second consecutive failure -> RETIRE.")


if __name__ == "__main__":
    main()
