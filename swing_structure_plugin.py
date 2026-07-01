"""
Swing Structure Break Plugin
-------------------------------
Signal timeframe : LTF candles (ltf_df) -- M30 in this configuration, but
                    generic to whatever mode/timeframe pairing is passed in.
HTF candles are received but unused -- pure price-structure signal, no
higher-timeframe trend filter.

Swing point detection: reuses indicators.detect_fractals() (the same
Williams Fractal method already used in the M30 stop-distance diagnostic),
with the standard N=2 definition -- a candle whose high is the highest of
the surrounding 5 candles (2*N+1), or whose low is the lowest of the
surrounding 5. A fractal at index j is only confirmed once N candles after
j have closed, so only fractals at or before (current index - N) are ever
used -- no look-ahead.

Entry rules:
  LONG  -- price closes above the most recent CONFIRMED swing high.
  SHORT -- price closes below the most recent CONFIRMED swing low.

Stop loss : just beyond the SAME swing point that was broken (the
            structural level itself), plus a small pip buffer -- for a
            long, just below the broken swing high; for a short, just
            above the broken swing low.
Take profit: fixed 2.5R, single level (all 3 TP slots identical), same
             convention as every other plugin in this project.

Re-entry guard (deliberately NOT the single-pending-block design used by
order_block_plugin.py):
  order_block_plugin tracks one "pending" candidate and suspends ALL
  scanning until it resolves, which starves the plugin of new opportunities
  (see RESEARCH_LOG.md's order-block findings -- pending duration alone
  ate 77-81% of all candles in some configurations). This plugin instead
  tracks only the identity (confirmed-bar timestamp) of the swing point
  last used to fire in each direction. A new swing high/low is a fresh
  identity the instant it confirms, and is immediately eligible to fire
  regardless of whether the previous swing point ever "resolved" --
  there is no pending state to get stuck in, and no scanning suspension
  at all. The guard only prevents re-firing on the *exact same* swing
  point across consecutive candles while price remains beyond it.

Usage:
    python D:/forex_bot/backtest.py --instrument GBP_USD --mode scalp \\
        --start 2023-01-01 --end 2024-01-01 \\
        --signals-module D:/forex_bot/swing_structure_plugin.py
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal
from indicators import detect_fractals


# ── Constants (captured automatically in backtest header) ─────────────────────

_FRACTAL_N       = 2      # standard Williams Fractal: high/low of surrounding 2N+1 candles
_SL_BUFFER_PIPS  = 2.0    # extra buffer beyond the broken swing point
_TP_R_MULTIPLE   = 2.5


def _pip_size(instrument: str) -> float:
    return 0.01 if "JPY" in instrument else 0.0001


# ── Re-entry state ────────────────────────────────────────────────────────────
# Identity (confirmed-bar timestamp) of the swing point last used to fire in
# each direction. Module-level so state persists across all generate_signal
# calls within a single run, then resets between separate runs because
# _load_plugin() creates a fresh module object each time.
_last_long_swing_id: object = None
_last_short_swing_id: object = None


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # unused -- pure price-structure signal
    ltf_df: pd.DataFrame,   # signal-timeframe candles
    mode: str,
) -> Signal | None:
    global _last_long_swing_id, _last_short_swing_id

    needed = _FRACTAL_N * 2 + 2
    if len(ltf_df) < needed:
        return None

    fdf = detect_fractals(ltf_df[["open", "high", "low", "close"]], period=_FRACTAL_N)

    # Only fractals confirmed as of THIS candle are usable -- a fractal at
    # index j needs _FRACTAL_N candles after j to confirm, so the latest
    # usable index is (current last index - _FRACTAL_N).
    confirmed_cutoff = len(ltf_df) - 1 - _FRACTAL_N
    if confirmed_cutoff < 0:
        return None

    fractal_highs = fdf["fractal_high"].iloc[: confirmed_cutoff + 1].dropna()
    fractal_lows  = fdf["fractal_low"].iloc[: confirmed_cutoff + 1].dropna()

    candle = ltf_df.iloc[-1]
    close  = float(candle["close"])
    pip    = _pip_size(instrument)
    buffer = _SL_BUFFER_PIPS * pip

    # ── LONG: close breaks above the most recent confirmed swing high ────────
    if not fractal_highs.empty:
        swing_high_id    = fractal_highs.index[-1]
        swing_high_price = float(fractal_highs.iloc[-1])
        if close > swing_high_price and swing_high_id != _last_long_swing_id:
            _last_long_swing_id = swing_high_id
            entry = close
            sl    = swing_high_price - buffer
            risk  = entry - sl
            if risk > 0:
                tp = entry + _TP_R_MULTIPLE * risk
                return Signal(
                    direction="long",
                    entry_price=entry,
                    stop_loss=sl,
                    take_profits=[tp, tp, tp],
                    instrument=instrument,
                    timeframe=ltf_df.index[-1].isoformat(),
                    reason=f"Swing structure break long (close {close:.5f} > "
                           f"swing high {swing_high_price:.5f})",
                )

    # ── SHORT: close breaks below the most recent confirmed swing low ────────
    if not fractal_lows.empty:
        swing_low_id    = fractal_lows.index[-1]
        swing_low_price = float(fractal_lows.iloc[-1])
        if close < swing_low_price and swing_low_id != _last_short_swing_id:
            _last_short_swing_id = swing_low_id
            entry = close
            sl    = swing_low_price + buffer
            risk  = sl - entry
            if risk > 0:
                tp = entry - _TP_R_MULTIPLE * risk
                return Signal(
                    direction="short",
                    entry_price=entry,
                    stop_loss=sl,
                    take_profits=[tp, tp, tp],
                    instrument=instrument,
                    timeframe=ltf_df.index[-1].isoformat(),
                    reason=f"Swing structure break short (close {close:.5f} < "
                           f"swing low {swing_low_price:.5f})",
                )

    return None
