"""
Keltner-breakout x {EUR_USD, GBP_USD} extension (registered 2026-07-15,
commit 75492f4, BEFORE results). Semantics verbatim via
megascreen_killtest.make_plugin("keltner"); OANDA data; verified FTMO
all-in costs 0.7p / 0.8p; M30 (mode scalp30).

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/kelfx_killtest.py [full]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import backtest
from megascreen_killtest import make_plugin

HERE = Path(__file__).parent
PAIRS = {"EUR_USD": 0.7, "GBP_USD": 0.8}
QUICK = (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc))
FULL = (datetime(2021, 1, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc))
FIXED_RISK = 80.0


def main():
    full = len(sys.argv) > 1 and sys.argv[1] == "full"
    backtest.TF_MAP.setdefault("scalp30", ("H4", "M30"))
    start, end = FULL if full else QUICK
    for pair, spread in PAIRS.items():
        pip = 0.01 if pair.endswith("JPY") else 0.0001
        name = f"kelfx_{pair}_{'full' if full else '2023'}"
        print(f"\n########## {name} ##########", flush=True)
        tr = backtest.run_backtest(
            instrument=pair, mode="scalp30", start=start, end=end,
            signal_plugin=make_plugin("keltner"), fixed_risk=FIXED_RISK,
            spread_pips=spread, strategy_name=name)
        tr.to_csv(HERE / f"{name}.csv", index=False)
        n = len(tr)
        net = tr["pnl"].sum() if n else 0.0
        exp = net / n if n else float("nan")
        med = (tr["entry"] - tr["sl"]).abs().median() / pip if n else float("nan")
        verdict = "KILL" if (n < 20 or exp <= 0 or med < 10 * spread) else "CLEAR"
        print(f"  RESULT {pair}: n={n} net=${net:.2f} exp=${exp:.2f}/tr "
              f"med_stop={med:.0f}p (floor {10*spread:.0f}p) -> {verdict}", flush=True)


if __name__ == "__main__":
    main()
