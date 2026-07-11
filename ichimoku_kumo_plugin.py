"""
Ichimoku Kumo Breakout Plugin — classic-indicator screen (registration
RESEARCH_LOG 2026-07-11)
-------------------------------------------------------------------------
Standard 9/26/52 Ichimoku, cloud (Kumo) breakout only. htf_df deliberately
ignored — standalone-indicator test.

Entry (at M30 close):
  LONG  — close crosses above the cloud top (close > max(SSA,SSB) at this bar,
          prior close <= prior cloud top)
  SHORT — symmetric below the cloud bottom.

Stop loss: Kijun-sen at signal (book-standard reference); skip if risk <= 0.
Take profit: 2.5R single target (all 3 TP slots identical), fire-and-forget.

Cross-detection is inherently one-shot (needs the prior bar on the other
side), so no armed flag is required.
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal

WARMUP_HTF_CANDLES = 110

_TENKAN, _KIJUN, _SENKOU = 9, 26, 52
_SHIFT = 26
_TP_R_MULTIPLE = 2.5

# The harness passes the full growing history each call; Ichimoku's rolling
# midpoints only look back _SENKOU + _SHIFT + 1 bars, so a fixed tail is
# EXACT (no recursion) and keeps per-candle cost constant.
_TAIL = 2 * (_SENKOU + _SHIFT)


def _midpoint(df: pd.DataFrame, period: int) -> pd.Series:
    return (df["high"].rolling(period).max() + df["low"].rolling(period).min()) / 2.0


def ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    """Standard 9/26/52 lines; ssa/ssb are the cloud AT each bar (spans
    computed _SHIFT bars earlier, i.e. already shifted forward)."""
    out = pd.DataFrame(index=df.index)
    out["tenkan"] = _midpoint(df, _TENKAN)
    out["kijun"]  = _midpoint(df, _KIJUN)
    out["ssa"] = ((out["tenkan"] + out["kijun"]) / 2.0).shift(_SHIFT)
    out["ssb"] = _midpoint(df, _SENKOU).shift(_SHIFT)
    return out


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # ignored — standalone-indicator test
    ltf_df: pd.DataFrame,
    mode: str,
) -> Signal | None:
    if len(ltf_df) < _SENKOU + _SHIFT + 2:
        return None

    ich = ichimoku(ltf_df.iloc[-_TAIL:])
    cur, prev = ich.iloc[-1], ich.iloc[-2]
    if cur[["ssa", "ssb", "kijun"]].isna().any() or prev[["ssa", "ssb"]].isna().any():
        return None

    close      = float(ltf_df["close"].iloc[-1])
    prev_close = float(ltf_df["close"].iloc[-2])
    cloud_top,  prev_top    = max(cur["ssa"], cur["ssb"]), max(prev["ssa"], prev["ssb"])
    cloud_bot,  prev_bot    = min(cur["ssa"], cur["ssb"]), min(prev["ssa"], prev["ssb"])
    kijun = float(cur["kijun"])

    # ── LONG: close crosses above the cloud top ───────────────────────────────
    if close > cloud_top and prev_close <= prev_top:
        risk = close - kijun
        if risk <= 0:
            return None
        tp = close + _TP_R_MULTIPLE * risk
        return Signal(
            direction="long",
            entry_price=close,
            stop_loss=kijun,
            take_profits=[tp, tp, tp],
            instrument=instrument,
            timeframe=ltf_df.index[-1].isoformat(),
            reason=f"Kumo breakout long (close {close:.5f} > cloud top {cloud_top:.5f}, Kijun SL {kijun:.5f})",
        )

    # ── SHORT: close crosses below the cloud bottom ───────────────────────────
    if close < cloud_bot and prev_close >= prev_bot:
        risk = kijun - close
        if risk <= 0:
            return None
        tp = close - _TP_R_MULTIPLE * risk
        return Signal(
            direction="short",
            entry_price=close,
            stop_loss=kijun,
            take_profits=[tp, tp, tp],
            instrument=instrument,
            timeframe=ltf_df.index[-1].isoformat(),
            reason=f"Kumo breakout short (close {close:.5f} < cloud bottom {cloud_bot:.5f}, Kijun SL {kijun:.5f})",
        )

    return None
