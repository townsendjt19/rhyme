"""
Order Block Plugin (simplest variant)
---------------------------------------
Signal timeframe : LTF candles (ltf_df) -- M15 in scalp, H1 in intraday, H4 in swing
HTF candles are received but unused -- this is a pure price-action signal
with no higher-timeframe trend filter, by design (the simplest version).

Definitions:
  Impulse        -- _IMPULSE_MIN_CANDLES or more consecutive same-direction
                     candles, each with a body >= _IMPULSE_BODY_MULTIPLIER times
                     the _AVG_BODY_PERIOD-candle average body size measured
                     BEFORE the impulse starts (so the impulse's own oversized
                     bodies never inflate the average they're compared against).
  Order block    -- the last opposing-direction candle immediately preceding
                     the impulse's first candle.
  Entry trigger  -- on a LATER candle (never the impulse's own candles), price
                     closes back inside the order block's [low, high] range.
  Invalidation   -- price closes beyond the order block's far (SL) edge before
                     ever retesting it -- the level was swept, not retested,
                     so the setup is abandoned without a trade.

Stop loss : just beyond the order block's far edge, with a small pip buffer.
Take profit: _TP_R_MULTIPLE (2.5R), single level (all 3 TP slots identical).

Re-entry guard:
  Donchian's plugin originally re-fired a fresh signal on every candle that
  stayed outside its channel, because it had no state at all. This plugin is
  built to avoid that class of bug from the start: at most one order block is
  "live" (pending retest) at a time, tracked in _pending_block. While a block
  is pending, no new impulses are scanned for. Once a block triggers a trade
  or is invalidated, its identifying timestamp is recorded in _done_block_ids
  so the exact same block can never produce a second signal, even if a stale
  reference to it somehow reappeared at the tail of the lookback window.

Usage:
    python D:/forex_bot/backtest.py --instrument GBP_USD --mode scalp \\
        --start 2023-01-01 --end 2024-01-01 \\
        --signals-module D:/forex_bot/order_block_plugin.py
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal


# ── Constants (captured automatically in backtest header) ─────────────────────

_IMPULSE_MIN_CANDLES      = 3      # consecutive same-direction candles required
_IMPULSE_BODY_MULTIPLIER  = 1.5    # each impulse candle's body >= this x avg body
_AVG_BODY_PERIOD          = 20     # lookback window for the average body size
_SL_BUFFER_PIPS           = 2.0    # extra buffer beyond the order block's far edge
_TP_R_MULTIPLE            = 2.5


def _pip_size(instrument: str) -> float:
    return 0.01 if "JPY" in instrument else 0.0001


def _body(candle) -> float:
    return abs(float(candle["close"]) - float(candle["open"]))


def _direction(candle) -> str:
    return "up" if float(candle["close"]) > float(candle["open"]) else "down"


# ── Re-entry state ────────────────────────────────────────────────────────────
# At most one order block is tracked at a time. Module-level so state persists
# across all generate_signal calls within a single run, then resets between
# separate runs because _load_plugin() creates a fresh module object each time.
_pending_block: dict | None = None
_done_block_ids: set = set()


def _find_fresh_impulse(ltf_df: pd.DataFrame):
    """
    Look at the most recent _IMPULSE_MIN_CANDLES candles. If they form a valid
    impulse (same direction, each body big enough relative to the prior
    average), and the candle immediately before the impulse is the opposing
    direction, return the order block dict. Otherwise return None.
    """
    n = _IMPULSE_MIN_CANDLES
    needed = n + 1 + _AVG_BODY_PERIOD
    if len(ltf_df) < needed:
        return None

    impulse = ltf_df.iloc[-n:]
    directions = [_direction(impulse.iloc[i]) for i in range(n)]
    if len(set(directions)) != 1:
        return None  # not all same direction
    impulse_dir = directions[0]

    # Average body size measured strictly BEFORE the impulse and the order
    # block candle, so neither contaminates the baseline it's compared against.
    avg_window = ltf_df.iloc[-(n + 1 + _AVG_BODY_PERIOD):-(n + 1)]
    avg_body = avg_window.apply(_body, axis=1).mean()
    if avg_body <= 0:
        return None

    for i in range(n):
        if _body(impulse.iloc[i]) < _IMPULSE_BODY_MULTIPLIER * avg_body:
            return None  # an impulse candle isn't large enough

    ob_candle = ltf_df.iloc[-(n + 1)]
    ob_id = ltf_df.index[-(n + 1)]
    if ob_id in _done_block_ids:
        return None  # this exact block already produced a trade or was invalidated

    if _direction(ob_candle) == impulse_dir:
        return None  # order block candle must OPPOSE the impulse direction

    ob_high = float(ob_candle["high"])
    ob_low  = float(ob_candle["low"])

    return {
        "id": ob_id,
        "impulse_dir": impulse_dir,   # "up" impulse -> long setup; "down" -> short setup
        "high": ob_high,
        "low": ob_low,
    }


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # unused -- no HTF filter in the simplest variant
    ltf_df: pd.DataFrame,   # signal-timeframe candles
    mode: str,
) -> Signal | None:
    global _pending_block

    if len(ltf_df) < _IMPULSE_MIN_CANDLES + 1 + _AVG_BODY_PERIOD:
        return None

    candle = ltf_df.iloc[-1]
    close  = float(candle["close"])
    pip    = _pip_size(instrument)
    buffer = _SL_BUFFER_PIPS * pip

    # ── A block is already pending: check retest / invalidation first ────────
    if _pending_block is not None:
        blk = _pending_block

        if blk["impulse_dir"] == "up":
            # Bullish setup: order block is the down-candle below the impulse.
            # Entry: close back inside [low, high]. Invalidation: close below
            # low (the SL side) before ever retesting -- swept, not retested.
            if blk["low"] <= close <= blk["high"]:
                entry = close
                sl    = blk["low"] - buffer
                risk  = entry - sl
                _done_block_ids.add(blk["id"])
                _pending_block = None
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
                    reason=f"Order block retest long (close {close:.5f} inside "
                           f"OB [{blk['low']:.5f}, {blk['high']:.5f}])",
                )
            if close < blk["low"]:
                _done_block_ids.add(blk["id"])
                _pending_block = None  # invalidated -- swept without retesting
                return None
            return None  # still waiting

        else:
            # Bearish setup: order block is the up-candle above the impulse.
            if blk["low"] <= close <= blk["high"]:
                entry = close
                sl    = blk["high"] + buffer
                risk  = sl - entry
                _done_block_ids.add(blk["id"])
                _pending_block = None
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
                    reason=f"Order block retest short (close {close:.5f} inside "
                           f"OB [{blk['low']:.5f}, {blk['high']:.5f}])",
                )
            if close > blk["high"]:
                _done_block_ids.add(blk["id"])
                _pending_block = None  # invalidated -- swept without retesting
                return None
            return None  # still waiting

    # ── No block pending: scan for a fresh impulse + order block ─────────────
    fresh = _find_fresh_impulse(ltf_df)
    if fresh is not None:
        _pending_block = fresh

    return None
