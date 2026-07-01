"""
Trend-Origin Pullback Plugin
-------------------------------
Trend/structure timeframe : HTF candles (htf_df) -- H4 in this configuration.
Signal timeframe          : LTF candles (ltf_df) -- M30 in this configuration.

Trend detection: reuses indicators.detect_fractals() (the same Williams
Fractal method used throughout this project), N=2 standard definition,
applied to the HTF candles. Only CONFIRMED fractals (period candles after
the fractal bar have closed) are ever used -- no look-ahead.

The trend is established via CONSECUTIVE swing highs/lows (classic Dow-
theory structure), not just "whichever swing point is most recent" (that
simpler rule is what fib_retracement_plugin.py and swing_structure_plugin.py
use -- this plugin is deliberately stricter):
  - UPTREND   : the last confirmed swing high > the previous confirmed
                swing high (higher high) AND the last confirmed swing low >
                the previous confirmed swing low (higher low).
  - DOWNTREND : the last swing high < the previous swing high (lower high)
                AND the last swing low < the previous swing low (lower low).
  - Anything else (e.g. a higher high but a lower low) is not a clean trend
    -- no signal.
This requires at least 2 confirmed fractal highs AND 2 confirmed fractal
lows, one more swing point of history than the single-swing-pair plugins
in this project need.

Entry rule (on the LTF/M30 candle):
  The pullback ZONE is the full price range between the two most recent
  confirmed swing points -- [last_swing_low, last_swing_high] -- not a
  specific Fibonacci ratio inside it. A signal requires:
    1. "Pulls back into the range" -- the M30 candle's own [low, high]
       overlaps the zone at all.
    2. "Closes back in the trend's favor" -- the candle's close is back
       beyond the TREND ORIGIN (see below), confirming the pullback held
       the level that started this leg rather than breaking through it.
  LONG  (uptrend)   -- overlap with the zone, AND close > trend origin.
  SHORT (downtrend) -- overlap with the zone, AND close < trend origin.

Trend origin (the whole point of this plugin, and the reason its name is
NOT just "swing structure v2"): the SL anchors to the swing point where
the CURRENT trend leg began, not whichever confirmed swing point happens
to be nearest to the entry price.
  - UPTREND   -- origin = the most recent confirmed swing LOW (the higher
                 low that anchors this up-leg; the swing HIGH is where the
                 leg currently stands, not where it started).
  - DOWNTREND -- origin = the most recent confirmed swing HIGH.
A small buffer (_SL_BUFFER_PCT of the zone's own span) is placed just
beyond the origin, in the adverse direction, so the stop sits structurally
past the level whose violation would actually invalidate the trend-origin
thesis -- exactly at the origin would let ordinary noise stop the trade out
by a tick.
Take profit: fixed 2.5R, single level (all 3 TP slots identical), same
             convention as every other plugin in this project.

Re-entry guard (same non-starving design as swing_structure_plugin.py and
fib_retracement_plugin.py, NOT order_block_plugin.py's single-pending-
block design): tracks the identity of the (last_swing_high, last_swing_low)
PAIR last used to fire a signal. A new swing high or swing low forming
changes that identity immediately, making a fresh pullback zone tradeable
the instant it's confirmed -- no "wait for the old setup to resolve" gate,
because there's no pending state to get stuck in.

Usage:
    python D:/rhyme/backtest.py --instrument USD_JPY --mode scalp30 \\
        --start 2023-01-01 --end 2024-01-01 \\
        --signals-module D:/rhyme/trend_origin_pullback_plugin.py
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal
from indicators import detect_fractals


# ── Constants (captured automatically in backtest header) ─────────────────────

_FRACTAL_N       = 2      # standard Williams Fractal: high/low of surrounding 2N+1 candles
_SL_BUFFER_PCT   = 0.05   # SL sits this fraction of the zone's span beyond the trend origin
_TP_R_MULTIPLE   = 2.5


# ── Re-entry state ────────────────────────────────────────────────────────────
# Identity of the (last_swing_high_id, last_swing_low_id) pair last used to
# fire a signal. Module-level so state persists across all generate_signal
# calls within a single run, then resets between separate runs because
# _load_plugin() creates a fresh module object each time.
_last_used_pair_id: tuple | None = None


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # H4 candles -- trend + swing structure computed here
    ltf_df: pd.DataFrame,   # M30 candles -- entry trigger computed here
    mode: str,
) -> Signal | None:
    global _last_used_pair_id

    needed = _FRACTAL_N * 2 + 2
    if len(htf_df) < needed or len(ltf_df) < 1:
        return None

    fdf = detect_fractals(htf_df[["open", "high", "low", "close"]], period=_FRACTAL_N)

    # Only fractals confirmed as of the latest HTF candle are usable.
    confirmed_cutoff = len(htf_df) - 1 - _FRACTAL_N
    if confirmed_cutoff < 0:
        return None

    fractal_highs = fdf["fractal_high"].iloc[: confirmed_cutoff + 1].dropna()
    fractal_lows  = fdf["fractal_low"].iloc[: confirmed_cutoff + 1].dropna()

    # Need at least 2 confirmed swing points of EACH type to compare
    # consecutive highs and consecutive lows -- one more than the
    # single-swing-pair plugins in this project require.
    if len(fractal_highs) < 2 or len(fractal_lows) < 2:
        return None

    last_high_id, last_high = fractal_highs.index[-1], float(fractal_highs.iloc[-1])
    prev_high_id, prev_high = fractal_highs.index[-2], float(fractal_highs.iloc[-2])
    last_low_id,  last_low  = fractal_lows.index[-1],  float(fractal_lows.iloc[-1])
    prev_low_id,  prev_low  = fractal_lows.index[-2],  float(fractal_lows.iloc[-2])

    uptrend   = last_high > prev_high and last_low > prev_low
    downtrend = last_high < prev_high and last_low < prev_low

    if not uptrend and not downtrend:
        return None  # no clean consecutive HH/HL or LH/LL structure -- no clear trend

    pair_id = (last_high_id, last_low_id)

    zone_low, zone_high = min(last_low, last_high), max(last_low, last_high)
    span = zone_high - zone_low
    if span <= 0:
        return None

    candle = ltf_df.iloc[-1]
    high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])

    # "Pulls back into the range" -- the M30 candle's own range overlaps the
    # zone between the two most recent confirmed swing points at all (not a
    # specific ratio inside it -- that's fib_retracement_plugin.py's job).
    touches = (low <= zone_high) and (high >= zone_low)

    if uptrend:
        origin = last_low   # where THIS leg began -- not last_high, even though
                             # last_high may be numerically closer to entry price
        bounces = close > origin

        if touches and bounces and pair_id != _last_used_pair_id:
            entry = close
            sl = origin - _SL_BUFFER_PCT * span
            risk = entry - sl
            if risk > 0:
                _last_used_pair_id = pair_id
                tp = entry + _TP_R_MULTIPLE * risk
                return Signal(
                    direction="long",
                    entry_price=entry,
                    stop_loss=sl,
                    take_profits=[tp, tp, tp],
                    instrument=instrument,
                    timeframe=ltf_df.index[-1].isoformat(),
                    reason=f"Trend-origin pullback long: HH {last_high:.5f}>{prev_high:.5f}, "
                           f"HL {last_low:.5f}>{prev_low:.5f}, pullback zone "
                           f"[{zone_low:.5f}, {zone_high:.5f}], origin (swing low) {origin:.5f}",
                )

    else:
        origin = last_high   # where THIS leg began -- not last_low
        bounces = close < origin

        if touches and bounces and pair_id != _last_used_pair_id:
            entry = close
            sl = origin + _SL_BUFFER_PCT * span
            risk = sl - entry
            if risk > 0:
                _last_used_pair_id = pair_id
                tp = entry - _TP_R_MULTIPLE * risk
                return Signal(
                    direction="short",
                    entry_price=entry,
                    stop_loss=sl,
                    take_profits=[tp, tp, tp],
                    instrument=instrument,
                    timeframe=ltf_df.index[-1].isoformat(),
                    reason=f"Trend-origin pullback short: LH {last_high:.5f}<{prev_high:.5f}, "
                           f"LL {last_low:.5f}<{prev_low:.5f}, pullback zone "
                           f"[{zone_low:.5f}, {zone_high:.5f}], origin (swing high) {origin:.5f}",
                )

    return None
