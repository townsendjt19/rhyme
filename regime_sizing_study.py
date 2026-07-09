"""
Entry-time regime-sizing study (registered 2026-07-09, committed before
results). Reopen bar of the exit-rule giveback study: 0.5x risk on entries
taken when the instrument's own daily ER(20) < 0.20, completed days only.
See RESEARCH_LOG registration (commit ab18f69) for the gates.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/regime_sizing_study.py
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent

ER_N, ER_THRESHOLD, MULT_RANGING = 20, 0.20, 0.5   # standing convention; chosen not tuned
DESIGN_END = pd.Timestamp("2024-01-01", tz="UTC")   # design 2021-2023 / held-out 2024-2026
COMMON_START, COMMON_END = "2022-10-01", "2026-07-01"  # book_prop_sim stream window
PHASEA_UTC_OFFSET = timedelta(hours=2)              # Phase A terminal: fixed UTC+2

BOOK = {   # mirrors book_prop_sim.STREAMS
    "xau": "gate2_XAUUSD_trend_origin_pullback_full.csv",
    "jpy": "backtests/corrected_f86d9f4_pullback30_2021-2026ytd.csv",
    "spx": "gate2_SPX_trend_origin_pullback_full.csv",
    "ospx": "orb_SPX_close_full.csv",
    "oxau": "orb_XAUUSD_close_full.csv",
}
FLEET = {  # mechanism corroboration only, never deploy evidence
    "intraday": "backtests/corrected_f86d9f4_intraday_2021-2026ytd.csv",
    "scalp30": "backtests/corrected_f86d9f4_scalp30_2021-2026ytd.csv",
    "pullback30": "backtests/corrected_f86d9f4_pullback30_2021-2026ytd.csv",
}
MT5_INSTRUMENTS = {"XAUUSD", "SPX"}   # Phase A daily source; everything else OANDA

_daily_cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}


def daily_er_series(instrument: str) -> tuple[np.ndarray, np.ndarray]:
    """(completed_at_utc[int64 ns], er[float]) — er[i] is the trailing ER(20)
    known once bar i has completed (open + 24h). Insufficient history -> NaN."""
    if instrument in _daily_cache:
        return _daily_cache[instrument]
    if instrument in MT5_INSTRUMENTS:
        import mt5_client
        df = mt5_client.get_history(instrument, "D",
                                    datetime(2020, 6, 1), datetime(2026, 7, 10))
        opens_utc = df.index - PHASEA_UTC_OFFSET   # server(+2, naive) -> UTC
        opens_utc = pd.DatetimeIndex(opens_utc).tz_localize("UTC")
    else:
        import data
        df = data.fetch_candles(instrument, "D",
                                from_time=datetime(2020, 6, 1, tzinfo=timezone.utc),
                                to_time=datetime(2026, 7, 8, tzinfo=timezone.utc))
        opens_utc = pd.DatetimeIndex(df.index).tz_convert("UTC")
    c = df["close"].astype(float).reset_index(drop=True)
    change = c.diff(ER_N).abs()
    path = c.diff().abs().rolling(ER_N).sum()
    er = (change / path.where(path > 0)).values          # NaN until 20 diffs exist
    completed = (opens_utc + pd.Timedelta(hours=24)).asi8
    _daily_cache[instrument] = (completed, er)
    return _daily_cache[instrument]


def attach_regime(df: pd.DataFrame) -> pd.DataFrame:
    """Adds er / mult columns: last daily bar completed at or before entry."""
    ers = np.full(len(df), np.nan)
    entry_ns = pd.DatetimeIndex(df["time"]).tz_convert("UTC").asi8
    for instrument in df["instrument"].unique():
        completed, er = daily_er_series(instrument)
        mask = (df["instrument"] == instrument).values
        idx = np.searchsorted(completed, entry_ns[mask], side="right") - 1
        vals = np.where(idx >= 0, er[np.clip(idx, 0, None)], np.nan)
        ers[mask] = vals
    df = df.copy()
    df["er"] = ers
    # NaN (insufficient history) reads as trending -> gate closed -> 1.0x
    df["mult"] = np.where(df["er"] < ER_THRESHOLD, MULT_RANGING, 1.0)
    df["ranging"] = df["er"] < ER_THRESHOLD
    return df


def load(csv: str, clip_common: bool) -> pd.DataFrame:
    df = pd.read_csv(HERE / csv, parse_dates=["time", "exit_time"])
    for col in ("time", "exit_time"):
        t = pd.DatetimeIndex(df[col])
        df[col] = t.tz_convert("UTC") if t.tz is not None else t.tz_localize("UTC")
    if clip_common:
        df = df[(df["time"] >= pd.Timestamp(COMMON_START, tz="UTC"))
                & (df["time"] < pd.Timestamp(COMMON_END, tz="UTC"))]
    return attach_regime(df[["time", "exit_time", "instrument", "pnl"]].reset_index(drop=True))


def regime_table(name: str, df: pd.DataFrame) -> dict:
    out = {}
    for window, sub in (("design", df[df["time"] < DESIGN_END]),
                        ("heldout", df[df["time"] >= DESIGN_END])):
        row = {}
        for label, s in (("ranging", sub[sub["ranging"]]), ("trending", sub[~sub["ranging"]])):
            r = s["pnl"].values / 80.0
            row[label] = {"n": len(r), "meanR": float(np.mean(r)) if len(r) else None}
        out[window] = row
        print(f"  {name:12s} {window:7s} "
              f"ranging n={row['ranging']['n']:5d} meanR={row['ranging']['meanR'] if row['ranging']['meanR'] is not None else float('nan'): .4f}   "
              f"trending n={row['trending']['n']:5d} meanR={row['trending']['meanR'] if row['trending']['meanR'] is not None else float('nan'): .4f}")
    return out


def curve_stats(df: pd.DataFrame, sized: bool) -> dict:
    """Fixed-$80 book curve sorted by exit_time; return/maxDD."""
    d = df.sort_values("exit_time")
    pnl = d["pnl"].values * (d["mult"].values if sized else 1.0)
    eq = np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    maxdd = float(np.max(peak - eq)) if len(eq) else 0.0
    net = float(eq[-1]) if len(eq) else 0.0
    return {"net": net, "maxDD": maxdd, "ret_dd": net / maxdd if maxdd > 0 else None}


def main() -> None:
    print("=" * 78)
    print("ENTRY-TIME REGIME SIZING -- ER(20)<0.20 at entry -> 0.5x (registration ab18f69)")
    print("=" * 78)

    book = {slot: load(csv, clip_common=True) for slot, csv in BOOK.items()}
    fleet = {n: load(csv, clip_common=False) for n, csv in FLEET.items()}

    print("\n[1] PER-RECORD REGIME EXPECTANCY (meanR by entry-time regime)")
    print(" -- book streams (deploy evidence, prop-sim common window):")
    for slot, df in book.items():
        regime_table(slot, df)
    print(" -- fleet records (corroboration only):")
    for n, df in fleet.items():
        regime_table(n, df)

    book_all = pd.concat(book.values(), ignore_index=True)
    fleet_all = pd.concat(fleet.values(), ignore_index=True)
    print("\n[2] POOLED (GATE M, design window: ranging must be >=0.05R below trending)")
    bp = regime_table("BOOK pooled", book_all)
    fp = regime_table("FLEET pooled", fleet_all)
    bd = bp["design"]
    gap = (bd["trending"]["meanR"] - bd["ranging"]["meanR"]
           if None not in (bd["trending"]["meanR"], bd["ranging"]["meanR"]) else float("nan"))
    fleet_ok = (fp["design"]["ranging"]["meanR"] is not None
                and fp["design"]["trending"]["meanR"] is not None
                and fp["design"]["ranging"]["meanR"] < fp["design"]["trending"]["meanR"])
    gate_m = bool(gap >= 0.05 and fleet_ok)
    print(f"\n  GATE M: book design gap (trending-ranging) = {gap:+.4f}R (need >= +0.05), "
          f"fleet ordering ok = {fleet_ok}  ->  {'PASS' if gate_m else 'FAIL'}")

    print("\n[3] GATE H (held-out 2024-2026 book curve, fixed-$80, sorted by exit_time)")
    held = book_all[book_all["time"] >= DESIGN_END]
    base = curve_stats(held, sized=False)
    sized = curve_stats(held, sized=True)
    print(f"  baseline : net={base['net']:+10.2f}  maxDD={base['maxDD']:8.2f}  ret/DD={base['ret_dd']:.3f}")
    print(f"  sized    : net={sized['net']:+10.2f}  maxDD={sized['maxDD']:8.2f}  ret/DD={sized['ret_dd']:.3f}")
    improve = sized["ret_dd"] / base["ret_dd"] - 1 if base["ret_dd"] else float("nan")
    gate_h = bool(improve >= 0.10)
    print(f"  GATE H: ret/DD improvement = {improve:+.1%} (need >= +10%)  ->  {'PASS' if gate_h else 'FAIL'}")

    des = book_all[book_all["time"] < DESIGN_END]
    db, ds = curve_stats(des, sized=False), curve_stats(des, sized=True)
    print(f"  (design window, informational: baseline ret/DD={db['ret_dd']:.3f} sized={ds['ret_dd']:.3f})")

    for slot, df in book.items():
        df[["time", "instrument", "pnl", "er", "mult"]].to_csv(
            HERE / f"regimeflag_{slot}.csv", index=False)
    print(f"\nSidecars written: regimeflag_<slot>.csv x{len(book)}")
    print(f"\nVERDICT: Gate M {'PASS' if gate_m else 'FAIL'}, Gate H {'PASS' if gate_h else 'FAIL'}"
          f" -> {'proceed to prop-sim deploy check' if gate_m and gate_h else 'KILL (failure_db)'}")


if __name__ == "__main__":
    main()
