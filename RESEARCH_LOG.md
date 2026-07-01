# RSI Crossover Strategy — Research Log

## Status: ABANDONED (2026-06-30)

## Signal Tested

- **Indicator:** RSI(14), crossover-based entry
- **Entry rule:** long when RSI crosses up through 30 with bullish HTF bias; short when RSI crosses down through 70 with bearish HTF bias
- **Exit:** fixed stop-loss at signal swing, take-profit at 2.5R (`rsi_plugin_25r.py`)
- **Position sizing:** fixed $80 risk per trade

## Pairs Tested

All 7 majors: GBP_USD, EUR_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF, NZD_USD

## Timeframes Tested

| Mode | Signal TF | HTF bias |
|---|---|---|
| Scalp | M15 | H1 |
| Intraday | H1 | H4 |
| Swing | H4 | Daily |

Backtest period: 2021–2026 YTD (6 years).

## Zero-Spread Results (scalp mode, all 7 majors)

| Pair | Net P&L (zero spread) |
|---|---|
| GBP_USD | +$7,771 |
| USD_CAD | +$5,867 |
| USD_JPY | +$2,407 |
| NZD_USD | +$1,678 |
| EUR_USD | +$503 |
| AUD_USD | -$1,901 |
| USD_CHF | -$2,313 |

GBP_USD and USD_CAD were the only consistently strong performers under the original (zero-spread) backtest assumption.

## Spread-Adjusted Results (scalp mode, all 7 majors)

Realistic OANDA average spreads applied retroactively to the same trade set:

| Pair | Spread (pips) | Net P&L (zero spread) | Net P&L (spread-adjusted) |
|---|---|---|---|
| GBP_USD | 1.0 | +$7,771 | **-$967** |
| USD_CAD | 1.2 | +$5,867 | **-$3,981** |
| USD_JPY | 0.8 | +$2,407 | **-$3,350** |
| NZD_USD | 1.5 | +$1,678 | **-$14,402** |
| EUR_USD | 0.8 | +$503 | **-$6,817** |
| AUD_USD | 1.0 | -$1,901 | **-$12,099** |
| USD_CHF | 1.2 | -$2,313 | **-$13,709** |

Every pair flips negative (or, where already negative, gets substantially worse) once realistic execution cost is applied.

## Timeframe Sub-Study (GBP_USD, USD_CAD — scalp / intraday / swing)

Hypothesis: wider timeframes use looser stops, reducing position size and therefore spread cost per trade as a fraction of edge.

| Pair | Mode | Net (zero spread) | Net (spread-adjusted) | Viable? |
|---|---|---|---|---|
| GBP_USD | Scalp (M15/H1) | +$7,771 | -$967 | NO |
| GBP_USD | Intraday (H1/H4) | positive | negative | NO |
| GBP_USD | Swing (H4/Daily) | positive | negative | NO |
| USD_CAD | Scalp (M15/H1) | +$5,867 | -$3,981 | NO |
| USD_CAD | Intraday (H1/H4) | positive | negative | NO |
| USD_CAD | Swing (H4/Daily) | positive | negative | NO |

Spread cost per trade did shrink with wider timeframes (scalp ~$9-11/trade → intraday ~$5-7/trade → swing ~$3-5/trade), confirming the position-sizing mechanism. But gross (pre-spread) edge shrank or disappeared at the same time, so no pair/mode combination survived. All 6 combinations tested: non-viable.

## Root Cause

The strategy's stop-loss distances are tight relative to fixed $80 risk sizing:

- Average SL in scalp mode: ~8-12 pips
- At $80 risk with a ~9 pip SL, position size works out to roughly 0.9 standard lots
- A 1 pip spread on a 0.9-lot position costs roughly $9/trade
- Average pre-spread edge per trade across the tested pairs was on the same order (~$6-8/trade)

Because position size is inversely proportional to SL distance under fixed-risk sizing, tighter stops simultaneously increase spread cost in dollar terms — the mechanism that should reduce risk (sizing to a fixed dollar amount) ends up amplifying the impact of the spread instead.

## Conclusion

RSI crossover entry signal abandoned — insufficient gross edge to survive execution costs at any timeframe tested (scalp, intraday, or swing) across any of the 7 major pairs. The backtest's original zero-spread assumption (a dead `SLIPPAGE_PIPS` constant that was never applied) made the strategy look profitable; once realistic OANDA spreads are priced in, no tested configuration retains positive expectancy.

Plugin files moved to `archived/` — see `archived/README.md`.

---

# Order Block Strategy — Research Log

## Status: ARCHIVED — architectural limitation, not signal-quality limitation (2026-06-30)

## Signal Tested

- **Impulse:** 3+ consecutive same-direction candles, each body ≥1.5x the 20-period average candle body size (measured before the impulse, so the impulse's own oversized candles never inflate the baseline)
- **Order block:** the last opposing-direction candle immediately preceding the impulse
- **Entry:** price closes back inside the order block's high-low range after the impulse (a "retest")
- **Stop loss:** just beyond the order block's far edge, plus a small pip buffer
- **Take profit:** fixed 2.5R
- **Re-entry guard:** one trade per order block — a single `_pending_block` is tracked at a time; once it triggers a trade or is invalidated (price closes through the far edge without retesting), its identifying timestamp is recorded so it can never fire again. Built in from the start specifically to avoid the class of bug found in Donchian's original re-entry logic.
- **Position sizing:** fixed $80 risk per trade

## Pairs / Timeframes Tested

GBP_USD only, all three timeframe modes, 2021–2026 YTD:

| Mode | Signal TF | HTF |
|---|---|---|
| Scalp | M15 | H1 |
| Intraday | H1 | H4 |
| Swing | H4 | Daily |

## Results by Mode

### Scalp (M15/H1) — REJECTED

2023 spot check: 52 trades, 26.9% win rate, avg SL 12.5 pips, avg spread cost $10.79/trade, net P&L **-$786.69** (spread-included). Win rate is below the 28.6% breakeven threshold at 2.5R even before spread (-$225 zero-spread). The same mechanism identified in the RSI research recurs here: tight stops force large position sizes under fixed-risk sizing, making spread cost dominate a thin or negative pre-spread edge.

### Intraday (H1/H4) — INCONCLUSIVE, fails minimum-sample-size filtering

Full 2021–2026ytd run: 45 trades total, aggregate **+$859.26**. However, applying a minimum-sample-size filter (n≥10 trades per pair-year-direction cell) leaves **zero surviving cells** — every single year/direction combination has fewer than 10 trades (the largest is 9). Two single-trade cells (2022 long: -$80.10; 2025 long: -$83.25) each unilaterally swing their entire year's result. The aggregate positive number cannot be distinguished from chance with this little data.

A follow-up test loosened the impulse threshold from 1.5x to 1.2x average body size, expecting higher signal frequency. It produced the opposite: trades dropped from 17 to 6 (2023 alone). Diagnosed root cause: the plugin's single-pending-block design only scans for a new impulse when no block is currently pending. A 1.2x-threshold impulse marks a weaker, less significant level, which takes far longer on average to be cleanly retested or invalidated (avg pending duration rose from 108.6 candles at 1.5x to 788.2 candles at 1.2x; invalidation rate dropped from 16.7% to 0%, since weak levels are rarely decisively broken, they're just ignored by price for a long time). The system spent 77.5% of the year "stuck" waiting on one pending block at 1.2x, versus 42.7% at 1.5x — leaving far fewer scanning opportunities for new impulses despite each individual 3-candle window being easier to qualify.

### Swing (H4/Daily) — REJECTED, essentially no signal

Full 2021–2026ytd run: **7 trades across 6 full years**, every single cell exactly 1 trade (zero survive min-N filtering). 2023 produced zero signals all year (confirmed genuine via the signal funnel, not a bug — 0 of 900 H4 candles passed). Aggregate net -$77.02 is statistically meaningless at this sample size. The hypothesis that swing's naturally lower frequency might suit a low-frequency plugin better was tested directly and disproven — swing made the sample-size problem categorically worse than intraday, not better.

## Root Cause

The plugin's single-pending-block architecture is the limiting factor at every timeframe tested, not the underlying price-action concept:

- Only one candidate order block can be tracked at a time; scanning for new impulses is fully suspended while a block is pending.
- Tightening the impulse threshold reduces trade frequency by making qualifying impulses rarer. Loosening it *also* reduces trade frequency, because weaker impulses produce less significant order blocks that take far longer to resolve (retest or invalidate), so the plugin spends a larger share of all candles "stuck" and has fewer opportunities to ever scan for the next setup.
- This is a non-monotonic, self-defeating relationship between the impulse-quality threshold and trade frequency — there is no single-pending-block parameter setting that escapes it, because the mechanism that creates positive results (waiting for a clean retest) is the same mechanism that starves the plugin of new opportunities while waiting.
- Timeframe choice doesn't escape this either: scalp has enough raw candle volume to generate trades but no edge (spread-dominated, like RSI); intraday has a directionally promising but statistically unusable trade count; swing has almost no signal at all because H4 simply doesn't produce enough 3-candle windows per year to overcome the single-block bottleneck.

## Conclusion

Order blocks as currently implemented don't generate sufficient trade frequency at any timeframe to either validate or trade reliably — this is an **architectural limitation of the single-pending-block design, not evidence that the underlying order-block concept lacks edge**. The intraday result (+$859.26 over 6 years) is directionally interesting but cannot be trusted given zero cells survive minimum-sample-size filtering.

Revisiting this would require a **multi-pending-block architecture** capable of tracking several candidate order blocks simultaneously (so a new impulse can still be detected and queued while an older block is still awaiting retest or invalidation) — that is a significant rebuild of the plugin's core state machine, not a parameter tweak like the threshold sweep already tried. Until that rebuild happens, this plugin is archived rather than iterated on further.

---

# Minimum-SL Filter Study — Does Rejecting Tight Stops Fix Scalp Mode?

## Status: TESTED, DOES NOT HELP (2026-06-30)

## Hypothesis

Every scalp-mode result so far (RSI, Donchian, order blocks) traces back to the same mechanism: tight stops force large position sizes under fixed $80 risk, and spread cost on that large position consumes a thin or negative pre-spread edge. If signals with a natural stop-loss tighter than some floor are rejected outright, position size shrinks, spread cost per trade should fall, and net P&L should improve — without touching the entry logic itself.

## Test Design

Added a `_MIN_SL_PIPS = 18.0` filter to two plugins, rejecting any signal whose natural SL distance falls below 18 pips, entry logic otherwise unchanged. Both run on GBP_USD, scalp mode (M15/H1), 2023 only, spread included, $80 fixed risk:

- **`order_block_plugin.py`** — has a single-pending-block state machine (see above). A too-tight retest is rejected but the block is left pending rather than consumed, since a later candle could retest the same block at a different, wider point.
- **`rsi_plugin_25r.py`** — stateless; a rejected signal is simply discarded, no re-evaluation possible. This isolates the filter's effect cleanly, with no architectural interaction to confound the result.

## Results

| Plugin | Trades (before → after) | Win rate (before → after) | Avg SL (before → after) | Avg spread cost/trade (before → after) | Net P&L (before → after) |
|---|---|---|---|---|---|
| Order block | 52 → **4** | 26.9% → 0.0% | 12.5p → 33.0p | $10.79 → $3.10 | -$786.69 → -$324.07 |
| RSI 25r | 206 → **24** | 32.5% → 33.3% | 12.0p → 25.2p | $8.06 → $3.35 | +$622.46 → +$244.41 |

**Order block result is confounded and inconclusive on its own.** Only 7 of the original 52 trades already had a natural SL ≥18 pips, so a clean filter should have left ~7 trades — instead only 4 survived. Traced to the same pending-block starvation mechanism documented in the threshold-sweep study above: leaving a too-tight retest pending (instead of resolving it immediately) delays when scanning resumes for the next impulse, which can prevent later blocks from ever forming. This is the architectural limitation showing up under a different parameter, not new evidence about the min-SL filter itself.

**RSI result is clean** — no pending-block state, so the sample shrank in direct proportion to the filter's selectivity (206 → 24, ~12% pass rate) with no cascading effects. This is the trustworthy read on the hypothesis:

- The mechanical prediction holds exactly: avg SL more than doubled (12.0p → 25.2p), position size fell proportionally, and spread cost per trade dropped 58% ($8.06 → $3.35).
- Win rate was unchanged within noise (32.5% → 33.3%) — filtering for wider stops doesn't make the crossover signal itself more accurate, as expected, since entry logic is untouched.
- But the zero-spread P&L collapsed by roughly the same proportion as trade count (+$2,283.76 → +$324.81) — the filtered trades' per-trade pre-spread edge (~$13.53) isn't meaningfully larger than baseline's (~$11.09). The filter isn't isolating a higher-quality subset of trades; it's discarding ~88% of the trade count to get a lower spread bill, and the dollar P&L falls anyway (+$622.46 → +$244.41) because there's much less volume left to compound the (unchanged) edge over.

## Conclusion

The minimum-SL filter reliably reduces spread cost per trade, exactly as the fixed-risk-sizing mechanism predicts — but it does so by proportionally cutting trade count, not by improving the underlying edge per trade. Net dollar P&L gets worse, not better, because the volume lost outweighs the spread saved. This is a real, clean, unconfounded result (via the RSI test) that closes off "just filter for wider stops" as a fix for scalp-mode economics.

## Scalp-Mode Research: Closed

Four independent approaches have now been tested on GBP_USD scalp mode at $80 fixed risk, spanning different signal types and different mitigation strategies:

1. **RSI crossover, unfiltered** — spread-dominated, net negative across the 6-year study (see top of this log).
2. **Donchian breakout, multiple channel periods (10/14/20)** — all three periods unprofitable; shortening the period made it worse, not better.
3. **Order blocks** — below-breakeven win rate, same spread-cost mechanism.
4. **RSI with a minimum-SL filter** — cleanly confirmed the filter cuts spread cost but proportionally cuts volume, netting worse dollar P&L.

All four converge on the same root cause (tight scalp-mode stops + fixed $80 risk sizing → position sizes large enough that spread cost consumes the available edge) regardless of signal type or filtering strategy tried. **Recommendation: do not pursue further scalp-mode strategy research at this risk sizing.** Intraday and swing modes remain the validated, productive timeframes going forward (see Donchian swing/intraday results, currently paper-traded live).
