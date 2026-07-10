"""
Campaign 5 Track A: volcomp x FTMO FX (registration ed31277, committed before
results). Mechanism verbatim from the validated gold design; OANDA data,
verified FTMO costs (spread + commission, pips-equiv RT). Rollover carve-out:
no entries on M30 bars whose ET time is in [17:00, 18:00).

Run:  venv/Scripts/python.exe volcomp_fx_killtest.py [quick|full]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import data
import orb_plugin_core as orb   # for the hand-verified _us_dst_offset

HERE = Path(__file__).parent
PAIRS = {"EUR_USD": 0.7, "USD_JPY": 0.9, "GBP_USD": 0.8}   # verified all-in cost, pips RT
RISK_USD, RR = 80.0, 2.5
START = datetime(2021, 6, 1, tzinfo=timezone.utc)
END = datetime(2026, 7, 1, tzinfo=timezone.utc)
QUICK = (pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC"))


def pip(pair):
    return 0.01 if pair.endswith("JPY") else 0.0001


def in_rollover(ts: pd.Timestamp) -> bool:
    et = ts.tz_convert("UTC").tz_localize(None) + pd.Timedelta(
        hours=orb._us_dst_offset(ts.tz_convert("UTC").tz_localize(None)))
    return et.hour == 17


def simulate(pair: str, cost_pips: float) -> pd.DataFrame:
    d1 = data.fetch_candles(pair, "D", from_time=START, to_time=END)
    m30 = data.fetch_candles(pair, "M30", from_time=START, to_time=END)
    d1.index = pd.DatetimeIndex(d1.index).tz_convert("UTC")
    m30.index = pd.DatetimeIndex(m30.index).tz_convert("UTC")
    rng = d1["high"] - d1["low"]
    inside = (d1["high"] < d1["high"].shift(1)) & (d1["low"] > d1["low"].shift(1))
    nr5 = rng == rng.rolling(5).min()
    compress = (inside | nr5) & rng.rolling(5).count().eq(5)
    cost_px = cost_pips * pip(pair)

    trades, open_until = [], None
    days = list(d1.index)
    for i in range(1, len(days)):
        if not compress.loc[days[i - 1]]:
            continue
        if open_until is not None and days[i] <= open_until:
            continue
        hi, lo = d1.loc[days[i - 1], "high"], d1.loc[days[i - 1], "low"]
        day_end = days[i + 1] if i + 1 < len(days) else days[i] + pd.Timedelta(days=1)
        bars = m30[(m30.index >= days[i]) & (m30.index < day_end)]
        sig = None
        for t, b in bars.iterrows():
            if in_rollover(t):
                continue                       # registered carve-out: no rollover entries
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
                exit_px, reason, exit_t = sl, "sl", t
                break
            if (dirn == 1 and b["high"] >= tp) or (dirn == -1 and b["low"] <= tp):
                exit_px, reason, exit_t = tp, "tp", t
                break
        if exit_px is None:
            exit_px, reason, exit_t = walk["close"].iloc[-1], "eod_data", walk.index[-1]
        open_until = exit_t.normalize()
        r = (dirn * (exit_px - entry) - cost_px) / risk
        trades.append({"time": t0, "instrument": pair, "strategy": f"volcomp_{pair}",
                       "direction": "long" if dirn == 1 else "short",
                       "entry": entry, "sl": sl, "tp1": tp, "tp2": tp, "tp3": tp,
                       "units": 0, "pnl": RISK_USD * r, "balance": 0.0,
                       "exit_reason": reason, "exit_time": exit_t, "risk_px": risk})
    out = pd.DataFrame(trades)
    if len(out):
        out["balance"] = 10_000 + out["pnl"].cumsum()
    return out


def adjudicate(df, cost_pips, ppip, label):
    n, net = len(df), df["pnl"].sum() if len(df) else 0.0
    exp = net / n if n else 0.0
    med_stop = (df["risk_px"].median() / ppip) if n else 0.0
    kill = exp <= 0 or n < 20 or med_stop < 10 * cost_pips
    print(f"  {label:22s} n={n:4d} net={net:+9.2f} exp={exp:+7.2f}/tr "
          f"medstop={med_stop:6.1f}p (floor {10*cost_pips:.0f}) -> {'KILL' if kill else 'clear'}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "quick"
    print(f"=== CAMPAIGN 5 TRACK A: volcomp x FX ({mode}) — registration ed31277 ===")
    for pair, cost in PAIRS.items():
        df = simulate(pair, cost)
        if mode == "quick":
            adjudicate(df[(df["time"] >= QUICK[0]) & (df["time"] < QUICK[1])], cost, pip(pair), f"{pair} 2023")
        else:
            adjudicate(df, cost, pip(pair), f"{pair} full")
            if len(df):
                yearly = df.set_index("time")["pnl"].resample("YE").sum()
                print("    yearly: " + " ".join(f"{t.year}:{v:+.0f}" for t, v in yearly.items()) +
                      f"  ex-best-year: {df['pnl'].sum() - yearly.max():+.2f}")
                df.drop(columns=["risk_px"]).to_csv(HERE / f"volcomp_fx_{pair}_full.csv", index=False)


if __name__ == "__main__":
    main()
