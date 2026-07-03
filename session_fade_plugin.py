"""
Session-Breakout Fade Plugin (Asian range) — Bot E parallel-protocol Candidate C
---------------------------------------------------------------------------------
Pre-registered ba84f74 (2026-07-02). The FADE variant only: a breakout of the
Asian-session range that fails (closes back inside) is faded toward the range
midpoint. The trend-continuation variant is deliberately excluded (overlaps
Donchian; London-breakout momentum already rejected at 7-22% WR).

Mechanics (constants inherited from project conventions, CHOSEN not tuned):
- Asian session = 23:00-07:00 UTC (Tokyo business hours; convention chosen
  once). Session range = high/low of the session's M30 candles; the range for
  day D is defined by candles in [D-1 23:00, D 07:00) UTC.
- Active window: after 07:00 UTC until the next session opens (23:00 UTC).
  A breakout beyond either boundary opens pending state tracking the
  excursion extreme; the first M30 close back INSIDE the range confirms ->
  fade toward the range MIDPOINT. Single-candle wick-out-and-close-back
  qualifies.
- SL beyond the excursion extreme by _SL_BUFFER_PCT of the session-range
  height -- STRUCTURE-ANCHORED, explicitly not candle-scale (pre-registration
  requirement). TP = range midpoint. Min R:R 1.2. Amendment-1 spread floor
  (TP distance >= 10x assumed live spread -- thin Asian ranges are filtered;
  that is the floor working). Amendment-2 fire-and-forget.
- One trade per (session date, direction); identity single-use. Silent on
  days with no session candles (weekends/holidays). No regime gate.
- Uses the LTF (M30) series only; the HTF frame is untouched.
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal


# ── Constants (captured automatically in backtest header; CHOSEN, not tuned) ──

_SESSION_START_UTC = 23   # inclusive, previous calendar day
_SESSION_END_UTC   = 7    # exclusive
_SL_BUFFER_PCT     = 0.05
_MIN_RR            = 1.2
_MIN_TP_TO_SPREAD  = 10.0

_ASSUMED_SPREAD_PIPS = {
    "USD_CAD": 1.7, "USD_JPY": 1.5, "EUR_USD": 1.5, "GBP_USD": 1.8,
    "EUR_JPY": 2.8, "AUD_USD": 1.3, "EUR_GBP": 1.3, "USD_CHF": 1.6,
}
_DEFAULT_ASSUMED_SPREAD = 2.0


def _pip_size(instrument: str) -> float:
    return 0.01 if "JPY" in instrument else 0.0001


# ── Session state (module-level; runners load a fresh module per run) ─────────
_pending: dict = {}   # (session_date, direction) -> excursion extreme
_used: set = set()


def _session_range(ltf_df: pd.DataFrame, now: pd.Timestamp):
    """Asian range for the session belonging to `now` (post-07:00 side).

    Returns (session_date, range_high, range_low) or None if `now` is inside
    the session itself, before completion, or the session had no candles.
    """
    hour = now.hour
    if hour >= _SESSION_START_UTC or hour < _SESSION_END_UTC:
        return None   # inside the (next) session -- no fading during formation
    day = now.normalize()
    start = day - pd.Timedelta(hours=24 - _SESSION_START_UTC)   # D-1 23:00
    end = day + pd.Timedelta(hours=_SESSION_END_UTC)            # D 07:00
    sess = ltf_df[(ltf_df.index >= start) & (ltf_df.index < end)]
    if len(sess) == 0:
        return None
    return day.date(), float(sess["high"].max()), float(sess["low"].min())


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # unused
    ltf_df: pd.DataFrame,   # M30 candles
    mode: str,
) -> Signal | None:
    if len(ltf_df) < 2:
        return None

    now = ltf_df.index[-1]
    sr = _session_range(ltf_df, now)
    if sr is None:
        return None
    sdate, r_high, r_low = sr
    height = r_high - r_low
    if height <= 0:
        return None
    midpoint = (r_high + r_low) / 2.0

    # Drop pending state from other sessions.
    for key in list(_pending):
        if key[0] != sdate:
            del _pending[key]

    candle = ltf_df.iloc[-1]
    high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])

    pip = _pip_size(instrument)
    assumed_spread = _ASSUMED_SPREAD_PIPS.get(instrument, _DEFAULT_ASSUMED_SPREAD)

    # ── SHORT: breakout above the session high fails ─────────────────────────
    key = (sdate, "short")
    if key not in _used:
        if high > r_high:
            _pending[key] = max(_pending.get(key, r_high), high)
        if key in _pending and close < r_high:
            extreme = _pending.pop(key)
            entry, sl, tp = close, extreme + _SL_BUFFER_PCT * height, midpoint
            risk, reward = sl - entry, entry - tp
            if risk > 0 and reward > 0:
                rr = reward / risk
                if rr >= _MIN_RR and (reward / pip) >= _MIN_TP_TO_SPREAD * assumed_spread:
                    _used.add(key)
                    return Signal(
                        direction="short", entry_price=entry, stop_loss=sl,
                        take_profits=[tp, tp, tp], instrument=instrument,
                        timeframe=now.isoformat(),
                        reason=f"Session fade short: failed break of Asian high {r_high:.5f} "
                               f"(extreme {extreme:.5f}), TP=mid {midpoint:.5f}, R:R {rr:.2f}",
                    )
            _used.add(key)   # confirmed-but-filtered breakout is consumed
            return None

    # ── LONG: breakout below the session low fails ───────────────────────────
    key = (sdate, "long")
    if key not in _used:
        if low < r_low:
            _pending[key] = min(_pending.get(key, r_low), low)
        if key in _pending and close > r_low:
            extreme = _pending.pop(key)
            entry, sl, tp = close, extreme - _SL_BUFFER_PCT * height, midpoint
            risk, reward = entry - sl, tp - entry
            if risk > 0 and reward > 0:
                rr = reward / risk
                if rr >= _MIN_RR and (reward / pip) >= _MIN_TP_TO_SPREAD * assumed_spread:
                    _used.add(key)
                    return Signal(
                        direction="long", entry_price=entry, stop_loss=sl,
                        take_profits=[tp, tp, tp], instrument=instrument,
                        timeframe=now.isoformat(),
                        reason=f"Session fade long: failed break of Asian low {r_low:.5f} "
                               f"(extreme {extreme:.5f}), TP=mid {midpoint:.5f}, R:R {rr:.2f}",
                    )
            _used.add(key)
            return None

    return None
