"""
Unit tests for broker-increment rounding: results must land EXACTLY on the
step grid (no binary-float dust). Regression guard for the 2026-07-09
lot-step bug (floor(0.41666/0.01)*0.01 -> 0.41000000000000003), found in
the FTMO trial bot and latent in risk._round_lots.

Run: D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/test_rounding.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from risk import _round_lots


def test_dust_values_land_on_grid():
    cases = [
        (0.41666, 0.01, 0.41),   # the observed production value
        (0.57, 0.01, 0.57),      # 0.57/0.01 = 56.99999... without care
        (2.3, 0.1, 2.3),         # classic 0.1-step dust
        (0.29, 0.01, 0.29),
        (1.005, 0.01, 1.0),      # floors down, never up
    ]
    for raw, step, expected in cases:
        got = _round_lots(raw, step)
        assert got == expected, f"_round_lots({raw}, {step}) = {got!r}, expected {expected!r}"
    print("PASS: dust values land exactly on the step grid")


def test_never_rounds_up():
    for raw in (0.419999, 0.410001, 0.99999):
        got = _round_lots(raw, 0.01)
        assert got <= raw + 1e-12, (raw, got)
    print("PASS: rounding is floor-direction only (never sizes above intent)")


def test_zero_and_small():
    assert _round_lots(0.0) == 0.0
    assert _round_lots(0.009) == 0.0
    print("PASS: zero and sub-step inputs floor to 0.0")


if __name__ == "__main__":
    tests = [test_dust_values_land_on_grid, test_never_rounds_up, test_zero_and_small]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ERROR {t.__name__}: {e}")
            failed += 1
    print(f"\nResults: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
