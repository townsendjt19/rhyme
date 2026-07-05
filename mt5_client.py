"""
MetaTrader 5 data client — Phase A (generic demo) data source for the
prop-firm multi-asset expansion. Kept fully separate from the OANDA
pipeline in data.py: different connection model (running terminal process
vs REST), different account, different fidelity guarantees.

Fidelity contract (Phase A):
  - Price/OHLC data: usable for Gate 0 (inventory) and Gate 1 (cheap
    mechanism checks).
  - Spread/cost data: NOT trustworthy. Gate-3 tradeability checks must
    wait for Phase B (broker-matched demo behind the target prop firm's
    challenge platform). Every DataFrame is tagged with a `source` column
    so Phase A and Phase B data can never be silently mixed.

Timezone caveat: MT5 bar timestamps are BROKER-SERVER time (typically
UTC+2/+3 with DST), not UTC like the OANDA pipeline. Anything
date/session-sensitive downstream must account for this — same class of
hazard the liquidity-trough line's Gate 2 exists to catch.

Terminal: portable instance at MT5_TERMINAL_PATH (see .env), which
auto-logs into the demo account saved in its own Config — no password is
stored in .env because the terminal holds the session credentials itself.
"""
import os
from datetime import datetime
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

TERMINAL_PATH = os.getenv("MT5_TERMINAL_PATH", r"D:\mt5_phaseA\terminal64.exe")

SOURCE_TAG = "mt5_potrade_demo"  # Phase A generic demo — not MetaQuotes-Demo,
                                 # see report; still generic-LP demo fidelity

_TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "D": mt5.TIMEFRAME_D1, "W": mt5.TIMEFRAME_W1, "M": mt5.TIMEFRAME_MN1,
}

_connected = False


def connect() -> None:
    """Initialize the MT5 terminal connection. Hard-fails unless the logged-in
    account is a DEMO account (mirrors the abort-on-non-practice pattern in
    inventory_instruments.py)."""
    global _connected
    if _connected:
        return
    if not mt5.initialize(path=TERMINAL_PATH, portable=True, timeout=90000):
        raise RuntimeError(
            f"MT5 initialize failed: {mt5.last_error()} — is the terminal at "
            f"{TERMINAL_PATH} present, and does its saved account still log in?"
        )
    account = mt5.account_info()
    if account is None:
        mt5.shutdown()
        raise RuntimeError(f"MT5 connected but no account logged in: {mt5.last_error()}")
    if account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        mt5.shutdown()
        raise RuntimeError(
            f"MT5 account {account.login} on {account.server} is not a DEMO "
            f"account (trade_mode={account.trade_mode}) — refusing to use it."
        )
    _connected = True


def disconnect() -> None:
    global _connected
    mt5.shutdown()
    _connected = False


def list_symbols() -> pd.DataFrame:
    """Full symbol list from the connected account, with the broker's own
    category path (e.g. 'Forex\\Majors\\EURUSD') — the primary classification
    signal MT5 exposes."""
    connect()
    rows = []
    for s in mt5.symbols_get():
        rows.append({
            "symbol": s.name,
            "description": s.description,
            "path": s.path,
            "currency_base": s.currency_base,
            "currency_profit": s.currency_profit,
            "digits": s.digits,
            "trade_mode": s.trade_mode,
        })
    return pd.DataFrame(rows)


def get_history(symbol: str, timeframe: str,
                start: datetime, end: datetime) -> pd.DataFrame:
    """OHLCV bars as a DataFrame matching data.py's shape (time index,
    open/high/low/close/volume) plus a `source` tag column.

    volume = MT5 tick_volume (real_volume is unpopulated on FX/CFD feeds).
    Timestamps are broker-server time — see module docstring.
    """
    connect()
    tf = _TIMEFRAMES.get(timeframe)
    if tf is None:
        raise ValueError(f"Unknown timeframe {timeframe!r}; use one of {list(_TIMEFRAMES)}")
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"symbol_select failed for {symbol}: {mt5.last_error()}")
    rates = mt5.copy_rates_range(symbol, tf, start, end)
    if rates is None:
        raise RuntimeError(f"copy_rates_range failed for {symbol}: {mt5.last_error()}")
    df = pd.DataFrame(rates)
    if df.empty:
        return df
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    df = df[["time", "open", "high", "low", "close", "volume"]]
    df["source"] = SOURCE_TAG
    df.set_index("time", inplace=True)
    df.sort_index(inplace=True)
    return df
