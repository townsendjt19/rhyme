"""
ER-Gated Liquidity Sweep Fade — Bot E candidate #6 (THE LAST DESIGN IN THE LINE)
---------------------------------------------------------------------------------
Pre-registered cc2bb99 (2026-07-02). Chassis = liquidity_sweep_fade_plugin.py
mechanics VERBATIM (82776d7); the ONE addition is an explicit regime gate:
trades fire only when trailing Kaufman ER(20) on the H4 closes is < 0.20 at
the confirmation candle (the regime map's metric and threshold, applied
per-trade). A confirmation arriving while ER >= 0.20 CONSUMES the sweep event
without trading (same convention as the R:R/spread filters). Pending/extreme
tracking runs regardless of gate state.

Pre-registered stopping rule: if this candidate fails at kill-test or full
window, the Bot E mean-reversion line closes formally. See RESEARCH_LOG.
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal
from indicators import detect_fractals


# ── Constants (captured automatically in backtest header; CHOSEN, not tuned) ──

_FRACTAL_N        = 2
_WINDOW_DAYS      = 20
_WINDOW_H4        = _WINDOW_DAYS * 6   # 120 H4 candles
_SL_BUFFER_PCT    = 0.05
_MIN_RR           = 1.2
_MIN_TP_TO_SPREAD = 10.0

_ER_PERIOD        = 20     # Kaufman ER period -- the regime map's metric
_ER_THRESHOLD     = 0.20   # the map's threshold, per its original justification

WARMUP_HTF_CANDLES = _WINDOW_H4 + 1 + 2 * _FRACTAL_N

_ASSUMED_SPREAD_PIPS = {
    "USD_CAD": 1.7, "USD_JPY": 1.5, "EUR_USD": 1.5, "GBP_USD": 1.8,
    "EUR_JPY": 2.8, "AUD_USD": 1.3, "EUR_GBP": 1.3, "USD_CHF": 1.6,
}
_DEFAULT_ASSUMED_SPREAD = 2.0


def _pip_size(instrument: str) -> float:
    return 0.01 if "JPY" in instrument else 0.0001


def _kaufman_er(closes: pd.Series, period: int = _ER_PERIOD) -> float:
    """Trailing Kaufman efficiency ratio over the last `period` closes."""
    c = closes.iloc[-(period + 1):]
    if len(c) < period + 1:
        return 1.0   # insufficient history reads as trending -> gate closed
    change = abs(float(c.iloc[-1]) - float(c.iloc[0]))
    path = float(c.diff().abs().sum())
    return change / path if path > 0 else 0.0


# ── Sweep state (module-level; runners load a fresh module per run) ───────────
_pending: dict = {}
_used: set = set()


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # H4 candles -- fractal levels, window midpoint, ER gate
    ltf_df: pd.DataFrame,   # M30 candles -- sweep trigger
    mode: str,
) -> Signal | None:
    if len(htf_df) < _WINDOW_H4 + 1 or len(ltf_df) < 1:
        return None

    fdf = detect_fractals(htf_df[["open", "high", "low", "close"]], period=_FRACTAL_N)
    confirmed_cutoff = len(htf_df) - 1 - _FRACTAL_N
    if confirmed_cutoff < 0:
        return None
    fractal_highs = fdf["fractal_high"].iloc[: confirmed_cutoff + 1].dropna()
    fractal_lows  = fdf["fractal_low"].iloc[: confirmed_cutoff + 1].dropna()
    if len(fractal_highs) < 1 or len(fractal_lows) < 1:
        return None

    window = htf_df.iloc[-(_WINDOW_H4 + 1):-1]
    window_start = window.index[0]
    zone_high = float(window["high"].max())
    zone_low  = float(window["low"].min())
    if zone_high <= zone_low:
        return None
    span = zone_high - zone_low
    midpoint = (zone_low + zone_high) / 2.0

    level_high_ts, level_high = fractal_highs.index[-1], float(fractal_highs.iloc[-1])
    level_low_ts,  level_low  = fractal_lows.index[-1],  float(fractal_lows.iloc[-1])

    current = {(level_high_ts, "short"), (level_low_ts, "long")}
    for key in list(_pending):
        ts, _d = key
        if key not in current or ts < window_start:
            del _pending[key]

    candle = ltf_df.iloc[-1]
    high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])

    pip = _pip_size(instrument)
    assumed_spread = _ASSUMED_SPREAD_PIPS.get(instrument, _DEFAULT_ASSUMED_SPREAD)

    # The gate reads the trailing H4 closes as of the current structural state.
    er = _kaufman_er(htf_df["close"])
    gate_open = er < _ER_THRESHOLD

    # ── SHORT: sweep of the fractal HIGH ─────────────────────────────────────
    key = (level_high_ts, "short")
    if level_high_ts >= window_start and key not in _used:
        if high > level_high:
            _pending[key] = max(_pending.get(key, level_high), high)
        if key in _pending and close < level_high:
            extreme = _pending.pop(key)
            if not gate_open:
                _used.add(key)   # gated confirmation is consumed, not deferred
                return None
            entry = close
            sl = extreme + _SL_BUFFER_PCT * span
            tp = midpoint
            risk, reward = sl - entry, entry - tp
            if risk > 0 and reward > 0:
                rr = reward / risk
                if rr >= _MIN_RR and (reward / pip) >= _MIN_TP_TO_SPREAD * assumed_spread:
                    _used.add(key)
                    return Signal(
                        direction="short", entry_price=entry, stop_loss=sl,
                        take_profits=[tp, tp, tp], instrument=instrument,
                        timeframe=ltf_df.index[-1].isoformat(),
                        reason=f"ER-gated sweep fade short (ER {er:.3f} < {_ER_THRESHOLD}): swept "
                               f"{level_high:.5f} (extreme {extreme:.5f}), TP mid {midpoint:.5f}, R:R {rr:.2f}",
                    )
            _used.add(key)
            return None

    # ── LONG: sweep of the fractal LOW ───────────────────────────────────────
    key = (level_low_ts, "long")
    if level_low_ts >= window_start and key not in _used:
        if low < level_low:
            _pending[key] = min(_pending.get(key, level_low), low)
        if key in _pending and close > level_low:
            extreme = _pending.pop(key)
            if not gate_open:
                _used.add(key)
                return None
            entry = close
            sl = extreme - _SL_BUFFER_PCT * span
            tp = midpoint
            risk, reward = entry - sl, tp - entry
            if risk > 0 and reward > 0:
                rr = reward / risk
                if rr >= _MIN_RR and (reward / pip) >= _MIN_TP_TO_SPREAD * assumed_spread:
                    _used.add(key)
                    return Signal(
                        direction="long", entry_price=entry, stop_loss=sl,
                        take_profits=[tp, tp, tp], instrument=instrument,
                        timeframe=ltf_df.index[-1].isoformat(),
                        reason=f"ER-gated sweep fade long (ER {er:.3f} < {_ER_THRESHOLD}): swept "
                               f"{level_low:.5f} (extreme {extreme:.5f}), TP mid {midpoint:.5f}, R:R {rr:.2f}",
                    )
            _used.add(key)
            return None

    return None
