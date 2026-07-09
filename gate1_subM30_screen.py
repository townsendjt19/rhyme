"""
Track 5 phase 2, Phase 0 -- sub-M30 cost/data screen (registered 2026-07-09,
committed before results). Real .sim spreads vs candle range at M15/M5.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/gate1_subM30_screen.py
"""
from datetime import datetime
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

TERMINAL = r"C:\Program Files\OANDA MetaTrader 5\terminal64.exe"
SYMBOLS = ["XAUUSD.sim", "US500.sim", "US100.sim", "US30.sim",
           "BTCUSD.sim", "USOIL.sim", "EURUSD.sim", "USDJPY.sim"]
TFS = {"M15": mt5.TIMEFRAME_M15, "M5": mt5.TIMEFRAME_M5}
COST_LIMIT = 0.25
DEFICIENT_FRAC_V2 = 0.60
MAX_DEFICIENT_SHARE = 0.05


def fetch(symbol, tf):
    mt5.symbol_select(symbol, True)
    for count in (200_000, 100_000, 50_000, 20_000):
        r = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if r is not None and len(r):
            break
    if r is None or not len(r):
        raise RuntimeError(f"no data {symbol}: {mt5.last_error()}")
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.set_index("time").sort_index()


def deficient_share(df):
    iso = df.index.isocalendar()
    key = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    weeks = df.groupby(key.values).size()
    first = df.groupby(key.values).apply(lambda g: g.index.min()).sort_values()
    weeks = weeks.reindex(first.index).iloc[1:-1]
    if not len(weeks):
        return float("nan")
    modal = int(weeks.mode().iloc[0])
    return float((weeks < DEFICIENT_FRAC_V2 * modal).mean())


def main():
    if not mt5.initialize(path=TERMINAL, timeout=90_000):
        raise RuntimeError(mt5.last_error())
    print(f"{'symbol':<12}{'tf':<5}{'depth':<8}{'deficient':<11}{'spread%range':<14}verdict")
    for sym in SYMBOLS:
        info = mt5.symbol_info(sym)
        for tfname, tf in TFS.items():
            try:
                df = fetch(sym, tf)
            except RuntimeError as e:
                print(f"{sym:<12}{tfname:<5}NO DATA ({e})")
                continue
            years = (df.index.max() - df.index.min()).days / 365.25
            dshare = deficient_share(df)
            nz = df.loc[df["spread"] > 0, "spread"]
            spread_price = float(nz.median()) * info.point if len(nz) else float("nan")
            med_range = float((df["high"] - df["low"]).median())
            ratio = spread_price / med_range
            if ratio >= COST_LIMIT:
                v = "EXCLUDE_cost"
            elif dshare > MAX_DEFICIENT_SHARE:
                v = "EXCLUDE_quality"
            elif years < 3.0:
                v = f"PASS_short_window({years:.1f}y)"
            else:
                v = "PASS"
            print(f"{sym:<12}{tfname:<5}{years:>5.1f}y  {dshare:>8.1%}  {100*ratio:>10.2f}%   {v}")
    mt5.shutdown()


if __name__ == "__main__":
    main()
