"""
Volume Profile — rolling 20-candle window.

Splits the price range of the window into bins, assigns volume to each bin,
and classifies bins as High Volume Node (HVN) or Low Volume Node (LVN).

A price is inside an LVN if it falls into a bin whose volume is below the
LVN threshold (default: bottom 30% of volume distribution).
"""
import numpy as np
import pandas as pd


def build_volume_profile(
    df: pd.DataFrame,
    window: int = 20,
    bins: int = 20,
    lvn_pct: float = 0.30,
) -> dict:
    """
    Build a volume profile over the last `window` candles.

    Returns a dict with:
        bin_edges  : array of price levels (len = bins + 1)
        bin_vol    : volume per bin (len = bins)
        lvn_ranges : list of (low, high) tuples for LVN zones
        hvn_ranges : list of (low, high) tuples for HVN zones
        threshold  : volume cutoff used to classify LVN vs HVN
    """
    subset = df.tail(window)
    if subset.empty:
        return {}

    price_low = subset["low"].min()
    price_high = subset["high"].max()

    if price_high == price_low:
        return {}

    bin_edges = np.linspace(price_low, price_high, bins + 1)
    bin_vol = np.zeros(bins)

    for _, row in subset.iterrows():
        # Distribute candle's volume proportionally across its price range
        candle_low = row["low"]
        candle_high = row["high"]
        vol = row["volume"]

        for b in range(bins):
            overlap_low = max(bin_edges[b], candle_low)
            overlap_high = min(bin_edges[b + 1], candle_high)
            if overlap_high <= overlap_low:
                continue
            candle_span = candle_high - candle_low
            if candle_span == 0:
                bin_vol[b] += vol / bins
            else:
                bin_vol[b] += vol * (overlap_high - overlap_low) / candle_span

    threshold = np.percentile(bin_vol[bin_vol > 0], lvn_pct * 100) if bin_vol.any() else 0

    lvn_ranges = []
    hvn_ranges = []
    for b in range(bins):
        lo, hi = float(bin_edges[b]), float(bin_edges[b + 1])
        if bin_vol[b] <= threshold:
            lvn_ranges.append((lo, hi))
        else:
            hvn_ranges.append((lo, hi))

    return {
        "bin_edges": bin_edges,
        "bin_vol": bin_vol,
        "lvn_ranges": lvn_ranges,
        "hvn_ranges": hvn_ranges,
        "threshold": threshold,
    }


def price_in_lvn(price: float, profile: dict) -> bool:
    """Return True if price falls inside any LVN zone."""
    if not profile:
        return False
    for lo, hi in profile.get("lvn_ranges", []):
        if lo <= price <= hi:
            return True
    return False


def price_in_hvn(price: float, profile: dict) -> bool:
    """Return True if price falls inside any HVN zone."""
    if not profile:
        return False
    for lo, hi in profile.get("hvn_ranges", []):
        if lo <= price <= hi:
            return True
    return False
