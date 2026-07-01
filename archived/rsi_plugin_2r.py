"""
RSI Scalp Strategy Plugin
--------------------------
Signal timeframe : M15  (ltf_df)
Trend filter     : H1   (htf_df)

Entry rules:
  LONG  — H1 bullish (EMA20 > EMA50) AND RSI(14) on M15 was below 30
           on the previous candle and is now >= 30 (oversold recovery)
  SHORT — H1 bearish (EMA20 < EMA50) AND RSI(14) on M15 was above 70
           on the previous candle and is now <= 70 (overbought rejection)

Risk management (delegated to framework):
  SL  : below signal candle low (long) / above signal candle high (short)
  TP  : 1.5 × risk (all three TP slots set to same level so full position exits)

Usage:
    python D:/rhyme/backtest.py --instrument EUR_USD --mode scalp \\
        --start 2023-01-01 --end 2024-01-01 \\
        --signals-module D:/rhyme/rsi_plugin.py
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from strategy import Signal


# ── RSI calculation ───────────────────────────────────────────────────────────

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder's smoothing (same as TradingView default)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ── Signal generator ──────────────────────────────────────────────────────────

_RSI_PERIOD = 14
_OVERSOLD = 30
_OVERBOUGHT = 70
_TP_R_MULTIPLE = 2.0
# Minimum candle body/wick to use as SL buffer (avoids zero-pip SL)
_SL_MIN_PIPS = {
    "EUR_USD": 0.0003,
    "GBP_USD": 0.0003,
    "USD_JPY": 0.03,
}
_SL_DEFAULT_BUFFER = 0.0003


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # H1 candles with ema_20, ema_50
    ltf_df: pd.DataFrame,   # M15 candles
    mode: str,
) -> Signal | None:
    # Need at least RSI period + 2 candles for crossover detection
    if len(ltf_df) < _RSI_PERIOD + 2 or len(htf_df) < 3:
        return None

    # ── Wednesday skip (day_of_week: 0=Mon … 2=Wed … 4=Fri) ─────────────────
    if ltf_df.index[-1].day_of_week == 2:
        return None

    # ── H1 trend filter ───────────────────────────────────────────────────────
    htf = htf_df.iloc[-1]
    htf_bull = htf["ema_20"] > htf["ema_50"]
    htf_bear = htf["ema_20"] < htf["ema_50"]

    if not htf_bull and not htf_bear:
        return None

    # ── RSI on M15 ────────────────────────────────────────────────────────────
    rsi = _rsi(ltf_df["close"], _RSI_PERIOD)
    if rsi.isna().iloc[-1] or rsi.isna().iloc[-2]:
        return None

    rsi_now = rsi.iloc[-1]
    rsi_prev = rsi.iloc[-2]

    candle = ltf_df.iloc[-1]
    buf = _SL_MIN_PIPS.get(instrument, _SL_DEFAULT_BUFFER)

    # ── LONG: oversold recovery ───────────────────────────────────────────────
    if htf_bull and rsi_prev < _OVERSOLD and rsi_now >= _OVERSOLD:
        entry = float(candle["close"])
        sl = float(candle["low"]) - buf
        risk = entry - sl
        if risk <= 0:
            return None
        tp = entry + _TP_R_MULTIPLE * risk
        return Signal(
            direction="long",
            entry_price=entry,
            stop_loss=sl,
            take_profits=[tp, tp, tp],   # all 3 slots = same level → full exit at 1.5R
            instrument=instrument,
            timeframe="M15",
            reason=f"RSI oversold recovery ({rsi_prev:.1f}→{rsi_now:.1f})",
        )

    # ── SHORT: overbought rejection ───────────────────────────────────────────
    if htf_bear and rsi_prev > _OVERBOUGHT and rsi_now <= _OVERBOUGHT:
        entry = float(candle["close"])
        sl = float(candle["high"]) + buf
        risk = sl - entry
        if risk <= 0:
            return None
        tp = entry - _TP_R_MULTIPLE * risk
        return Signal(
            direction="short",
            entry_price=entry,
            stop_loss=sl,
            take_profits=[tp, tp, tp],
            instrument=instrument,
            timeframe="M15",
            reason=f"RSI overbought rejection ({rsi_prev:.1f}→{rsi_now:.1f})",
        )

    return None
