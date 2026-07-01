"""
Moving Average Pullback Plugin
---------------------------------
Signal timeframe : LTF candles (ltf_df) -- M30 in this configuration, but
                    generic to whatever mode/timeframe pairing is passed in.
Trend filter      : HTF candles (htf_df) -- price vs 50 EMA, continuously
                    re-evaluated every candle (not a discrete alignment
                    state that locks in and persists) -- H4 in this
                    configuration.

Entry rules:
  LONG  -- HTF close > HTF ema_50 (continuous bull filter) AND the current
           LTF candle's range touches its own 20 EMA (low <= ema_20 <= high)
           AND the candle closes back above it (close > ema_20) -- a
           pullback-and-reclaim of the average as support.
  SHORT -- mirror image: HTF close < HTF ema_50, LTF candle touches its 20
           EMA, closes back below it (close < ema_20) -- reclaim as
           resistance.

Stop loss : just beyond the pullback candle's own extreme (low for long,
            high for short), plus a small pip buffer.
Take profit: fixed 2.5R, single level (all 3 TP slots identical), same
             convention as every other plugin in this project.

Re-entry guard:
  A single "touch and reclaim" condition is NOT self-limiting the way an
  RSI crossover is -- if price hugs the 20 EMA for several consecutive
  candles, every one of them could independently satisfy touch+reclaim and
  fire a fresh signal, the same class of bug found in Donchian's original
  design. Guarded here with per-direction armed flags: firing a signal
  disarms that direction; it only re-arms once a LATER candle's range
  clears the EMA entirely (doesn't touch it), meaning price has moved
  cleanly away and a future touch-and-reclaim is a genuinely new setup.

Usage:
    python D:/forex_bot/backtest.py --instrument GBP_USD --mode scalp \\
        --start 2023-01-01 --end 2024-01-01 \\
        --signals-module D:/forex_bot/ma_pullback_plugin.py
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal


# ── Constants (captured automatically in backtest header) ─────────────────────

_SL_BUFFER_PIPS = 2.0
_TP_R_MULTIPLE  = 2.5


def _pip_size(instrument: str) -> float:
    return 0.01 if "JPY" in instrument else 0.0001


# ── Re-entry state ────────────────────────────────────────────────────────────
# Module-level so state persists across all generate_signal calls within a
# single run, then resets between separate runs because _load_plugin()
# creates a fresh module object each time.
_long_armed:  bool = True
_short_armed: bool = True


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # higher-timeframe candles with ema_50
    ltf_df: pd.DataFrame,   # signal-timeframe candles with ema_20
    mode: str,
) -> Signal | None:
    global _long_armed, _short_armed

    if len(htf_df) < 2 or len(ltf_df) < 2:
        return None

    pip = _pip_size(instrument)
    buffer = _SL_BUFFER_PIPS * pip

    # ── Continuous HTF trend filter: price vs 50 EMA, re-evaluated every call
    htf = htf_df.iloc[-1]
    htf_bull = htf["close"] > htf["ema_50"]
    htf_bear = htf["close"] < htf["ema_50"]

    candle = ltf_df.iloc[-1]
    high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])
    ema20 = float(candle["ema_20"])

    touches_ema = low <= ema20 <= high

    # ── Re-arm: candle clears the EMA entirely (no touch) -- price has moved
    # cleanly away, so a future touch-and-reclaim is a fresh setup.
    if not touches_ema:
        _long_armed = True
        _short_armed = True

    # ── LONG: pullback touch + reclaim above the 20 EMA ───────────────────────
    if htf_bull and touches_ema and close > ema20 and _long_armed:
        _long_armed = False
        entry = close
        sl = low - buffer
        risk = entry - sl
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
            reason=f"MA pullback long (touch {ema20:.5f}, close {close:.5f} reclaimed above)",
        )

    # ── SHORT: pullback touch + reclaim below the 20 EMA ──────────────────────
    if htf_bear and touches_ema and close < ema20 and _short_armed:
        _short_armed = False
        entry = close
        sl = high + buffer
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
            timeframe=ltf_df.index[-1].isoformat(),
            reason=f"MA pullback short (touch {ema20:.5f}, close {close:.5f} reclaimed below)",
        )

    return None
