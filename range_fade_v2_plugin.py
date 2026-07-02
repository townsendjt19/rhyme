"""
Range Fade Plugin v2 — Bot E candidate (mean reversion)
----------------------------------------------------------
Successor to range_fade_plugin.py (v1, killed at the crown-jewel
kill-test 2026-07-02 -- see RESEARCH_LOG). ONE change from v1, addressing
its diagnosed failure (stale fractal-pair boundaries): range boundaries
are the ROLLING _WINDOW_DAYS-day extremes of the H4 series (highest high
/ lowest low over the trailing window, CURRENT candle excluded -- no
self-touch, no look-ahead), refreshing continuously instead of waiting
for fractal confirmation.

N = 20 trading days (_WINDOW_H4 = 120 H4 candles), CHOSEN ONCE from the
regime map and logged as chosen-not-tuned (pre-registration 2705540):
ranging stretches run 2-5 quarters, v1's boundaries staled within ~1
quarter, and 20 days refreshes ~3x per ranging quarter; 20 is also this
project's established structural lookback scale.

EVERYTHING ELSE IS v1 VERBATIM: structural non-trend gate (fractal-based
NOT-HH/HL and NOT-LH/LL -- the trend-origin inversion); M30 boundary-zone
(inner 15%) touch + close-back-inside fade, both directions, no
directional carve-outs; SL structural at _SL_BUFFER_PCT of span beyond
the faded boundary; TP at the range midpoint; min-R:R 1.2; Amendment-1
spread guard (TP distance >= 10x assumed live spread); Amendment-2
fire-and-forget (structural-invalidation exit = separately-validated v3
hypothesis, not a forward-testing tweak); non-starving re-entry guard,
identity = (timestamp of the window's high-setting bar, timestamp of the
low-setting bar), refreshing whenever a new extreme forms or an old one
ages out of the window.

Usage:
    python D:/rhyme/backtest.py --instrument USD_CAD --mode scalp30 \\
        --start 2022-07-01 --end 2023-10-01 \\
        --signals-module D:/rhyme/range_fade_v2_plugin.py
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal
from indicators import detect_fractals


# ── Constants (captured automatically in backtest header; CHOSEN, not tuned) ──

_FRACTAL_N          = 2      # for the non-trend gate only (unchanged from v1)
_WINDOW_DAYS        = 20     # rolling extreme window, trading days -- chosen from the regime map
_WINDOW_H4          = _WINDOW_DAYS * 6   # 120 H4 candles
_BOUNDARY_ZONE_PCT  = 0.15
_SL_BUFFER_PCT      = 0.05
_MIN_RR             = 1.2
_MIN_TP_TO_SPREAD   = 10.0

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
    htf_df: pd.DataFrame,   # H4 candles -- rolling extremes + non-trend gate
    ltf_df: pd.DataFrame,   # M30 candles -- entry trigger
    mode: str,
) -> Signal | None:
    global _last_used_pair_id

    if len(htf_df) < _WINDOW_H4 + 1 or len(ltf_df) < 1:
        return None

    # ── Non-trend gate: unchanged v1 mechanics (fractal-based inversion) ─────
    fdf = detect_fractals(htf_df[["open", "high", "low", "close"]], period=_FRACTAL_N)
    confirmed_cutoff = len(htf_df) - 1 - _FRACTAL_N
    if confirmed_cutoff < 0:
        return None
    fractal_highs = fdf["fractal_high"].iloc[: confirmed_cutoff + 1].dropna()
    fractal_lows  = fdf["fractal_low"].iloc[: confirmed_cutoff + 1].dropna()
    if len(fractal_highs) < 2 or len(fractal_lows) < 2:
        return None
    uptrend   = float(fractal_highs.iloc[-1]) > float(fractal_highs.iloc[-2]) and \
                float(fractal_lows.iloc[-1])  > float(fractal_lows.iloc[-2])
    downtrend = float(fractal_highs.iloc[-1]) < float(fractal_highs.iloc[-2]) and \
                float(fractal_lows.iloc[-1])  < float(fractal_lows.iloc[-2])
    if uptrend or downtrend:
        return None

    # ── v2 range: rolling extremes over the trailing window, current bar excluded
    window = htf_df.iloc[-(_WINDOW_H4 + 1):-1]
    zone_high = float(window["high"].max())
    zone_low  = float(window["low"].min())
    if zone_high <= zone_low:
        return None
    span = zone_high - zone_low

    # Identity: the bars that SET the extremes -- refreshes when a new extreme
    # forms or an old one ages out of the window.
    pair_id = (window["high"].idxmax(), window["low"].idxmin())

    midpoint = (zone_low + zone_high) / 2.0
    lower_zone_top = zone_low + _BOUNDARY_ZONE_PCT * span
    upper_zone_bot = zone_high - _BOUNDARY_ZONE_PCT * span

    candle = ltf_df.iloc[-1]
    high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])

    pip = _pip_size(instrument)
    assumed_spread = _ASSUMED_SPREAD_PIPS.get(instrument, _DEFAULT_ASSUMED_SPREAD)

    # ── LONG fade at the lower boundary ──────────────────────────────────────
    if low <= lower_zone_top and close > lower_zone_top and pair_id != _last_used_pair_id:
        entry = close
        sl = zone_low - _SL_BUFFER_PCT * span
        tp = midpoint
        risk, reward = entry - sl, tp - entry
        if risk > 0 and reward > 0:
            rr = reward / risk
            if rr >= _MIN_RR and (reward / pip) >= _MIN_TP_TO_SPREAD * assumed_spread:
                _last_used_pair_id = pair_id
                return Signal(
                    direction="long", entry_price=entry, stop_loss=sl,
                    take_profits=[tp, tp, tp], instrument=instrument,
                    timeframe=ltf_df.index[-1].isoformat(),
                    reason=f"Range fade v2 long at lower boundary: rolling {_WINDOW_DAYS}d range "
                           f"[{zone_low:.5f}, {zone_high:.5f}], TP midpoint {midpoint:.5f}, R:R {rr:.2f}",
                )
        return None

    # ── SHORT fade at the upper boundary ─────────────────────────────────────
    if high >= upper_zone_bot and close < upper_zone_bot and pair_id != _last_used_pair_id:
        entry = close
        sl = zone_high + _SL_BUFFER_PCT * span
        tp = midpoint
        risk, reward = sl - entry, entry - tp
        if risk > 0 and reward > 0:
            rr = reward / risk
            if rr >= _MIN_RR and (reward / pip) >= _MIN_TP_TO_SPREAD * assumed_spread:
                _last_used_pair_id = pair_id
                return Signal(
                    direction="short", entry_price=entry, stop_loss=sl,
                    take_profits=[tp, tp, tp], instrument=instrument,
                    timeframe=ltf_df.index[-1].isoformat(),
                    reason=f"Range fade v2 short at upper boundary: rolling {_WINDOW_DAYS}d range "
                           f"[{zone_low:.5f}, {zone_high:.5f}], TP midpoint {midpoint:.5f}, R:R {rr:.2f}",
                )
        return None

    return None
