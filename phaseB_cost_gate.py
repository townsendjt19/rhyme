"""
Phase B cost gate — FTMO US (.sim) real-spread re-adjudication.

Spec pre-registered in RESEARCH_LOG.md (2026-07-09) BEFORE this script was
written. Self-contained Phase B fetches (the MetaTrader5 module holds one
terminal per process, so this script owns the OANDA-terminal connection;
Phase A stays in mt5_client.py). Source tag: ftmo_us_sim.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/phaseB_cost_gate.py
"""
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

from data import fetch_candles as oanda_fetch

HERE = Path(__file__).parent
TERMINAL = r"C:\Program Files\OANDA MetaTrader 5\terminal64.exe"
SOURCE_TAG = "ftmo_us_sim"

# Registered XAUUSD conventions (Gate-2): pip 0.01, pip-value $0.10/lot/pip
XAU_PIP = 0.01
XAU_PV = 0.10
ASSUMED_SPREAD_PIPS = 37.0
XAU_POINT = 0.001  # .sim spread column is in points of this size

CLOCK_MONTHS = [
    ("winter", datetime(2026, 1, 5), datetime(2026, 1, 31)),
    ("summer", datetime(2025, 7, 7), datetime(2025, 8, 2)),
]
MIN_CLOCK_CORR = 0.999
COST_RATIO_LIMIT = 0.25  # Gate-1 threshold, applied to US500 with real data


def fetch(symbol, start, end):
    """M30 bars in SERVER time (naive), with spread column, source-tagged."""
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"symbol_select {symbol}: {mt5.last_error()}")
    r = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M30, start, end)
    if r is None or not len(r):
        raise RuntimeError(f"copy_rates_range {symbol}: {mt5.last_error()}")
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df["source"] = SOURCE_TAG
    return df.set_index("time").sort_index()


def clock_offsets():
    out = {}
    for label, start, end in CLOCK_MONTHS:
        month = {}
        for sym, inst in {"EURUSD.sim": "EUR_USD", "USDJPY.sim": "USD_JPY"}.items():
            mdf = fetch(sym, start, end)
            odf = oanda_fetch(inst, "M30", from_time=start.replace(tzinfo=timezone.utc),
                              to_time=end.replace(tzinfo=timezone.utc))
            oser = odf["close"]
            if oser.index.tz is not None:
                oser.index = oser.index.tz_convert("UTC").tz_localize(None)
            best = (None, -1.0)
            for off in (0, 1, 2, 3):
                mser = mdf["close"].copy()
                mser.index = mser.index - pd.Timedelta(hours=off)
                j = pd.concat([mser.rename("m"), oser.rename("o")], axis=1, join="inner")
                if len(j) < 100:
                    continue
                c = j["m"].corr(j["o"])
                if c > best[1]:
                    best = (off, c)
            month[sym] = best
        offs = {v[0] for v in month.values()}
        out[label] = {"offset": offs.pop() if len(offs) == 1 else None,
                      "min_corr": min(v[1] for v in month.values()), "detail": month}
    return out


def eu_dst_offset(ts_utc, winter_off, summer_off):
    """European DST: last Sunday of March 01:00 UTC -> last Sunday of October 01:00 UTC."""
    y = ts_utc.year
    def last_sunday(month):
        d = pd.Timestamp(y, month, 31)
        while d.month != month:
            d -= pd.Timedelta(days=1)
        return d - pd.Timedelta(days=d.dayofweek + 1) if d.dayofweek != 6 else d
    start = last_sunday(3).replace(hour=1)
    end = last_sunday(10).replace(hour=1)
    return summer_off if start <= ts_utc < end else winter_off


def main():
    if not mt5.initialize(path=TERMINAL, timeout=90000):
        raise RuntimeError(f"attach failed: {mt5.last_error()}")
    a = mt5.account_info()
    assert a.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO, "not a demo account -- abort"
    print(f"Connected: {a.login} @ {a.server} ({a.company}), demo, ${a.balance:,.0f}")

    print("\n== [1] Clock check ==")
    clocks = clock_offsets()
    for label, r in clocks.items():
        print(f"  {label}: offset=+{r['offset']}h min_corr={r['min_corr']:.6f} {r['detail']}")
        if r["offset"] is None or r["min_corr"] < MIN_CLOCK_CORR:
            print("SOURCE-LEVEL FAIL -- aborting per registration.")
            return
    w_off, s_off = clocks["winter"]["offset"], clocks["summer"]["offset"]

    print("\n== [2] XAUUSD re-adjudication ==")
    xau = fetch("XAUUSD.sim", datetime(2022, 4, 1), datetime(2026, 7, 2))
    spread_pips = xau["spread"] * XAU_POINT / XAU_PIP  # points -> pips
    hour_median = spread_pips.groupby(xau.index.hour).median()

    tr = pd.read_csv(HERE / "gate2_XAUUSD_trend_origin_pullback_full.csv", parse_dates=["time"])
    fallback = 0
    real_pips = []
    for t in tr.itertuples():
        ts = t.time.tz_convert("UTC").tz_localize(None) if t.time.tzinfo else t.time
        server_ts = ts + pd.Timedelta(hours=eu_dst_offset(ts, w_off, s_off))
        if server_ts in spread_pips.index:
            real_pips.append(spread_pips.loc[server_ts])
        else:
            real_pips.append(hour_median[server_ts.hour])
            fallback += 1
    tr["real_spread_pips"] = real_pips
    # harness cost formula: spread_pips * units * pv / 100_000
    tr["cost_assumed"] = ASSUMED_SPREAD_PIPS * tr["units"] * XAU_PV / 100_000
    tr["cost_real"] = tr["real_spread_pips"] * tr["units"] * XAU_PV / 100_000
    tr["pnl_real"] = tr["pnl"] + tr["cost_assumed"] - tr["cost_real"]

    net_old, net_new = tr["pnl"].sum(), tr["pnl_real"].sum()
    med, p90 = tr["real_spread_pips"].median(), tr["real_spread_pips"].quantile(0.9)
    tr.to_csv(HERE / "phaseB_xau_cost_readjudication.csv", index=False)
    print(f"  trades={len(tr)}  fallback-priced={fallback}")
    print(f"  real spread at entries: median={med:.1f} pips, p90={p90:.1f} pips (assumed {ASSUMED_SPREAD_PIPS})")
    print(f"  net: assumed=${net_old:,.2f} -> real=${net_new:,.2f}")
    print(f"  VERDICT: {'PASS STANDS' if net_new > 0 else 'KILLED (spread-eaten)'}")

    print("\n== [3] US500 final cost screen ==")
    us = fetch("US500.sim", datetime(2022, 4, 1), datetime(2026, 7, 2))
    med_spread_price = (us["spread"] * 0.1).median()   # US500 point = 0.1
    med_range = (us["high"] - us["low"]).median()
    ratio = med_spread_price / med_range
    print(f"  median spread={med_spread_price:.2f} vs median M30 range={med_range:.2f} "
          f"-> {ratio:.1%} of range; limit {COST_RATIO_LIMIT:.0%}")
    print(f"  VERDICT: {'UNPARKED (Gate-2 eligible)' if ratio < COST_RATIO_LIMIT else 'EXCLUDE FINAL'}")

    mt5.shutdown()


if __name__ == "__main__":
    main()
