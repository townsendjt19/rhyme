# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

Set these env vars before running anything:

```powershell
$env:OANDA_ACCOUNT_ID = "..."
$env:OANDA_ACCESS_TOKEN = "..."
$env:OANDA_ENV = "live"   # or "practice"
```

Install dependencies:
```bash
python -m pip install -r requirements.txt
```

## Key Commands

**Backtest a single pair:**
```bash
python D:/forex_bot/backtest.py --instrument EUR_USD --mode scalp --start 2023-01-01 --end 2024-01-01 --balance 4075.63
```

**Backtest with optional filters:**
```bash
python D:/forex_bot/backtest.py --instrument EUR_USD --mode scalp --start 2023-01-01 --end 2024-01-01 --balance 4075.63 --skip-wednesday --skip-382
```

**Live trading loop:**
```bash
python D:/forex_bot/main.py --mode scalp --pairs EUR_USD,GBP_USD,USD_JPY
```

**Analyze losses from a completed backtest CSV:**
```bash
python D:/forex_bot/analyze_losses.py   # reads backtest_EUR_USD_scalp.csv
```

## Architecture

All modules are flat in `D:/forex_bot/`. There is no package structure — scripts import each other directly, so they must be run with `PYTHONPATH=D:/forex_bot` or from that directory.

### Data flow

```
data.py  →  indicators.py + fibonacci.py + patterns.py + volume_profile.py
                                    ↓
                              strategy.py   (evaluate() → Signal)
                                    ↓
              backtest.py (historical)  /  main.py (live)
                                    ↓
                               broker.py   (OANDA API)
                               risk.py     (lot sizing)
```

### The six-filter pipeline (`strategy.py`)

`evaluate()` returns `(Signal | None, stage_name)`. Every filter returns early with the stage name it failed at, which `backtest.py` uses to build the funnel report. Filters run in strict order:

1. **HTF EMA alignment** — higher TF 20 > 50 > 100 (bull) or 20 < 50 < 100 (bear)
2. **LTF EMA crossover** — 20 crosses 50 on the signal candle (`lookback=1`); both correct side of 100
3. **Williams Fractal break** — close beyond last confirmed fractal high/low
4. **Candlestick filter** — skip if opposing pattern (Doji, Engulfing, Hammer, Shooting Star, Morning/Evening Star, Pin Bar)
5. **Volume Profile LVN** — skip if price inside a Low Volume Node (rolling 20-candle window)
6. **Fibonacci confirmation** — price within 0.5% of 38.2%, 50%, or 61.8% retracement anchored from last fractal swing

Optional filters controlled via `StrategyConfig(skip_wednesday=True, skip_382_fib=True)` — passed to `evaluate()` or enabled via `--skip-wednesday` / `--skip-382` CLI flags on `backtest.py`.

### Timeframe modes

| Mode | HTF (confirms) | LTF (triggers) | Candle interval |
|---|---|---|---|
| swing | D | H4 | 4h |
| intraday | H4 | H1 | 1h |
| scalp | H1 | M15 | 15m |

### Stop / TP logic

- **SL**: whichever is further from entry — last fractal high/low or 100 EMA
- **TP**: Fibonacci extensions at 1.272, 1.618, 2.0 projected from the fractal swing
- **Partial close**: 33% at TP1, 33% at TP2, remainder at TP3
- **Trailing stop**: trails to EMA20 after each TP hit; closes on EMA20 cross-back

### Risk

`risk.py` sizes every trade at **2% of account balance**. USD/JPY pip value should be recalculated live using `pip_value_jpyfx(current_rate)` — the static table value is approximate.

### OANDA API notes

- `data.py` auto-chunks large date ranges — OANDA caps at 4,999 candles per request
- `broker.py` wraps `oandapyV20`; all order placement goes through `place_market_order()`
- `OANDA_ENV=live` hits `api-fxtrade.oanda.com`; `practice` hits `api-fxpractice.oanda.com` — the API token is environment-specific

### Backtest output

Each run saves `backtest_{INSTRUMENT}_{MODE}.csv` and prints:
- A signal funnel showing how many candles were eliminated at each filter stage
- Trade-level metrics (win rate, avg win/loss, R:R, final balance)

`analyze_losses.py` enriches losses with hour/day/Fib level/candlestick pattern and saves `losses_enriched.csv`.

## Backtesting findings (EUR/USD, GBP/USD, USD/JPY — scalp, 2023)

- Filter 2 (EMA crossover) eliminates ~99% of candidates — it is intentionally strict
- All EUR/USD signals triggered at the 38.2% Fib level; `--skip-382` eliminates all trades for that pair
- USD/JPY outperforms (76% win rate, +$207) vs GBP/USD (37.5%, -$160) on scalp mode
- Wednesday produces disproportionate losses on EUR/USD; `--skip-wednesday` is the recommended single filter to test
- Combined across all 3 pairs: 62 trades, 48.4% win rate, net +$22 (carried by USD/JPY)
