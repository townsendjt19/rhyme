"""
Capture-engineering k-cap study (registration 601591c, committed before
results). Greedy chronological replay allowing up to k concurrent positions
per slot at risk/k each (worst-case slot exposure constant). Reports per-
record capture and the book's pessimistic-bound prop-sim as a function of k.

Run:  venv/Scripts/python.exe kcap_study.py
"""
import pandas as pd

import book_prop_sim as bps

RECORDS = {
    "jpy": "backtests/corrected_f86d9f4_pullback30_2021-2026ytd.csv",
    "spx": "gate2_SPX_trend_origin_pullback_full.csv",
    "ospx": "orb_SPX_close_full.csv",
    "oxau": "orb_XAUUSD_close_full.csv",
    "tl": "trendline_USD_JPY_full.csv",
    "xau": "gate2_XAUUSD_trend_origin_pullback_full.csv",   # data-collection-only, informational
}
UNAFFECTED = {"vxau": ("volcomp_XAUUSD_full.csv", 0.005),
              "gap": ("c6_wkndgap_EUR_USD.csv", 0.005)}


def kcap(path: str, k: int) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["time", "exit_time"]).sort_values("time")
    t = pd.DatetimeIndex(df["time"])
    x = pd.DatetimeIndex(df["exit_time"])
    if t.tz is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    if x.tz is not None:
        x = x.tz_convert("UTC").tz_localize(None)
    df = df.assign(_t=t, _x=x)
    kept, open_exits = [], []
    for _, r in df.iterrows():
        open_exits = [e for e in open_exits if e > r["_t"]]
        if len(open_exits) < k:
            kept.append(r)
            open_exits.append(r["_x"])
    return pd.DataFrame(kept).drop(columns=["_t", "_x"])


def main() -> None:
    print("=== per-record capture (net in $80-risk units; live risk scales 1/k) ===")
    print(f"{'slot':6s}" + "".join(f"{'k='+str(k):>18s}" for k in (1, 2, 3)) + f"{'record':>18s}")
    kcsv = {}
    for slot, path in RECORDS.items():
        row = f"{slot:6s}"
        full = pd.read_csv(path)["pnl"].sum()
        for k in (1, 2, 3):
            kdf = kcap(path, k)
            out = path.replace(".csv", f"_k{k}cap.csv") if k > 1 else path.replace(".csv", "_1cap.csv")
            kdf.to_csv(out, index=False)
            kcsv[(slot, k)] = out
            # risk-adjusted capture: net at constant slot exposure = sum(pnl)/k
            row += f"{kdf['pnl'].sum()/k:>10.0f} ({100*kdf['pnl'].sum()/k/full:3.0f}%)"
        print(row + f"{full:>14.0f}")

    print("\n=== pessimistic-bound prop-sim vs k (xau data-only excluded; slot risk 0.005/k) ===")
    for k in (1, 2, 3):
        streams = dict(UNAFFECTED)
        for slot in ("jpy", "spx", "ospx", "oxau", "tl"):
            streams[slot] = (kcsv[(slot, k)], 0.005 / k)
        bps.STREAMS = streams
        risk = {s: r for s, (_p, r) in streams.items()}
        bank = bps.load_streams(0.0)
        ch = bps.run_paths(bank, 0.10, 90, risk)
        tr = bps.run_paths(bank, 0.05, 13, risk)
        print(f"k={k}: challenge P={ch['P_target']:.3f} breach={ch['P_breach']:.3f} "
              f"timeout={ch['P_timeout']:.3f} | trial13 P={tr['P_target']:.3f}")


if __name__ == "__main__":
    main()
