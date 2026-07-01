"""
Fibonacci Retracement Bounce Plugin
--------------------------------------
Trend/structure timeframe : HTF candles (htf_df) -- H4 in this configuration.
Signal timeframe          : LTF candles (ltf_df) -- M30 in this configuration.

Swing point detection: reuses indicators.detect_fractals() (the same
Williams Fractal method already used in the M30 stop-distance diagnostic
and swing_structure_plugin.py), N=2 standard definition, applied to the
HTF candles. Only CONFIRMED fractals (period candles after the fractal bar
have closed) are ever used -- no look-ahead.

Trend direction is derived from which confirmed swing point is more
recent:
  - swing high more recent than swing low -> uptrend (low -> high),
    retracement measured from the low (0%) to the high (100%); a pullback
    down to the 61.8% level is a dip-buy setup.
  - swing low more recent than swing high -> downtrend (high -> low),
    retracement measured from the high (0%) to the low (100%); a rally up
    to the 61.8% level is a sell-the-rip setup.

Entry rule (on the LTF/M30 candle):
  LONG  (uptrend) -- candle's range touches the 61.8% retracement level
        from above (low <= level) AND closes back above it (bounce
        confirmation, not just a touch).
  SHORT (downtrend) -- candle's range touches the 61.8% level from below
        (high >= level) AND closes back below it.

Stop loss: just beyond whichever of {the 78.6% retracement level, the
           original swing extreme that started the retracement} is
           CLOSER to entry -- the point where the retracement thesis is
           genuinely invalidated, using the tighter of the two candidate
           invalidation levels rather than always defaulting to one.
Take profit: fixed 2.5R, single level (all 3 TP slots identical), same
             convention as every other plugin in this project.

Volume-profile confluence gate (added on top of the ORIGINAL entry
logic, which is otherwise byte-for-byte unchanged -- swing detection,
SL placement, and TP are identical to the ungated version, so any
change in backtest results is attributable to this gate alone): reuses
volume_profile.py's build_volume_profile(), the same rolling-window
Volume Profile / HVN-LVN machinery already used by strategy.py's
built-in filter 5, over the trailing _VOLUME_PROFILE_WINDOW M30
candles. The Point of Control (POC -- the single highest-volume bin,
identified here via bin_vol.argmax()) is computed for completeness and
included in the reason string, but the actual gate checks the 61.8%
trigger level against every HVN range, not just the POC bin: a
touch-and-bounce only fires if trigger_level falls inside an HVN zone,
or within _HVN_PROXIMITY_TOLERANCE times that zone's own width of its
nearest edge (e.g. tolerance=1.0 means a zone can be "reached" from up
to one full zone-width away, not just from directly inside it). This
requires the retracement level to correspond to a real zone of prior
acceptance, not merely to arithmetic 61.8%-of-swing-range with no
volume behind it.

Re-entry guard (same non-starving design as swing_structure_plugin.py,
NOT order_block_plugin.py's single-pending-block design): tracks the
identity of the (swing_high, swing_low) PAIR last used to fire a signal.
A new swing high or swing low forming changes that identity immediately,
making a fresh retracement grid tradeable the instant it's confirmed --
no "wait for the old setup to resolve" gate, because there's no pending
state to get stuck in.

Usage:
    python D:/rhyme/backtest.py --instrument USD_JPY --mode scalp30 \\
        --start 2023-01-01 --end 2024-01-01 \\
        --signals-module D:/rhyme/fib_retracement_plugin.py
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal
from indicators import detect_fractals
from volume_profile import build_volume_profile


# ── Constants (captured automatically in backtest header) ─────────────────────

_FRACTAL_N        = 2       # standard Williams Fractal: high/low of surrounding 2N+1 candles
_FIB_TRIGGER_LEVEL = 0.618  # retracement level that triggers entry on touch+bounce
_FIB_SL_LEVEL      = 0.786  # deeper retracement level used for invalidation / SL
_TP_R_MULTIPLE     = 2.5

_VOLUME_PROFILE_WINDOW    = 50   # rolling M30 candle window the volume profile is built over
_HVN_PROXIMITY_TOLERANCE  = 1.0  # trigger level counts as "near" an HVN within this many zone-widths of its edge


def _level_near_hvn(price: float, profile: dict, tolerance: float) -> bool:
    """True if `price` falls inside an HVN zone, or within `tolerance`
    zone-widths of that zone's nearest edge. tolerance=0 means strict
    containment only; tolerance=1.0 extends each zone by its own width
    on both sides before checking."""
    if not profile:
        return False
    for lo, hi in profile.get("hvn_ranges", []):
        width = hi - lo
        buffer = tolerance * width
        if (lo - buffer) <= price <= (hi + buffer):
            return True
    return False


def _point_of_control(profile: dict) -> float | None:
    """Price at the center of the single highest-volume bin -- the POC.
    Computed for the reason string / completeness; the entry gate itself
    checks against ALL hvn_ranges, not just the POC bin, since a genuine
    volume shelf away from the single busiest bin is still real
    confluence, not just the one densest print."""
    if not profile or "bin_vol" not in profile:
        return None
    bin_vol = profile["bin_vol"]
    if not len(bin_vol) or not bin_vol.any():
        return None
    edges = profile["bin_edges"]
    idx = int(bin_vol.argmax())
    return float((edges[idx] + edges[idx + 1]) / 2)


# ── Re-entry state ────────────────────────────────────────────────────────────
# Identity of the (swing_high_id, swing_low_id) pair last used to fire a
# signal. Module-level so state persists across all generate_signal calls
# within a single run, then resets between separate runs because
# _load_plugin() creates a fresh module object each time.
_last_used_pair_id: tuple | None = None


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # H4 candles -- swing structure computed here
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

    if fractal_highs.empty or fractal_lows.empty:
        return None  # need BOTH a confirmed swing high and swing low to draw a grid

    swing_high_id, swing_high = fractal_highs.index[-1], float(fractal_highs.iloc[-1])
    swing_low_id,  swing_low  = fractal_lows.index[-1],  float(fractal_lows.iloc[-1])

    if swing_high <= swing_low:
        return None  # degenerate / stale structure, can't form a valid grid

    pair_id = (swing_high_id, swing_low_id)
    span = swing_high - swing_low

    candle = ltf_df.iloc[-1]
    high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])

    # Volume-profile confluence gate -- computed once per call, direction-
    # agnostic (the same rolling M30 window regardless of which branch below
    # ends up using it). Everything else in this function is unchanged from
    # the ungated version.
    profile = build_volume_profile(ltf_df, window=_VOLUME_PROFILE_WINDOW)
    poc = _point_of_control(profile)

    if swing_high_id > swing_low_id:
        # ── Uptrend: high is the more recent point. Pullback DOWN to 61.8%. ──
        trigger_level = swing_high - _FIB_TRIGGER_LEVEL * span
        sl_fib_level  = swing_high - _FIB_SL_LEVEL * span

        touches = low <= trigger_level <= high
        bounces = close > trigger_level
        near_hvn = _level_near_hvn(trigger_level, profile, _HVN_PROXIMITY_TOLERANCE)

        if touches and bounces and near_hvn and pair_id != _last_used_pair_id:
            entry = close
            # Whichever invalidation level is CLOSER to entry (higher, for a
            # long) is the tighter, more meaningful stop.
            sl_candidates = [c for c in (sl_fib_level, swing_low) if c < entry]
            if not sl_candidates:
                return None
            sl = max(sl_candidates)
            risk = entry - sl
            if risk > 0:
                _last_used_pair_id = pair_id
                tp = entry + _TP_R_MULTIPLE * risk
                poc_str = f", POC {poc:.5f}" if poc is not None else ""
                return Signal(
                    direction="long",
                    entry_price=entry,
                    stop_loss=sl,
                    take_profits=[tp, tp, tp],
                    instrument=instrument,
                    timeframe=ltf_df.index[-1].isoformat(),
                    reason=f"Fib retracement bounce long at 61.8% ({trigger_level:.5f}), "
                           f"swing low {swing_low:.5f} -> swing high {swing_high:.5f}, "
                           f"HVN-confirmed{poc_str}",
                )

    else:
        # ── Downtrend: low is the more recent point. Rally UP to 61.8%. ──────
        trigger_level = swing_low + _FIB_TRIGGER_LEVEL * span
        sl_fib_level  = swing_low + _FIB_SL_LEVEL * span

        touches = low <= trigger_level <= high
        bounces = close < trigger_level
        near_hvn = _level_near_hvn(trigger_level, profile, _HVN_PROXIMITY_TOLERANCE)

        if touches and bounces and near_hvn and pair_id != _last_used_pair_id:
            entry = close
            sl_candidates = [c for c in (sl_fib_level, swing_high) if c > entry]
            if not sl_candidates:
                return None
            sl = min(sl_candidates)
            risk = sl - entry
            if risk > 0:
                _last_used_pair_id = pair_id
                tp = entry - _TP_R_MULTIPLE * risk
                poc_str = f", POC {poc:.5f}" if poc is not None else ""
                return Signal(
                    direction="short",
                    entry_price=entry,
                    stop_loss=sl,
                    take_profits=[tp, tp, tp],
                    instrument=instrument,
                    timeframe=ltf_df.index[-1].isoformat(),
                    reason=f"Fib retracement bounce short at 61.8% ({trigger_level:.5f}), "
                           f"swing high {swing_high:.5f} -> swing low {swing_low:.5f}, "
                           f"HVN-confirmed{poc_str}",
                )

    return None
