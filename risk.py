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

RISK_PCT = 0.02              # 2 % of account per trade
GLOBAL_RISK_CAP_PCT = 0.06   # 6 % total account exposure cap across ALL open positions/modes

# Max net NOTIONAL exposure to any single currency, as a MULTIPLE of account
# balance (not a fraction -- retail FX is leveraged, so even one normal-sized
# trade's notional naturally runs several multiples of account equity by
# design; a sub-1.0 fraction here would reject nearly every trade regardless
# of actual concentration risk). Converted to USD so different currencies
# compare on a common basis (a currency's net exposure is the sum of its
# signed unit exposure across every open position touching it -- see
# portfolio_state.py). This is a concentration cap, distinct from
# GLOBAL_RISK_CAP_PCT (which bounds potential LOSS) and the margin check in
# broker.py (which bounds CAPITAL REQUIRED): a portfolio can be well within
# both of those and still be dangerously concentrated in one currency (e.g.
# long USD_JPY, long EUR_USD, long GBP_USD all at once -- three
# "diversified" pairs that are actually one large short-USD bet).
#
# Sizing math (USD_JPY, ~21,000-unit typical trade = $21,000 USD notional
# 1:1 since USD is the base currency, on a $4,075.63 balance):
#   1 position (zero headroom)    ->  5.15x balance required
#   2 positions (room for 1 more) -> 10.31x balance required
#   3 positions (room for 2 more) -> 15.46x balance required
# 12.0x was chosen to comfortably fit 2 full-size same-currency trades
# (2 x $21,000 = $42,000 well under the $48,900 cap at this balance) with
# real headroom before a 3rd is blocked, while still capping at ~60% of
# this account's total margin capacity (~$81,500 at USD_JPY's 20:1 margin
# rate) rather than ~77%+ -- a meaningful concentration constraint, not a
# rubber stamp. Not a backtested constant -- tune here if it proves too
# tight or too loose live, and re-derive if account balance changes a lot.
#
# CALIBRATION REFERENCE CASE -- re-verify this ratio if either changes:
#   Account balance : $4,075.63
#   Margin rate      : 0.05 (USD_JPY, 20:1) -- the dominant position-size
#                       driver at calibration time
#   Result           : N (=1200%/515%) is approx 2.3 same-currency positions,
#                       approx 60% of total margin capacity
# This 12.0x multiple is NOT a universal constant -- it was reverse-engineered
# from one specific balance and one specific pair's margin rate. If the
# account balance grows substantially, the same 12.0x multiple no longer
# maps to "~2.3 positions, ~60% of margin" -- re-run the sizing math above
# with the new balance. Likewise, if a pair with a meaningfully different
# margin rate (e.g. a 50:1/0.02 major, or a higher-margin exotic) becomes the
# typical/dominant position-size driver instead of USD_JPY, the "~60% of
# margin capacity" relationship shifts even at the same balance, since
# margin capacity = balance / margin_rate -- re-derive rather than assuming
# 12.0x still means the same thing.
CURRENCY_EXPOSURE_CAP_PCT = 12.0   # 1200 % of account balance, net notional, per currency

# Max OPEN POSITIONS per instrument, counted across ALL modes/processes.
# BROKER-ENFORCED at 1 on this account: OANDA's NFA FIFO compliance
# safeguard instantly cancels any second same-instrument order carrying
# its own attached SL/TP (observed live 2026-07-01 -- Bot D's first order,
# create transaction 41, cancelled in the same batch with reason
# FIFO_VIOLATION_SAFEGUARD_VIOLATION while trade 37 held USD_JPY). A
# cap-2 stacking design was built, unit-tested, and committed (202a8f8)
# before this was discovered; it is unexecutable here, so the cap is
# reverted to 1 to match broker reality rather than letting orders be
# placed only to be broker-cancelled. Multi-position-per-instrument is
# achievable only via separate sub-accounts (see Bot D's isolated-account
# deployment). The count-based gate implementation is kept (not the old
# blanket set-membership check) so this stays a one-line change if the
# account type ever permits it.
MAX_POSITIONS_PER_INSTRUMENT = 1

# Max projected TOTAL margin utilization as a fraction of NAV, checked
# pre-trade including the candidate order's own margin at the instrument's
# per-instrument rate. Distinct from the existing marginAvailable check
# (which only asks "can this order be placed at all"): this bounds how
# deep into the account's margin capacity the whole book may go, so a
# stack of individually-placeable positions can't walk utilization up to
# the closeout edge (the 3x USD_JPY stack at median sizes would use 93%
# of NAV -- placeable, but one adverse move from forced liquidation).
MARGIN_UTILIZATION_CAP_PCT = 0.60


def _is_jpy_pair(instrument: str) -> bool:
    """Any pair quoted in JPY, not just the three originally hardcoded."""
    return instrument.endswith("_JPY") or instrument == "USD_JPY"


def price_precision(instrument: str) -> int:
    """Decimal places OANDA expects for this instrument's price fields.

    JPY pairs quote to 3 decimals (pip = 0.01, so 3dp = 1/10 pip); every
    other pair quotes to 5 decimals (pip = 0.0001, so 5dp = 1/10 pip).
    Formatting a JPY price to 5 decimals sends OANDA excess precision it
    doesn't accept, which can cause silent rejection or truncation at
    order-submission time.
    """
    return 3 if _is_jpy_pair(instrument) else 5


# Instruments that need dynamic JPY pip value (all JPY crosses share the same formula).
# Kept as a callable check (not a fixed set) so crosses like AUD_JPY/CAD_JPY/CHF_JPY
# aren't silently missed -- a missing entry here used to make pip_size() fall back to
# the 0.0001 USD-pair default (100x too small for JPY pairs), which collapsed lot
# sizing to zero and silently dropped every trade despite signals passing all filters.
JPY_PAIRS = _is_jpy_pair


def pip_size(instrument: str) -> float:
    if _is_jpy_pair(instrument):
        return 0.01
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
    if _is_jpy_pair(instrument):
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
