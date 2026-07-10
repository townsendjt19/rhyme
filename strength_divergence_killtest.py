"""
Campaign 4 Track B: currency-strength divergence (registration 1e1d1b1,
committed before results). 8 majors; strength per currency = flat-weighted
mean of its 7 pairs' trailing 20-trading-day returns (sign-adjusted),
sampled daily at 12:00 UTC. Trade the single pair pairing strongest vs
weakest currency, long the strong; exit next trading day 12:00 UTC;
protective stop 1x ATR(20d); one trade per day.

Costs (pre-stated): per-pair median quoted spread of the 12:00 UTC hour
(12mo MBA sample) + 1.0 pip/night flat financing (conservative).
Target venue: personal OANDA account. Gates: 2023 quick-check (grid
criteria) -> full window.

Run:  venv/Scripts/python.exe strength_divergence_killtest.py
"""
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import pandas as pd

import data

HERE = Path(__file__).parent
CCY = ["USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"]
LOOKBACK, RISK_USD, FIN_PIPS_NIGHT = 20, 80.0, 1.0
START = datetime(2021, 6, 1, tzinfo=timezone.utc)
END = datetime(2026, 7, 1, tzinfo=timezone.utc)
QUICK = (pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC"))

# OANDA instrument name for each unordered currency pair (standard quote order)
ORDER = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"]


def instrument(a: str, b: str) -> str:
    base, quote = sorted([a, b], key=ORDER.index)
    return f"{base}_{quote}"


PAIRS = [instrument(a, b) for a, b in combinations(CCY, 2)]


def pip(pair):
    return 0.01 if pair.endswith("JPY") else 0.0001


def fetch_h1(pair):
    df = data.fetch_candles(pair, "H1", from_time=START, to_time=END)
    df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
    return df


def spread_at_noon(pair) -> float:
    """Median quoted spread (pips) of the 12:00 UTC hour, trailing 12mo MBA."""
    from oandapyV20.endpoints.instruments import InstrumentsCandles
    from data import get_client, _dt_to_rfc3339
    req = InstrumentsCandles(instrument=pair, params={
        "granularity": "H1", "price": "MBA", "count": 5000})
    get_client().request(req)
    sp = [float(c["ask"]["c"]) - float(c["bid"]["c"])
          for c in req.response.get("candles", [])
          if c.get("complete") and pd.Timestamp(c["time"]).hour == 12]
    return float(pd.Series(sp).median() / pip(pair)) if sp else 1.5


def main() -> None:
    print(f"=== TRACK B strength divergence — {len(PAIRS)} pairs (registration 1e1d1b1) ===")
    h1, noon, atr = {}, {}, {}
    for p in PAIRS:
        df = fetch_h1(p)
        h1[p] = df
        at12 = df[df.index.hour == 12]
        s = at12["open"]
        s.index = pd.DatetimeIndex(at12.index.date)
        noon[p] = s[~s.index.duplicated()]
        day_rng = (df["high"].groupby(df.index.date).max()
                   - df["low"].groupby(df.index.date).min())
        day_rng.index = pd.DatetimeIndex(day_rng.index)   # align with noon-series keys
        atr[p] = day_rng.rolling(LOOKBACK).mean()
        print(f"  fetched {p}: {len(df)} H1 bars")
    spreads = {p: spread_at_noon(p) for p in PAIRS}
    print("  noon spreads (pips): " + " ".join(f"{p}:{s:.1f}" for p, s in spreads.items()))

    ret20 = {p: noon[p] / noon[p].shift(LOOKBACK) - 1 for p in PAIRS}
    days = sorted(set.intersection(*(set(r.dropna().index) for r in ret20.values())))

    trades = []
    for i, d in enumerate(days[:-1]):
        strength = {}
        for c in CCY:
            vals = []
            for p in PAIRS:
                base, quote = p.split("_")
                if c == base:
                    vals.append(ret20[p].get(d))
                elif c == quote:
                    vals.append(-ret20[p].get(d))
            strength[c] = sum(v for v in vals if v == v) / len(vals)
        strong = max(strength, key=strength.get)
        weak = min(strength, key=strength.get)
        pair = instrument(strong, weak)
        base = pair.split("_")[0]
        dirn = 1 if base == strong else -1
        df = h1[pair]
        seg = df[(df.index >= pd.Timestamp(d).tz_localize("UTC").replace(hour=12))
                 & (df.index <= pd.Timestamp(days[i + 1]).tz_localize("UTC").replace(hour=12))]
        if len(seg) < 5:
            continue
        a = atr[pair].get(d)
        if a is None or a != a or a <= 0:
            continue
        entry = seg["open"].iloc[0]
        sl = entry - dirn * a
        exit_px, reason, exit_t = None, "time", seg.index[-1]
        for t, b in seg.iterrows():
            if (dirn == 1 and b["low"] <= sl) or (dirn == -1 and b["high"] >= sl):
                exit_px, reason, exit_t = sl, "sl", t
                break
        if exit_px is None:
            exit_px = seg["close"].iloc[-1]
        cost_px = (spreads[pair] + FIN_PIPS_NIGHT) * pip(pair)
        r = (dirn * (exit_px - entry) - cost_px) / a
        trades.append({"time": seg.index[0], "instrument": pair,
                       "strategy": "strength_divergence",
                       "direction": "long" if dirn == 1 else "short",
                       "entry": entry, "sl": sl, "tp1": 0.0, "tp2": 0.0, "tp3": 0.0,
                       "units": 0, "pnl": RISK_USD * r, "balance": 0.0,
                       "exit_reason": reason, "exit_time": exit_t, "risk_px": a})
    tr = pd.DataFrame(trades)
    tr["balance"] = 10_000 + tr["pnl"].cumsum()

    for label, g in [("2023 quick-check", tr[(tr["time"] >= QUICK[0]) & (tr["time"] < QUICK[1])]),
                     ("full window", tr)]:
        n, net = len(g), g["pnl"].sum()
        exp = net / n if n else 0.0
        kill = exp <= 0 or n < 20
        print(f"  {label:16s} n={n:4d} net={net:+9.2f} exp={exp:+6.2f}/tr "
              f"WR={100 * (g['pnl'] > 0).mean():.1f}% -> {'KILL' if kill else 'clear'}")
    yearly = tr.set_index("time")["pnl"].resample("YE").sum()
    print("  yearly: " + " ".join(f"{t.year}:{v:+.0f}" for t, v in yearly.items()) +
          f"  ex-best-year: {tr['pnl'].sum() - yearly.max():+.2f}")
    print("  top traded pairs: " + str(tr["instrument"].value_counts().head(5).to_dict()))
    tr.drop(columns=["risk_px"]).to_csv(HERE / "strength_divergence_full.csv", index=False)


if __name__ == "__main__":
    main()
