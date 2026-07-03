"""
Unit tests: atomic two-leg execution failure modes (spec §1/§1a).

Covers the paths the deployment handoff scoped: leg-2 failure -> unwind;
unwind failure -> NAKED_LEG + suspend signal; leg-1 no-fill -> clean abort;
startup orphan reconciliation; §1a staleness skip semantics (via live_z).

Run: D:/rhyme/venv/Scripts/python.exe D:/rhyme/test_spread_execution.py
"""
import numpy as np

import spread_execution as sx
from spread_execution import SpreadLeg, execute_spread_idea, reconcile_orphans

sx.UNWIND_BACKOFF_S = 0.0   # no sleeping in tests

LEG1 = SpreadLeg("NZD_USD", 10_000, 0.5500)
LEG2 = SpreadLeg("USD_CAD", -13_500, 1.4200)


class FakeOps:
    def __init__(self, fills=None, close_ok=True, open_trades=None):
        self.fills = fills or {}          # instrument -> trade_id | None
        self.close_ok = close_ok
        self.open_trades = open_trades or []
        self.placed, self.closed = [], []

    def place_fok(self, instrument, units, sl_price, tag):
        self.placed.append((instrument, units, sl_price, tag))
        return self.fills.get(instrument)

    def close_trade(self, trade_id):
        self.closed.append(trade_id)
        return self.close_ok

    def list_open_spread_trades(self):
        return self.open_trades


def test_happy_path_both_fill():
    ops = FakeOps(fills={"NZD_USD": "t1", "USD_CAD": "t2"})
    r = execute_spread_idea("idea-1", LEG1, LEG2, ops)
    assert r["status"] == "open" and r["legs"] == {"NZD_USD": "t1", "USD_CAD": "t2"}
    assert all(p[3] == "spread:idea-1" for p in ops.placed), "both legs must carry the idea tag"
    assert ops.placed[0][0] == "NZD_USD", "less-liquid leg must go first"
    print("PASS: happy path -- both legs fill, tagged, leg order respected")


def test_leg1_nofill_clean_abort():
    ops = FakeOps(fills={"NZD_USD": None})
    r = execute_spread_idea("idea-2", LEG1, LEG2, ops)
    assert r["status"] == "aborted_leg1" and not r["legs"]
    assert len(ops.placed) == 1 and not ops.closed, "leg 2 must never be attempted; nothing to unwind"
    print("PASS: leg-1 FOK no-fill aborts cleanly -- nothing open, nothing unwound")


def test_leg2_failure_unwinds_leg1():
    ops = FakeOps(fills={"NZD_USD": "t1", "USD_CAD": None})
    r = execute_spread_idea("idea-3", LEG1, LEG2, ops)
    assert r["status"] == "aborted_unwound"
    assert ops.closed == ["t1"], "leg 1 must be market-unwound exactly once on first success"
    assert any("unwinding leg1" in i for i in r["incidents"])
    print("PASS: leg-2 failure -> immediate leg-1 unwind, incident recorded")


def test_unwind_failure_is_naked_leg_suspend():
    ops = FakeOps(fills={"NZD_USD": "t1", "USD_CAD": None}, close_ok=False)
    r = execute_spread_idea("idea-4", LEG1, LEG2, ops)
    assert r["status"] == "NAKED_LEG" and r["naked_trade_id"] == "t1"
    assert len(ops.closed) == sx.UNWIND_RETRIES, "must retry the unwind the specified number of times"
    assert any("must suspend" in i for i in r["incidents"])
    print("PASS: unwind failure x3 -> NAKED_LEG status carries the suspend signal and the bounded trade id")


def test_orphan_reconciliation():
    ops = FakeOps(open_trades=[
        {"trade_id": "t9", "instrument": "NZD_USD", "tag": "spread:idea-9"},           # orphan
        {"trade_id": "t7a", "instrument": "NZD_USD", "tag": "spread:idea-7"},          # intact pair
        {"trade_id": "t7b", "instrument": "USD_CAD", "tag": "spread:idea-7"},
    ])
    incidents = reconcile_orphans(ops)
    assert ops.closed == ["t9"], "only the orphan gets unwound; the intact idea is untouched"
    assert any("orphaned spread leg" in i for i in incidents)
    print("PASS: startup reconciliation unwinds the orphan and leaves the intact idea alone")


def test_staleness_live_z_semantics():
    from spread_signal import live_z, Z_ENTRY
    sig = {"alpha_spread_last": 0.02, "mu": 0.0, "sigma": 0.01, "beta": 1.35,
           "y_close": 0.5500, "x_close": 1.4200}
    # unchanged mids -> z unchanged (2.0, exactly at threshold -> proceeds)
    z_same = live_z(sig, 0.5500, 1.4200)
    assert abs(z_same - 2.0) < 1e-9
    # y rallies back toward the mean -> z decays below entry -> §1a skips
    z_decayed = live_z(sig, 0.5500 * np.exp(-0.006), 1.4200)
    assert z_decayed < Z_ENTRY, z_decayed
    print(f"PASS: §1a staleness -- unchanged mids keep z at {z_same:.2f}; a reversion move decays it to "
          f"{z_decayed:.2f} < {Z_ENTRY} and the entry skips")


if __name__ == "__main__":
    test_happy_path_both_fill()
    test_leg1_nofill_clean_abort()
    test_leg2_failure_unwinds_leg1()
    test_unwind_failure_is_naked_leg_suspend()
    test_orphan_reconciliation()
    test_staleness_live_z_semantics()
    print("\nALL 6 TESTS PASSED")
