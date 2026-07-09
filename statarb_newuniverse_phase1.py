"""
Track 5 phase 2, Line A -- stat-arb phase 1 on the new universe (registered
2026-07-09, committed before results). Rolling-90 OLS adaptive-beta ADF
battery + beta-sanity guard, the FX line's discriminating instrument.

Runs the registered EUR_USD/GBP_USD parity check FIRST; new-universe numbers
mean nothing if the tool can't reproduce the published FX result.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/statarb_newuniverse_phase1.py
"""
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

WINDOW = 90          # rolling OLS window (registered, from the FX line)
CV_LIMIT = 0.5
BREAK_DATE = "2024-01-01"

PAIRS = [
    ("XAUUSD", "XAGUSD"),
    ("SPX", "YM"),
    ("SPX", "NQ"),
    ("BTCUSD", "XAUUSD"),
]


def rolling_beta_spread(y: pd.Series, x: pd.Series):
    """Rolling-90 OLS of ln(y) on ln(x); returns (spread, beta) post-burn-in."""
    ly, lx = np.log(y), np.log(x)
    beta = ly.rolling(WINDOW).cov(lx) / lx.rolling(WINDOW).var()
    alpha = ly.rolling(WINDOW).mean() - beta * lx.rolling(WINDOW).mean()
    spread = (ly - (alpha + beta * lx)).iloc[WINDOW - 1:]
    return spread.dropna(), beta.iloc[WINDOW - 1:].dropna()


def battery(spread: pd.Series):
    def p(s):
        s = s.dropna()
        if len(s) < 30:
            return None
        return adfuller(s, autolag="AIC")[1]
    full = p(spread)
    pre = p(spread[spread.index < BREAK_DATE])
    post = p(spread[spread.index >= BREAK_DATE])
    years = {}
    for y in sorted(set(spread.index.year)):
        s = spread[spread.index.year == y]
        # only full-ish years carry a vote (the FX convention: yearly n~260)
        if len(s) >= 150:
            years[y] = p(s)
    year_pass = sum(1 for v in years.values() if v is not None and v < 0.10)
    need = math.ceil(len(years) * 2 / 3) if years else 0
    ok = (full is not None and full < 0.05
          and pre is not None and pre < 0.05
          and post is not None and post < 0.05
          and years and year_pass >= need)
    return ok, full, pre, post, years, year_pass, need


def guard(beta: pd.Series):
    b = beta.dropna()
    same_sign = (b > 0).all() or (b < 0).all()
    cv = b.std() / abs(b.mean()) if b.mean() else float("inf")
    return same_sign and cv < CV_LIMIT, float(b.mean()), float(cv), bool(same_sign)


def report(name, y, x):
    common = y.index.intersection(x.index)
    y, x = y.loc[common], x.loc[common]
    spread, beta = rolling_beta_spread(y, x)
    ok_b, full, pre, post, years, ypass, need = battery(spread)
    ok_g, bmean, cv, sign = guard(beta)
    verdict = "PASS" if (ok_b and ok_g) else "FAIL"
    ys = " ".join(f"{k}:{v:.3f}" for k, v in years.items())
    print(f"{name}: window {common.min().date()}->{common.max().date()} n={len(common)}")
    print(f"  battery full={full:.4f} pre24={pre:.4f} post24={post:.4f} years[{ypass}/{len(years)} need {need}] ({ys})")
    print(f"  guard beta_mean={bmean:+.3f} CV={cv:.3f} same_sign={sign}")
    print(f"  -> {verdict}\n")
    return verdict


def oanda_daily(instrument):
    from data import fetch_candles
    df = fetch_candles(instrument, "D",
                       from_time=datetime(2021, 1, 1, tzinfo=timezone.utc),
                       to_time=datetime(2026, 7, 1, tzinfo=timezone.utc))
    c = df["close"]
    c.index = c.index.tz_convert("UTC").tz_localize(None).normalize()
    return c[~c.index.duplicated()]


def phase_a_daily(symbol):
    import MetaTrader5 as mt5
    mt5.symbol_select(symbol, True)
    r = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_D1,
                             datetime(2021, 1, 1), datetime(2026, 7, 1))
    if r is None or not len(r):
        r = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 2000)
    if r is None or not len(r):
        raise RuntimeError(f"no D1 data {symbol}: {mt5.last_error()}")
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s").dt.normalize()
    return df.set_index("time")["close"][lambda s: ~s.index.duplicated()]


def main():
    print("== Parity check: EUR_USD/GBP_USD on OANDA daily (target: FX line's published PASS) ==")
    report("EUR_USD/GBP_USD", oanda_daily("EUR_USD"), oanda_daily("GBP_USD"))

    import MetaTrader5 as mt5
    if not mt5.initialize(path=r"D:\mt5_phaseA\terminal64.exe", portable=True, timeout=90_000):
        raise RuntimeError(mt5.last_error())
    print("== New universe (Phase A daily closes) ==")
    for a, b in PAIRS:
        report(f"{a}/{b}", phase_a_daily(a), phase_a_daily(b))
    mt5.shutdown()


if __name__ == "__main__":
    main()
