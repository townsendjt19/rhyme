"""
Fetch OANDA candles for any pair/timeframe.
Returns a pandas DataFrame with columns: time, open, high, low, close, volume.
"""
import os
import time
import logging
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from oandapyV20 import API
from oandapyV20.endpoints.instruments import InstrumentsCandles

load_dotenv(Path(__file__).parent / ".env", override=True)

logger = logging.getLogger(__name__)

ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
ACCESS_TOKEN = os.getenv("OANDA_ACCESS_TOKEN", "")
ENVIRONMENT = os.getenv("OANDA_ENV", "practice")  # "practice" or "live" — default is practice/demo

# OANDA max candles per request
_MAX_COUNT = 4999

# Approximate candle duration in seconds per granularity (for chunking)
_GRAN_SECONDS: dict[str, int] = {
    "S5": 5, "S10": 10, "S15": 15, "S30": 30,
    "M1": 60, "M2": 120, "M4": 240, "M5": 300,
    "M10": 600, "M15": 900, "M30": 1800,
    "H1": 3600, "H2": 7200, "H3": 10800, "H4": 14400,
    "H6": 21600, "H8": 28800, "H12": 43200,
    "D": 86400, "W": 604800, "M": 2592000,
}

_client: API | None = None


def get_client() -> API:
    global _client
    if _client is None:
        _client = API(access_token=ACCESS_TOKEN, environment=ENVIRONMENT)
    return _client


def _fetch_chunk(instrument: str, granularity: str, params: dict) -> list[dict]:
    request = InstrumentsCandles(instrument=instrument, params=params)
    get_client().request(request)
    return request.response.get("candles", [])


def _parse_candles(candles: list[dict]) -> list[dict]:
    rows = []
    for c in candles:
        if not c.get("complete", True):
            continue
        mid = c["mid"]
        rows.append({
            "time": pd.Timestamp(c["time"]),
            "open": float(mid["o"]),
            "high": float(mid["h"]),
            "low": float(mid["l"]),
            "close": float(mid["c"]),
            "volume": int(c.get("volume", 0)),
        })
    return rows


def fetch_candles(
    instrument: str,
    granularity: str,
    count: int = 500,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> pd.DataFrame:
    """
    Fetch OANDA candles, automatically chunking large date ranges.

    instrument  : e.g. "EUR_USD"
    granularity : e.g. "D", "H4", "H1", "M15"
    count       : number of candles (used when from_time is None)
    from_time   : UTC datetime (inclusive)
    to_time     : UTC datetime (inclusive, defaults to now)
    """
    if from_time is None:
        # Simple count-based fetch
        params = {"granularity": granularity, "price": "M", "count": min(count, _MAX_COUNT)}
        rows = _parse_candles(_fetch_chunk(instrument, granularity, params))
    else:
        # Chunked date-range fetch
        if from_time.tzinfo is None:
            from_time = from_time.replace(tzinfo=timezone.utc)
        end = to_time or datetime.now(timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        gran_secs = _GRAN_SECONDS.get(granularity, 3600)
        chunk_secs = gran_secs * _MAX_COUNT
        chunk_delta = timedelta(seconds=chunk_secs)

        rows = []
        cursor = from_time
        while cursor < end:
            chunk_end = min(cursor + chunk_delta, end)
            params = {
                "granularity": granularity,
                "price": "M",
                "from": _dt_to_rfc3339(cursor),
                "to": _dt_to_rfc3339(chunk_end),
            }
            logger.info("Fetching %s %s chunk %s → %s", instrument, granularity,
                        cursor.date(), chunk_end.date())
            chunk = _fetch_chunk(instrument, granularity, params)
            rows.extend(_parse_candles(chunk))
            cursor = chunk_end
            if len(chunk) > 0:
                time.sleep(0.1)  # gentle rate-limit respect

    df = pd.DataFrame(rows)
    if not df.empty:
        df.set_index("time", inplace=True)
        df.sort_index(inplace=True)
        df = df[~df.index.duplicated(keep="last")]
    return df


def _dt_to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# Convenience wrappers
def fetch_daily(instrument: str, count: int = 500) -> pd.DataFrame:
    return fetch_candles(instrument, "D", count)

def fetch_4h(instrument: str, count: int = 500) -> pd.DataFrame:
    return fetch_candles(instrument, "H4", count)

def fetch_1h(instrument: str, count: int = 500) -> pd.DataFrame:
    return fetch_candles(instrument, "H1", count)

def fetch_15m(instrument: str, count: int = 500) -> pd.DataFrame:
    return fetch_candles(instrument, "M15", count)
