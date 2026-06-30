"""
RSI Scalp + ATR Dynamic TP Plugin
-----------------------------------
Same entry rules as rsi_plugin.py (RSI oversold/overbought crossover + H1 trend filter
+ Wednesday skip), but TP is set dynamically at 2× the 14-period ATR at signal time
instead of a fixed R multiple.

SL: candle low/high + buffer (same as base plugin)
TP: entry ± 2 × ATR(14) on M15  —  all three TP slots set to the same level so
    the full position closes at once.

Usage:
    python D:/forex_bot/backtest.py --instrument EUR_USD --mode scalp \\
        --start 2023-01-01 --end 2024-01-01 \\
        --signals-module D:/forex_bot/rsi_plugin_atr.py
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from strategy import Signal

_RSI_PERIOD  = 14
_ATR_PERIOD  = 14
_ATR_MULT    = 2.0      # TP = entry ± ATR_MULT × ATR
_OVERSOLD    = 30
_OVERBOUGHT  = 70
_SL_MIN_PIPS = {"EUR_USD": 0.0003, "GBP_USD": 0.0003, "USD_JPY": 0.03}
_SL_DEFAULT_BUFFER = 0.0003


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hi, lo, prev_c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([hi - lo, (hi - prev_c).abs(), (lo - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,
    ltf_df: pd.DataFrame,
    mode: str,
) -> Signal | None:
    if len(ltf_df) < max(_RSI_PERIOD, _ATR_PERIOD) + 2 or len(htf_df) < 3:
        return None

    # Wednesday skip
    if ltf_df.index[-1].day_of_week == 2:
        return None

    # H1 trend filter
    htf      = htf_df.iloc[-1]
    htf_bull = htf["ema_20"] > htf["ema_50"]
    htf_bear = htf["ema_20"] < htf["ema_50"]
    if not htf_bull and not htf_bear:
        return None

    # RSI on M15
    rsi = _rsi(ltf_df["close"], _RSI_PERIOD)
    if rsi.isna().iloc[-1] or rsi.isna().iloc[-2]:
        return None
    rsi_now, rsi_prev = rsi.iloc[-1], rsi.iloc[-2]

    # ATR on M15
    atr_series = _atr(ltf_df, _ATR_PERIOD)
    if atr_series.isna().iloc[-1]:
        return None
    atr_val = float(atr_series.iloc[-1])

    candle = ltf_df.iloc[-1]
    buf    = _SL_MIN_PIPS.get(instrument, _SL_DEFAULT_BUFFER)

    if htf_bull and rsi_prev < _OVERSOLD and rsi_now >= _OVERSOLD:
        entry = float(candle["close"])
        sl    = float(candle["low"]) - buf
        if sl >= entry:
            return None
        tp    = entry + _ATR_MULT * atr_val
        return Signal(
            direction="long", entry_price=entry, stop_loss=sl,
            take_profits=[tp, tp, tp], instrument=instrument, timeframe="M15",
            reason=f"RSI oversold + ATR TP ({atr_val:.5f})",
        )

    if htf_bear and rsi_prev > _OVERBOUGHT and rsi_now <= _OVERBOUGHT:
        entry = float(candle["close"])
        sl    = float(candle["high"]) + buf
        if sl <= entry:
            return None
        tp    = entry - _ATR_MULT * atr_val
        return Signal(
            direction="short", entry_price=entry, stop_loss=sl,
            take_profits=[tp, tp, tp], instrument=instrument, timeframe="M15",
            reason=f"RSI overbought + ATR TP ({atr_val:.5f})",
        )

    return None
