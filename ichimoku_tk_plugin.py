"""
Ichimoku Tenkan/Kijun Cross Plugin — classic-indicator screen (registration
RESEARCH_LOG 2026-07-11)
-----------------------------------------------------------------------------
Standard 9/26/52 Ichimoku, TK cross only — no cloud filter; tests the cross
alone. htf_df deliberately ignored — standalone-indicator test. Separate file
from the Kumo variant so each registration hash covers exactly one mechanism.

Entry (at M30 close):
  LONG  — Tenkan crosses above Kijun on this bar (prior Tenkan <= prior Kijun)
  SHORT — symmetric.

Stop loss: far cloud boundary — min(SSA,SSB) for longs, max(SSA,SSB) for
shorts (Kijun is degenerate as a stop at the cross); skip if risk <= 0, which
also drops entries on the wrong side of the cloud (inverted stop).
Take profit: 2.5R single target (all 3 TP slots identical), fire-and-forget.

Cross-detection is inherently one-shot, so no armed flag is required.
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal

WARMUP_HTF_CANDLES = 110

_TENKAN, _KIJUN, _SENKOU = 9, 26, 52
_SHIFT = 26
_TP_R_MULTIPLE = 2.5

# Fixed tail is EXACT for rolling midpoints (see ichimoku_kumo_plugin note).
_TAIL = 2 * (_SENKOU + _SHIFT)


def _midpoint(df: pd.DataFrame, period: int) -> pd.Series:
    return (df["high"].rolling(period).max() + df["low"].rolling(period).min()) / 2.0


def ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    """Standard 9/26/52 lines; ssa/ssb are the cloud AT each bar (spans
    computed _SHIFT bars earlier, i.e. already shifted forward). Duplicated
    from ichimoku_kumo_plugin by design — self-contained mechanism files."""
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
    if len(ltf_df) < 52 + 26 + 2:
        return None

    ich = ichimoku(ltf_df.iloc[-_TAIL:])
    cur, prev = ich.iloc[-1], ich.iloc[-2]
    if cur[["tenkan", "kijun", "ssa", "ssb"]].isna().any() or prev[["tenkan", "kijun"]].isna().any():
        return None

    close = float(ltf_df["close"].iloc[-1])
    cloud_bot = float(min(cur["ssa"], cur["ssb"]))
    cloud_top = float(max(cur["ssa"], cur["ssb"]))

    # ── LONG: Tenkan crosses above Kijun ──────────────────────────────────────
    if cur["tenkan"] > cur["kijun"] and prev["tenkan"] <= prev["kijun"]:
        sl = cloud_bot
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
            reason=f"TK cross long (Tenkan {cur['tenkan']:.5f} x Kijun {cur['kijun']:.5f}, cloud SL {sl:.5f})",
        )

    # ── SHORT: Tenkan crosses below Kijun ─────────────────────────────────────
    if cur["tenkan"] < cur["kijun"] and prev["tenkan"] >= prev["kijun"]:
        sl = cloud_top
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
            reason=f"TK cross short (Tenkan {cur['tenkan']:.5f} x Kijun {cur['kijun']:.5f}, cloud SL {sl:.5f})",
        )

    return None
