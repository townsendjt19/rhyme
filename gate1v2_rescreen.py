"""
Track 5 line 1 -- tradeable-universe data screen (registered 2026-07-09,
committed before results).

Gate-1 v2 completeness criterion: a week is deficient only below 60% of the
symbol's modal weekly bars (holiday-tolerant); deficient-week share limit
unchanged at 5%. Window >= 3.0y. Cost limit 25% of median M30 range.

Two sources, sequentially in one process:
  Phase A (potrade)  -- YM, XAGUSD re-screens (indicative cost, gate-1 convention)
  FTMO .sim (OANDA)  -- USOIL, BTCUSD first screens (REAL cost, 2026 populated bars)

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/gate1v2_rescreen.py
"""
from datetime import datetime
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

HERE = Path(__file__).parent
WINDOW_END = datetime(2026, 7, 1)
HISTORY_START = datetime(2018, 1, 1)
COST_START = datetime(2025, 7, 1)

MIN_YEARS = 3.0
DEFICIENT_FRAC_V2 = 0.60
MAX_DEFICIENT_SHARE = 0.05
COST_LIMIT = 0.25


def weekly_deficient_share(df):
    iso = df.index.isocalendar()
    key = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    weeks = df.groupby(key.values).size()
    first = df.groupby(key.values).apply(lambda g: g.index.min()).sort_values()
    weeks = weeks.reindex(first.index).iloc[1:-1]
    modal = int(weeks.mode().iloc[0])
    return float((weeks < DEFICIENT_FRAC_V2 * modal).mean()), modal


def fetch(symbol, start, end):
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"symbol_select {symbol}: {mt5.last_error()}")
    r = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M30, start, end)
    if r is None or not len(r):
        raise RuntimeError(f"no data {symbol}: {mt5.last_error()}")
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.set_index("time").sort_index()


def screen(symbol, cost_mode):
    df = fetch(symbol, HISTORY_START, WINDOW_END)
    years = (WINDOW_END - df.index.min().to_pydatetime()).days / 365.25
    deficient, modal = weekly_deficient_share(df)
    recent = df[df.index >= COST_START]
    med_range = float((recent["high"] - recent["low"]).median())
    info = mt5.symbol_info(symbol)
    if cost_mode == "real":
        nz = df.loc[df["spread"] > 0, "spread"]
        spread_price = float(nz.median()) * info.point if len(nz) else float("nan")
    else:
        spread_price = info.spread * info.point
    ratio = spread_price / med_range
    if years < MIN_YEARS:
        verdict = "EXCLUDE_window"
    elif deficient > MAX_DEFICIENT_SHARE:
        verdict = "EXCLUDE_quality_v2"
    elif ratio >= COST_LIMIT:
        verdict = "PROVISIONAL_EXCLUDE_cost" if cost_mode == "indicative" else "EXCLUDE_cost_FINAL"
    else:
        verdict = "PASS"
    print(f"  {symbol:<10} {years:>4.1f}y  deficient(v2)={deficient:.1%}  "
          f"spread={100*ratio:.2f}% of median range ({cost_mode})  -> {verdict}")


def main():
    print("== Phase A source (potrade) ==")
    if not mt5.initialize(path=r"D:\mt5_phaseA\terminal64.exe", portable=True, timeout=90000):
        raise RuntimeError(f"phase A attach: {mt5.last_error()}")
    for sym in ("YM", "XAGUSD"):
        screen(sym, "indicative")
    mt5.shutdown()

    print("== FTMO .sim source (OANDA terminal) ==")
    if not mt5.initialize(path=r"C:\Program Files\OANDA MetaTrader 5\terminal64.exe", timeout=90000):
        raise RuntimeError(f".sim attach: {mt5.last_error()}")
    for sym in ("USOIL.sim", "BTCUSD.sim"):
        screen(sym, "real")
    mt5.shutdown()


if __name__ == "__main__":
    main()
