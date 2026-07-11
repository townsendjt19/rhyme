"""
Read-only probe: how far back does OANDA's candle history actually go for
USD_JPY? The repo standardized on 2021-2026 and never tested earlier
availability; the pre-2021 regime test (RESEARCH_LOG DRAFT registration,
2026-07-10) needs to know what OANDA can supply before Dukascopy fills the
rest.

For each granularity, requests a 30-day window starting at several historical
probe dates and reports the first candle returned (empty = no data there).

Run: D:/workspace/rhyme/venv/Scripts/python.exe probe_oanda_depth.py
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from data import fetch_candles

INSTRUMENT = "USD_JPY"
GRANULARITIES = ["M30", "H1", "H4"]
PROBE_DATES = [2005, 2008, 2010, 2015, 2018, 2020]


def main() -> None:
    print(f"OANDA candle-depth probe: {INSTRUMENT}")
    for gran in GRANULARITIES:
        print(f"\n  {gran}:")
        for year in PROBE_DATES:
            start = datetime(year, 1, 1, tzinfo=timezone.utc)
            try:
                df = fetch_candles(INSTRUMENT, gran,
                                   from_time=start, to_time=start + timedelta(days=30))
                if df.empty:
                    print(f"    {year}-01: no data")
                else:
                    print(f"    {year}-01: first candle {df.index[0]}  ({len(df)} candles in 30d)")
            except Exception as e:
                print(f"    {year}-01: ERROR {e}")

    # Earliest candle overall, per granularity: probe from a very early date.
    print("\n  Earliest available candle per granularity:")
    for gran in GRANULARITIES:
        try:
            df = fetch_candles(INSTRUMENT, gran,
                               from_time=datetime(2002, 1, 1, tzinfo=timezone.utc),
                               to_time=datetime(2002, 12, 31, tzinfo=timezone.utc))
            if df.empty:
                print(f"    {gran}: nothing in 2002 -- see per-year probes above")
            else:
                print(f"    {gran}: {df.index[0]}")
        except Exception as e:
            print(f"    {gran}: ERROR {e}")


if __name__ == "__main__":
    main()
