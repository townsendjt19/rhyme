"""
Line B kill-test runner (registered 2026-07-09, committed before results).
3 instruments x 2 entry variants x 2 stretches; both stretches must pass
per (instrument, variant) cell: net-positive AND n >= 30.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/orb_killtest.py
"""
from datetime import datetime, timezone
from pathlib import Path

import backtest
import risk
from gate2_killtest import mt5_fetch_candles

HERE = Path(__file__).parent

SYMBOLS = {
    # pip conventions per the standing registrations; spreads = real .sim medians
    "SPX":    {"pip_size": 0.10, "pip_value": 0.10, "spread_pips": 5.0},
    "YM":     {"pip_size": 1.00, "pip_value": 0.10, "spread_pips": 2.0},
    "XAUUSD": {"pip_size": 0.01, "pip_value": 0.10, "spread_pips": 25.0},
}
PLUGINS = ["orb_close_plugin.py", "orb_touch_plugin.py"]
STRETCHES = {
    "A2023": (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)),
    "B24H2": (datetime(2024, 7, 1, tzinfo=timezone.utc), datetime(2025, 7, 1, tzinfo=timezone.utc)),
}
FIXED_RISK = 80.0


def main():
    backtest.fetch_candles = mt5_fetch_candles
    for sym, conv in SYMBOLS.items():
        risk._PIP_SIZE[sym] = conv["pip_size"]
        risk._PIP_VALUE_USD[sym] = conv["pip_value"]

    for sym, conv in SYMBOLS.items():
        for plug in PLUGINS:
            for label, (start, end) in STRETCHES.items():
                plugin_fn = backtest._load_plugin(str(HERE / plug))
                name = f"orb_{sym}_{plug.replace('orb_','').replace('_plugin.py','')}_{label}"
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
                verdict = "PASS" if (net > 0 and n >= 30) else "FAIL"
                print(f"  n={n}  net=${net:.2f}  WR={wr:.1f}%  -> {verdict}")


if __name__ == "__main__":
    main()
