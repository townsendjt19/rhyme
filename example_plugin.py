"""
Example external signal plugin for backtest.py.

Usage:
    python D:/forex_bot/backtest.py --instrument EUR_USD --mode scalp \
        --start 2023-01-01 --end 2024-01-01 \
        --signals-module D:/forex_bot/example_plugin.py

The framework calls generate_signal() on every M15 candle.
The DataFrames already have EMA and fractal columns added:
    ema_20, ema_50, ema_100, fractal_high, fractal_low

Return a Signal to enter a trade, or None to skip.
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # higher TF (H1 for scalp mode), with ema/fractal columns
    ltf_df: pd.DataFrame,   # trigger TF (M15 for scalp mode), with ema/fractal columns
    mode: str,
) -> Signal | None:
    """
    Simple EMA crossover strategy: enter long when EMA20 crosses above EMA50
    on the LTF, confirmed by HTF trend (EMA20 > EMA50).

    Replace this logic with your own strategy.
    """
    if len(htf_df) < 3 or len(ltf_df) < 3:
        return None

    htf = htf_df.iloc[-1]
    ltf_now = ltf_df.iloc[-1]
    ltf_prev = ltf_df.iloc[-2]

    # HTF trend confirmation
    htf_bull = htf["ema_20"] > htf["ema_50"]
    htf_bear = htf["ema_20"] < htf["ema_50"]

    # LTF crossover
    bull_cross = ltf_prev["ema_20"] <= ltf_prev["ema_50"] and ltf_now["ema_20"] > ltf_now["ema_50"]
    bear_cross = ltf_prev["ema_20"] >= ltf_prev["ema_50"] and ltf_now["ema_20"] < ltf_now["ema_50"]

    if htf_bull and bull_cross:
        entry = ltf_now["close"]
        # SL below recent low
        sl = ltf_df["low"].iloc[-5:].min() - 0.0010
        # Fixed TP levels (not Fibonacci — just flat targets for demo)
        tp1 = entry + (entry - sl) * 1.272
        tp2 = entry + (entry - sl) * 1.618
        tp3 = entry + (entry - sl) * 2.0
        return Signal(
            direction="long",
            entry_price=entry,
            stop_loss=sl,
            take_profits=[tp1, tp2, tp3],
            instrument=instrument,
            timeframe="M15",
            reason="EMA crossover long (example plugin)",
        )

    if htf_bear and bear_cross:
        entry = ltf_now["close"]
        sl = ltf_df["high"].iloc[-5:].max() + 0.0010
        tp1 = entry - (sl - entry) * 1.272
        tp2 = entry - (sl - entry) * 1.618
        tp3 = entry - (sl - entry) * 2.0
        return Signal(
            direction="short",
            entry_price=entry,
            stop_loss=sl,
            take_profits=[tp1, tp2, tp3],
            instrument=instrument,
            timeframe="M15",
            reason="EMA crossover short (example plugin)",
        )

    return None
