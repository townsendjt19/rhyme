"""
Track B: volatility-compression breakout on XAUUSD + US500 (Campaign 2,
registration 9d510ee, committed before results). Structural trigger, no
parameters: the prior D1 bar (server day, Phase A UTC+2) is an inside day
OR the narrowest range of the last 5 days -> first M30 CLOSE beyond that
compression bar's high/low during the NEXT day enters; SL at the compression
bar's opposite extreme; TP 2.5R (house convention); fire-and-forget.
One position per symbol; signal expires at day end. Costs: registered .sim
median spreads. Distinct by registration from Donchian (fixed-lookback
channel) and ORB (clock-anchored): the entry condition is volatility STATE.

Run:  venv/Scripts/python.exe volcomp_killtest.py [quick|full]
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import mt5_client

HERE = Path(__file__).parent
SYMBOLS = {"XAUUSD": 0.25, "SPX": 0.5}          # registered .sim median spreads
RISK_USD = 80.0
RR = 2.5
START, END = datetime(2021, 6, 1), datetime(2026, 7, 1)
QUICK = (pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"))


def simulate(symbol: str, spread: float) -> pd.DataFrame:
    d1 = mt5_client.get_history(symbol, "D", START, END)
    m30 = mt5_client.get_history(symbol, "M30", START, END)
    rng = d1["high"] - d1["low"]
    inside = (d1["high"] < d1["high"].shift(1)) & (d1["low"] > d1["low"].shift(1))
    nr5 = rng == rng.rolling(5).min()
    compress = (inside | nr5) & rng.rolling(5).count().eq(5)
    m30_day = pd.DatetimeIndex(m30.index).normalize()

    trades, open_until = [], None
    days = list(d1.index)
    for i in range(1, len(days)):
        if not compress.loc[days[i - 1]]:
            continue
        if open_until is not None and days[i] <= open_until:
            continue
        hi, lo = d1.loc[days[i - 1], "high"], d1.loc[days[i - 1], "low"]
        bars = m30[m30_day == days[i].normalize()]
        sig = None
        for t, b in bars.iterrows():
            if b["close"] > hi:
                sig = (1, b["close"], lo, t)
                break
            if b["close"] < lo:
                sig = (-1, b["close"], hi, t)
                break
        if sig is None:
            continue
        dirn, entry, sl, t0 = sig
        risk = abs(entry - sl)
        if risk == 0:
            continue
        tp = entry + dirn * RR * risk
        walk = m30[m30.index > t0]
        exit_px, reason, exit_t = None, None, None
        for t, b in walk.iterrows():
            if (dirn == 1 and b["low"] <= sl) or (dirn == -1 and b["high"] >= sl):
                exit_px, reason, exit_t = sl, "sl", t             # conservative SL-first
                break
            if (dirn == 1 and b["high"] >= tp) or (dirn == -1 and b["low"] <= tp):
                exit_px, reason, exit_t = tp, "tp", t
                break
        if exit_px is None:
            exit_px, reason, exit_t = walk["close"].iloc[-1], "eod_data", walk.index[-1]
        open_until = exit_t.normalize()
        r = (dirn * (exit_px - entry) - spread) / risk
        trades.append({"time": t0 - pd.Timedelta(hours=2),      # server -> UTC
                       "instrument": symbol, "strategy": f"volcomp_{symbol}",
                       "direction": "long" if dirn == 1 else "short",
                       "entry": entry, "sl": sl, "tp1": tp, "tp2": tp, "tp3": tp,
                       "units": 0, "pnl": RISK_USD * r, "balance": 0.0,
                       "exit_reason": reason,
                       "exit_time": exit_t - pd.Timedelta(hours=2), "risk_px": risk})
    out = pd.DataFrame(trades)
    if len(out):
        out["balance"] = 10_000 + out["pnl"].cumsum()
    return out


def adjudicate(df: pd.DataFrame, spread: float, label: str) -> None:
    n, net = len(df), df["pnl"].sum() if len(df) else 0.0
    exp = net / n if n else 0.0
    med_stop = df["risk_px"].median() if n else 0.0
    kill = exp <= 0 or n < 20 or med_stop < 10 * spread
    print(f"  {label:14s} n={n:4d} net={net:+9.2f} exp={exp:+7.2f}/tr "
          f"medstop={med_stop:8.2f} (floor {10*spread:.1f}) -> {'KILL' if kill else 'clear'}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "quick"
    print(f"=== TRACK B vol-compression breakout ({mode}) — registration 9d510ee ===")
    for sym, spread in SYMBOLS.items():
        df = simulate(sym, spread)
        if mode == "quick":
            q = df[(df["time"] >= QUICK[0]) & (df["time"] < QUICK[1])]
            adjudicate(q, spread, f"{sym} 2023")
        else:
            adjudicate(df, spread, f"{sym} full")
            yearly = df.set_index("time")["pnl"].resample("YE").sum()
            print("    yearly: " + " ".join(f"{t.year}:{v:+.0f}" for t, v in yearly.items()))
            print(f"    ex-best-year: {df['pnl'].sum() - yearly.max():+.2f}  "
                  f"WR {100 * (df['pnl'] > 0).mean():.1f}%")
            df.drop(columns=["risk_px"]).to_csv(HERE / f"volcomp_{sym}_full.csv", index=False)


if __name__ == "__main__":
    main()
