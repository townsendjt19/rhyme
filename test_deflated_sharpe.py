"""
Tests for deflated_sharpe.py -- DSR sanity properties on synthetic series.

Run: D:/workspace/rhyme/venv/Scripts/python.exe test_deflated_sharpe.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import deflated_sharpe as ds


def _series(mean: float, std: float, t: int, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mean, std, t))


def test_dsr_monotone_decreasing_in_n() -> None:
    s = _series(0.002, 0.01, 260)   # healthy weekly edge
    dsrs = [ds.deflated_sharpe(s, n)["dsr"] for n in (1, 5, 25, 100, 500)]
    assert all(a >= b for a, b in zip(dsrs, dsrs[1:])), f"DSR not monotone in N: {dsrs}"
    print(f"PASS: DSR monotone decreasing in N ({['%.3f' % d for d in dsrs]})")


def test_n1_matches_plain_sharpe_pvalue() -> None:
    # At N=1, SR0=0 and DSR reduces to the (skew/kurt-adjusted) p-value of
    # SR itself -- a strongly positive series must sit near 1.0.
    s = _series(0.005, 0.01, 260)
    d = ds.deflated_sharpe(s, 1)
    assert d["sr0_wk"] == 0.0
    assert d["dsr"] > 0.99, f"strong edge at N=1 should have DSR~1, got {d['dsr']}"
    print(f"PASS: N=1 sanity (SR0=0, DSR={d['dsr']:.4f})")


def test_zero_edge_low_dsr_at_large_n() -> None:
    s = _series(0.0, 0.01, 260)
    d = ds.deflated_sharpe(s, 100)
    assert d["dsr"] < 0.5, f"no-edge series at N=100 must have low DSR, got {d['dsr']}"
    print(f"PASS: skill-less series deflates to DSR={d['dsr']:.3f} at N=100")


def test_zero_variance_no_crash() -> None:
    s = pd.Series([0.0] * 50)
    d = ds.deflated_sharpe(s, 66)
    assert d["dsr"] != d["dsr"] or d["dsr"] is not None   # NaN acceptable, no crash
    print("PASS: zero-variance series does not crash")


def test_expected_max_sharpe_grows_with_n() -> None:
    vals = [ds.expected_max_sharpe(n, 260) for n in (2, 10, 66, 500)]
    assert all(b > a for a, b in zip(vals, vals[1:])), vals
    assert ds.expected_max_sharpe(1, 260) == 0.0
    print(f"PASS: E[max SR] grows with N ({['%.4f' % v for v in vals]})")


def test_live_table_runs() -> None:
    # End-to-end over the real roster CSVs + failure_db (read-only).
    n, derivation = ds.n_trials()
    assert n >= 60, f"expected >=60 trials (59 kills + roster), got {n}"
    t = ds.table()
    assert len(t) == len(ds.ROSTER)
    assert t["dsr"].notna().all(), f"NaN DSRs in live table:\n{t}"
    print(f"PASS: live table computes for all {len(t)} roster strategies ({derivation})")


if __name__ == "__main__":
    test_dsr_monotone_decreasing_in_n()
    test_n1_matches_plain_sharpe_pvalue()
    test_zero_edge_low_dsr_at_large_n()
    test_zero_variance_no_crash()
    test_expected_max_sharpe_grows_with_n()
    test_live_table_runs()
    print("ALL PASS: test_deflated_sharpe.py")
