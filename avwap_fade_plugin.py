"""
Anchored-VWAP Fade Plugin — mean-reversion candidate #7 (line reopened 2026-07-03)
-----------------------------------------------------------------------------------
Pre-registered e211a17 BEFORE this file existed. Session-anchored volume-weighted
fair value: VWAP recomputed fresh from every daily 00:00 UTC open (hard reset —
no state survives 24h; structurally immune to v1's staleness failure mode) with
volume-weighted sigma bands. Close beyond 2σ fades toward VWAP; stop at 3σ
(frozen, band-width-derived); TP = VWAP (frozen). Fire-and-forget.

Formula (from the registered spec):
    tp_i    = (H_i + L_i + C_i) / 3          M30 candles since 00:00 UTC
    VWAP_t  = Σ(tp_i·v_i) / Σ(v_i)           v = OANDA tick volume (stated proxy)
    σ_t     = sqrt( Σ v_i·(tp_i − VWAP_t)² / Σ v_i )
Lookback = session-cumulative; no rolling window exists to tune.

Inherited: Amendment-1 spread floor (TP distance ≥ 10× assumed spread),
Amendment-2 fire-and-forget, min R:R 1.2, one trade per (session, direction),
single-use identities, both directions, no regime gate, no carve-outs.
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal

# ── Constants (registered e211a17; CHOSEN, not tuned) ─────────────────────────

_ENTRY_SIGMA          = 2.0
_STOP_SIGMA           = 3.0
_MIN_RR               = 1.2
_MIN_TP_TO_SPREAD     = 10.0
_MIN_SESSION_CANDLES  = 6      # 3 hours of M30 before sigma is trusted

_ASSUMED_SPREAD_PIPS = {
    "USD_CAD": 1.7, "USD_JPY": 1.5, "EUR_USD": 1.5, "GBP_USD": 1.8,
    "EUR_JPY": 2.8, "AUD_USD": 1.3, "EUR_GBP": 1.3, "USD_CHF": 1.6,
}
_DEFAULT_ASSUMED_SPREAD = 2.0

# Session-anchored: needs only same-day M30 candles; declared small so the
# harness warm-up audit sees an explicit requirement.
WARMUP_HTF_CANDLES = 12


def _pip_size(instrument: str) -> float:
    return 0.01 if "JPY" in instrument else 0.0001


_used: set = set()   # (session_date, direction) — single-use identities


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # unused
    ltf_df: pd.DataFrame,   # M30 candles
    mode: str,
) -> Signal | None:
    if len(ltf_df) < 2:
        return None

    now = ltf_df.index[-1]
    anchor = now.normalize()                 # today's 00:00 UTC
    sess = ltf_df[ltf_df.index >= anchor]
    if len(sess) < _MIN_SESSION_CANDLES:
        return None

    tp_price = (sess["high"] + sess["low"] + sess["close"]) / 3.0
    vol = sess["volume"].astype(float)
    if vol.sum() <= 0:
        return None
    vwap = float((tp_price * vol).sum() / vol.sum())
    sigma = float(((vol * (tp_price - vwap) ** 2).sum() / vol.sum()) ** 0.5)
    if sigma <= 0:
        return None

    close = float(ltf_df.iloc[-1]["close"])
    upper2, lower2 = vwap + _ENTRY_SIGMA * sigma, vwap - _ENTRY_SIGMA * sigma

    if close > upper2:
        direction, entry = "short", close
        sl, tp = vwap + _STOP_SIGMA * sigma, vwap
        risk, reward = sl - entry, entry - tp
    elif close < lower2:
        direction, entry = "long", close
        sl, tp = vwap - _STOP_SIGMA * sigma, vwap
        risk, reward = entry - sl, tp - entry
    else:
        return None

    key = (anchor.date(), direction)
    if key in _used:
        return None
    _used.add(key)   # confirmed signal consumes the identity, filtered or not

    if risk <= 0 or reward <= 0:
        return None
    rr = reward / risk
    pip = _pip_size(instrument)
    assumed_spread = _ASSUMED_SPREAD_PIPS.get(instrument, _DEFAULT_ASSUMED_SPREAD)
    if rr < _MIN_RR or (reward / pip) < _MIN_TP_TO_SPREAD * assumed_spread:
        return None

    return Signal(
        direction=direction, entry_price=entry, stop_loss=sl,
        take_profits=[tp, tp, tp], instrument=instrument,
        timeframe=now.isoformat(),
        reason=f"AVWAP fade {direction}: close {close:.5f} beyond {_ENTRY_SIGMA:.0f}s band "
               f"({lower2:.5f}/{upper2:.5f}), VWAP {vwap:.5f}, sigma {sigma:.5f}, R:R {rr:.2f}",
    )
