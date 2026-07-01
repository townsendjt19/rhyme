"""
MACD + RSI Confluence Plugin
------------------------------
Signal timeframe : M15  (ltf_df)
Trend filter     : H1   (htf_df — ema_20 vs ema_50, pre-computed by backtest.py)

Entry rules
-----------
Long  : MACD line crosses ABOVE signal line  AND  RSI in 40-60  AND  H1 ema_20 > ema_50
Short : MACD line crosses BELOW signal line  AND  RSI in 40-60  AND  H1 ema_20 < ema_50

The RSI 40-60 band confirms that momentum is building but not yet exhausted —
it screens out entries at overbought/oversold extremes where mean-reversion risk is high.

Filters
-------
  • Wednesday skip
  • Minimum SL distance (to avoid near-zero-risk trades from tiny candles)

Trade management
----------------
  SL  : signal candle low  − pip buffer  (long)
         signal candle high + pip buffer  (short)
  TP  : entry ± 2.5 × risk  (all three TP slots set equal → full exit at once)

Usage
-----
    python D:/rhyme/backtest.py --instrument USD_JPY --mode scalp \\
        --start 2023-01-01 --end 2024-01-01 \\
        --signals-module D:/rhyme/macd_rsi_plugin.py
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from strategy import Signal

# ── Tunable parameters ────────────────────────────────────────────────────────

_MACD_FAST   = 12
_MACD_SLOW   = 26
_MACD_SIGNAL = 9
_RSI_PERIOD  = 14
_RSI_LOW     = 40    # RSI must be ABOVE this for both long and short
_RSI_HIGH    = 60    # RSI must be BELOW this for both long and short
_TP_R        = 2.5

# Minimum SL distance (price units).  Avoids sizing into tiny-candle setups.
_SL_MIN: dict[str, float] = {
    "EUR_USD": 0.0005,   # 5 pips
    "GBP_USD": 0.0005,
    "AUD_USD": 0.0005,
    "USD_CAD": 0.0005,
    "USD_JPY": 0.05,     # 5 pips
    "EUR_JPY": 0.05,
    "GBP_JPY": 0.05,
}
_SL_MIN_DEFAULT = 0.0005

# SL buffer beyond candle wick (price units)
_SL_BUFFER: dict[str, float] = {
    "USD_JPY": 0.03, "EUR_JPY": 0.03, "GBP_JPY": 0.03,
}
_SL_BUFFER_DEFAULT = 0.0003

# Minimum candles needed for MACD warm-up
_MIN_CANDLES = _MACD_SLOW + _MACD_SIGNAL + 10


# ── Indicator helpers ─────────────────────────────────────────────────────────

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Returns (macd_line, signal_line)."""
    fast   = _ema(close, _MACD_FAST)
    slow   = _ema(close, _MACD_SLOW)
    macd   = fast - slow
    signal = _ema(macd, _MACD_SIGNAL)
    return macd, signal


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder smoothing RSI (matches rsi_plugin.py)."""
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ── Signal generator ──────────────────────────────────────────────────────────

def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # H1 — provides trend filter via ema_20 / ema_50
    ltf_df: pd.DataFrame,   # M15 — MACD + RSI signal source
    mode: str,
) -> Signal | None:

    if len(ltf_df) < _MIN_CANDLES or len(htf_df) < 3:
        return None

    # ── 1. Wednesday skip ─────────────────────────────────────────────────────
    if ltf_df.index[-1].day_of_week == 2:
        return None

    # ── 2. H1 trend filter (ema_20 vs ema_50 pre-computed by backtest.py) ────
    htf      = htf_df.iloc[-1]
    htf_bull = float(htf["ema_20"]) > float(htf["ema_50"])
    htf_bear = float(htf["ema_20"]) < float(htf["ema_50"])
    if not htf_bull and not htf_bear:
        return None

    # ── 3. MACD crossover on M15 ──────────────────────────────────────────────
    macd_line, sig_line = _macd(ltf_df["close"])

    if macd_line.isna().iloc[-1] or macd_line.isna().iloc[-2]:
        return None
    if sig_line.isna().iloc[-1] or sig_line.isna().iloc[-2]:
        return None

    macd_now   = float(macd_line.iloc[-1])
    macd_prev  = float(macd_line.iloc[-2])
    sig_now    = float(sig_line.iloc[-1])
    sig_prev   = float(sig_line.iloc[-2])

    crossed_up   = macd_prev < sig_prev and macd_now >= sig_now
    crossed_down = macd_prev > sig_prev and macd_now <= sig_now

    if not crossed_up and not crossed_down:
        return None

    # ── 4. RSI confirmation (40-60 band) ─────────────────────────────────────
    rsi_series = _rsi(ltf_df["close"], _RSI_PERIOD)
    if rsi_series.isna().iloc[-1]:
        return None
    rsi_now = float(rsi_series.iloc[-1])
    if not (_RSI_LOW <= rsi_now <= _RSI_HIGH):
        return None

    # ── 5. Build SL from signal candle ───────────────────────────────────────
    candle = ltf_df.iloc[-1]
    buf    = _SL_BUFFER.get(instrument, _SL_BUFFER_DEFAULT)
    sl_min = _SL_MIN.get(instrument, _SL_MIN_DEFAULT)

    # ── 6a. Long entry ────────────────────────────────────────────────────────
    if crossed_up and htf_bull:
        entry = float(candle["close"])
        sl    = float(candle["low"]) - buf
        risk  = entry - sl
        if risk < sl_min:
            return None
        tp = entry + _TP_R * risk
        return Signal(
            direction="long",
            entry_price=entry,
            stop_loss=sl,
            take_profits=[tp, tp, tp],
            instrument=instrument,
            timeframe="M15",
            reason=(
                f"MACD x-up ({macd_now:.6f}>{sig_now:.6f}) "
                f"RSI={rsi_now:.1f} H1-bull"
            ),
        )

    # ── 6b. Short entry ───────────────────────────────────────────────────────
    if crossed_down and htf_bear:
        entry = float(candle["close"])
        sl    = float(candle["high"]) + buf
        risk  = sl - entry
        if risk < sl_min:
            return None
        tp = entry - _TP_R * risk
        return Signal(
            direction="short",
            entry_price=entry,
            stop_loss=sl,
            take_profits=[tp, tp, tp],
            instrument=instrument,
            timeframe="M15",
            reason=(
                f"MACD x-down ({macd_now:.6f}<{sig_now:.6f}) "
                f"RSI={rsi_now:.1f} H1-bear"
            ),
        )

    return None
