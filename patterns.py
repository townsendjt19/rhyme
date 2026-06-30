"""
Candlestick pattern recognition — all five families.

Returns True if an opposing pattern is detected on the signal candle,
which means the entry should be SKIPPED.

Families:
  1. Doji
  2. Engulfing (Bullish / Bearish)
  3. Hammer / Hanging Man
  4. Shooting Star / Inverted Hammer
  5. Morning Star / Evening Star (3-candle)
  6. Pin Bar (inside the Hammer/Shooting Star family but listed separately)
"""
import pandas as pd


def _body(row: pd.Series) -> float:
    return abs(row["close"] - row["open"])


def _candle_range(row: pd.Series) -> float:
    return row["high"] - row["low"]


def _upper_wick(row: pd.Series) -> float:
    return row["high"] - max(row["open"], row["close"])


def _lower_wick(row: pd.Series) -> float:
    return min(row["open"], row["close"]) - row["low"]


def _is_bullish(row: pd.Series) -> bool:
    return row["close"] > row["open"]


def _is_bearish(row: pd.Series) -> bool:
    return row["close"] < row["open"]


# ── 1. Doji ──────────────────────────────────────────────────────────────────

def is_doji(row: pd.Series, threshold: float = 0.1) -> bool:
    """Body is <= threshold fraction of the full range."""
    rng = _candle_range(row)
    if rng == 0:
        return True
    return _body(row) / rng <= threshold


# ── 2. Engulfing ─────────────────────────────────────────────────────────────

def is_bullish_engulfing(prev: pd.Series, cur: pd.Series) -> bool:
    return (
        _is_bearish(prev)
        and _is_bullish(cur)
        and cur["open"] <= prev["close"]
        and cur["close"] >= prev["open"]
    )


def is_bearish_engulfing(prev: pd.Series, cur: pd.Series) -> bool:
    return (
        _is_bullish(prev)
        and _is_bearish(cur)
        and cur["open"] >= prev["close"]
        and cur["close"] <= prev["open"]
    )


# ── 3. Hammer / Hanging Man ───────────────────────────────────────────────────

def is_hammer(row: pd.Series) -> bool:
    """Long lower wick, small body, tiny upper wick — bullish reversal pattern."""
    body = _body(row)
    lower = _lower_wick(row)
    upper = _upper_wick(row)
    if body == 0:
        return False
    return lower >= 2 * body and upper <= 0.3 * body


def is_hanging_man(row: pd.Series) -> bool:
    """Same shape as hammer — context (after uptrend) makes it bearish."""
    return is_hammer(row)


# ── 4. Shooting Star / Inverted Hammer ───────────────────────────────────────

def is_shooting_star(row: pd.Series) -> bool:
    """Long upper wick, small body, tiny lower wick — bearish reversal."""
    body = _body(row)
    upper = _upper_wick(row)
    lower = _lower_wick(row)
    if body == 0:
        return False
    return upper >= 2 * body and lower <= 0.3 * body


def is_inverted_hammer(row: pd.Series) -> bool:
    return is_shooting_star(row)


# ── 5. Pin Bar ────────────────────────────────────────────────────────────────

def is_pin_bar_bull(row: pd.Series) -> bool:
    """Bullish pin bar: long lower wick >= 2/3 of total range, body in upper 1/3."""
    rng = _candle_range(row)
    if rng == 0:
        return False
    lower = _lower_wick(row)
    return lower / rng >= 0.66


def is_pin_bar_bear(row: pd.Series) -> bool:
    """Bearish pin bar: long upper wick >= 2/3 of total range, body in lower 1/3."""
    rng = _candle_range(row)
    if rng == 0:
        return False
    upper = _upper_wick(row)
    return upper / rng >= 0.66


# ── 6. Morning / Evening Star ────────────────────────────────────────────────

def is_morning_star(c1: pd.Series, c2: pd.Series, c3: pd.Series) -> bool:
    """
    Bullish 3-candle pattern:
      c1 = large bearish, c2 = small body (gap down), c3 = large bullish closing into c1 body.
    """
    large_bear = _is_bearish(c1) and _body(c1) > 0.5 * _candle_range(c1)
    small_mid = _body(c2) < 0.3 * _body(c1)
    bull_close = _is_bullish(c3) and c3["close"] > (c1["open"] + c1["close"]) / 2
    return large_bear and small_mid and bull_close


def is_evening_star(c1: pd.Series, c2: pd.Series, c3: pd.Series) -> bool:
    """
    Bearish 3-candle pattern:
      c1 = large bullish, c2 = small body (gap up), c3 = large bearish closing into c1 body.
    """
    large_bull = _is_bullish(c1) and _body(c1) > 0.5 * _candle_range(c1)
    small_mid = _body(c2) < 0.3 * _body(c1)
    bear_close = _is_bearish(c3) and c3["close"] < (c1["open"] + c1["close"]) / 2
    return large_bull and small_mid and bear_close


# ── Opposing-pattern filter (used by strategy.py) ────────────────────────────

def has_opposing_pattern_long(df: pd.DataFrame, idx: int = -1) -> bool:
    """
    Return True if the signal candle (idx) shows a pattern that opposes a LONG
    entry — i.e. a bearish or indecision pattern.

    Checked: Doji, Bearish Engulfing, Shooting Star, Bearish Pin Bar, Evening Star.
    """
    i = idx if idx >= 0 else len(df) + idx
    row = df.iloc[i]

    if is_doji(row):
        return True

    if i >= 1:
        prev = df.iloc[i - 1]
        if is_bearish_engulfing(prev, row):
            return True
        if i >= 2:
            c1 = df.iloc[i - 2]
            c2 = prev
            if is_evening_star(c1, c2, row):
                return True

    if is_shooting_star(row):
        return True

    if is_pin_bar_bear(row):
        return True

    return False


def has_opposing_pattern_short(df: pd.DataFrame, idx: int = -1) -> bool:
    """
    Return True if the signal candle shows a pattern that opposes a SHORT entry
    — i.e. a bullish or indecision pattern.

    Checked: Doji, Bullish Engulfing, Hammer, Bullish Pin Bar, Morning Star.
    """
    i = idx if idx >= 0 else len(df) + idx
    row = df.iloc[i]

    if is_doji(row):
        return True

    if i >= 1:
        prev = df.iloc[i - 1]
        if is_bullish_engulfing(prev, row):
            return True
        if i >= 2:
            c1 = df.iloc[i - 2]
            c2 = prev
            if is_morning_star(c1, c2, row):
                return True

    if is_hammer(row):
        return True

    if is_pin_bar_bull(row):
        return True

    return False
