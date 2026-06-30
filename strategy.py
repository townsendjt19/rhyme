"""
Combined signal logic — all six conditions evaluated in order.

Timeframe modes:
  swing    : higher_tf = Daily,  trigger_tf = H4
  intraday : higher_tf = H4,     trigger_tf = H1
  scalp    : higher_tf = H1,     trigger_tf = M15

Returns a Signal dataclass or None.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol
import pandas as pd

from indicators import (
    add_emas,
    detect_fractals,
    ema_aligned_bull,
    ema_aligned_bear,
    crossover_bull,
    crossover_bear,
    last_fractal_high,
    last_fractal_low,
)
from patterns import has_opposing_pattern_long, has_opposing_pattern_short
from volume_profile import build_volume_profile, price_in_lvn
from fibonacci import (
    fib_retracements_long,
    fib_retracements_short,
    price_near_retracement,
    get_extension_tps,
    RETRACE_LEVELS,
)


# ── Optional filter config ────────────────────────────────────────────────────
# Toggle these flags to enable/disable the extra filters globally,
# or pass a StrategyConfig to evaluate() for per-call control.

@dataclass
class StrategyConfig:
    skip_wednesday: bool = False        # skip all entries on Wednesday (UTC)
    skip_382_fib: bool = False          # only allow 50% and 61.8% fib entries
    min_rr: float = 0.0                 # minimum R:R required (TP3 vs SL); 0 = disabled


DEFAULT_CONFIG = StrategyConfig()


@dataclass
class Signal:
    direction: str          # "long" or "short"
    entry_price: float
    stop_loss: float
    take_profits: list[float]
    instrument: str
    timeframe: str
    fib_retracements: dict = field(default_factory=dict)
    reason: str = ""


# ── External signal provider protocol ────────────────────────────────────────

class SignalProvider(Protocol):
    """
    Interface for plugging any strategy into the backtest/live framework.

    Implement this in an external module and pass the module path to backtest.py
    via --signals-module. The module must expose a top-level function with this
    exact signature.

    The framework supplies pre-fetched, indicator-enriched DataFrames.
    Return a Signal to enter a trade, or None to pass.

    Example module (my_strategy.py):

        from strategy import Signal

        def generate_signal(
            instrument: str,
            htf_df: pd.DataFrame,   # higher TF candles with ema_20/50/100, fractal_high/low
            ltf_df: pd.DataFrame,   # trigger TF candles with same columns
            mode: str,
        ) -> Signal | None:
            ...
            return Signal(
                direction="long",
                entry_price=ltf_df.iloc[-1]["close"],
                stop_loss=...,
                take_profits=[tp1, tp2, tp3],
                instrument=instrument,
                timeframe="M15",
                reason="my custom signal",
            )
    """
    def __call__(
        self,
        instrument: str,
        htf_df: "pd.DataFrame",
        ltf_df: "pd.DataFrame",
        mode: str,
    ) -> "Signal | None": ...


# Canonical filter stage names (used as dict keys in funnel counts)
FILTER_STAGES = [
    "1_htf_ema_alignment",
    "2_ltf_ema_crossover",
    "3_fractal_break",
    "4_candlestick_filter",
    "5_volume_profile_lvn",
    "6_fib_confirmation",
    "passed",
]


def _nearest_fib_level(price: float, retracements: dict) -> float | None:
    """Return the ratio key (e.g. 0.382) of the closest retracement level."""
    best_ratio, best_dist = None, float("inf")
    for ratio, level in retracements.items():
        dist = abs(price - level) / level if level else float("inf")
        if dist < best_dist:
            best_dist = dist
            best_ratio = ratio
    return best_ratio


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = add_emas(df)
    df = detect_fractals(df)
    return df


def evaluate(
    instrument: str,
    higher_tf_df: pd.DataFrame,
    trigger_tf_df: pd.DataFrame,
    mode: str = "intraday",
    config: StrategyConfig | None = None,
) -> tuple[Signal | None, str]:
    """
    Evaluate all six entry conditions plus optional extra filters.

    Returns (Signal, stage) where stage is the name of the filter that passed
    or failed. If Signal is None, stage is the name of the failing filter.

    higher_tf_df  : already-fetched candles for the confirming timeframe
    trigger_tf_df : already-fetched candles for the triggering timeframe
    mode          : "swing" | "intraday" | "scalp"
    config        : StrategyConfig — optional filter toggles
    """
    cfg = config if config is not None else DEFAULT_CONFIG
    tf_label = {"swing": "H4", "intraday": "H1", "scalp": "M15"}.get(mode, "H1")

    htf = _prepare(higher_tf_df)
    ltf = _prepare(trigger_tf_df)

    if len(htf) < 5 or len(ltf) < 5:
        return None, "1_htf_ema_alignment"

    # ── Optional: skip Wednesday entries ─────────────────────────────────────
    if cfg.skip_wednesday:
        signal_time = ltf.index[-1]
        if signal_time.day_of_week == 2:  # 0=Mon … 2=Wed … 4=Fri
            return None, "1_htf_ema_alignment"

    # ── 1. Higher TF 3MA alignment ───────────────────────────────────────────
    bull_htf = ema_aligned_bull(htf)
    bear_htf = ema_aligned_bear(htf)

    if not bull_htf and not bear_htf:
        return None, "1_htf_ema_alignment"

    direction = "long" if bull_htf else "short"

    # ── 2. Lower TF 3MA crossover (same candle) ───────────────────────────────
    if direction == "long" and not crossover_bull(ltf, lookback=1):
        return None, "2_ltf_ema_crossover"
    if direction == "short" and not crossover_bear(ltf, lookback=1):
        return None, "2_ltf_ema_crossover"

    # ── 3. Williams Fractal break (same candle) ───────────────────────────────
    signal_close = ltf.iloc[-1]["close"]
    signal_high = ltf.iloc[-1]["high"]
    signal_low = ltf.iloc[-1]["low"]

    last_fh = last_fractal_high(ltf, before_idx=-1)
    last_fl = last_fractal_low(ltf, before_idx=-1)

    if direction == "long":
        if last_fh is None or signal_close <= last_fh:
            return None, "3_fractal_break"
    else:
        if last_fl is None or signal_close >= last_fl:
            return None, "3_fractal_break"

    # ── 4. Candlestick filter ─────────────────────────────────────────────────
    if direction == "long" and has_opposing_pattern_long(ltf):
        return None, "4_candlestick_filter"
    if direction == "short" and has_opposing_pattern_short(ltf):
        return None, "4_candlestick_filter"

    # ── 5. Volume Profile — skip if inside LVN ────────────────────────────────
    profile = build_volume_profile(ltf)
    if price_in_lvn(signal_close, profile):
        return None, "5_volume_profile_lvn"

    # ── 6. Fibonacci confirmation — price bouncing off retracement ────────────
    if direction == "long":
        retracements = fib_retracements_long(ltf, before_idx=-1)
    else:
        retracements = fib_retracements_short(ltf, before_idx=-1)

    if not price_near_retracement(signal_close, retracements):
        return None, "6_fib_confirmation"

    # ── Optional: skip 38.2% fib entries — only allow 50% and 61.8% ─────────
    if cfg.skip_382_fib:
        active_level = _nearest_fib_level(signal_close, retracements)
        if active_level == 0.382:
            return None, "6_fib_confirmation"

    # ── Stop loss: further of fractal level or 100 EMA ───────────────────────
    ema100 = float(ltf.iloc[-1]["ema_100"])

    if direction == "long":
        fractal_sl = last_fl if last_fl is not None else signal_low
        stop_loss = min(fractal_sl, ema100)
    else:
        fractal_sl = last_fh if last_fh is not None else signal_high
        stop_loss = max(fractal_sl, ema100)

    # ── Take profit: Fibonacci extensions ─────────────────────────────────────
    take_profits = get_extension_tps(ltf, direction, before_idx=-1)
    if not take_profits:
        return None, "6_fib_confirmation"

    # ── Optional: minimum R:R gate (measured to TP3 vs SL) ───────────────────
    if cfg.min_rr > 0:
        tp3 = take_profits[-1]
        reward = abs(tp3 - signal_close)
        risk = abs(signal_close - stop_loss)
        if risk == 0 or (reward / risk) < cfg.min_rr:
            return None, "6_fib_confirmation"

    return Signal(
        direction=direction,
        entry_price=signal_close,
        stop_loss=stop_loss,
        take_profits=take_profits,
        instrument=instrument,
        timeframe=tf_label,
        fib_retracements=retracements,
        reason=f"All 6 conditions passed ({mode})",
    ), "passed"
