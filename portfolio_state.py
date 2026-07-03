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
class ModeOverlap:
    """Two or more open positions on the SAME instrument, SAME direction,
    opened by DIFFERENT modes/strategies. Distinct from a correlation
    cluster (which is about shared currency exposure across DIFFERENT
    instruments): this is about redundant exposure to what is very likely
    the SAME underlying signal on the SAME instrument, paying spread and
    margin twice for it.

    Detection is generic -- grouped purely by (instrument, direction), with
    no mode-pair-specific logic -- so it applies to any pair of modes that
    happen to both be open on the same instrument+direction, not just the
    two cases already analyzed in RESEARCH_LOG.md:
      - donchian_plugin_swing vs. donchian_plugin_intraday (96.4% direction
        agreement, median 1h timing gap on their 4 shared pairs) -- swing
        was retired on those pairs as a result.
      - donchian_plugin_intraday vs. donchian_plugin_scalp30 on USD_JPY
        (97.3% agreement, median 0.5h gap -- even tighter) -- NOT acted on,
        since scalp30's own validation dataset overlaps heavily with this
        comparison; treat this one as descriptive (both modes are reading
        nearly the same signal) rather than prescriptive (don't retire
        intraday's USD_JPY on this basis alone).
    Any future mode pair that ends up both open on the same instrument and
    direction will be flagged here the same way, without code changes."""
    instrument: str
    direction: str
    positions: list[OpenPosition]   # 2+, one per overlapping mode


@dataclass
class PortfolioState:
    timestamp: datetime
    balance: float
    open_positions: list[OpenPosition]
    net_exposure_by_currency: dict[str, int]   # signed units, summed across all open positions
    clusters: list[list[OpenPosition]]         # positions grouped by shared-currency connectivity
    mode_overlaps: list[ModeOverlap]            # same instrument+direction, different modes -- see ModeOverlap
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


def _detect_mode_overlaps(positions: list[OpenPosition]) -> list[ModeOverlap]:
    """Group open positions by (instrument, direction); any group with 2+
    positions attributed to different strategy/mode tags is a mode overlap
    -- visible, explicit redundant exposure rather than hidden inside two
    separately-computed per-process views. Positions with the same
    strategy tag never overlap with themselves here since each mode's own
    "position already open" check in main.py already prevents a single
    mode from holding two positions on the same instrument."""
    groups: dict[tuple[str, str], list[OpenPosition]] = {}
    for pos in positions:
        key = (pos.instrument, pos.direction)
        groups.setdefault(key, []).append(pos)

    overlaps: list[ModeOverlap] = []
    for (instrument, direction), group in groups.items():
        distinct_strategies = {p.strategy for p in group}
        if len(group) >= 2 and len(distinct_strategies) >= 2:
            overlaps.append(ModeOverlap(instrument=instrument, direction=direction, positions=group))
    return overlaps


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
            net_exposure_by_currency={}, clusters=[], mode_overlaps=[],
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
    mode_overlaps = _detect_mode_overlaps(positions)

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
        mode_overlaps=mode_overlaps,
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


# ── Spread-trade (two-leg trade-idea) grouping — stat-arb Phase 2, 2026-07-02 ─
# A spread trade is ONE trade idea spanning two instruments. These gates
# evaluate the idea atomically: the joint projection is computed BEFORE either
# leg is placed, per the atomic-execution design (RESEARCH_LOG, Phase 2
# deployment spec). Legs are tagged with a shared idea id at placement
# (clientExtensions "spread:<idea_id>") so downstream accounting can group
# them back into one risk unit.

def project_spread_exposure(
    state: PortfolioState, legs: list[tuple[str, int]]
) -> dict[str, int]:
    """Joint currency projection of ALL legs of one trade idea — pure.

    Both legs project together so a currency shared across legs (e.g. the
    USD in NZD_USD long / USD_CAD short) nets exactly once. Projecting legs
    through separate sequential gate calls both risks mis-counting the shared
    currency mid-sequence and permits the half-approved state the atomic
    design forbids.
    """
    projected = dict(state.net_exposure_by_currency)
    for instrument, units in legs:
        for ccy, delta in _currency_deltas(instrument, units).items():
            projected[ccy] = projected.get(ccy, 0) + delta
    return projected


def check_spread_currency_exposure_cap(
    state: PortfolioState,
    legs: list[tuple[str, int]],
    cap_pct: float = CURRENCY_EXPOSURE_CAP_PCT,
) -> tuple[bool, str]:
    """Atomic exposure-cap check for a multi-leg trade idea.

    Same worsening-only semantics as the single-instrument check, evaluated
    on the COMBINED projection. Every currency of every leg is examined
    individually against the joint projection — the gross non-shared legs
    (NZD, CAD in the example) are never netted away by the shared-currency
    netting. Returns (allowed, reason) exactly like the single check; a
    rejection rejects the WHOLE idea (no leg places).
    """
    balance = state.balance or 0.0
    cap_usd = balance * cap_pct
    projected = project_spread_exposure(state, legs)

    ccys: list[str] = []
    for instrument, _u in legs:
        for c in instrument.split("_"):
            if c not in ccys:
                ccys.append(c)

    for ccy in ccys:
        current_units = state.net_exposure_by_currency.get(ccy, 0)
        projected_units = projected.get(ccy, 0)
        if abs(projected_units) <= abs(current_units):
            continue
        notional_usd = convert_to_usd(abs(projected_units), ccy)
        if notional_usd > cap_usd:
            return False, (
                f"spread trade idea rejected atomically: {ccy} net exposure "
                f"would reach {projected_units:+,} units (~${notional_usd:,.0f}) "
                f"> {cap_pct:.0%} of balance (${cap_usd:,.0f} cap)"
            )
    return True, ""


def check_spread_position_cap(
    state: PortfolioState, legs: list[tuple[str, int]]
) -> tuple[bool, str]:
    """Position-cap / collision check for a spread idea, evaluated atomically.

    Each leg's instrument must be FREE of any existing open position — a leg
    colliding with an existing position is both a MAX_POSITIONS_PER_INSTRUMENT
    breach and (same-account) an NFA/FIFO broker-side cancellation waiting to
    happen (the Bot D discovery, 2026-07-01). Rejecting the whole idea when
    either leg collides is the point: a spread whose second leg would be
    cancelled broker-side must never place its first leg.
    """
    open_instruments = {p.instrument for p in state.open_positions}
    for instrument, _u in legs:
        if instrument in open_instruments:
            return False, (
                f"spread leg collision: {instrument} already has an open position "
                f"(per-instrument cap / FIFO); the whole idea is rejected"
            )
    return True, ""


def group_positions_by_idea(positions: list[OpenPosition]) -> dict[str, list[OpenPosition]]:
    """Group open positions into trade ideas for risk accounting.

    Legs tagged "spread:<idea_id>" in their strategy attribution group
    together and count as ONE risk unit (the idea risks one fixed-$ amount
    across both legs — counting each leg separately would double-count
    deployed risk). Untagged positions group singly under their trade id.
    """
    groups: dict[str, list[OpenPosition]] = {}
    for p in positions:
        strat = p.strategy or ""
        key = strat if strat.startswith("spread:") else f"single:{p.trade_id}"
        groups.setdefault(key, []).append(p)
    return groups
