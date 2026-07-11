"""
ADX Gate Plugin — classic-indicator screen (registration RESEARCH_LOG 2026-07-11)
---------------------------------------------------------------------------------
Book-spec Wilder DMI/ADX(14) as the ONLY filter on a minimal directional entry.
Tests the trend-strength filter's standalone informational value — htf_df is
deliberately ignored (no EMA trend filter, no combination with anything).

Entry (at M30 close):
  LONG  — +DI14 > −DI14 AND ADX14 >= 25, first bar the joint condition
          becomes true (armed flag; re-arms when ADX < 25 or DI dominance flips)
  SHORT — symmetric.

25 is the canonical textbook trending threshold, registered once — no retries
at other thresholds.

Stop loss:
  Last confirmed Williams fractal low (long) / high (short) — the repo's
  structural-stop convention. Wilder's extreme-point stop is candle-scale and
  pre-known spread-eaten on this account.

Take profit: 2.5R single target (all 3 TP slots identical), fire-and-forget.
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal
from indicators import last_fractal_high, last_fractal_low

WARMUP_HTF_CANDLES = 110

_ADX_PERIOD    = 14
_ADX_THRESHOLD = 25.0
_TP_R_MULTIPLE = 2.5

# The harness passes the full growing history each call; Wilder smoothing
# (alpha = 1/14) only needs a bounded tail — seed influence decays by
# (13/14)^T, below double precision within ~1000 bars. Computing on this
# fixed tail is numerically identical at the evaluated bar and keeps the
# per-candle cost constant instead of O(history).
_TAIL = 1000

# ── Re-entry state ────────────────────────────────────────────────────────────
# Fires once per gate-opening: after a signal, disarm until ADX drops below the
# threshold or DI dominance flips. Module-level; fresh module per run via
# _load_plugin.
_long_armed:  bool = True
_short_armed: bool = True


def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
    """Wilder's recursive smoothing (alpha = 1/period). ewm(adjust=False)
    seeds with the first value rather than the book's first-`period` mean;
    with the _TAIL warm-up the seed difference decays below double precision
    at the evaluated bar, so the two constructions coincide where it counts."""
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def _adx(df: pd.DataFrame, period: int = _ADX_PERIOD) -> tuple[float, float, float]:
    """Return (+DI, −DI, ADX) at the last bar, book-spec Wilder."""
    high, low, close = df["high"], df["low"], df["close"]
    up_move   = high.diff()
    down_move = -low.diff()
    # Wilder's mutual-exclusion rule: only the larger of the two moves counts,
    # and only if positive.
    plus_dm  = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    atr = _wilder_smooth(tr, period)
    plus_di  = 100.0 * _wilder_smooth(plus_dm, period) / atr
    minus_di = 100.0 * _wilder_smooth(minus_dm, period) / atr
    dx  = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = _wilder_smooth(dx.fillna(0.0), period)
    return float(plus_di.iloc[-1]), float(minus_di.iloc[-1]), float(adx.iloc[-1])


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # ignored — standalone-indicator test
    ltf_df: pd.DataFrame,
    mode: str,
) -> Signal | None:
    global _long_armed, _short_armed

    if len(ltf_df) < 3 * _ADX_PERIOD:
        return None

    plus_di, minus_di, adx = _adx(ltf_df.iloc[-_TAIL:])

    # ── Re-arm: gate closed or dominance flipped since the last signal ────────
    if adx < _ADX_THRESHOLD or plus_di <= minus_di:
        _long_armed = True
    if adx < _ADX_THRESHOLD or minus_di <= plus_di:
        _short_armed = True

    if adx < _ADX_THRESHOLD:
        return None

    candle = ltf_df.iloc[-1]
    close  = float(candle["close"])

    if plus_di > minus_di and _long_armed:
        _long_armed = False
        sl = last_fractal_low(ltf_df)
        if sl is None:
            return None
        risk = close - sl
        if risk <= 0:
            return None
        tp = close + _TP_R_MULTIPLE * risk
        return Signal(
            direction="long",
            entry_price=close,
            stop_loss=sl,
            take_profits=[tp, tp, tp],
            instrument=instrument,
            timeframe=ltf_df.index[-1].isoformat(),
            reason=f"ADX gate long (+DI {plus_di:.1f} > -DI {minus_di:.1f}, ADX {adx:.1f} >= {_ADX_THRESHOLD})",
        )

    if minus_di > plus_di and _short_armed:
        _short_armed = False
        sl = last_fractal_high(ltf_df)
        if sl is None:
            return None
        risk = sl - close
        if risk <= 0:
            return None
        tp = close - _TP_R_MULTIPLE * risk
        return Signal(
            direction="short",
            entry_price=close,
            stop_loss=sl,
            take_profits=[tp, tp, tp],
            instrument=instrument,
            timeframe=ltf_df.index[-1].isoformat(),
            reason=f"ADX gate short (-DI {minus_di:.1f} > +DI {plus_di:.1f}, ADX {adx:.1f} >= {_ADX_THRESHOLD})",
        )

    return None
