"""
Position sizing and risk management.

Risk per trade: 2% of account equity.
Lot size calculated from stop distance in pips.
"""
import math
import os


# Standard pip values (per 1 standard lot = 100,000 units) in USD.
# JPY pairs and USD_CAD are rate-dependent — use the dynamic helpers below.
_PIP_VALUE_USD: dict[str, float] = {
    "EUR_USD": 10.0,
    "GBP_USD": 10.0,
    "AUD_USD": 10.0,
    "USD_JPY": 9.0,   # placeholder; use pip_value_jpyfx(usdjpy_rate)
    "EUR_JPY": 9.0,   # placeholder; use pip_value_jpyfx(usdjpy_rate)
    "GBP_JPY": 9.0,   # placeholder; use pip_value_jpyfx(usdjpy_rate)
    "USD_CAD": 7.50,  # placeholder; use pip_value_cadpair(usdcad_rate)
}

_PIP_SIZE: dict[str, float] = {
    "EUR_USD": 0.0001,
    "GBP_USD": 0.0001,
    "AUD_USD": 0.0001,
    "USD_JPY": 0.01,
    "EUR_JPY": 0.01,
    "GBP_JPY": 0.01,
    "USD_CAD": 0.0001,
}

# Instruments that need dynamic JPY pip value (all JPY crosses share the same formula)
JPY_PAIRS: frozenset[str] = frozenset({"USD_JPY", "EUR_JPY", "GBP_JPY"})

RISK_PCT = 0.02  # 2 % of account per trade


def pip_size(instrument: str) -> float:
    return _PIP_SIZE.get(instrument, 0.0001)


def stop_distance_pips(entry: float, stop: float, instrument: str) -> float:
    return abs(entry - stop) / pip_size(instrument)


def lot_size(
    account_balance: float,
    entry: float,
    stop: float,
    instrument: str,
    pip_value_usd: float | None = None,
    risk_pct: float = RISK_PCT,
) -> float:
    """
    Return lot size (in standard lots) that risks risk_pct of account_balance.

    pip_value_usd : value of 1 pip per standard lot in account currency.
                    If None, uses default table value.
    """
    pv = pip_value_usd if pip_value_usd is not None else _PIP_VALUE_USD.get(instrument, 10.0)
    risk_amount = account_balance * risk_pct
    pips = stop_distance_pips(entry, stop, instrument)
    if pips == 0:
        return 0.0
    raw = risk_amount / (pips * pv)
    return _round_lots(raw)


def _round_lots(lots: float, step: float = 0.01) -> float:
    """Round down to nearest allowed lot step (0.01 = 1 micro lot)."""
    return math.floor(lots / step) * step


def units_from_lots(lots: float, instrument: str) -> int:
    """Convert lots to OANDA units (1 lot = 100,000 units)."""
    return int(lots * 100_000)


def pip_value_jpyfx(entry_usdjpy: float) -> float:
    """
    Pip value in USD for any JPY pair (USD/JPY, EUR/JPY, GBP/JPY).
    Pass the current USD/JPY rate regardless of which cross is being traded.
    Formula: (0.01 / usdjpy_rate) * 100,000
    """
    return (0.01 / entry_usdjpy) * 100_000


def pip_value_cadpair(entry_usdcad: float) -> float:
    """
    Pip value in USD for USD/CAD.
    Formula: (0.0001 / usdcad_rate) * 100,000
    """
    return (0.0001 / entry_usdcad) * 100_000


def dynamic_pip_value(instrument: str, entry: float) -> float | None:
    """
    Return a dynamically calculated pip value where the static table is inaccurate.
    Returns None for pairs whose static table value is reliable (USD-quoted majors).

    JPY pairs  : entry is the JPY cross price (not USDJPY); approximate is close
                 enough for sizing — caller can pass real USDJPY rate for precision.
    USD_CAD    : entry is the USDCAD price.
    """
    if instrument in JPY_PAIRS:
        return pip_value_jpyfx(entry)
    if instrument == "USD_CAD":
        return pip_value_cadpair(entry)
    return None


def trailing_stop_price(
    direction: str,
    current_price: float,
    ema_20: float,
) -> float:
    """
    Trail stop to the 20 EMA once 1:1 R:R is reached.
    Returns the new stop price (ema_20 is the trail).
    """
    return ema_20


def should_advance_stop(
    direction: str,
    current_price: float,
    next_tp: float,
) -> bool:
    """Return True if price has reached the next TP level."""
    if direction == "long":
        return current_price >= next_tp
    return current_price <= next_tp


def partial_close_size(total_units: int, tp_index: int) -> int:
    """
    Size of partial close at each TP level.
    TP1 (1.272): close 33%
    TP2 (1.618): close 33%
    TP3 (2.000): close remaining
    """
    fractions = [0.33, 0.33, 1.0]
    frac = fractions[min(tp_index, len(fractions) - 1)]
    return int(total_units * frac)
