"""
FrAMA Cross Plugin — classic-indicator screen (registration RESEARCH_LOG
2026-07-11)
--------------------------------------------------------------------------
Ehlers Fractal Adaptive Moving Average, N=16, price-cross entry. htf_df
deliberately ignored — standalone-indicator test. FrAMA slope is NOT
registered (one canonical signal per mechanism).

Indicator (Ehlers spec):
  Window of N=16 split into halves of 8.
  N1 = (HH−LL of first half)/8, N2 = same for second half,
  N3 = (HH−LL of full 16)/16
  D = (log(N1+N2) − log(N3)) / log 2
  alpha = exp(−4.6·(D−1)), clamped to [0.01, 1]
  FrAMA_t = alpha·close + (1−alpha)·FrAMA_{t−1}, seeded with close.

Entry (at M30 close):
  LONG  — close crosses above FrAMA (prior close <= prior FrAMA)
  SHORT — symmetric.

Stop loss: last confirmed Williams fractal low/high (FrAMA is degenerate at
the cross); skip if risk <= 0.
Take profit: 2.5R single target (all 3 TP slots identical), fire-and-forget.

Cross-detection is inherently one-shot, so no armed flag is required.
"""
from __future__ import annotations
import math
import pandas as pd
from strategy import Signal
from indicators import last_fractal_high, last_fractal_low

WARMUP_HTF_CANDLES = 110

_N = 16                    # Ehlers' published default, even by construction
_HALF = _N // 2
_TP_R_MULTIPLE = 2.5

# The harness passes the full growing history each call; FrAMA's recursion
# only needs a bounded tail — with alpha >= 0.01 the seed's influence decays
# by (1-0.01)^T, below double precision within ~2000 bars. Computing on this
# fixed tail is numerically identical to the full recursion and keeps the
# per-candle cost constant instead of O(history).
_TAIL = 2000


def frama(df: pd.DataFrame, n: int = _N) -> pd.Series:
    """Ehlers FrAMA over close, computed sequentially (recursive filter)."""
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    out = [float(close[0])]
    for i in range(1, len(close)):
        if i < n:
            # Not enough history for the fractal dimension yet: pass close
            # through (alpha=1) so the warm-up region carries no signal.
            out.append(float(close[i]))
            continue
        h1 = high[i - n + 1 : i - _HALF + 1]
        l1 = low[i - n + 1 : i - _HALF + 1]
        h2 = high[i - _HALF + 1 : i + 1]
        l2 = low[i - _HALF + 1 : i + 1]
        n1 = (h1.max() - l1.min()) / _HALF
        n2 = (h2.max() - l2.min()) / _HALF
        n3 = (max(h1.max(), h2.max()) - min(l1.min(), l2.min())) / n
        if n1 + n2 <= 0 or n3 <= 0:
            alpha = 1.0
        else:
            d = (math.log(n1 + n2) - math.log(n3)) / math.log(2)
            alpha = min(1.0, max(0.01, math.exp(-4.6 * (d - 1.0))))
        out.append(alpha * float(close[i]) + (1.0 - alpha) * out[-1])
    return pd.Series(out, index=df.index)


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # ignored — standalone-indicator test
    ltf_df: pd.DataFrame,
    mode: str,
) -> Signal | None:
    if len(ltf_df) < 2 * _N:
        return None

    fr = frama(ltf_df.iloc[-_TAIL:])
    close, prev_close = float(ltf_df["close"].iloc[-1]), float(ltf_df["close"].iloc[-2])
    f_cur, f_prev = float(fr.iloc[-1]), float(fr.iloc[-2])

    # ── LONG: close crosses above FrAMA ───────────────────────────────────────
    if close > f_cur and prev_close <= f_prev:
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
            reason=f"FrAMA cross long (close {close:.5f} > FrAMA {f_cur:.5f}, fractal SL {sl:.5f})",
        )

    # ── SHORT: close crosses below FrAMA ──────────────────────────────────────
    if close < f_cur and prev_close >= f_prev:
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
            reason=f"FrAMA cross short (close {close:.5f} < FrAMA {f_cur:.5f}, fractal SL {sl:.5f})",
        )

    return None
