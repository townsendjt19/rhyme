"""
Campaign 3 Track A: intraday cross-sectional index momentum (registration
c1dd8c2, committed before results). Each US trading day at 09:30 ET, rank
SPX/NQ/YM by trailing 20-completed-day return; LONG the top from the 09:30
M30 open, SHORT the bottom; protective stop 1x ATR(20d, mean daily range);
exit at the 16:00 ET close. Day-neutral: zero financing, zero gap risk.
1R = $80 on the ATR. Costs: registered .sim median spreads, $0 commission.

Run:  venv/Scripts/python.exe xsmom_killtest.py [quick|full]
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import mt5_client
import orb_plugin_core as orb

HERE = Path(__file__).parent
SERVER_UTC_OFFSET = pd.Timedelta(hours=2)
SYMBOLS = {"SPX": 0.5, "NQ": 1.8, "YM": 2.0}   # registered .sim median spreads
LOOKBACK, RISK_USD = 20, 80.0
START, END = datetime(2021, 6, 1), datetime(2026, 7, 1)
QUICK = (pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"))


def load(symbol: str):
    """(daily df with ret20/atr20 on completed days, per-ET-date RTH M30 bars)."""
    d1 = mt5_client.get_history(symbol, "D", START, END)
    d1["ret20"] = d1["close"].pct_change(LOOKBACK)
    d1["atr20"] = (d1["high"] - d1["low"]).rolling(LOOKBACK).mean()
    m30 = mt5_client.get_history(symbol, "M30", START, END)
    utc = m30.index - SERVER_UTC_OFFSET
    et = utc + pd.Series(utc, index=m30.index).map(
        lambda t: pd.Timedelta(hours=orb._us_dst_offset(pd.Timestamp(t)))).values
    m30 = m30.assign(et_date=pd.DatetimeIndex(et).date,
                     et_min=[t.hour * 60 + t.minute for t in pd.DatetimeIndex(et)])
    rth = m30[(m30["et_min"] >= 570) & (m30["et_min"] < 960)]
    days = {d: g for d, g in rth.groupby("et_date")
            if g["et_min"].iloc[0] == 570 and len(g) >= 10}
    return d1, days


def leg(symbol: str, bars: pd.DataFrame, dirn: int, atr: float, spread: float) -> dict:
    entry = bars["open"].iloc[0]
    sl = entry - dirn * atr
    exit_px, reason, exit_t = None, "close", bars.index[-1]
    for t, b in bars.iterrows():
        if (dirn == 1 and b["low"] <= sl) or (dirn == -1 and b["high"] >= sl):
            exit_px, reason, exit_t = sl, "sl", t          # conservative SL-first
            break
    if exit_px is None:
        exit_px = bars["close"].iloc[-1]
    r = (dirn * (exit_px - entry) - spread) / atr
    return {"time": bars.index[0] - SERVER_UTC_OFFSET, "instrument": symbol,
            "strategy": f"xsmom_{'long' if dirn == 1 else 'short'}",
            "direction": "long" if dirn == 1 else "short", "entry": entry,
            "sl": sl, "tp1": 0.0, "tp2": 0.0, "tp3": 0.0, "units": 0,
            "pnl": RISK_USD * r, "balance": 0.0, "exit_reason": reason,
            "exit_time": exit_t - SERVER_UTC_OFFSET, "risk_px": atr}


def simulate() -> pd.DataFrame:
    data = {s: load(s) for s in SYMBOLS}
    common = sorted(set.intersection(*(set(d[1]) for d in data.values())))
    trades = []
    for day in common:
        ranks = {}
        for s, (d1, days_map) in data.items():
            prior = d1[d1.index.normalize() < pd.Timestamp(day)]
            if len(prior) < LOOKBACK + 1 or pd.isna(prior["ret20"].iloc[-1]):
                break
            ranks[s] = (prior["ret20"].iloc[-1], prior["atr20"].iloc[-1])
        if len(ranks) < 3:
            continue
        top = max(ranks, key=lambda s: ranks[s][0])
        bot = min(ranks, key=lambda s: ranks[s][0])
        trades.append(leg(top, data[top][1][day], +1, ranks[top][1], SYMBOLS[top]))
        trades.append(leg(bot, data[bot][1][day], -1, ranks[bot][1], SYMBOLS[bot]))
    df = pd.DataFrame(trades).sort_values("time").reset_index(drop=True)
    df["balance"] = 10_000 + df["pnl"].cumsum()
    return df


def adjudicate(df: pd.DataFrame, label: str) -> None:
    for name, g in [("combined", df)] + list(df.groupby("strategy")):
        n, net = len(g), g["pnl"].sum()
        exp = net / n if n else 0.0
        med_stop = g["risk_px"].median() if n else 0.0
        floor = 10 * max(SYMBOLS.values())
        kill = exp <= 0 or n < 20
        print(f"  {label} {name:12s} n={n:5d} net={net:+10.2f} exp={exp:+7.2f}/tr "
              f"medstop={med_stop:7.2f} (worst floor {floor:.0f}) -> {'KILL' if kill else 'clear'}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "quick"
    print(f"=== TRACK A intraday XSMOM ({mode}) — registration c1dd8c2 ===")
    df = simulate()
    if mode == "quick":
        adjudicate(df[(df["time"] >= QUICK[0]) & (df["time"] < QUICK[1])], "2023")
    else:
        adjudicate(df, "full")
        yearly = df.set_index("time")["pnl"].resample("YE").sum()
        print("    yearly: " + " ".join(f"{t.year}:{v:+.0f}" for t, v in yearly.items()))
        print(f"    ex-best-year: {df['pnl'].sum() - yearly.max():+.2f}  "
              f"WR {100 * (df['pnl'] > 0).mean():.1f}%")
        df.drop(columns=["risk_px"]).to_csv(HERE / "xsmom_full.csv", index=False)


if __name__ == "__main__":
    main()
