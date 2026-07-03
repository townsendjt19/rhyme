"""
Volume-Profile Mean-Reversion Plugin — Bot E parallel-protocol Candidate A
---------------------------------------------------------------------------
Pre-registered ba84f74 (2026-07-02). Fade of a FAILED excursion outside the
volume-profile value area, back toward the point of control.

Mechanics (constants inherited from project conventions, CHOSEN not tuned):
- Profile over the trailing _WINDOW_H4=120 H4 candles (current bar excluded),
  built with the existing volume_profile.build_volume_profile machinery,
  _BINS=20 (that module's convention).
- POC = center of the max-volume bin. Value Area = standard contiguous 70%
  expansion around the POC bin (industry-standard VA fraction).
- Entry: an M30 candle trades OUTSIDE the value area (beyond VAH / below
  VAL); pending state tracks the excursion extreme; the first M30 close back
  INSIDE the VA confirms -> fade toward POC. Single-candle wick-out-and-
  close-back qualifies.
- SL beyond the excursion extreme by _SL_BUFFER_PCT of the profile-window
  span (structure-anchored). TP = POC. Min R:R 1.2. Amendment-1 spread floor
  (TP distance >= 10x assumed live spread). Amendment-2 fire-and-forget.
- Re-entry identity = (window extreme-setting bar timestamps, direction),
  single-use, non-starving (new window extremes refresh the identity).
- No regime gate.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from strategy import Signal
from volume_profile import build_volume_profile


# ── Constants (captured automatically in backtest header; CHOSEN, not tuned) ──

_WINDOW_DAYS      = 20
_WINDOW_H4        = _WINDOW_DAYS * 6   # 120 H4 candles
_BINS             = 20                 # volume_profile module convention
_VALUE_AREA_PCT   = 0.70               # industry-standard VA fraction
_SL_BUFFER_PCT    = 0.05
_MIN_RR           = 1.2
_MIN_TP_TO_SPREAD = 10.0

WARMUP_HTF_CANDLES = _WINDOW_H4 + 1

_ASSUMED_SPREAD_PIPS = {
    "USD_CAD": 1.7, "USD_JPY": 1.5, "EUR_USD": 1.5, "GBP_USD": 1.8,
    "EUR_JPY": 2.8, "AUD_USD": 1.3, "EUR_GBP": 1.3, "USD_CHF": 1.6,
}
_DEFAULT_ASSUMED_SPREAD = 2.0


def _pip_size(instrument: str) -> float:
    return 0.01 if "JPY" in instrument else 0.0001


def _value_area(profile: dict) -> tuple[float, float, float] | None:
    """(VAL, VAH, POC) via contiguous 70% expansion around the POC bin."""
    vol = np.asarray(profile["bin_vol"], dtype=float)
    edges = np.asarray(profile["bin_edges"], dtype=float)
    total = vol.sum()
    if total <= 0:
        return None
    poc_i = int(np.argmax(vol))
    lo_i = hi_i = poc_i
    acc = vol[poc_i]
    while acc < _VALUE_AREA_PCT * total:
        nxt_lo = vol[lo_i - 1] if lo_i > 0 else -1.0
        nxt_hi = vol[hi_i + 1] if hi_i < len(vol) - 1 else -1.0
        if nxt_hi < 0 and nxt_lo < 0:
            break
        if nxt_hi >= nxt_lo:
            hi_i += 1
            acc += nxt_hi
        else:
            lo_i -= 1
            acc += nxt_lo
    poc = (edges[poc_i] + edges[poc_i + 1]) / 2.0
    return float(edges[lo_i]), float(edges[hi_i + 1]), float(poc)


# ── Excursion state (module-level; runners load a fresh module per run) ───────
_pending: dict = {}   # (identity, direction) -> excursion extreme
_used: set = set()


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # H4 candles -- volume profile window
    ltf_df: pd.DataFrame,   # M30 candles -- excursion trigger
    mode: str,
) -> Signal | None:
    if len(htf_df) < _WINDOW_H4 + 1 or len(ltf_df) < 1:
        return None

    window = htf_df.iloc[-(_WINDOW_H4 + 1):-1]
    if "volume" not in window.columns:
        return None
    span = float(window["high"].max()) - float(window["low"].min())
    if span <= 0:
        return None

    profile = build_volume_profile(window, window=len(window), bins=_BINS)
    if not profile:
        return None
    va = _value_area(profile)
    if va is None:
        return None
    val, vah, poc = va

    # Identity: the bars that set the window extremes (v2 convention) --
    # refreshes when a new extreme forms or an old one ages out.
    ident = (window["high"].idxmax(), window["low"].idxmin())
    for key in list(_pending):
        if key[0] != ident:
            del _pending[key]

    candle = ltf_df.iloc[-1]
    high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])

    pip = _pip_size(instrument)
    assumed_spread = _ASSUMED_SPREAD_PIPS.get(instrument, _DEFAULT_ASSUMED_SPREAD)

    # ── SHORT: excursion above VAH fails ─────────────────────────────────────
    key = (ident, "short")
    if key not in _used:
        if high > vah:
            _pending[key] = max(_pending.get(key, vah), high)
        if key in _pending and close < vah:
            extreme = _pending.pop(key)
            entry, sl, tp = close, extreme + _SL_BUFFER_PCT * span, poc
            risk, reward = sl - entry, entry - tp
            if risk > 0 and reward > 0:
                rr = reward / risk
                if rr >= _MIN_RR and (reward / pip) >= _MIN_TP_TO_SPREAD * assumed_spread:
                    _used.add(key)
                    return Signal(
                        direction="short", entry_price=entry, stop_loss=sl,
                        take_profits=[tp, tp, tp], instrument=instrument,
                        timeframe=ltf_df.index[-1].isoformat(),
                        reason=f"VP reversion short: failed excursion above VAH {vah:.5f} "
                               f"(extreme {extreme:.5f}), TP=POC {poc:.5f}, R:R {rr:.2f}",
                    )
            _used.add(key)   # confirmed-but-filtered excursion is consumed
            return None

    # ── LONG: excursion below VAL fails ──────────────────────────────────────
    key = (ident, "long")
    if key not in _used:
        if low < val:
            _pending[key] = min(_pending.get(key, val), low)
        if key in _pending and close > val:
            extreme = _pending.pop(key)
            entry, sl, tp = close, extreme - _SL_BUFFER_PCT * span, poc
            risk, reward = entry - sl, tp - entry
            if risk > 0 and reward > 0:
                rr = reward / risk
                if rr >= _MIN_RR and (reward / pip) >= _MIN_TP_TO_SPREAD * assumed_spread:
                    _used.add(key)
                    return Signal(
                        direction="long", entry_price=entry, stop_loss=sl,
                        take_profits=[tp, tp, tp], instrument=instrument,
                        timeframe=ltf_df.index[-1].isoformat(),
                        reason=f"VP reversion long: failed excursion below VAL {val:.5f} "
                               f"(extreme {extreme:.5f}), TP=POC {poc:.5f}, R:R {rr:.2f}",
                    )
            _used.add(key)
            return None

    return None
