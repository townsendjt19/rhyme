"""
Liquidity Sweep Fade Plugin — Bot E candidate #3 (mean reversion)
------------------------------------------------------------------
Pre-registered ac51eed (2026-07-02), after range_fade v1 (384982b) and v2
(a3592f7) were killed. Design thesis under test: an entry that REQUIRES a
confirmed breakout failure (price sweeps a confirmed H4 fractal level, then
an M30 candle closes back inside) self-gates in persistent trends -- the
criterion-3 failure mode both prior candidates died of. Accordingly there is
NO separate regime gate (no fractal non-trend gate, no ER gate).

Mechanics (constants inherited from project conventions, CHOSEN not tuned):
- Reference levels: most recent CONFIRMED fractal high (short setups) and
  fractal low (long setups), _FRACTAL_N=2, level bar within the trailing
  _WINDOW_H4=120 window.
- Sweep lifecycle: pending opens when an M30 candle trades beyond the level;
  the sweep extreme tracks the excursion; the first M30 close back inside
  CONFIRMS -> enter at that close against the sweep. Single-candle
  wick-through-and-close-back qualifies. Pending drops when a newer confirmed
  fractal replaces the level or the level ages out of the window.
- SL beyond the sweep extreme by _SL_BUFFER_PCT of window span; TP at the
  window midpoint (current bar excluded); min R:R 1.2; Amendment-1 spread
  floor (TP distance >= 10x assumed spread); Amendment-2 fire-and-forget.
- Non-starving re-entry guard: identity = (level timestamp, direction);
  each swept level trades at most once; new confirmed fractals arm
  immediately. Both directions, no carve-outs.
- A runaway excursion that confirms late has a distant SL -> the R:R filter
  rejects it naturally; no discretionary cap.

Usage:
    python D:/rhyme/backtest.py --instrument USD_CAD --mode scalp30 \\
        --start 2022-07-01 --end 2023-10-01 \\
        --signals-module D:/rhyme/liquidity_sweep_fade_plugin.py
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal
from indicators import detect_fractals


# ── Constants (captured automatically in backtest header; CHOSEN, not tuned) ──

_FRACTAL_N        = 2
_WINDOW_DAYS      = 20
_WINDOW_H4        = _WINDOW_DAYS * 6   # 120 H4 candles
_SL_BUFFER_PCT    = 0.05               # of window span, beyond the sweep extreme
_MIN_RR           = 1.2
_MIN_TP_TO_SPREAD = 10.0

# Declared history requirement (2026-07-02 boundary-parity fix).
WARMUP_HTF_CANDLES = _WINDOW_H4 + 1 + 2 * _FRACTAL_N

_ASSUMED_SPREAD_PIPS = {
    "USD_CAD": 1.7, "USD_JPY": 1.5, "EUR_USD": 1.5, "GBP_USD": 1.8,
    "EUR_JPY": 2.8, "AUD_USD": 1.3, "EUR_GBP": 1.3, "USD_CHF": 1.6,
}
_DEFAULT_ASSUMED_SPREAD = 2.0


def _pip_size(instrument: str) -> float:
    return 0.01 if "JPY" in instrument else 0.0001


# ── Sweep state (module-level; runners load a fresh module per run) ───────────
# _pending: identity -> sweep extreme so far.  _used: identities already traded.
# identity = (level_timestamp, direction)
_pending: dict = {}
_used: set = set()


def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # H4 candles -- fractal levels + window midpoint
    ltf_df: pd.DataFrame,   # M30 candles -- sweep trigger
    mode: str,
) -> Signal | None:
    if len(htf_df) < _WINDOW_H4 + 1 or len(ltf_df) < 1:
        return None

    # Confirmed fractal levels
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

    # Drop pending state for levels that are no longer the current reference
    # (replaced by a newer confirmed fractal) or that aged out of the window.
    current = {(level_high_ts, "short"), (level_low_ts, "long")}
    for key in list(_pending):
        ts, _d = key
        if key not in current or ts < window_start:
            del _pending[key]

    candle = ltf_df.iloc[-1]
    high, low, close = float(candle["high"]), float(candle["low"]), float(candle["close"])

    pip = _pip_size(instrument)
    assumed_spread = _ASSUMED_SPREAD_PIPS.get(instrument, _DEFAULT_ASSUMED_SPREAD)

    # ── SHORT: sweep of the fractal HIGH ─────────────────────────────────────
    key = (level_high_ts, "short")
    if level_high_ts >= window_start and key not in _used:
        breached = high > level_high
        if breached:
            _pending[key] = max(_pending.get(key, level_high), high)
        if key in _pending and close < level_high:
            extreme = _pending.pop(key)
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
                        reason=f"Liquidity sweep fade short: swept fractal high {level_high:.5f} "
                               f"(extreme {extreme:.5f}), closed back inside; TP midpoint "
                               f"{midpoint:.5f}, R:R {rr:.2f}",
                    )
            # Confirmed but filtered (R:R / spread floor): the sweep event is
            # consumed -- mark used so a worse late re-confirmation can't fire.
            _used.add(key)
            return None

    # ── LONG: sweep of the fractal LOW ───────────────────────────────────────
    key = (level_low_ts, "long")
    if level_low_ts >= window_start and key not in _used:
        breached = low < level_low
        if breached:
            _pending[key] = min(_pending.get(key, level_low), low)
        if key in _pending and close > level_low:
            extreme = _pending.pop(key)
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
                        reason=f"Liquidity sweep fade long: swept fractal low {level_low:.5f} "
                               f"(extreme {extreme:.5f}), closed back inside; TP midpoint "
                               f"{midpoint:.5f}, R:R {rr:.2f}",
                    )
            _used.add(key)
            return None

    return None
