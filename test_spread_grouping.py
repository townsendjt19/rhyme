"""
Unit tests: spread-trade (two-leg trade-idea) risk-layer grouping.

Verifies BOTH mis-count directions the Phase 2 handoff named:
  - no DOUBLE-count: a currency shared across legs (the USD in
    NZD_USD / USD_CAD) nets exactly once in the joint projection;
  - no UNDER-count: the gross non-shared legs (NZD, CAD) are fully
    counted, never netted away by the shared-currency netting.
Plus the atomic collision check and one-idea risk grouping.

Run: D:/rhyme/venv/Scripts/python.exe D:/rhyme/test_spread_grouping.py
"""
from datetime import datetime, timezone

import portfolio_state as ps
from portfolio_state import (
    OpenPosition, PortfolioState,
    project_spread_exposure, check_spread_currency_exposure_cap,
    check_spread_position_cap, group_positions_by_idea,
)


def mk_state(balance=4000.0, positions=None, exposure=None):
    return PortfolioState(
        timestamp=datetime.now(tz=timezone.utc), balance=balance,
        open_positions=positions or [], net_exposure_by_currency=exposure or {},
        clusters=[], mode_overlaps=[], risk_deployed_pct=0.0,
        risk_cap_pct=0.06, risk_headroom_pct=0.06, remaining_trade_capacity=3,
    )


def mk_pos(trade_id, instrument, units, strategy):
    return OpenPosition(trade_id=trade_id, instrument=instrument,
                        direction="long" if units > 0 else "short", units=units,
                        entry_price=1.0, unrealized_pnl=0.0, strategy=strategy,
                        open_time=None)


# Long the NZD_USD/USD_CAD spread: buy 10,000 NZD_USD, sell 13,500 USD_CAD.
LEGS = [("NZD_USD", 10_000), ("USD_CAD", -13_500)]


def test_no_double_count_shared_currency():
    proj = project_spread_exposure(mk_state(), LEGS)
    # NZD_USD long: NZD +10,000, USD -10,000. USD_CAD short: USD -13,500,
    # CAD +13,500. Shared USD must net ONCE: -10,000 + (-13,500) = -23,500.
    assert proj["USD"] == -23_500, proj
    print(f"PASS: shared USD nets exactly once across legs ({proj['USD']:+,})")


def test_no_under_count_gross_legs():
    proj = project_spread_exposure(mk_state(), LEGS)
    # The gross legs must be FULLY present -- a naive "net spread exposure"
    # shortcut that nets the whole idea toward zero would under-count both.
    assert proj["NZD"] == 10_000 and proj["CAD"] == 13_500, proj
    print(f"PASS: gross legs fully counted (NZD {proj['NZD']:+,}, CAD {proj['CAD']:+,})")


def test_atomic_cap_rejects_whole_idea():
    # convert_to_usd stubbed 1:1 so the numbers are deterministic.
    orig = ps.convert_to_usd
    ps.convert_to_usd = lambda amount, ccy: float(amount)
    try:
        # Cap = 12.0 x balance; balance $1,000 -> $12,000 cap. Combined USD
        # exposure -23,500 breaches; each leg alone (10k / 13.5k... 13.5k
        # breaches too, but 10k does NOT) -- the joint check must reject the
        # WHOLE idea even though leg 1 alone would have passed.
        state = mk_state(balance=1_000.0)
        ok_leg1, _ = ps.check_currency_exposure_cap(state, "NZD_USD", 10_000)
        assert ok_leg1, "leg 1 alone passes the single-instrument gate"
        ok, reason = check_spread_currency_exposure_cap(state, LEGS)
        assert not ok and "USD" in reason, (ok, reason)
        print("PASS: joint projection rejects the whole idea where leg-1-alone would have passed "
              "(the half-filled-spread hazard the atomic design forbids)")
    finally:
        ps.convert_to_usd = orig


def test_collision_check_rejects_either_leg():
    state = mk_state(positions=[mk_pos("41", "USD_CAD", 8_000, "donchian_plugin_intraday")])
    ok, reason = check_spread_position_cap(state, LEGS)
    assert not ok and "USD_CAD" in reason
    ok2, _ = check_spread_position_cap(mk_state(), LEGS)
    assert ok2
    print("PASS: a collision on EITHER leg rejects the whole idea; clean instruments pass")


def test_idea_grouping_counts_one_risk_unit():
    positions = [
        mk_pos("101", "NZD_USD", 10_000, "spread:idea-7"),
        mk_pos("102", "USD_CAD", -13_500, "spread:idea-7"),
        mk_pos("46", "GBP_USD", 5_000, "donchian_plugin_intraday"),
    ]
    groups = group_positions_by_idea(positions)
    assert len(groups) == 2, groups.keys()
    assert len(groups["spread:idea-7"]) == 2
    print(f"PASS: 3 open positions group into {len(groups)} risk units -- the spread's two legs count once")


if __name__ == "__main__":
    test_no_double_count_shared_currency()
    test_no_under_count_gross_legs()
    test_atomic_cap_rejects_whole_idea()
    test_collision_check_rejects_either_leg()
    test_idea_grouping_counts_one_risk_unit()
    print("\nALL 5 TESTS PASSED")
