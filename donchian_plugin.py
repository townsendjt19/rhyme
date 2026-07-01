"""
Donchian Channel Breakout Plugin
---------------------------------
Signal timeframe : LTF candles (ltf_df)  — H4 in swing, H1 in intraday, M15 in scalp
Trend filter     : HTF candles (htf_df)  — EMA20 > EMA50 required for direction

Entry rules:
  LONG  — HTF bullish (EMA20 > EMA50) AND close of current candle breaks above
           the 20-period Donchian upper band (highest high of last 20 candles)
  SHORT — HTF bearish (EMA20 < EMA50) AND close of current candle breaks below
           the 20-period Donchian lower band (lowest low of last 20 candles)

Stop loss:
  Midpoint of the channel at time of signal.
  This gives ~1:1 risk relative to half the channel width, producing meaningful
  R:R when combined with the 2.5R TP target.

Take profit:
  2.5R — full position exits at a single level (all 3 TP slots identical).

No day-of-week filter — test clean, analyze Wednesday separately.

Usage:
    python D:/rhyme/backtest.py --instrument GBP_USD --mode swing \\
        --start 2023-01-01 --end 2024-01-01 \\
        --signals-module D:/rhyme/donchian_plugin.py
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal


# ── Constants (captured automatically in backtest header) ─────────────────────

_DONCHIAN_PERIOD = 20
_TP_R_MULTIPLE   = 2.5

# ── Re-entry state ────────────────────────────────────────────────────────────
# A signal fires only once per breakout. After a long signal fires, _long_armed
# is set False and only re-arms when price closes back inside the channel
# (close <= upper). Symmetric for shorts. Module-level so state persists across
# all generate_signal calls within a single backtest run, then resets between
# separate runs because _load_plugin() creates a fresh module object each time.
_long_armed:  bool = True
_short_armed: bool = True


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # higher-timeframe candles with ema_20, ema_50
    ltf_df: pd.DataFrame,   # signal-timeframe candles
    mode: str,
) -> Signal | None:
    global _long_armed, _short_armed

    if len(ltf_df) < _DONCHIAN_PERIOD + 1 or len(htf_df) < 2:
        return None

    # ── HTF trend filter ──────────────────────────────────────────────────────
    htf = htf_df.iloc[-1]
    htf_bull = htf["ema_20"] > htf["ema_50"]
    htf_bear = htf["ema_20"] < htf["ema_50"]

    if not htf_bull and not htf_bear:
        return None

    # ── Donchian channel on LTF (exclude current candle from lookback) ────────
    # Use the prior _DONCHIAN_PERIOD candles so the channel is defined before
    # the breakout candle closes — avoids look-ahead bias.
    lookback = ltf_df.iloc[-(_DONCHIAN_PERIOD + 1):-1]
    upper = float(lookback["high"].max())
    lower = float(lookback["low"].min())
    mid   = (upper + lower) / 2.0

    candle = ltf_df.iloc[-1]
    close  = float(candle["close"])

    # ── Re-arm: price returned inside the channel since the last signal ────────
    # Long re-arms when close drops back to or below the upper band.
    # Short re-arms when close rises back to or above the lower band.
    if close <= upper:
        _long_armed = True
    if close >= lower:
        _short_armed = True

    # ── LONG: close breaks above upper band (first candle only) ───────────────
    if htf_bull and close > upper and _long_armed:
        _long_armed = False   # disarm until price returns inside the channel
        entry = close
        sl    = mid
        risk  = entry - sl
        if risk <= 0:
            return None
        tp = entry + _TP_R_MULTIPLE * risk
        return Signal(
            direction="long",
            entry_price=entry,
            stop_loss=sl,
            take_profits=[tp, tp, tp],
            instrument=instrument,
            timeframe=ltf_df.index[-1].isoformat(),
            reason=f"Donchian breakout long (close {close:.5f} > upper {upper:.5f}, mid SL {sl:.5f})",
        )

    # ── SHORT: close breaks below lower band (first candle only) ──────────────
    if htf_bear and close < lower and _short_armed:
        _short_armed = False  # disarm until price returns inside the channel
        entry = close
        sl    = mid
        risk  = sl - entry
        if risk <= 0:
            return None
        tp = entry - _TP_R_MULTIPLE * risk
        return Signal(
            direction="short",
            entry_price=entry,
            stop_loss=sl,
            take_profits=[tp, tp, tp],
            instrument=instrument,
            timeframe=ltf_df.index[-1].isoformat(),
            reason=f"Donchian breakout short (close {close:.5f} < lower {lower:.5f}, mid SL {sl:.5f})",
        )

    return None
