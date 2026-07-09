"""
Track 5 line 1 continuation -- Gate 2 on the .sim-only symbols (USOIL, BTCUSD).

Registered 2026-07-09 (committed before results). Same protocol as
gate2_killtest.py; the only new machinery is the .sim fetch seam: frames
from the FTMO/OANDA terminal converted to UTC via the measured piecewise
clock (winter +2h / summer +3h, European DST boundaries).

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/gate2sim_killtest.py [full] [SYMBOLS...]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

import backtest
import risk

HERE = Path(__file__).parent
TERMINAL = r"C:\Program Files\OANDA MetaTrader 5\terminal64.exe"

SYMBOLS = {
    "USOIL.sim":  {"pip_size": 0.01, "pip_value": 0.10, "spread_pips": 3.0},
    "BTCUSD.sim": {"pip_size": 1.00, "pip_value": 0.10, "spread_pips": 2.0},
}
PLUGINS = ["donchian_plugin.py", "trend_origin_pullback_plugin.py"]

START = datetime(2023, 1, 1, tzinfo=timezone.utc)
END = datetime(2024, 1, 1, tzinfo=timezone.utc)
FULL_WINDOWS = {
    "USOIL.sim":  (datetime(2022, 7, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc)),
    "BTCUSD.sim": (datetime(2022, 10, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc)),
}
FIXED_RISK = 80.0
WINTER_OFF, SUMMER_OFF = 2, 3   # measured (Phase B cost gate, 2026-07-09)


def _offset_hours(ts: pd.Timestamp) -> int:
    """European DST on an approximately-UTC timestamp (server-2h)."""
    y = ts.year
    def last_sunday(month):
        d = pd.Timestamp(y, month, 31)
        while d.month != month:
            d -= pd.Timedelta(days=1)
        return d if d.dayofweek == 6 else d - pd.Timedelta(days=d.dayofweek + 1)
    approx_utc = ts - pd.Timedelta(hours=WINTER_OFF)
    if last_sunday(3).replace(hour=1) <= approx_utc < last_sunday(10).replace(hour=1):
        return SUMMER_OFF
    return WINTER_OFF


def sim_fetch_candles(instrument, granularity, count=500, from_time=None, to_time=None):
    """Drop-in for data.fetch_candles serving .sim data in UTC."""
    tf = {"H4": mt5.TIMEFRAME_H4, "M30": mt5.TIMEFRAME_M30}[granularity]
    if not mt5.symbol_select(instrument, True):
        raise RuntimeError(f"symbol_select {instrument}: {mt5.last_error()}")
    # Request in server time with a generous pad; trim after conversion.
    r = mt5.copy_rates_range(instrument, tf,
                             (from_time + pd.Timedelta(hours=4)).replace(tzinfo=None) - pd.Timedelta(hours=8),
                             (to_time + pd.Timedelta(hours=4)).replace(tzinfo=None))
    if r is None or not len(r):
        for cnt in (100_000, 50_000, 20_000):
            r = mt5.copy_rates_from_pos(instrument, tf, 0, cnt)
            if r is not None and len(r):
                break
    if r is None or not len(r):
        raise RuntimeError(f"no data {instrument}: {mt5.last_error()}")
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    df = df[["time", "open", "high", "low", "close", "volume"]].set_index("time").sort_index()
    offs = df.index.to_series().apply(_offset_hours)
    df.index = pd.DatetimeIndex(df.index - pd.to_timedelta(offs.values, unit="h")).tz_localize("UTC")
    return df[(df.index >= from_time) & (df.index <= to_time)]


def main():
    if not mt5.initialize(path=TERMINAL, timeout=90_000):
        raise RuntimeError(f"attach failed: {mt5.last_error()}")
    a = mt5.account_info()
    assert a.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO

    backtest.TF_MAP.setdefault("scalp30", ("H4", "M30"))
    backtest.fetch_candles = sim_fetch_candles
    for sym, conv in SYMBOLS.items():
        risk._PIP_SIZE[sym] = conv["pip_size"]
        risk._PIP_VALUE_USD[sym] = conv["pip_value"]

    full = len(sys.argv) > 1 and sys.argv[1] == "full"
    syms = sys.argv[2:] if full else sys.argv[1:]
    only = set(syms) or None

    for sym, conv in SYMBOLS.items():
        if only and sym not in only:
            continue
        for plug in PLUGINS:
            plugin_fn = backtest._load_plugin(str(HERE / plug))
            start, end = FULL_WINDOWS[sym] if full else (START, END)
            name = f"gate2sim_{sym.replace('.sim','')}_{plug.replace('_plugin.py', '')}_{'full' if full else '2023'}"
            print(f"\n########## {name} ##########")
            tr = backtest.run_backtest(
                instrument=sym, mode="scalp30", start=start, end=end,
                signal_plugin=plugin_fn, fixed_risk=FIXED_RISK,
                spread_pips=conv["spread_pips"], strategy_name=name,
            )
            tr.to_csv(HERE / f"{name}.csv", index=False)
            n = len(tr)
            net = tr["pnl"].sum() if n else 0.0
            exp = net / n if n else float("nan")
            med_stop = (tr["entry"] - tr["sl"]).abs().median() / conv["pip_size"] if n else float("nan")
            floor = 10 * conv["spread_pips"]
            verdict = "KILL" if n < 20 or exp < 0 or med_stop < floor else "CLEAR"
            print(f"  n={n}  net=${net:.2f}  expectancy=${exp:.2f}/trade  "
                  f"median_stop={med_stop:.0f} pips (floor {floor:.0f})  -> {verdict}")

    mt5.shutdown()


if __name__ == "__main__":
    main()
