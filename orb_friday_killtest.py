"""
ORB weekend-flat ("friday-close") exit variant runner.

Registered 2026-07-13 in RESEARCH_LOG.md BEFORE this script was written.
A/B vs the incumbent fire-and-forget on the two deployed ORB cells
(SPX x close, XAUUSD x close). The rule touches EXITS ONLY: any position
still open is force-closed at the close of the last M15 bar opening before
Friday 17:00 ET of the entry's week (the .sim weekly close).

Seam: wraps backtest._simulate_trade and truncates each trade's
future-candle window at the deadline; the engine's own
remaining-units-at-last-close path books the exit. backtest.py and the
plugins are untouched.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/orb_friday_killtest.py [full]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

import backtest
import risk
from gate2_killtest import mt5_fetch_candles

HERE = Path(__file__).parent
_ET = ZoneInfo("America/New_York")

# Registered Line B conventions (2026-07-09), deployed cells only.
SYMBOLS = {
    "SPX":    {"pip_size": 0.10, "pip_value": 0.10, "spread_pips": 5.0},
    "XAUUSD": {"pip_size": 0.01, "pip_value": 0.10, "spread_pips": 25.0},
}
PLUGIN = "orb_close_plugin.py"
STRETCHES = {
    "A2023": (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)),
    "B24H2": (datetime(2024, 7, 1, tzinfo=timezone.utc), datetime(2025, 7, 1, tzinfo=timezone.utc)),
}
FULL_WINDOWS = {
    "SPX":    (datetime(2022, 7, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc)),
    "XAUUSD": (datetime(2021, 12, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc)),
}
FIXED_RISK = 80.0


def friday_deadline_utc(entry_ts: pd.Timestamp) -> pd.Timestamp:
    """First Friday 17:00 ET boundary strictly after entry_ts, as UTC.

    Entries fire 10:00-15:30 ET on weekdays, so for a Friday entry the
    deadline is the same day's 17:00 ET. The registration allows the IANA
    zone here; test_orb_friday_killtest.py asserts it matches the plugin's
    statutory-DST rule across the data window, transition weeks included.
    """
    # Calendar arithmetic on the naive ET wall clock: Timedelta on a tz-aware
    # timestamp adds absolute hours, which shifts the 17:00 wall time by an
    # hour when the added span crosses a DST transition.
    et = entry_ts.tz_convert(_ET).tz_localize(None)
    days_ahead = (4 - et.weekday()) % 7          # 4 = Friday
    candidate = (et + pd.Timedelta(days=days_ahead)).replace(
        hour=17, minute=0, second=0, microsecond=0)
    if candidate <= et:
        candidate += pd.Timedelta(days=7)
    return candidate.tz_localize(_ET).tz_convert("UTC")


def _wrap_simulate(orig):
    """Truncate each trade's future window at the entry's weekend boundary."""
    def wrapped(direction, entry, sl, tps, future, total_units, instrument, **kw):
        if len(future):
            deadline = friday_deadline_utc(future.index[0])
            truncated = future[future.index < deadline]
            bound = len(truncated) < len(future)
        else:
            truncated, bound = future, False
        result = orig(direction, entry, sl, tps, truncated, total_units, instrument, **kw)
        if bound and result["exit_reason"] == "end_of_data":
            result["exit_reason"] = "friday_close"
        return result
    return wrapped


def main():
    full = len(sys.argv) > 1 and sys.argv[1] == "full"
    backtest.fetch_candles = mt5_fetch_candles
    backtest._simulate_trade = _wrap_simulate(backtest._simulate_trade)
    for sym, conv in SYMBOLS.items():
        risk._PIP_SIZE[sym] = conv["pip_size"]
        risk._PIP_VALUE_USD[sym] = conv["pip_value"]

    for sym, conv in SYMBOLS.items():
        stage = {"full": FULL_WINDOWS[sym]} if full else STRETCHES
        for label, (start, end) in stage.items():
            plugin_fn = backtest._load_plugin(str(HERE / PLUGIN))
            name = f"orbfri_{sym}_close_{label}"
            print(f"\n########## {name} ##########")
            tr = backtest.run_backtest(
                instrument=sym, mode="scalp", start=start, end=end,
                signal_plugin=plugin_fn, fixed_risk=FIXED_RISK,
                spread_pips=conv["spread_pips"], strategy_name=name,
            )
            tr.to_csv(HERE / f"{name}.csv", index=False)
            n = len(tr)
            net = tr["pnl"].sum() if n else 0.0
            wr = (tr["pnl"] > 0).mean() * 100 if n else float("nan")
            n_fri = (tr["exit_reason"] == "friday_close").sum() if n else 0
            pnl_fri = tr.loc[tr["exit_reason"] == "friday_close", "pnl"].sum() if n else 0.0
            print(f"  n={n}  net=${net:.2f}  WR={wr:.1f}%  "
                  f"friday_close: n={n_fri} pnl=${pnl_fri:.2f}")


if __name__ == "__main__":
    main()
