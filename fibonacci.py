"""
Fibonacci retracement and extension levels.

Direction-aware:
  Long  — anchor = swing low,  peak = swing high
           Retracements draw DOWN from peak toward anchor.
           Extensions project UP   beyond peak.

  Short — anchor = swing high, peak = swing low
           Retracements draw UP   from peak toward anchor.
           Extensions project DOWN beyond peak.

Swing points are sourced from Williams Fractal detection in indicators.py.
"""
import pandas as pd
import numpy as np
from indicators import last_fractal_high, last_fractal_low

RETRACE_LEVELS = [0.382, 0.500, 0.618]
EXTENSION_LEVELS = [1.272, 1.618, 2.000]


def _swing_for_long(df: pd.DataFrame, before_idx: int | None = None):
    """Return (swing_low, swing_high) for a long trade using fractals."""
    swing_low = last_fractal_low(df, before_idx)
    swing_high = last_fractal_high(df, before_idx)
    return swing_low, swing_high


def _swing_for_short(df: pd.DataFrame, before_idx: int | None = None):
    """Return (swing_high, swing_low) for a short trade using fractals."""
    swing_high = last_fractal_high(df, before_idx)
    swing_low = last_fractal_low(df, before_idx)
    return swing_high, swing_low


def fib_retracements_long(df: pd.DataFrame, before_idx: int | None = None) -> dict:
    """
    Compute retracement prices for a long setup.
    anchor = swing_low, peak = swing_high
    retracement = peak - ratio * (peak - anchor)
    """
    anchor, peak = _swing_for_long(df, before_idx)
    if anchor is None or peak is None or peak <= anchor:
        return {}
    span = peak - anchor
    return {r: round(peak - r * span, 6) for r in RETRACE_LEVELS}


def fib_extensions_long(df: pd.DataFrame, before_idx: int | None = None) -> dict:
    """
    Compute extension TP prices for a long setup.
    extension = anchor + ratio * (peak - anchor)
    where anchor = swing_low, peak = swing_high
    """
    anchor, peak = _swing_for_long(df, before_idx)
    if anchor is None or peak is None or peak <= anchor:
        return {}
    span = peak - anchor
    return {r: round(anchor + r * span, 6) for r in EXTENSION_LEVELS}


def fib_retracements_short(df: pd.DataFrame, before_idx: int | None = None) -> dict:
    """
    Compute retracement prices for a short setup.
    anchor = swing_high, peak = swing_low
    retracement = peak + ratio * (anchor - peak)   (draws UP)
    """
    anchor, peak = _swing_for_short(df, before_idx)
    if anchor is None or peak is None or anchor <= peak:
        return {}
    span = anchor - peak
    return {r: round(peak + r * span, 6) for r in RETRACE_LEVELS}


def fib_extensions_short(df: pd.DataFrame, before_idx: int | None = None) -> dict:
    """
    Compute extension TP prices for a short setup.
    extension = anchor - ratio * (anchor - peak)   (projects DOWN)
    """
    anchor, peak = _swing_for_short(df, before_idx)
    if anchor is None or peak is None or anchor <= peak:
        return {}
    span = anchor - peak
    return {r: round(anchor - r * span, 6) for r in EXTENSION_LEVELS}


def price_near_retracement(price: float, retracements: dict, tolerance: float = 0.005) -> bool:
    """
    Return True if price is within tolerance fraction of any retracement level.
    Default 0.5% tolerance.
    """
    for level_price in retracements.values():
        if abs(price - level_price) / level_price <= tolerance:
            return True
    return False


def get_extension_tps(df: pd.DataFrame, direction: str, before_idx: int | None = None) -> list[float]:
    """
    Return ordered list of TP prices at 1.272, 1.618, 2.0 extensions.

    direction : "long" or "short"
    """
    if direction == "long":
        ext = fib_extensions_long(df, before_idx)
    else:
        ext = fib_extensions_short(df, before_idx)

    if not ext:
        return []

    ordered = sorted(EXTENSION_LEVELS)
    if direction == "short":
        ordered = list(reversed(ordered))  # TPs go lower for shorts

    return [ext[r] for r in ordered if r in ext]
