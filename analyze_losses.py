"""
Analyze losing trades from a backtest CSV.
Enriches each loss with: hour, day of week, active Fib level, candlestick pattern.
"""
import sys
import pandas as pd
import numpy as np
from datetime import timezone

from data import fetch_candles
from indicators import add_emas, detect_fractals
from fibonacci import fib_retracements_long, fib_retracements_short, RETRACE_LEVELS
from patterns import (
    is_doji, is_hammer, is_shooting_star, is_pin_bar_bull, is_pin_bar_bear,
    is_bullish_engulfing, is_bearish_engulfing, is_morning_star, is_evening_star,
    _body, _candle_range,
)

CSV = "backtest_EUR_USD_scalp.csv"
INSTRUMENT = "EUR_USD"
TOLERANCE = 0.005  # 0.5% fib tolerance


def nearest_fib(price, retracements):
    best_label, best_dist = None, float("inf")
    for ratio, level in retracements.items():
        dist = abs(price - level) / level
        if dist < best_dist:
            best_dist = dist
            best_label = f"{ratio*100:.1f}%"
    return best_label, best_dist


def detect_patterns(df, i):
    row = df.iloc[i]
    found = []
    if is_doji(row):
        found.append("Doji")
    if is_hammer(row):
        found.append("Hammer")
    if is_shooting_star(row):
        found.append("ShootingStar")
    if is_pin_bar_bull(row):
        found.append("PinBarBull")
    if is_pin_bar_bear(row):
        found.append("PinBarBear")
    if i >= 1:
        prev = df.iloc[i - 1]
        if is_bullish_engulfing(prev, row):
            found.append("BullEngulf")
        if is_bearish_engulfing(prev, row):
            found.append("BearEngulf")
    if i >= 2:
        c1, c2 = df.iloc[i - 2], df.iloc[i - 1]
        if is_morning_star(c1, c2, row):
            found.append("MorningStar")
        if is_evening_star(c1, c2, row):
            found.append("EveningStar")
    return found if found else ["None"]


def main():
    df_trades = pd.read_csv(CSV, parse_dates=["time"])
    losses = df_trades[df_trades["pnl"] <= 0].copy()

    if losses.empty:
        print("No losses found.")
        return

    print(f"Fetching M15 candles for enrichment...")
    m15 = fetch_candles(INSTRUMENT, "M15", count=500,
                        from_time=pd.Timestamp("2023-01-01", tz="UTC").to_pydatetime(),
                        to_time=pd.Timestamp("2024-01-01", tz="UTC").to_pydatetime())
    m15 = add_emas(detect_fractals(m15))

    rows = []
    for _, trade in losses.iterrows():
        t = pd.Timestamp(trade["time"])
        if t.tzinfo is None:
            t = t.tz_localize("UTC")

        # Find the candle index in m15 closest to trade time
        idx_pos = m15.index.searchsorted(t)
        if idx_pos >= len(m15):
            idx_pos = len(m15) - 1
        if idx_pos < 5:
            continue

        window = m15.iloc[:idx_pos + 1]

        direction = trade["direction"]
        price = trade["entry"]

        if direction == "long":
            retrace = fib_retracements_long(window, before_idx=-1)
        else:
            retrace = fib_retracements_short(window, before_idx=-1)

        fib_label, fib_dist = nearest_fib(price, retrace) if retrace else ("N/A", 999)

        patterns = detect_patterns(m15, idx_pos)

        rows.append({
            "time":       t,
            "hour_utc":   t.hour,
            "day":        t.day_name(),
            "direction":  direction,
            "entry":      price,
            "pnl":        trade["pnl"],
            "fib_level":  fib_label,
            "fib_dist":   round(fib_dist * 100, 3),
            "patterns":   ", ".join(patterns),
        })

    enriched = pd.DataFrame(rows)
    enriched.to_csv("losses_enriched.csv", index=False)

    n = len(enriched)
    print(f"\n{'='*60}")
    print(f"LOSS BREAKDOWN — EUR/USD Scalp 2023  ({n} losing trades)")
    print("=" * 60)

    # Hour of day
    print("\n--- Hour of day (UTC) ---")
    hour_counts = enriched["hour_utc"].value_counts().sort_index()
    for h, c in hour_counts.items():
        bar = "#" * c
        session = _session(h)
        print(f"  {h:02d}:00  {bar:<12} {c} trade(s)  [{session}]")

    # Day of week
    print("\n--- Day of week ---")
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
    day_counts = enriched["day"].value_counts().reindex(day_order).fillna(0).astype(int)
    for day, c in day_counts.items():
        bar = "#" * c
        print(f"  {day:<12} {bar:<12} {c}")

    # Fib level
    print("\n--- Nearest Fib retracement level at entry ---")
    fib_counts = enriched["fib_level"].value_counts()
    for lvl, c in fib_counts.items():
        avg_dist = enriched[enriched["fib_level"] == lvl]["fib_dist"].mean()
        print(f"  {lvl:<8} {c} trade(s)  avg distance from level: {avg_dist:.2f}%")

    # Candlestick patterns
    print("\n--- Candlestick patterns on signal candle ---")
    all_patterns = []
    for p in enriched["patterns"]:
        all_patterns.extend([x.strip() for x in p.split(",")])
    from collections import Counter
    pattern_counts = Counter(all_patterns)
    for pat, c in pattern_counts.most_common():
        print(f"  {pat:<18} {c} occurrence(s)")

    # Direction split
    print("\n--- Direction ---")
    for d, c in enriched["direction"].value_counts().items():
        avg_pnl = enriched[enriched["direction"] == d]["pnl"].mean()
        print(f"  {d:<6} {c} losses  avg PnL: ${avg_pnl:.2f}")

    print(f"\n{'='*60}")
    print("Full detail saved to losses_enriched.csv")
    print("=" * 60)


def _session(hour):
    if 0 <= hour < 8:
        return "Asia"
    elif 8 <= hour < 12:
        return "London open"
    elif 12 <= hour < 17:
        return "NY overlap"
    else:
        return "NY/close"


if __name__ == "__main__":
    main()
