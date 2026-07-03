"""
NY-close / Sydney-open liquidity trough — cheap falsification check.

Pre-scoping triage (2026-07-03), NOT an active research line. Tests whether
the 17:00-19:00 ET FX liquidity trough shows a structural, cross-pair
range/volatility/activity anomaly on M5 bars. Data-analysis only: no entry
logic, no backtest, no sizing. Decision criteria per the handoff: visible
cross-pair dip/spike in the window vs neighboring hours = worth continuing;
flat or single-pair-only = dead, same-day kill.

Run: D:/rhyme/venv/Scripts/python.exe D:/rhyme/liquidity_trough_check.py
Output: liquidity_trough_check.png + console readout table.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from data import fetch_candles

PAIRS = ["AUD_USD", "NZD_USD", "USD_JPY"]
GRANULARITY = "M5"
# 12 months so both US DST transitions (Nov 2025, Mar 2026) are inside the
# window — a correct tz_convert must keep the 17:00 ET bucket aligned across
# both regimes, and the window is long enough to average single-event noise.
START = datetime(2025, 7, 1, tzinfo=timezone.utc)
END = datetime(2026, 7, 1, tzinfo=timezone.utc)
ET = ZoneInfo("America/New_York")  # IANA zone: exact per-date DST, no fixed offset

WINDOW = (17 * 60, 19 * 60)          # 17:00-19:00 ET, minutes-of-day
NEIGHBORS = [(15 * 60, 17 * 60), (19 * 60, 21 * 60)]


def pip_size(pair: str) -> float:
    return 0.01 if pair.endswith("JPY") else 0.0001


def bucket_stats(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    """Per minute-of-day (ET) bucket: mean bar range (pips), stdev of
    bar-to-bar log returns, mean tick volume."""
    et_index = df.index.tz_convert(ET)
    df = df.copy()
    df["minute_of_day"] = et_index.hour * 60 + et_index.minute
    df["et_weekday"] = et_index.weekday  # 0=Mon .. 6=Sun
    # Exclude ET Sunday: the Sunday 17:00 Sydney open is the WEEKLY open
    # (gap over two closed days) — a different phenomenon than the daily
    # Mon-Thu rollover trough this idea is about.
    df = df[df["et_weekday"] != 6]
    df["range_pips"] = (df["high"] - df["low"]) / pip_size(pair)
    df["log_ret"] = np.log(df["close"]).diff()
    g = df.groupby("minute_of_day")
    out = pd.DataFrame({
        "mean_range_pips": g["range_pips"].mean(),
        "ret_stdev": g["log_ret"].std(),
        "mean_volume": g["volume"].mean(),
        "n_bars": g.size(),
    })
    return out


def window_mean(stats: pd.DataFrame, col: str, lo: int, hi: int) -> float:
    mask = (stats.index >= lo) & (stats.index < hi)
    return float(stats.loc[mask, col].mean())


def main():
    all_stats: dict[str, pd.DataFrame] = {}
    for pair in PAIRS:
        print(f"Fetching {pair} {GRANULARITY} {START.date()} -> {END.date()} ...")
        df = fetch_candles(pair, GRANULARITY, from_time=START, to_time=END)
        print(f"  {len(df)} bars")
        all_stats[pair] = bucket_stats(df, pair)

    metrics = [
        ("mean_range_pips", "Mean bar range (rel. to pair median)"),
        ("ret_stdev", "Stdev of bar returns (rel. to pair median)"),
        ("mean_volume", "Mean tick volume (rel. to pair median)"),
    ]

    fig, axes = plt.subplots(len(metrics), 1, figsize=(14, 11), sharex=True)
    hours = np.arange(0, 25, 2)
    for ax, (col, title) in zip(axes, metrics):
        for pair in PAIRS:
            s = all_stats[pair][col]
            ax.plot(s.index / 60, s / s.median(), label=pair, alpha=0.8, lw=0.9)
        ax.axvspan(17, 19, color="red", alpha=0.12, label="17:00-19:00 ET")
        ax.axhline(1.0, color="gray", lw=0.5, ls="--")
        ax.set_title(title)
        ax.set_xticks(hours)
        ax.set_xlim(0, 24)
        ax.legend(loc="upper right", fontsize=8)
    axes[-1].set_xlabel("Hour of day (ET, DST-adjusted per bar date)")
    fig.suptitle("NY-close/Sydney-open liquidity trough check — "
                 f"M5, {START.date()} to {END.date()}, ET Sundays excluded")
    fig.tight_layout()
    out_png = "liquidity_trough_check.png"
    fig.savefig(out_png, dpi=110)
    print(f"\nSaved {out_png}")

    # Readout table: window vs flanking 2h neighbors, per pair per metric
    print("\n=== 17:00-19:00 ET window vs neighbors (15-17 and 19-21 ET) ===")
    for col, _ in metrics:
        print(f"\n{col}:")
        print(f"{'pair':<10}{'window':>12}{'15-17':>12}{'19-21':>12}{'win/avg-nbr':>14}")
        for pair in PAIRS:
            st = all_stats[pair]
            w = window_mean(st, col, *WINDOW)
            n1 = window_mean(st, col, *NEIGHBORS[0])
            n2 = window_mean(st, col, *NEIGHBORS[1])
            ratio = w / ((n1 + n2) / 2)
            print(f"{pair:<10}{w:>12.4g}{n1:>12.4g}{n2:>12.4g}{ratio:>14.3f}")

    # Bar-count sanity: DST misalignment or a broken feed shows up here
    print("\nBar counts per bucket (sanity — should be roughly uniform "
          "across active hours):")
    for pair in PAIRS:
        st = all_stats[pair]
        w = window_mean(st, "n_bars", *WINDOW)
        day = st["n_bars"].median()
        print(f"  {pair}: window mean {w:.0f} bars/bucket vs day median "
              f"{day:.0f} ({w / day:.2f}x)")


if __name__ == "__main__":
    main()
