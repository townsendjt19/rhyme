"""
Trend-Origin Pullback Plugin — LONG-ONLY variant (USD_JPY "Bot D" candidate)
------------------------------------------------------------------------------
This is trend_origin_pullback_plugin.py with the SHORT branch removed and
nothing else changed: identical fractal-based consecutive-HH/HL trend
detection, identical pullback-zone entry, identical origin-anchored SL,
identical 2.5R TP, identical non-starving re-entry guard. See that file's
docstring for the full mechanics.

WHY LONG-ONLY -- AND WHY THIS IS EXPLICITLY NOT A VALIDATED STRATEGY:
The full long+short design's 2021-2026 USD_JPY backtest showed the long
side positive every single year (+$18,864 total, 40.2% WR) while the short
side lost in 5 of 6 years (-$4,727, 26.0% WR). This variant is a POST-HOC
DIRECTIONAL SELECTION from that result: the same historical data that
revealed the asymmetry was used to choose this variant, so no historical
backtest of this file can count as validation -- it would be reading the
answer key. The stated mechanical rationale (shorts fight the structural
yen-weakness backdrop of BoJ policy divergence that defined the entire
window) is a HYPOTHESIS, not an established fact. Validation criterion is
FORWARD PAPER PERFORMANCE ONLY, under the probation terms recorded in
RESEARCH_LOG.md at creation time (before any forward data existed).

Usage:
    python D:/rhyme/backtest.py --instrument USD_JPY --mode scalp30 \\
        --start 2023-01-01 --end 2024-01-01 \\
        --signals-module D:/rhyme/trend_origin_pullback_long_plugin.py
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

    confirmed_cutoff = len(htf_df) - 1 - _FRACTAL_N
    if confirmed_cutoff < 0:
        return None

    fractal_highs = fdf["fractal_high"].iloc[: confirmed_cutoff + 1].dropna()
    fractal_lows  = fdf["fractal_low"].iloc[: confirmed_cutoff + 1].dropna()

    if len(fractal_highs) < 2 or len(fractal_lows) < 2:
        return None

    last_high_id, last_high = fractal_highs.index[-1], float(fractal_highs.iloc[-1])
    prev_high = float(fractal_highs.iloc[-2])
    last_low_id,  last_low  = fractal_lows.index[-1],  float(fractal_lows.iloc[-1])
    prev_low = float(fractal_lows.iloc[-2])

    # LONG-ONLY: uptrend (consecutive higher high AND higher low) or nothing.
    uptrend = last_high > prev_high and last_low > prev_low
    if not uptrend:
        return None

    pair_id = (last_high_id, last_low_id)

    zone_low, zone_high = min(last_low, last_high), max(last_low, last_high)
    span = zone_high - zone_low
    if span <= 0:
        return None

    candle = ltf_df.iloc[-1]
    high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])

    touches = (low <= zone_high) and (high >= zone_low)
    origin = last_low
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
                reason=f"Trend-origin pullback long (long-only variant): HH {last_high:.5f}>{prev_high:.5f}, "
                       f"HL {last_low:.5f}>{prev_low:.5f}, pullback zone "
                       f"[{zone_low:.5f}, {zone_high:.5f}], origin (swing low) {origin:.5f}",
            )

    return None
