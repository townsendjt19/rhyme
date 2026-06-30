"""
20/50/100 EMA calculation and Williams Fractal detection.
"""
import pandas as pd
import numpy as np


def add_emas(df: pd.DataFrame) -> pd.DataFrame:
    """Add ema_20, ema_50, ema_100 columns in-place and return df."""
    df = df.copy()
    df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema_100"] = df["close"].ewm(span=100, adjust=False).mean()
    return df


def ema_aligned_bull(df: pd.DataFrame, idx: int = -1) -> bool:
    """Return True when 20 > 50 > 100 at the given row index."""
    row = df.iloc[idx]
    return row["ema_20"] > row["ema_50"] > row["ema_100"]


def ema_aligned_bear(df: pd.DataFrame, idx: int = -1) -> bool:
    """Return True when 20 < 50 < 100 at the given row index."""
    row = df.iloc[idx]
    return row["ema_20"] < row["ema_50"] < row["ema_100"]


def detect_fractals(df: pd.DataFrame, period: int = 2) -> pd.DataFrame:
    """
    Williams Fractal detection.

    A fractal high at bar i: high[i] is the highest high of the surrounding
    (2*period + 1) bars.
    A fractal low  at bar i: low[i]  is the lowest  low  of the surrounding
    (2*period + 1) bars.

    Adds columns:
        fractal_high  : high price at fractal high bars, NaN elsewhere
        fractal_low   : low  price at fractal low  bars, NaN elsewhere
    """
    df = df.copy()
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)

    frac_high = np.full(n, np.nan)
    frac_low = np.full(n, np.nan)

    for i in range(period, n - period):
        window_high = highs[i - period: i + period + 1]
        window_low = lows[i - period: i + period + 1]

        if highs[i] == window_high.max():
            frac_high[i] = highs[i]
        if lows[i] == window_low.min():
            frac_low[i] = lows[i]

    df["fractal_high"] = frac_high
    df["fractal_low"] = frac_low
    return df


def last_fractal_high(df: pd.DataFrame, before_idx: int | None = None) -> float | None:
    """Return the most recent confirmed fractal high price before before_idx."""
    series = df["fractal_high"]
    if before_idx is not None:
        series = series.iloc[:before_idx]
    valid = series.dropna()
    return float(valid.iloc[-1]) if not valid.empty else None


def last_fractal_low(df: pd.DataFrame, before_idx: int | None = None) -> float | None:
    """Return the most recent confirmed fractal low price before before_idx."""
    series = df["fractal_low"]
    if before_idx is not None:
        series = series.iloc[:before_idx]
    valid = series.dropna()
    return float(valid.iloc[-1]) if not valid.empty else None


def crossover_bull(df: pd.DataFrame, idx: int = -1, lookback: int = 1) -> bool:
    """
    True if ema_20 crossed above ema_50 within the last `lookback` candles
    and both ema_20 and ema_50 are above ema_100 on the signal candle.

    lookback=1 means only the current candle (original strict behaviour).
    lookback=3 means the crossover can have occurred on any of the last 3 candles.
    """
    n = len(df)
    if n < 2:
        return False
    # Resolve negative index to positive
    pos = idx if idx >= 0 else n + idx
    cur = df.iloc[pos]
    above_100 = cur["ema_20"] > cur["ema_100"] and cur["ema_50"] > cur["ema_100"]
    if not above_100:
        return False
    # Check each candle in the lookback window as the crossover bar
    for offset in range(lookback):
        i = pos - offset          # crossover bar
        if i < 1:
            break
        c = df.iloc[i]
        p = df.iloc[i - 1]
        if p["ema_20"] <= p["ema_50"] and c["ema_20"] > c["ema_50"]:
            return True
    return False


def crossover_bear(df: pd.DataFrame, idx: int = -1, lookback: int = 1) -> bool:
    """
    True if ema_20 crossed below ema_50 within the last `lookback` candles
    and both ema_20 and ema_50 are below ema_100 on the signal candle.

    lookback=1 means only the current candle (original strict behaviour).
    lookback=3 means the crossover can have occurred on any of the last 3 candles.
    """
    n = len(df)
    if n < 2:
        return False
    pos = idx if idx >= 0 else n + idx
    cur = df.iloc[pos]
    below_100 = cur["ema_20"] < cur["ema_100"] and cur["ema_50"] < cur["ema_100"]
    if not below_100:
        return False
    for offset in range(lookback):
        i = pos - offset
        if i < 1:
            break
        c = df.iloc[i]
        p = df.iloc[i - 1]
        if p["ema_20"] >= p["ema_50"] and c["ema_20"] < c["ema_50"]:
            return True
    return False
