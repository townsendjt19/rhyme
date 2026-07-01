# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository, **Rhyme** — a quantitative forex strategy research and live paper-trading project.

## Environment

Set these env vars before running anything:

```powershell
$env:OANDA_ACCOUNT_ID = "..."
$env:OANDA_ACCESS_TOKEN = "..."
$env:OANDA_ENV = "live"   # or "practice"
```

**Always run scripts through the venv's own python.exe, not the base
`D:\python.exe` directly.** The base interpreter has a resolved
`sys.prefix` of the bare `"D:"` (no trailing slash), which makes its
site-packages a cwd-dependent drive-relative path (`os.path.join("D:",
"lib", "site-packages")` → `"D:lib\site-packages"`, which Windows
resolves against the *current directory of the D: drive*, not the drive
root) -- so `pandas`/`requests`/etc. only import successfully when cwd
happens to be `D:\`, and silently `ModuleNotFoundError` from any other
cwd (this bit three separate restarts before being fixed). The venv at
`D:/rhyme/venv` has its own absolute prefix and does not have this
problem regardless of cwd.

If the venv doesn't exist yet (fresh clone), create it once:
```bash
D:\python.exe -m venv D:\rhyme\venv
D:\rhyme\venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Key Commands

**Backtest a single pair:**
```bash
D:/rhyme/venv/Scripts/python.exe D:/rhyme/backtest.py --instrument EUR_USD --mode scalp --start 2023-01-01 --end 2024-01-01 --balance 4075.63
```

**Backtest with optional filters:**
```bash
D:/rhyme/venv/Scripts/python.exe D:/rhyme/backtest.py --instrument EUR_USD --mode scalp --start 2023-01-01 --end 2024-01-01 --balance 4075.63 --skip-wednesday --skip-382
```

**Live trading loop (ad-hoc/experimental modes only — see "Paper-trading bots" below for the three production bots):**
```bash
D:/rhyme/venv/Scripts/python.exe D:/rhyme/main.py --mode scalp --pairs EUR_USD,GBP_USD,USD_JPY
```

## Paper-trading bots: launch and restart procedure

The three production paper-trading bots (swing, intraday, scalp30) are
launched EXCLUSIVELY via Windows Task Scheduler — tasks `\Rhyme\Rhyme-Swing`,
`\Rhyme\Rhyme-Intraday`, `\Rhyme\Rhyme-Scalp30` (XML definitions in
`D:/rhyme/scheduler/`). They auto-start at user logon with staggered delays
(30s/60s/90s) so the three don't hit the OANDA API simultaneously.

**Never launch a bot with `Start-Process` (or any direct python invocation)
— the scheduler is the sole launch path.** Mixing launch paths causes log-
file handle contention: a bot started one way holds its stdout log open in
a mode that blocks the other path's redirect from even starting (verified
empirically — a task triggered while a `Start-Process`-launched bot ran
failed at the redirect with exit 1 before python ever launched).

**Restart procedure for a single bot:**
1. Verify the target bot's process is actually dead:
   `tasklist /FI "IMAGENAME eq python.exe"` and cross-check the PID in
   `D:/rhyme/paper_trader_<mode>.pid`. If it's still alive and you intend
   to restart it, stop it first (requires the usual Stop-Process approval
   gate) and delete the stale pidfile.
2. Trigger the task: `schtasks /run /tn "\Rhyme\Rhyme-<Mode>"`.
3. Verify the startup header in `D:/rhyme/paper_trade_<mode>_stdout.log`
   (appended, not truncated): plugin, pairs, git commit hash, PID matching
   the fresh pidfile.

`schtasks /run`, `/delete`, and `/change` are in the project deny list —
they launch/kill/alter paper-trader processes, so they carry the same
manual-approval gate as `Stop-Process`. `schtasks /query` is read-only and
unrestricted.

**Analyze losses from a completed backtest CSV:**
```bash
D:/rhyme/venv/Scripts/python.exe D:/rhyme/analyze_losses.py   # reads backtest_EUR_USD_scalp.csv
```

## Architecture

All modules are flat in `D:/rhyme/`. There is no package structure — scripts import each other directly, so they must be run with `PYTHONPATH=D:/rhyme` or from that directory.

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
