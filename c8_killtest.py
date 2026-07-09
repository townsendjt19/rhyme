"""
Candidate #8 kill-test runner -- AVWAP fade on XAUUSD, two pre-committed
stretches, both must pass (registration 2026-07-09, committed before results).

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/c8_killtest.py
"""
from datetime import datetime, timezone
from pathlib import Path

import backtest
import risk
from gate2_killtest import mt5_fetch_candles

HERE = Path(__file__).parent

STRETCHES = {
    "A": (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)),
    "B": (datetime(2024, 7, 1, tzinfo=timezone.utc), datetime(2025, 7, 1, tzinfo=timezone.utc)),
}
FIXED_RISK = 80.0
SPREAD_PIPS = 25.0   # real Phase B platform median


def main():
    backtest.TF_MAP.setdefault("scalp30", ("H4", "M30"))
    backtest.fetch_candles = mt5_fetch_candles
    risk._PIP_SIZE["XAUUSD"] = 0.01
    risk._PIP_VALUE_USD["XAUUSD"] = 0.10

    for label, (start, end) in STRETCHES.items():
        plugin = backtest._load_plugin(str(HERE / "avwap_fade_xau_plugin.py"))
        name = f"c8_xau_avwap_{label}"
        print(f"\n########## {name} ##########")
        tr = backtest.run_backtest(
            instrument="XAUUSD", mode="scalp30", start=start, end=end,
            signal_plugin=plugin, fixed_risk=FIXED_RISK,
            spread_pips=SPREAD_PIPS, strategy_name=name,
        )
        tr.to_csv(HERE / f"{name}.csv", index=False)
        n = len(tr)
        net = tr["pnl"].sum() if n else 0.0
        wr = (tr["pnl"] > 0).mean() * 100 if n else float("nan")
        verdict = "PASS" if (net > 0 and n >= 30) else "FAIL"
        print(f"  n={n}  net=${net:.2f}  WR={wr:.1f}%  -> {verdict}")


if __name__ == "__main__":
    main()
