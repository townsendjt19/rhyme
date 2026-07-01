"""
Portfolio State — Single Source of Truth for Cross-Bot Position Awareness
----------------------------------------------------------------------------
Every running bot process (swing, intraday, scalp30, ...) independently
calls OANDA to check get_open_trades() before placing an order, but none of
them has a *complete* structured view of the account: net exposure per
currency, which open positions are correlated, or how much headroom remains
under GLOBAL_RISK_CAP_PCT once every process's positions are counted together.

get_portfolio_state() is that single structured snapshot. It reads OANDA's
live open trades directly -- not any one bot process's in-memory state --
so it reflects every mode's positions regardless of which process opened
them. paper_trades.csv (the shared trade log every mode appends to via
main.py's _log_trade_csv) is used only for strategy/mode attribution; a
trade_id not found there (e.g. a manually placed trade) is labeled
"unknown" rather than dropped.

Any future currency-factor exposure cap should call get_portfolio_state()
rather than recomputing its own partial view of open positions from
get_open_trades() directly -- that per-process partial view is exactly the
gap this module exists to close.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from broker import convert_to_usd, get_account_balance, get_open_trades
from risk import CURRENCY_EXPOSURE_CAP_PCT, GLOBAL_RISK_CAP_PCT, RISK_PCT

BOT_DIR = Path(__file__).parent
PAPER_TRADES_CSV = BOT_DIR / "paper_trades.csv"


@dataclass
class OpenPosition:
    trade_id: str
    instrument: str
    direction: str          # "long" or "short"
    units: int              # signed: positive = long, negative = short
    entry_price: float
    unrealized_pnl: float
    strategy: str            # from paper_trades.csv attribution, else "unknown"
    open_time: str | None    # OANDA's own openTime, if present


@dataclass
class PortfolioState:
    timestamp: datetime
    balance: float
    open_positions: list[OpenPosition]
    net_exposure_by_currency: dict[str, int]   # signed units, summed across all open positions
    clusters: list[list[OpenPosition]]         # positions grouped by shared-currency connectivity
    risk_deployed_pct: float
    risk_cap_pct: float
    risk_headroom_pct: float
    remaining_trade_capacity: int
    error: str | None = None


def _load_strategy_attribution() -> dict[str, str]:
    """trade_id -> strategy tag, read from paper_trades.csv."""
    attribution: dict[str, str] = {}
    if not PAPER_TRADES_CSV.exists():
        return attribution
    with PAPER_TRADES_CSV.open(newline="") as fh:
        for row in csv.DictReader(fh):
            trade_id = row.get("trade_id")
            if trade_id:
                attribution[trade_id] = row.get("strategy") or "unknown"
    return attribution


def _currency_deltas(instrument: str, units: int) -> dict[str, int]:
    """Signed unit exposure contributed to each of the pair's two currencies.

    Long EUR_USD (units > 0): +EUR, -USD. Short GBP_JPY (units < 0): -GBP, +JPY.
    """
    base, quote = instrument.split("_")
    return {base: units, quote: -units}


def _build_clusters(positions: list[OpenPosition]) -> list[list[OpenPosition]]:
    """Group open positions into correlation clusters via shared-currency
    connectivity (union-find): two positions cluster together if they share
    a currency, directly or transitively. An open USD_JPY and an open
    GBP_JPY position cluster (share JPY); if a EUR_USD position is also
    open, it joins the same cluster (shares USD with USD_JPY) even though
    it shares no currency with GBP_JPY directly.
    """
    parent: dict[int, int] = {i: i for i in range(len(positions))}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    currency_to_first_idx: dict[str, int] = {}
    for i, pos in enumerate(positions):
        base, quote = pos.instrument.split("_")
        for ccy in (base, quote):
            if ccy in currency_to_first_idx:
                union(i, currency_to_first_idx[ccy])
            else:
                currency_to_first_idx[ccy] = i

    groups: dict[int, list[OpenPosition]] = {}
    for i, pos in enumerate(positions):
        groups.setdefault(find(i), []).append(pos)

    return list(groups.values())


def get_portfolio_state() -> PortfolioState:
    """
    The single structured snapshot of the account's true live state: every
    open position across every mode/process, net currency exposure,
    correlation clusters, and risk-cap headroom.
    """
    now = datetime.now(tz=timezone.utc)

    try:
        balance = get_account_balance()
        raw_trades = get_open_trades()
    except Exception as e:
        return PortfolioState(
            timestamp=now, balance=0.0, open_positions=[],
            net_exposure_by_currency={}, clusters=[],
            risk_deployed_pct=0.0, risk_cap_pct=GLOBAL_RISK_CAP_PCT,
            risk_headroom_pct=GLOBAL_RISK_CAP_PCT, remaining_trade_capacity=0,
            error=str(e),
        )

    attribution = _load_strategy_attribution()

    positions: list[OpenPosition] = []
    for t in raw_trades:
        trade_id = t.get("id", "")
        units = int(float(t.get("currentUnits", 0)))
        positions.append(OpenPosition(
            trade_id=trade_id,
            instrument=t.get("instrument", ""),
            direction="long" if units > 0 else "short",
            units=units,
            entry_price=float(t.get("price", 0.0)),
            unrealized_pnl=float(t.get("unrealizedPL", 0.0)),
            strategy=attribution.get(trade_id, "unknown"),
            open_time=t.get("openTime"),
        ))

    net_exposure: dict[str, int] = {}
    for pos in positions:
        for ccy, delta in _currency_deltas(pos.instrument, pos.units).items():
            net_exposure[ccy] = net_exposure.get(ccy, 0) + delta

    clusters = _build_clusters(positions)

    n_open = len(positions)
    risk_deployed_pct = n_open * RISK_PCT
    risk_headroom_pct = max(0.0, GLOBAL_RISK_CAP_PCT - risk_deployed_pct)
    # round(), not int(division) -- GLOBAL_RISK_CAP_PCT / RISK_PCT is a clean
    # integer ratio by construction (e.g. 0.06 / 0.02 = 3 trades), but binary
    # float representation makes 0.06 - 0.04 evaluate to 0.019999999999999997,
    # so int(headroom / RISK_PCT) truncates to 0 instead of 1 -- an off-by-one
    # undercount of remaining capacity. Computing the max slot count first and
    # subtracting n_open (integers) avoids the float subtraction entirely.
    max_trade_capacity = round(GLOBAL_RISK_CAP_PCT / RISK_PCT) if RISK_PCT else 0
    remaining_trade_capacity = max(0, max_trade_capacity - n_open)

    return PortfolioState(
        timestamp=now,
        balance=balance,
        open_positions=positions,
        net_exposure_by_currency=net_exposure,
        clusters=clusters,
        risk_deployed_pct=risk_deployed_pct,
        risk_cap_pct=GLOBAL_RISK_CAP_PCT,
        risk_headroom_pct=risk_headroom_pct,
        remaining_trade_capacity=remaining_trade_capacity,
    )


# ── Currency-factor exposure cap ─────────────────────────────────────────────
# Concentration cap, distinct from GLOBAL_RISK_CAP_PCT (bounds potential LOSS)
# and the margin check (bounds CAPITAL REQUIRED): a portfolio can be well
# within both of those and still be dangerously concentrated in one currency
# (e.g. long USD_JPY, long EUR_USD, long GBP_USD at once -- three
# "diversified" pairs that are actually one large short-USD bet). Callers
# should query get_portfolio_state() once and pass the SAME snapshot to
# check_currency_exposure_cap() for every candidate trade in that decision
# cycle, rather than each caller re-fetching its own partial view.

def project_exposure(
    state: PortfolioState, instrument: str, units: int
) -> dict[str, int]:
    """Return net_exposure_by_currency as it would look if a new trade of
    `units` on `instrument` (signed: positive = long, negative = short) were
    added to the CURRENT state -- a pure projection, does not place
    anything or mutate state."""
    projected = dict(state.net_exposure_by_currency)
    for ccy, delta in _currency_deltas(instrument, units).items():
        projected[ccy] = projected.get(ccy, 0) + delta
    return projected


def check_currency_exposure_cap(
    state: PortfolioState,
    instrument: str,
    units: int,
    cap_pct: float = CURRENCY_EXPOSURE_CAP_PCT,
) -> tuple[bool, str]:
    """
    Would adding this trade push net notional exposure to either of
    `instrument`'s two currencies beyond cap_pct of account balance (in USD,
    via live conversion so different currencies compare on a common basis)?

    Only blocks trades that make concentration WORSE: a trade is rejected
    only if it both (a) increases |net exposure| to a currency versus the
    CURRENT state, and (b) the resulting projected notional exceeds the cap.
    A trade that reduces exposure to an already-over-cap currency (e.g. a
    partial de-risking trade) is never blocked by this check, even though
    the post-trade state may still nominally exceed the cap -- rejecting a
    risk-*reducing* trade because the portfolio was already over cap before
    it arrived would be perverse.

    Returns (allowed, reason). reason is "" when allowed; otherwise a
    human-readable message naming the currency and amounts, suitable for
    logging directly at the call site.
    """
    balance = state.balance or 0.0
    cap_usd = balance * cap_pct

    projected = project_exposure(state, instrument, units)
    base, quote = instrument.split("_")

    for ccy in (base, quote):
        current_units = state.net_exposure_by_currency.get(ccy, 0)
        projected_units = projected.get(ccy, 0)
        if abs(projected_units) <= abs(current_units):
            continue  # this trade doesn't worsen concentration in ccy -- never block it

        notional_usd = convert_to_usd(abs(projected_units), ccy)
        if notional_usd > cap_usd:
            return False, (
                f"currency exposure cap would be breached: {ccy} net exposure "
                f"would reach {projected_units:+,} units (~${notional_usd:,.0f}) "
                f"> {cap_pct:.0%} of balance (${cap_usd:,.0f} cap)"
            )

    return True, ""
