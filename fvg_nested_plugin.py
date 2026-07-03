"""
Nested Fair-Value-Gap Plugin — grid cell 1 (M5 entry / 4H anchor)
------------------------------------------------------------------
Spec logged b2285b1 (2026-07-03) before first run; constants from project
conventions, CHOSEN not tuned. Registered in the July 2026 timeframe grid
(aaf7882/20ee8d5); 2023 quick-check kill criteria apply.

Mechanics:
- 4H anchor: most recent UNFILLED 4H FVG within the trailing _WINDOW_H4
  candles. FVG = 3-candle imbalance: bullish when low(i) > high(i-2), zone
  [high(i-2), low(i)]; bearish mirror. Unfilled = no later 4H candle has
  traded through the zone's far edge.
- Nested trigger: while the M5 close is INSIDE the active 4H zone, an M5 FVG
  forms in the anchor's direction -> enter at that M5 candle's close.
- SL: 4H zone far edge + _SL_BUFFER_PCT of zone height (anchor invalidation).
  TP: 2.5R (trend-continuation family convention).
- Amendment-1 spread floor; one trade per 4H-FVG identity (formation
  timestamp); both directions.
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal


# ── Constants (captured automatically in backtest header; CHOSEN, not tuned) ──

_WINDOW_H4        = 120
_SL_BUFFER_PCT    = 0.05
_TP_R_MULTIPLE    = 2.5
_MIN_TP_TO_SPREAD = 10.0

WARMUP_HTF_CANDLES = _WINDOW_H4 + 1

_ASSUMED_SPREAD_PIPS = {
    "USD_CAD": 1.7, "USD_JPY": 1.5, "EUR_USD": 1.5, "GBP_USD": 1.8,
    "EUR_JPY": 2.8, "AUD_USD": 1.3, "EUR_GBP": 1.3, "USD_CHF": 1.6,
}
_DEFAULT_ASSUMED_SPREAD = 2.0


def _pip_size(instrument: str) -> float:
    return 0.01 if "JPY" in instrument else 0.0001


def _latest_unfilled_fvg(df: pd.DataFrame) -> tuple | None:
    """Most recent unfilled FVG in df (a 4H window). Returns
    (formation_ts, direction, zone_lo, zone_hi) or None."""
    highs, lows = df["high"].values, df["low"].values
    n = len(df)
    for i in range(n - 1, 1, -1):
        # bullish gap at i: low(i) > high(i-2); zone [high(i-2), low(i)]
        if lows[i] > highs[i - 2]:
            lo, hi = highs[i - 2], lows[i]
            filled = any(lows[j] <= lo for j in range(i + 1, n))
            if not filled:
                return df.index[i], "long", float(lo), float(hi)
        # bearish gap at i: high(i) < low(i-2); zone [high(i), low(i-2)]
        if highs[i] < lows[i - 2]:
            lo, hi = highs[i], lows[i - 2]
            filled = any(highs[j] >= hi for j in range(i + 1, n))
            if not filled:
                return df.index[i], "short", float(lo), float(hi)
    return None


# ── Re-entry state (fresh module per run via _load_plugin) ────────────────────
_used: set = set()


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # 4H candles -- anchor FVGs
    ltf_df: pd.DataFrame,   # M5 candles -- nested trigger
    mode: str,
) -> Signal | None:
    if len(htf_df) < _WINDOW_H4 + 1 or len(ltf_df) < 3:
        return None

    window = htf_df.iloc[-(_WINDOW_H4 + 1):-1]
    anchor = _latest_unfilled_fvg(window)
    if anchor is None:
        return None
    ts, direction, zone_lo, zone_hi = anchor
    if (ts, direction) in _used:
        return None
    height = zone_hi - zone_lo
    if height <= 0:
        return None

    candle = ltf_df.iloc[-1]
    close = float(candle["close"])
    if not (zone_lo <= close <= zone_hi):
        return None   # nested trigger only fires INSIDE the anchor zone

    # M5 FVG in the anchor direction on the last three M5 candles
    c0, c2 = ltf_df.iloc[-3], candle
    m5_bull = float(c2["low"]) > float(c0["high"])
    m5_bear = float(c2["high"]) < float(c0["low"])
    if direction == "long" and not m5_bull:
        return None
    if direction == "short" and not m5_bear:
        return None

    pip = _pip_size(instrument)
    assumed_spread = _ASSUMED_SPREAD_PIPS.get(instrument, _DEFAULT_ASSUMED_SPREAD)

    entry = close
    if direction == "long":
        sl = zone_lo - _SL_BUFFER_PCT * height
        risk = entry - sl
        tp = entry + _TP_R_MULTIPLE * risk
        reward = tp - entry
    else:
        sl = zone_hi + _SL_BUFFER_PCT * height
        risk = sl - entry
        tp = entry - _TP_R_MULTIPLE * risk
        reward = entry - tp
    if risk <= 0:
        return None
    if (reward / pip) < _MIN_TP_TO_SPREAD * assumed_spread:
        _used.add((ts, direction))   # consumed: this anchor can't clear the floor
        return None

    _used.add((ts, direction))
    return Signal(
        direction=direction, entry_price=entry, stop_loss=sl,
        take_profits=[tp, tp, tp], instrument=instrument,
        timeframe=ltf_df.index[-1].isoformat(),
        reason=f"Nested FVG {direction}: 4H zone [{zone_lo:.5f}, {zone_hi:.5f}] "
               f"(formed {ts}), M5 FVG confirmation, SL beyond anchor, TP 2.5R",
    )
