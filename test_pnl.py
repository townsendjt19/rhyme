"""
Unit tests for _simulate_trade PnL sign correctness.

Four cases tested:
  1. Long TP exit  → must be positive
  2. Long SL exit  → must be negative
  3. Short TP exit → must be positive
  4. Short SL exit → must be negative
"""
import sys
import pandas as pd
sys.path.insert(0, r"D:\forex_bot")
from backtest import _simulate_trade

INSTRUMENT = "GBP_USD"
UNITS      = 10_000


def _candles(high, low, close=None):
    """Build a single-row future DataFrame that hits the given high/low."""
    if close is None:
        close = (high + low) / 2
    return pd.DataFrame([{"high": high, "low": low, "close": close}])


def test_long_tp_positive():
    """Long trade: price rises to TP → profit."""
    entry = 1.25000
    sl    = 1.24500   # 50 pip stop below entry
    tp    = 1.25125   # 2.5R above entry

    future = _candles(high=tp + 0.0010, low=entry)   # high clears TP
    result = _simulate_trade("long", entry, sl, [tp, tp, tp], future, UNITS, INSTRUMENT)

    assert result["exit_reason"] == "tp_all", f"Expected tp_all, got {result['exit_reason']}"
    assert result["pnl"] > 0, f"FAIL: long TP exit produced PnL={result['pnl']:.4f}, expected positive"
    print(f"  PASS  long TP exit:  PnL = ${result['pnl']:+.4f}  (exit_reason={result['exit_reason']})")


def test_long_sl_negative():
    """Long trade: price drops to SL → loss."""
    entry = 1.25000
    sl    = 1.24500
    tp    = 1.25125

    future = _candles(high=entry, low=sl - 0.0010)   # low breaches SL
    result = _simulate_trade("long", entry, sl, [tp, tp, tp], future, UNITS, INSTRUMENT)

    assert result["exit_reason"] == "sl", f"Expected sl, got {result['exit_reason']}"
    assert result["pnl"] < 0, f"FAIL: long SL exit produced PnL={result['pnl']:.4f}, expected negative"
    print(f"  PASS  long SL exit:  PnL = ${result['pnl']:+.4f}  (exit_reason={result['exit_reason']})")


def test_short_tp_positive():
    """Short trade: price falls to TP → profit."""
    entry = 1.25000
    sl    = 1.25500   # 50 pip stop above entry
    tp    = 1.24875   # 2.5R below entry

    future = _candles(high=entry, low=tp - 0.0010)   # low clears TP
    result = _simulate_trade("short", entry, sl, [tp, tp, tp], future, UNITS, INSTRUMENT)

    assert result["exit_reason"] == "tp_all", f"Expected tp_all, got {result['exit_reason']}"
    assert result["pnl"] > 0, f"FAIL: short TP exit produced PnL={result['pnl']:.4f}, expected positive"
    print(f"  PASS  short TP exit: PnL = ${result['pnl']:+.4f}  (exit_reason={result['exit_reason']})")


def test_short_sl_negative():
    """Short trade: price rises to SL → loss."""
    entry = 1.25000
    sl    = 1.25500
    tp    = 1.24875

    future = _candles(high=sl + 0.0010, low=entry)   # high breaches SL
    result = _simulate_trade("short", entry, sl, [tp, tp, tp], future, UNITS, INSTRUMENT)

    assert result["exit_reason"] == "sl", f"Expected sl, got {result['exit_reason']}"
    assert result["pnl"] < 0, f"FAIL: short SL exit produced PnL={result['pnl']:.4f}, expected negative"
    print(f"  PASS  short SL exit: PnL = ${result['pnl']:+.4f}  (exit_reason={result['exit_reason']})")


if __name__ == "__main__":
    tests = [test_long_tp_positive, test_long_sl_negative, test_short_tp_positive, test_short_sl_negative]
    passed = 0
    failed = 0
    print("Running PnL sign tests...\n")
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {t.__name__}: {e}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
