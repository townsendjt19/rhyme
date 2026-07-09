"""
Track A: opening-gap dynamics on US indices (Campaign 2, registration 9d510ee,
committed before results). One structural rule, chosen not tuned:
  gap opening INSIDE the prior RTH day's range  -> fade toward prior close
     (TP = prior close, SL symmetric at |gap| beyond entry)
  gap opening OUTSIDE the prior range           -> continuation
     (SL = violated boundary, TP = 2x risk)
Time-stop: RTH close (16:00 ET). One trade/day/symbol. Conservative SL-first
on both-touch bars. Costs: registered .sim median spreads (orb_plugin_core).

Also emits the Track C overnight-drift measurement (same frames, zero extra
fetch): per-symbol close(16:00)->open(09:30) drift vs financing+spread drag.

Run:  venv/Scripts/python.exe gapline_killtest.py [quick|full]
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import mt5_client
import orb_plugin_core as orb

HERE = Path(__file__).parent
SERVER_UTC_OFFSET = pd.Timedelta(hours=2)   # Phase A fixed UTC+2

SYMBOLS = {"SPX": 0.5, "NQ": 1.8, "YM": 2.0}   # registered .sim median spreads, price units
SWAP_ANNUAL_LONG = {"SPX": -2.53, "NQ": -6.07, "YM": -6.16}  # %/yr, INTEREST_CURRENT (read 2026-07-09)
RISK_USD = 80.0
START, END = datetime(2022, 1, 1), datetime(2026, 7, 1)
QUICK = (pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"))


def sessions(symbol: str) -> pd.DataFrame:
    """One row per ET trading date: prior-RTH-derived fields + today's bars."""
    df = mt5_client.get_history(symbol, "M30", START, END)
    utc = df.index - SERVER_UTC_OFFSET
    et = utc + pd.Series(utc, index=df.index).map(
        lambda t: pd.Timedelta(hours=orb._us_dst_offset(pd.Timestamp(t)))).values
    df = df.assign(et=et, et_date=pd.DatetimeIndex(et).date,
                   et_min=[t.hour * 60 + t.minute for t in pd.DatetimeIndex(et)])
    rth = df[(df["et_min"] >= 570) & (df["et_min"] < 960)]        # 09:30-16:00
    rows = []
    for d, g in rth.groupby("et_date"):
        if g["et_min"].iloc[0] != 570 or len(g) < 10:              # need the 09:30 bar, full-ish session
            continue
        rows.append({"date": d, "open": g["open"].iloc[0], "high": g["high"].max(),
                     "low": g["low"].min(), "close": g["close"].iloc[-1],
                     "open_utc": g.index[0] - pd.Timedelta(0), "bars": g})
    return pd.DataFrame(rows)


def simulate(symbol: str, spread: float) -> pd.DataFrame:
    ses = sessions(symbol)
    trades = []
    for i in range(1, len(ses)):
        prev, cur = ses.iloc[i - 1], ses.iloc[i]
        entry, gap = cur["open"], cur["open"] - prev["close"]
        if prev["low"] <= entry <= prev["high"]:
            if gap == 0:
                continue
            arm, dirn = "fade", (1 if gap < 0 else -1)             # fade toward prior close
            risk = abs(gap)
            tp, sl = prev["close"], entry - dirn * risk
        else:
            arm = "cont"
            dirn = 1 if entry > prev["high"] else -1
            sl = prev["high"] if dirn == 1 else prev["low"]
            risk = abs(entry - sl)
            if risk == 0:
                continue
            tp = entry + dirn * 2 * risk
        exit_px, reason, exit_t = None, "time", None
        for t, bar in cur["bars"].iterrows():
            if (dirn == 1 and bar["low"] <= sl) or (dirn == -1 and bar["high"] >= sl):
                exit_px, reason, exit_t = sl, "sl", t              # conservative: SL first
                break
            if (dirn == 1 and bar["high"] >= tp) or (dirn == -1 and bar["low"] <= tp):
                exit_px, reason, exit_t = tp, "tp", t
                break
        if exit_px is None:
            exit_px, exit_t = cur["bars"]["close"].iloc[-1], cur["bars"].index[-1]
        r = (dirn * (exit_px - entry) - spread) / risk
        trades.append({"time": cur["bars"].index[0] - SERVER_UTC_OFFSET,
                       "instrument": symbol, "strategy": f"gapline_{arm}",
                       "direction": "long" if dirn == 1 else "short",
                       "entry": entry, "sl": sl, "tp1": tp, "tp2": tp, "tp3": tp,
                       "units": 0, "pnl": RISK_USD * r, "balance": 0.0,
                       "exit_reason": reason,
                       "exit_time": exit_t - SERVER_UTC_OFFSET, "risk_px": risk})
    out = pd.DataFrame(trades)
    out["balance"] = 10_000 + out["pnl"].cumsum()
    return out


def overnight_report(symbol: str, spread: float) -> None:
    ses = sessions(symbol)
    prev_close = ses["close"].values[:-1]
    ret_bp = 1e4 * (ses["open"].values[1:] - prev_close) / prev_close
    dates = pd.DatetimeIndex(pd.to_datetime(ses["date"].values[1:]))
    spread_bp = 1e4 * spread / ses["close"].mean()
    fin_bp = abs(SWAP_ANNUAL_LONG[symbol]) * 100 / 252
    net = pd.Series(ret_bp - spread_bp - fin_bp, index=dates)
    print(f"  {symbol}: n={len(net)} nights  raw {ret_bp.mean():+.2f} bp/night  "
          f"- spread {spread_bp:.2f} - financing {fin_bp:.2f} = NET {net.mean():+.2f} bp/night")
    yearly = net.resample("YE").agg(["sum", "count"])
    print("    yearly net (bp): " + " ".join(
        f"{t.year}:{v['sum']:+.0f}({int(v['count'])}n)" for t, v in yearly.iterrows()))
    eq = net.cumsum()
    maxdd = (eq.cummax() - eq).max()
    ex_best = net.sum() - yearly["sum"].max()
    print(f"    total {net.sum():+.0f} bp  ex-best-year {ex_best:+.0f} bp  maxDD {maxdd:.0f} bp  "
          f"worst night {net.min():+.0f} bp  p1 {net.quantile(0.01):+.0f} bp")


def adjudicate(df: pd.DataFrame, spread: float, label: str) -> None:
    for arm, g in df.groupby("strategy"):
        n, net = len(g), g["pnl"].sum()
        exp, med_stop = net / n if n else 0.0, g["risk_px"].median() if n else 0.0
        kill = exp <= 0 or n < 20 or med_stop < 10 * spread
        print(f"  {label} {arm:13s} n={n:4d} net={net:+9.2f} exp={exp:+7.2f}/tr "
              f"medstop={med_stop:8.2f} (floor {10*spread:.1f}) -> {'KILL' if kill else 'clear'}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "quick"
    print(f"=== TRACK A opening-gap killtest ({mode}) — registration 9d510ee ===")
    for sym, spread in SYMBOLS.items():
        df = simulate(sym, spread)
        if mode == "quick":
            q = df[(df["time"] >= QUICK[0]) & (df["time"] < QUICK[1])]
            adjudicate(q, spread, f"{sym} 2023")
        else:
            adjudicate(df, spread, f"{sym} full")
            for arm, g in df.groupby("strategy"):
                yearly = g.set_index("time")["pnl"].resample("YE").sum()
                print(f"    {sym} {arm} yearly: " +
                      " ".join(f"{t.year}:{v:+.0f}" for t, v in yearly.items()))
                g.drop(columns=["risk_px"]).to_csv(
                    HERE / f"gapline_{sym}_{arm.split('_')[1]}_full.csv", index=False)
    print("\n=== TRACK C overnight drift (same frames; financing INTEREST_CURRENT read 2026-07-09) ===")
    for sym, spread in SYMBOLS.items():
        overnight_report(sym, spread)


if __name__ == "__main__":
    main()
