"""
Range Fade Plugin — Bot E candidate v1 (mean reversion)
---------------------------------------------------------
Trend/structure timeframe : HTF candles (htf_df) -- H4 in this configuration.
Signal timeframe          : LTF candles (ltf_df) -- M30 in this configuration.

THE BEHAVIOR SOUGHT: mean reversion inside a structurally-defined range --
the portfolio's first non-trend-capture candidate (GOVERNANCE one-behavior
note; Bot E slot). Its validity condition is deliberately the EXACT
INVERSION of the trend-origin family's: this plugin only trades when the
H4 structure is NOT consecutive HH/HL and NOT consecutive LH/LL -- i.e.
precisely the structural state in which pullback30 goes silent. The two
behaviors are mechanically complementary by construction.

Range definition (H4): the zone between the two most recent CONFIRMED
fractal extremes (indicators.detect_fractals, N=2, same machinery as every
plugin in this project; only fractals confirmed as of the latest H4 candle
are used -- no look-ahead). Requires >= 2 confirmed highs AND >= 2
confirmed lows (to evaluate the non-trend condition on consecutive pairs).

Entry (M30): price touches the boundary zone (the inner _BOUNDARY_ZONE_PCT
of the range height at either edge) and CLOSES back inside the interior --
fade the boundary. Long at the lower boundary, short at the upper. BOTH
directions, no directional carve-outs (pre-committed: the post-hoc
long-only selection of pullback30 is not repeated here).

Stop loss : structural -- beyond the faded boundary by _SL_BUFFER_PCT of
            the range span (the level whose break means the range thesis
            is dead and a breakout is underway).
Take profit: the RANGE MIDPOINT -- structural, NOT a fixed R multiple.
            Mean reversion's natural target is the middle of the range;
            demanding the opposite boundary (or a fixed 2.5R) would turn
            the fade into a range-traversal bet. R:R is whatever the range
            geometry gives, floored by _MIN_RR.
Min R:R    : skip fades where the midpoint is closer than _MIN_RR x risk.

Amendment 1 -- minimum absolute range size (the anti-RSI-death guard):
skip any setup where the assumed spread exceeds ~10% of the midpoint-TP
distance, i.e. TP distance must be >= _MIN_TP_TO_SPREAD x spread. MR's
high-frequency/modest-target profile is spread's favorite prey; this is
a hard floor, not a tunable. For USD_CAD at 1.7p spread: TP distance
>= 17 pips, which implies range span >= ~34p for an entry right at the
boundary and >= ~49p for an entry at the interior edge of the 15%
boundary zone.

Amendment 2 -- trade management model, PRE-REGISTERED: v1 is
fire-and-forget (broker-side SL/TP placed at entry, no mid-trade exits),
consistent with the whole fleet. Structural-invalidation exit (closing
early when a new fractal confirms BEYOND the faded boundary mid-trade)
is a V2 HYPOTHESIS requiring its own validation -- explicitly not a
tweak to be invented during forward testing.

Re-entry guard: non-starving (last_high_id, last_low_id) pair identity,
same design as trend_origin_pullback / swing_structure / fib_retracement.

All constants below were CHOSEN, not tuned (RESEARCH_LOG pre-registration,
2026-07-02) -- they are not to be optimized against results.

Usage:
    python D:/rhyme/backtest.py --instrument USD_CAD --mode scalp30 \\
        --start 2022-07-01 --end 2023-10-01 \\
        --signals-module D:/rhyme/range_fade_plugin.py
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal
from indicators import detect_fractals


# ── Constants (captured automatically in backtest header; CHOSEN, not tuned) ──

_FRACTAL_N          = 2      # standard Williams Fractal: extreme of surrounding 2N+1 candles
_BOUNDARY_ZONE_PCT  = 0.15   # boundary zone = inner 15% of range height at each edge
_SL_BUFFER_PCT      = 0.05   # SL sits this fraction of the span beyond the faded boundary
_MIN_RR             = 1.2    # skip fades where midpoint TP is closer than 1.2x risk
_MIN_TP_TO_SPREAD   = 10.0   # TP distance must be >= 10x assumed spread (Amendment 1)

# Assumed spreads (pips) for the Amendment-1 floor -- live-measured values
# from the 2026-07-01 pair sweep (oanda_pairs_raw.json), NOT backtest.py's
# SPREAD_PIPS table (which is what gets charged in backtests; this table
# only gates which setups are eligible). Default for unlisted pairs: 2.0.
_ASSUMED_SPREAD_PIPS = {
    "USD_CAD": 1.7, "USD_JPY": 1.5, "EUR_USD": 1.5, "GBP_USD": 1.8,
    "EUR_JPY": 2.8, "AUD_USD": 1.3, "EUR_GBP": 1.3, "USD_CHF": 1.6,
}
_DEFAULT_ASSUMED_SPREAD = 2.0


def _pip_size(instrument: str) -> float:
    return 0.01 if "JPY" in instrument else 0.0001


# ── Re-entry state ────────────────────────────────────────────────────────────

_last_used_pair_id: tuple | None = None


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # H4 candles -- range structure computed here
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
    last_low_id, last_low = fractal_lows.index[-1], float(fractal_lows.iloc[-1])
    prev_low = float(fractal_lows.iloc[-2])

    # Non-trend condition: the EXACT inversion of trend_origin_pullback's.
    uptrend   = last_high > prev_high and last_low > prev_low
    downtrend = last_high < prev_high and last_low < prev_low
    if uptrend or downtrend:
        return None

    zone_low, zone_high = last_low, last_high
    if zone_high <= zone_low:
        return None
    span = zone_high - zone_low
    pair_id = (last_high_id, last_low_id)

    midpoint = (zone_low + zone_high) / 2.0
    lower_zone_top = zone_low + _BOUNDARY_ZONE_PCT * span
    upper_zone_bot = zone_high - _BOUNDARY_ZONE_PCT * span

    candle = ltf_df.iloc[-1]
    high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])

    pip = _pip_size(instrument)
    assumed_spread = _ASSUMED_SPREAD_PIPS.get(instrument, _DEFAULT_ASSUMED_SPREAD)

    # ── LONG fade at the lower boundary ──────────────────────────────────────
    touches_lower = low <= lower_zone_top
    bounces_up    = close > lower_zone_top   # closed back inside the interior

    if touches_lower and bounces_up and pair_id != _last_used_pair_id:
        entry = close
        sl = zone_low - _SL_BUFFER_PCT * span
        tp = midpoint
        risk = entry - sl
        reward = tp - entry
        if risk > 0 and reward > 0:
            rr = reward / risk
            tp_dist_pips = reward / pip
            if rr >= _MIN_RR and tp_dist_pips >= _MIN_TP_TO_SPREAD * assumed_spread:
                _last_used_pair_id = pair_id
                return Signal(
                    direction="long",
                    entry_price=entry,
                    stop_loss=sl,
                    take_profits=[tp, tp, tp],
                    instrument=instrument,
                    timeframe=ltf_df.index[-1].isoformat(),
                    reason=f"Range fade long at lower boundary: range [{zone_low:.5f}, {zone_high:.5f}] "
                           f"(non-trending: highs {prev_high:.5f}->{last_high:.5f}, lows {prev_low:.5f}->{last_low:.5f}), "
                           f"TP midpoint {midpoint:.5f}, R:R {rr:.2f}",
                )
        return None

    # ── SHORT fade at the upper boundary ─────────────────────────────────────
    touches_upper = high >= upper_zone_bot
    bounces_down  = close < upper_zone_bot

    if touches_upper and bounces_down and pair_id != _last_used_pair_id:
        entry = close
        sl = zone_high + _SL_BUFFER_PCT * span
        tp = midpoint
        risk = sl - entry
        reward = entry - tp
        if risk > 0 and reward > 0:
            rr = reward / risk
            tp_dist_pips = reward / pip
            if rr >= _MIN_RR and tp_dist_pips >= _MIN_TP_TO_SPREAD * assumed_spread:
                _last_used_pair_id = pair_id
                return Signal(
                    direction="short",
                    entry_price=entry,
                    stop_loss=sl,
                    take_profits=[tp, tp, tp],
                    instrument=instrument,
                    timeframe=ltf_df.index[-1].isoformat(),
                    reason=f"Range fade short at upper boundary: range [{zone_low:.5f}, {zone_high:.5f}] "
                           f"(non-trending: highs {prev_high:.5f}->{last_high:.5f}, lows {prev_low:.5f}->{last_low:.5f}), "
                           f"TP midpoint {midpoint:.5f}, R:R {rr:.2f}",
                )
        return None

    return None
