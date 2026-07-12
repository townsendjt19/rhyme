"""
Classic-indicator screen kill-test (registration RESEARCH_LOG 2026-07-11):
ADX gate / Ichimoku Kumo breakout / Ichimoku TK cross / FrAMA cross, each as
a standalone entry at the fleet's scalp30 (H4/M30) configuration.

Grid: 4 variants x 7 majors = 28 cells. OANDA data, $80 fixed risk, harness
SPREAD_PIPS defaults, backtest.py unmodified.

Kill criteria (verbatim from the registration): quick-check on calendar 2023,
per (pair, variant) cell — KILL iff expectancy <= $0/trade OR n < 20 OR
median stop distance < 10x the assumed spread. Decisive; no retuning.
Survivors only: full window 2021-07-01 -> 2026-07-01, with yearly and
ex-best-year print (windfall check: net minus best calendar year <= $0 fails).
Dev-tree KILLS are final; passes are pitch, not evidence (frozen validator).

Run:  venv/Scripts/python.exe classicind_killtest.py                        # 28 quick-check cells
      venv/Scripts/python.exe classicind_killtest.py full EUR_USD           # full window, all variants of a pair
      venv/Scripts/python.exe classicind_killtest.py full EUR_USD adxgate   # full window, single survivor cell
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import backtest

HERE = Path(__file__).parent

PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF", "NZD_USD"]
VARIANTS = {
    "adxgate":  "adx_gate_plugin.py",
    "kumo":     "ichimoku_kumo_plugin.py",
    "tkcross":  "ichimoku_tk_plugin.py",
    "frama":    "frama_plugin.py",
}
QUICK = (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc))
FULL  = (datetime(2021, 7, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc))


def _median_stop_pips(tr: pd.DataFrame, pair: str) -> float:
    pip = 0.01 if pair.endswith("JPY") else 0.0001
    return float(((tr["entry"] - tr["sl"]).abs() / pip).median()) if len(tr) else float("nan")


def run_cell(pair: str, variant: str, plugin_file: str, label: str,
             start: datetime, end: datetime) -> pd.DataFrame:
    plugin = backtest._load_plugin(str(HERE / plugin_file))
    name = f"classicind_{pair}_{variant}_{label}"
    print(f"\n########## {name} ##########")
    tr = backtest.run_backtest(
        instrument=pair, mode="scalp30", start=start, end=end,
        signal_plugin=plugin, fixed_risk=80.0, strategy_name=name,
    )
    tr.to_csv(HERE / f"{name}.csv", index=False)
    return tr


def adjudicate_quick(tr: pd.DataFrame, pair: str) -> tuple[str, str]:
    """Apply the registered criteria verbatim. Returns (verdict, detail)."""
    spread = backtest.SPREAD_PIPS.get(pair, backtest.DEFAULT_SPREAD_PIPS)
    n = len(tr)
    exp = tr["pnl"].mean() if n else float("nan")
    med_stop = _median_stop_pips(tr, pair)
    detail = f"n={n}  exp=${exp:.2f}/trade  med_stop={med_stop:.1f}p  (10x spread={10 * spread:.1f}p)"
    if n < 20:
        return "KILL", detail + "  [n < 20]"
    if exp <= 0:
        return "KILL", detail + "  [expectancy <= 0]"
    if med_stop < 10 * spread:
        return "KILL", detail + "  [median stop < 10x spread]"
    return "PASS", detail


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "full":
        pairs = [sys.argv[2]] if len(sys.argv) > 2 else PAIRS
        only_variant = sys.argv[3] if len(sys.argv) > 3 else None
        for pair in pairs:
            for variant, plugin_file in VARIANTS.items():
                if only_variant and variant != only_variant:
                    continue
                tr = run_cell(pair, variant, plugin_file, "full", *FULL)
                n = len(tr)
                net = tr["pnl"].sum() if n else 0.0
                wr = (tr["pnl"] > 0).mean() * 100 if n else float("nan")
                print(f"  n={n}  net=${net:.2f}  WR={wr:.1f}%")
                if n:
                    yearly = (tr.assign(t=pd.to_datetime(tr["time"]))
                                .set_index("t")["pnl"].resample("YE").sum())
                    ex_best = net - yearly.max()
                    print("  yearly: " + " ".join(f"{t.year}:{v:+.0f}" for t, v in yearly.items())
                          + f"  ex-best-year: {ex_best:+.2f}"
                          + ("  [WINDFALL FAIL]" if ex_best <= 0 else ""))
        return

    verdicts = []
    for pair in PAIRS:
        for variant, plugin_file in VARIANTS.items():
            tr = run_cell(pair, variant, plugin_file, "2023", *QUICK)
            verdict, detail = adjudicate_quick(tr, pair)
            print(f"  {verdict}: {detail}")
            verdicts.append((pair, variant, verdict, detail))

    print("\n\n================ QUICK-CHECK SUMMARY (28 cells) ================")
    for pair, variant, verdict, detail in verdicts:
        print(f"{pair:9s} {variant:8s} {verdict:4s}  {detail}")
    survivors = [(p, v) for p, v, verdict, _ in verdicts if verdict == "PASS"]
    print(f"\nSurvivors: {survivors if survivors else 'none'}")


if __name__ == "__main__":
    main()
