"""
London Breakout Strategy Plugin  (v4 — previous-day range)
------------------------------------------------------------
Range definition:
    High and low of all H1 candles whose date falls on the PREVIOUS
    trading day (Friday for Monday entries; skips weekends automatically
    because H1 candles only exist on trading days).

Entry window: M15 candles whose open time is 07:00-10:00 UTC.
    Long  : M15 close > prev_day_high  → enter long
    Short : M15 close < prev_day_low   → enter short
    First break only — no second entry on the same day.

Filters:
    1. Wednesday skip
    2. Minimum range width >= 30 pips (too tight = noise, not structure)

SL  : opposite daily boundary  ±  small pip buffer
TP  : 2.5 × risk  (all three TP slots equal → full position exits at once)

Usage:
    python D:/rhyme/backtest.py --instrument EUR_USD --mode scalp \\
        --start 2023-01-01 --end 2024-01-01 \\
        --signals-module D:/rhyme/london_breakout_plugin.py
"""
from __future__ import annotations
import pandas as pd
from strategy import Signal

# ── Constants ─────────────────────────────────────────────────────────────────

_TP_R            = 2.5
_MIN_RANGE_PIPS  = 30        # skip if previous-day range < 30 pips
_SL_BUFFER_PIPS  = 2         # extra buffer beyond opposite daily level
_ENTRY_START_MIN = 7 * 60    # 07:00 UTC  (minutes since midnight)
_ENTRY_END_MIN   = 10 * 60   # 10:00 UTC  (last entry candle opens at 09:45)

_PIP_SIZE: dict[str, float] = {
    "EUR_USD": 0.0001, "GBP_USD": 0.0001,
    "AUD_USD": 0.0001, "USD_CAD": 0.0001,
    "USD_JPY": 0.01,   "EUR_JPY": 0.01,   "GBP_JPY": 0.01,
}
_DEFAULT_PIP = 0.0001


# ── Signal generator ──────────────────────────────────────────────────────────

def generate_signal(
    instrument: str,
    htf_df: pd.DataFrame,   # H1 candles — used to build previous-day range
    ltf_df: pd.DataFrame,   # M15 candles — signal timeframe
    mode: str,
) -> Signal | None:
    if len(ltf_df) < 2 or len(htf_df) < 24:
        return None

    signal_time = ltf_df.index[-1]

    # ── 1. Wednesday skip ─────────────────────────────────────────────────────
    if signal_time.day_of_week == 2:
        return None

    # ── 2. Entry window check (07:00–10:00 UTC) ───────────────────────────────
    candle_min = signal_time.hour * 60 + signal_time.minute
    if not (_ENTRY_START_MIN <= candle_min < _ENTRY_END_MIN):
        return None

    # ── 3. Build previous-day range from H1 candles ───────────────────────────
    # "Previous trading day" = the most recent date in htf_df strictly before
    # signal_time.date().  This naturally skips weekends because H1 candles
    # only exist on trading days (Mon-Fri).
    today = signal_time.normalize()          # midnight UTC of current day
    past_htf = htf_df[htf_df.index < today]
    if past_htf.empty:
        return None

    prev_day_date = past_htf.index[-1].normalize()
    prev_candles  = htf_df[
        (htf_df.index >= prev_day_date) &
        (htf_df.index <  prev_day_date + pd.Timedelta(days=1))
    ]
    if len(prev_candles) < 4:               # need at least 4 H1 candles
        return None

    prev_high = float(prev_candles["high"].max())
    prev_low  = float(prev_candles["low"].min())

    pip         = _PIP_SIZE.get(instrument, _DEFAULT_PIP)
    range_pips  = (prev_high - prev_low) / pip

    # ── 4. Minimum range width filter (>= 30 pips) ───────────────────────────
    if range_pips < _MIN_RANGE_PIPS:
        return None

    # ── 5. First-break-only gate ──────────────────────────────────────────────
    entry_start_ts = today + pd.Timedelta(hours=7)
    prev_window = ltf_df[
        (ltf_df.index >= entry_start_ts) &
        (ltf_df.index <  signal_time)
    ]
    already_long  = not prev_window.empty and (prev_window["close"] > prev_high).any()
    already_short = not prev_window.empty and (prev_window["close"] < prev_low).any()
    if already_long or already_short:
        return None

    current_close = float(ltf_df.iloc[-1]["close"])
    sl_buf        = pip * _SL_BUFFER_PIPS

    # ── 6a. Long entry ────────────────────────────────────────────────────────
    if current_close > prev_high:
        entry = current_close
        sl    = prev_low - sl_buf
        risk  = entry - sl
        if risk <= 0:
            return None
        tp = entry + _TP_R * risk
        return Signal(
            direction="long",
            entry_price=entry,
            stop_loss=sl,
            take_profits=[tp, tp, tp],
            instrument=instrument,
            timeframe="M15",
            reason=(
                f"LB-PDH long | prev day {prev_low:.5f}-{prev_high:.5f} "
                f"({range_pips:.0f}pip) | break {signal_time.strftime('%H:%M')} UTC"
            ),
        )

    # ── 6b. Short entry ───────────────────────────────────────────────────────
    if current_close < prev_low:
        entry = current_close
        sl    = prev_high + sl_buf
        risk  = sl - entry
        if risk <= 0:
            return None
        tp = entry - _TP_R * risk
        return Signal(
            direction="short",
            entry_price=entry,
            stop_loss=sl,
            take_profits=[tp, tp, tp],
            instrument=instrument,
            timeframe="M15",
            reason=(
                f"LB-PDH short | prev day {prev_low:.5f}-{prev_high:.5f} "
                f"({range_pips:.0f}pip) | break {signal_time.strftime('%H:%M')} UTC"
            ),
        )

    return None
