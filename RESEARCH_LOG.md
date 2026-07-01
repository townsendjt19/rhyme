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

---

# M30/H4 Donchian — USD_JPY-Specific Finding

## Status: VALIDATED for USD_JPY only, paper trading live (2026-06-30)

## Origin

The scalp-mode closure above is specific to M15 (and worse at M5) — a natural stop-distance diagnostic (ATR(14), 20-candle swing-structure, and confirmed-fractal distance, all computed directly from candle data with no trading involved) showed every method clusters in the 5-13 pip range on M15 for GBP_USD/USD_JPY/AUD_JPY, with under 25% of candles ever producing a stop wider than 18 pips on any method. The same diagnostic extended to M30 showed a qualitative shift: USD_JPY's ATR and swing-structure methods both cross into the 29-41% range for stops ≥18 pips, meaningfully wider than GBP_USD/AUD_JPY at the same timeframe. This motivated testing a Donchian variant on the M30 signal timeframe specifically, rather than treating scalp-mode's closure as covering all short timeframes uniformly.

## Configuration

- **Plugin:** `donchian_plugin.py`, unmodified (same re-entry guard as swing/intraday)
- **Timeframe pairing:** M30 signal / H4 HTF filter — H4 chosen over H1 because an 8x gap gives real trend-filter separation (matching intraday's H1(sig)/H4(htf) spacing), whereas H1 is only 2x M30 and adds little filtering value
- **Position sizing:** fixed $80 risk per trade
- **Pairs tested:** USD_JPY, GBP_USD, AUD_JPY — the same three pairs that performed best at swing/intraday
- **Period:** 2021–2026 YTD, all cells pass n≥10 minimum-sample-size filtering (thinnest cell: 37 trades; largest: 385)

## Results

| Pair | Trades | Win rate | Net P&L | Total spread cost | Avg SL | Verdict |
|---|---|---|---|---|---|---|
| **USD_JPY** | 2,719 | 33.5% | **+$28,000.34** | -$6,301 | 40.9p | **VALIDATED** |
| GBP_USD | 2,740 | 27.8% | -$14,314.01 | -$8,548 | 33.7p | REJECTED |
| AUD_JPY | 2,616 | 31.6% | -$3,127.84 | -$23,085 | 34.2p | REJECTED |

**GBP_USD and AUD_JPY were explicitly tested at this identical M30/H4 configuration and rejected.** GBP_USD's win rate (27.8%) sits below the 28.6% breakeven line at 2.5R. AUD_JPY's win rate (31.6%) is closer to USD_JPY's but its 3.0-pip spread (vs. USD_JPY's 0.8-pip) drives spread cost to -$23,085 — nearly 4x USD_JPY's despite similar trade volume — which is the dominant reason it fails despite a comparable underlying edge. **This is a USD_JPY-specific result, not a general M30/H4 recommendation.** Do not extend this configuration to other pairs without independently backtesting them first.

USD_JPY is positive in 4 of 6 years (2021 +$6,906, 2022 +$15,413, 2023 +$3,376, 2024 +$6,572; only 2025 -$943 and partial 2026ytd -$3,324 negative), with the highest trade volume of any validated result in this project (2,719 trades, zero min-N filter flags across all 36 pair-year-direction cells).

## 2022 Concentration and Macro Check

The 2022 result (+$15,413.14, 498 trades, 41.2% win rate) was checked for the same two failure modes as the earlier intraday-mode 2022 investigation:

- **Not concentrated:** top 10 trades account for only 12.9% of net P&L; every win is capped near the same ceiling ($198.74 max) by the fixed 2.5R take-profit; zero trades exceed 3x the average win. 9 of 12 months were individually positive.
- **Same macro regime, independently confirmed:** USD_JPY's daily efficiency ratio (Kaufman ER, 20-period) for 2022 has a median of 0.285 — the highest of any year 2021-2026ytd — with 32.0% of days classified as strongly trending (ER>0.4), nearly double the next-highest year. This is identical to the finding from the H1/H4 intraday-mode investigation, and since ER is computed on daily bars independent of signal timeframe, it confirms M30/H4 and H1/H4 are two different lenses on the same real, well-documented 2022 BoJ-Fed policy divergence trend (USD/JPY rallied from ~115 to ~131, +13.9% on the year) — not a coincidental or timeframe-specific artifact.

## Conclusion (original 3-pair test)

USD_JPY M30/H4 Donchian is validated and now paper-traded live alongside the swing and intraday configurations. It is the highest-volume, most statistically solid result in this project's research history, and its two strongest years (2022, 2024) trace to real, independently-verified trending regimes rather than backtest artifacts or concentration in a handful of lucky trades. GBP_USD and AUD_JPY remain excluded from this specific mode at this configuration.

## Expansion to GBP_JPY and EUR_JPY

The M30 stop-distance diagnostic was extended to the two JPY crosses that showed promise at intraday mode. Results were striking: **GBP_JPY is the first pair in the entire study where the median ATR(14) itself clears 18 pips** (19.3p median, 60.9% of candles >18p on the ATR method alone) — a materially wider natural-stop profile than USD_JPY. EUR_JPY sits between USD_JPY and GBP_JPY (ATR median 15.6p, 30.4% >18p). Both were backtested at the identical M30/H4 Donchian configuration, 2021–2026ytd, $80 fixed risk, spread included.

| Pair | Trades | Win rate | Net P&L | Total spread cost | Avg SL | Verdict |
|---|---|---|---|---|---|---|
| GBP_JPY | 2,645 | 29.8% | **-$7,493.25** | -$15,315.91 | **55.0p (widest of any pair tested)** | REJECTED |
| EUR_JPY | 2,549 | 30.6% | +$4,687.09 | -$7,764.63 | 41.9p | NOT ADDED (see below) |

All 24 pair-year-direction cells across both pairs pass n≥10 minimum-sample-size filtering (thinnest: 48 trades).

**GBP_JPY: rejected despite having the widest natural-stop profile of any pair tested.** Its win rate (29.8%) sits barely above the 28.6% breakeven line — too thin a margin to overcome execution costs, even with reduced spread drag from unusually wide stops. This is direct confirmation that a favorable stop-distance diagnostic only qualifies a pair for testing; it does not predict win rate or profitability (the same lesson AUD_JPY taught earlier in this study, via a different mechanism — AUD_JPY had adequate win rate but was spread-dominated; GBP_JPY has adequate stops but inadequate win rate).

**EUR_JPY: net positive overall (+$4,687.09) but with a declining win-rate trend that was investigated in depth before deciding not to add it to live trading.**

Per-year win rate:

| Year | N | Win rate | R:R | Net P&L | EV/trade |
|---|---|---|---|---|---|
| 2021 | 491 | 33.2% | 2.28 (lowest of all years) | +$3,690.52 | +$7.52 |
| 2022 | 459 | 32.5% | 2.36 | +$3,386.43 | +$7.38 |
| 2023 | 494 | 29.8% | 2.37 | +$99.42 | +$0.20 |
| 2024 | 479 | 31.3% | 2.37 | +$2,175.24 | +$4.54 |
| 2025 | 474 | 29.1% | 2.35 | -$967.01 | -$2.04 |
| 2026ytd | 152 | 21.1% | 2.35 | -$3,697.51 | -$24.33 |

Two hypotheses were tested and ruled out as explanations for 2021's outsized share of the 6-year total:

1. **Was 2021 a single outlier year (concentration)?** No. Top 10 trades account for only 6.3% of gross winnings (comparable to USD_JPY 2022's 5.1%); zero trades exceed 3x the average win; every win is capped near the same ceiling by the fixed 2.5R TP; 7 of 12 months were individually positive. Not concentrated in a handful of lucky trades.
2. **Was 2021's win rate statistically elevated versus the other years?** No. A z-test on proportions shows 2021 (33.2%) is not significantly different from 2022, 2023, 2024, or 2025 (all |z| < 1.4, versus the 1.96 threshold for 95% confidence). 2021 and 2022 are essentially indistinguishable in accuracy (z=0.24). Notably, **2021 had the *lowest* R:R of any year (2.28)** — if favorable R:R or trade sequencing explained 2021, R:R should have been elevated, not depressed. Neither win-rate accuracy nor R:R singles out 2021 as special; the "2021 = 78.7% of total" framing is mostly an artifact of 2025/2026ytd being drag years that shrink the 6-year total, not evidence that 2021 itself was anomalous.

The more concerning pattern is a **gradual decline in win rate from 2021 (33.2%) to 2026ytd (21.1%)**, which was checked against the same declining-trend-efficiency mechanism that explained the June–November 2025 chop period for other pairs' swing-mode results:

| Year | Win rate | ER median | % days ER>0.4 |
|---|---|---|---|
| 2021 | 33.2% | 0.239 (highest) | 12.9% |
| 2022 | 32.5% | 0.178 | 11.6% |
| 2023 | 29.8% | 0.165 | 14.3% |
| 2024 | 31.3% | 0.220 (2nd highest) | **16.9% (highest of any year)** |
| 2025 | 29.1% | 0.202 | 15.1% |
| 2026ytd | 21.1% | 0.156 (lowest) | 5.5% |

**The decline is NOT explained by declining trend efficiency.** Correlation between win rate and %ER>0.4 is +0.743 across all 6 years, but that flips to **-0.548** when the noisy, partial 2026ytd sample is excluded — a sign-unstable result that isn't trustworthy either way. More directly, **2024 is a clean counter-example**: it has the highest %ER>0.4 of any year in the dataset (16.9%, more strongly-trending days than 2021's 12.9% or 2022's 11.6%), yet its win rate (31.3%) is only third-best, not the best. If chop/trend-efficiency were driving the decline the way it drove the 2025 cross-pair swing-mode chop period, 2024 should have shown a win-rate rebound; it didn't. This rules out the mechanism that explained the earlier 2025 finding — EUR_JPY's decline has a different, currently unidentified cause.

**Root cause: unresolved.** Candidate explanations not yet tested include session-timing effects (does EUR_JPY's breakout timing relative to London/Tokyo/NY sessions shift over the period?), spread-regime changes (has EUR_JPY's realistic spread widened since 2021 independent of the flat 1.2p assumption used here?), or a change in the impulse-formation rate itself (is the plugin finding the same *kind* of setup each year, or drifting toward weaker qualifying impulses as under the earlier order-block threshold-sweep mechanism?).

## Conclusion (updated)

**USD_JPY M30/H4 remains the sole validated pair for this configuration**, and is the only one of the four pairs tested (USD_JPY, GBP_USD, AUD_JPY, GBP_JPY, EUR_JPY — five total across both rounds) currently paper-traded live.

- **GBP_JPY: rejected outright.** Insufficient win rate (29.8%, barely above breakeven) despite having the widest natural stop-distance profile of any pair tested in this entire project (55.0p average).
- **EUR_JPY: not added to live trading.** Net positive over 6 years (+$4,687.09), and the concentration/win-rate-significance checks rule out "2021 was a lucky outlier" as an explanation — but 2025 and 2026ytd are both negative, and the underlying cause of the win-rate decline from 2021 to present is unresolved. Current performance, not the unexplained cause, is the deciding factor: a strategy that is presently losing money should not go live regardless of whether its earlier years are explicable.
- **AUD_JPY and GBP_USD remain rejected** from the original 3-pair test (spread-dominated and below-breakeven, respectively).

If EUR_JPY is revisited later, the root-cause candidates above (session timing, spread-regime drift, impulse-formation rate) should be investigated first, the same way the order-block plugin's threshold-sensitivity was diagnosed before being ruled out as fixable.
