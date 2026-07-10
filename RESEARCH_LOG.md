# Rhyme — Research Log

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

## Broad Sweep: EUR_AUD and the Verified-Clean-Spread Universe

Before treating USD_JPY as the final word on this configuration, the candidate universe was widened systematically. OANDA's practice account was queried directly (`AccountInstruments` + `PricingInfo` endpoints) for its full 68-pair currency universe, confirming all 68 have complete 2021-2026ytd historical candle data. Filtering to a live-snapshot spread ≤3 pips left 23 pairs, split into 7 majors, 2 JPY crosses (AUD_JPY, EUR_JPY — already covered above), 6 G10 minors, and 8 exotic-adjacent pairs.

**3 of the 8 exotic-adjacent pairs were excluded as spread artifacts, not tested:** HKD_JPY (0.23p), TRY_JPY (1.1p), and ZAR_JPY (2.4p) are implausibly tight for currencies (HKD, TRY, ZAR) that show far wider spreads on their own USD pairs on the same account (USD_TRY 110.2p, USD_ZAR 94.5p) — almost certainly stale or thin-liquidity snapshot artifacts on the demo feed, not genuinely tradeable prices.

**The remaining 5 exotic-adjacent pairs (CAD_SGD, EUR_SGD, NZD_SGD, USD_SGD, SGD_CHF) were also excluded, but for a different reason: unverifiable, not implausible.** OANDA's own published spread documentation (US and UK trading/spreads pages, historical-spreads tool) does not list per-pair figures for SGD crosses at all — the historical-spreads tool is an interactive chart with no static data, and third-party broker-comparison sites don't break out SGD minors either. A live re-query during the London/NY liquidity overlap (~12:00-16:00 UTC) was planned to resolve this by comparing against the original off-peak-adjacent snapshot (CAD_SGD 1.9p, EUR_SGD 2.9p, NZD_SGD 2.2p, USD_SGD 2.9p, SGD_CHF 1.5p), but session-scheduling tools were unavailable to defer the check to the correct time window. **Status: unresolved, not tested.** Revisit with either OANDA's official published typical-spread table (if one becomes available) or a same-session live query taken during the overlap window.

**The M30 stop-distance diagnostic (ATR/Swing/Fractal) was run on all 15 verified-clean pairs (7 majors + 2 JPY crosses + 6 G10 minors).** Every pair clustered in the familiar 4-16 pip band on all three methods except one outlier: **EUR_AUD's ATR/Swing median (16.6p/16.2p) and %>18p rate (34.0%/44.7%) rivaled EUR_JPY's profile** — the only G10 minor (non-JPY-cross) pair to show a stop-distance profile wide enough to justify a full backtest. All other majors and G10 minors stayed in the same tight 5-13 pip range already established as unviable for this configuration.

**EUR_AUD full Donchian M30/H4 backtest, 2021-2026ytd, $80 fixed risk, spread included: REJECTED.**

| Metric | Value |
|---|---|
| Trades | 2,581 (zero cells below n=10 minimum-sample-size threshold) |
| Win rate | 28.0% (below the 28.6% breakeven line at 2.5R) |
| Net P&L | **-$18,823.25** |
| Total spread cost | -$14,526.99 |
| Avg SL distance | 43.4p |

5 of 6 years were individually negative; only 2022 was positive (+$1,458.33). 2021's loss (-$8,114.56) is 43.1% of the total — large enough to trigger the same concentration/efficiency-ratio check applied to USD_JPY 2022 and EUR_JPY 2021. Unlike EUR_JPY's ambiguous case, **EUR_AUD 2021 has a clean, mechanistically consistent explanation**: not concentrated (only 2 of 12 months positive; worst 10 losses are just 3.2% of total gross losses; no trade exceeds 3x the average win), and its daily efficiency ratio for 2021 (0.145 median, 9.2% of days trending) is the **lowest of any year in the dataset** — a textbook case of a breakout strategy failing hardest in its choppiest year, the same mechanism (in the opposite direction) that explained the June-November 2025 cross-pair swing-mode chop period.

## Conclusion (final, after broad sweep)

**USD_JPY M30/H4 remains the sole validated pair for this configuration after testing 6 real candidates end-to-end:**

| Pair | Verdict | Cause |
|---|---|---|
| **USD_JPY** | **VALIDATED, live** | 33.5% WR, +$28,000.34/6yr, zero min-N flags |
| GBP_USD | Rejected | Win rate (27.8%) below breakeven |
| AUD_JPY | Rejected | Adequate win rate, spread-dominated (3.0p spread → -$23,085 total cost) |
| EUR_JPY | Not added | Net positive but declining win rate with unresolved cause; currently unprofitable (2025-2026ytd negative) |
| GBP_JPY | Rejected | Widest stop profile of any pair tested, still insufficient win rate (29.8%) |
| EUR_AUD | Rejected | Below-breakeven win rate (28.0%), worst year cleanly explained by genuine low trend-efficiency (chop) |

Two categories of pairs remain untested rather than rejected: **HKD_JPY/TRY_JPY/ZAR_JPY** (excluded as implausible spread-snapshot artifacts) and **CAD_SGD/EUR_SGD/NZD_SGD/USD_SGD/SGD_CHF** (excluded as unverifiable — no published documentation, live re-check deferred pending session tooling). Neither should be read as "tested and failed" — they are open questions, not closed ones, and should be revisited if a reliable spread source becomes available.

## RSI M30/H4 — Investigated as a Second Signal for USD_JPY, Not Added

With USD_JPY M30/H4 validated for Donchian, RSI(14) crossover was tested at the identical configuration (M30 signal / H4 HTF, $80 fixed risk, spread included) to check whether it could serve as either a standalone second strategy or a complementary signal alongside Donchian on the same pair.

**Standalone result: near-breakeven, does not clear the bar.** Full 2021-2026ytd backtest: 600 trades, 30.2% win rate, **net -$144.02** — essentially flat over 6 years, and nowhere close to Donchian's +$28,000.34 on the identical pair/timeframe/period. All 12 pair-year-direction cells pass min-N filtering. Only 2025 was a significant loser (-$2,144.29); every other year was modestly positive (2021 +$983, 2022 +$265, 2023 +$285, 2024 +$174, 2026ytd +$293).

**This is another instance of a single-year premise check not predicting full-window performance** — the initial 2023-only spot check (+$285.43, 31.0% WR) looked like a clean pass, and in isolation was indistinguishable from a genuinely viable signal. Only the full 6-year run revealed it nets out to roughly zero. This reinforces the standing practice in this project of never trusting a single-year result (see also: GBP_JPY's promising stop-distance profile that didn't translate to win rate; EUR_AUD's stop-distance profile that also didn't hold up) — RSI's 2023 result was real, not a bug, but not representative.

**Overlap analysis with Donchian (same pair, same M30/H4 configuration): the two signals are not independent.**

| Finding | Result |
|---|---|
| RSI trading days (6yr) | 379 |
| Donchian trading days (6yr) | 1,085 |
| Days both fired at least one trade | 207 (54.6% of RSI's trading days) |
| Same direction on overlap days | **184 of 207 (88.9%)** |
| Opposite direction | 18 (8.7%) |
| Median timing gap between same-direction trades on overlap days | 9.0 hours (100% within 24h) |

On more than half of all days RSI trades at all, Donchian is also trading, and when both fire they agree on direction 88.9% of the time, typically within the same day. **Root cause: both plugins gate direction using the same HTF EMA20/50 alignment filter on H4** — RSI's oversold/overbought crossover and Donchian's channel breakout are two different *entry triggers* layered on an essentially identical *directional read* of the market. RSI functions as a delayed, weaker echo of the same trend call Donchian is already making, not an independent source of edge.

## Conclusion

**RSI is not added alongside Donchian on USD_JPY M30/H4**, either as a standalone third process or as a combined/confirming filter. As a standalone strategy it doesn't clear breakeven over the full window despite a promising single-year spot check. As a companion to Donchian, the overlap analysis shows it would mostly duplicate exposure to the same H4-driven trend calls rather than diversify them, while additionally contributing a near-zero (and possibly negative) marginal edge of its own. This closes the RSI M30/H4 investigation.

## Order Block M30/H4 — Architecture Limitation Confirmed at Widened Timeframe

With the RSI angle closed, order_block_plugin.py was checked at the identical M30(sig)/H4(HTF) configuration on USD_JPY, 2023 only, unmodified 1.5x impulse threshold, $80 fixed risk, spread included.

**Trade count: 8 — too thin to assess edge.** Net P&L (+$156.75, 37.5% WR) is not meaningful at this sample size; the point of this check was purely to see whether the plugin produces a usable trade count at M30, not to evaluate profitability.

**Pending-duration diagnostic (same instrumentation used in the earlier impulse-threshold sweep) confirms the single-pending-block architecture is the cause, not genuine signal scarcity — and it is worse at M30 than at H1:**

| Metric | Value |
|---|---|
| Total M30 candles evaluated | 12,320 |
| Blocks formed | 12 |
| Blocks invalidated | 2 |
| Avg pending duration | 190.6 candles (**~95.3 hours, ~4 days**) |
| Max pending duration | 1,701 candles (~35 days) |
| **Candles spent stuck pending** | **10,030 of 12,320 (81.4%)** |
| Candles spent actively scanning | 2,290 of 12,320 (18.6%) |

81.4% stuck exceeds even the 77.5%-stuck figure found for the *loosened* 1.2x threshold at H1 signal timeframe (GBP_USD, earlier in this log) — and this is at the *default, unmodified* 1.5x threshold. **Widening the signal timeframe makes the bottleneck worse, not better**: M30's wider natural order-block zones (consistent with the M30 stop-distance diagnostic that made Donchian more viable here) take proportionally longer to be cleanly retested or invalidated, extending average pending duration well beyond the H1 case. The same mechanism that helps Donchian at M30 (wider zones, less spread drag) actively hurts order block, because its limiting factor was never spread cost — it's the single-pending-block gate, which scales unfavorably with timeframe width.

**Conclusion: order blocks are confirmed non-viable at M30/H4, for the same architectural reason already documented at scalp mode, intraday, and swing.** No timeframe tested across this entire project escapes the single-pending-block limitation; a multi-pending-block rebuild remains the only path to revisiting this plugin.

## M30 Signal Search on USD_JPY: Closed

Two candidate signals were tested against Donchian's validated USD_JPY M30/H4 result, both at the identical configuration, and neither replicated or improved on it:

| Signal | Verdict | Reason |
|---|---|---|
| **Donchian** | **VALIDATED, live** | +$28,000.34/6yr, 33.5% WR, zero min-N flags |
| RSI(14) | Rejected | Near-breakeven standalone (-$144.02/6yr); 88.9% direction-overlap with Donchian means it would add correlated exposure, not diversification |
| Order blocks | Rejected | Architecturally incapable of sufficient sample size (81.4% of candles stuck on a single pending block) |

USD_JPY M30/H4 Donchian remains the sole validated signal at this configuration. This closes the M30 signal-search thread for USD_JPY.

---

# Swing Structure Plugin — Rejected Under Both SL Conventions

## Status: REJECTED, both variants (2026-07-01)

## Signal Tested

`swing_structure_plugin.py`: reuses `indicators.detect_fractals()` (N=2, the same Williams Fractal method used in the M30 stop-distance diagnostic) to identify the most recent confirmed swing high/low. Long on close above the most recent confirmed swing high; short on close below the most recent confirmed swing low. TP fixed 2.5R throughout. Re-entry guard tracks only the identity of the swing point last used per direction (not a single-pending-block design), so a fresh swing point is immediately tradeable with no starvation the moment it confirms — verified via unit test to correctly avoid the order-block class of bug from the start.

Two SL conventions were tested on the same entry logic, same pair/timeframe/period (USD_JPY, M30/H4, 2023, $80 fixed risk, spread included):

| SL convention | Trades | Win rate | Avg SL | Avg spread cost/trade | Net (zero-spread) | **Net (spread-incl)** |
|---|---|---|---|---|---|---|
| Buffer (just beyond the broken swing point) | 1,115 | 32.6% | 10.1p | $11.40 | +$12,654.32 | **-$62.16** |
| Midpoint (vs. opposite-side swing point, Donchian-style) | 1,114 | 28.7% | 25.0p | $3.93 | +$334.83 | **-$4,044.13** |

## Findings

**Buffer-SL version**: strong underlying edge (+$12,654 zero-spread), but the stop is inherently tight (10.1p avg) because it's anchored to the just-broken level itself — the same scalp-mode failure mechanism documented throughout this project (tight SL → large position under fixed-risk sizing → spread cost dominates). Net result nearly breakeven only because the zero-spread edge was unusually large to begin with; spread consumed 100.5% of it.

**Midpoint-SL version**: the stop-widening fix worked exactly as designed — avg SL more than doubled (10.1p → 25.0p) and spread cost per trade fell 66% ($11.40 → $3.93), mechanically identical to how Donchian's channel-midpoint SL keeps its spread cost low. But **win rate collapsed from 32.6% to 28.7%** (below the 28.6% breakeven line) and the zero-spread edge nearly vanished (+$12,654 → +$334) on the *same* entry signal, *same* trade timestamps in aggregate (1,114 vs 1,115 trades). The wider stop is not a free improvement -- it changes which trades win and lose, because the SL now sits roughly halfway back toward the previous opposite-side swing extreme, a fundamentally different risk/reward geometry than a tight stop just past the breakout level. Net result got *worse* in dollar terms despite the correct, working fix to the spread-cost problem.

## Conclusion — a generalizable refinement to the M30 finding

**Swing structure plugin is rejected under both SL conventions.** Neither is viable on USD_JPY M30/H4 as currently designed.

This refines the earlier M30/H4 conclusion beyond "wider timeframe -> wider stops -> lower spread cost" (which was true but incomplete). The more precise finding: **a stop only widens "for free" when its placement is intrinsic to the entry signal's own logic.** Donchian's channel-midpoint SL is a natural extension of its breakout definition -- the channel that defines the entry also defines the stop, so widening the timeframe widens both together in a way that preserves the signal's own logic. Bolting a structurally wider stop (even the *identical* midpoint convention Donchian uses) onto a *different* entry signal not designed around it does not carry the same free lunch -- as demonstrated here, it can destroy most of the underlying edge rather than merely diluting it with lower spread cost. Any future SL-widening experiment on a new or existing plugin should treat "does this stop placement fit the signal's own structure" as a prior question, not assume any wider stop is a strict improvement over a tighter one.

---

# Fibonacci Retracement Bounce Plugin — Rejected, Pure Signal-Quality Failure

## Status: REJECTED (2026-07-01)

## Signal Tested

`fib_retracement_plugin.py`: identifies the most recent confirmed H4 swing high/low pair (same `detect_fractals()` N=2 method used throughout this project), draws the retracement grid between them, and enters on M30 when price touches the 61.8% level and closes back in the trend direction (bounce confirmation, not just a touch). SL sits at the closer of the 78.6% level or the original swing extreme; TP fixed at 2.5R. Re-entry guard tracks `(swing_high_id, swing_low_id)` pair identity — a non-starving design verified by unit test, including the edge case where a newer swing low outdates the prior swing high as the most-recent point and correctly flips the setup from long to short.

A 2023-only premise check looked marginally viable (+$55.87 net, 177 trades). The full 2021-2026 YTD window was run to check whether that held up.

## Full-Window Results — USD_JPY, M30/H4, 2021-2026 YTD, $80 fixed risk, spread included

**938 trades, 28.3% win rate, net -$5,093.72 (spread-included); -$1,376.90 (zero-spread).** Only 2 of 6 years (2023, 2025) were net positive; the other 4 were meaningfully negative. Zero-spread P&L is also negative overall, so this is not primarily a spread-cost story the way swing_structure_plugin was.

| Year | n | Spread-incl. P&L | Zero-spread P&L |
|---|---|---|---|
| 2021 | 174 | -$1,842.63 | -$686.59 |
| 2022 | 165 | -$1,424.83 | -$899.59 |
| 2023 | 177 | +$55.87 | +$687.19 |
| 2024 | 168 | -$1,614.31 | -$1,046.38 |
| 2025 | 171 | +$299.91 | +$776.88 |
| 2026 YTD | 83 | -$567.72 | -$208.40 |
| **Total** | **938** | **-$5,093.72** | **-$1,376.90** |

## Root Cause: Confirmed Signal-Quality Issue, Not a Mechanical Bug

By direction, the loss is concentrated almost entirely on the short side:

| Direction | n | Win rate | Realized R:R | Breakeven WR | EV/trade | Net P&L |
|---|---|---|---|---|---|---|
| Long | 401 | 30.4% | 2.32 | 30.2% | +$0.72 | +$288.86 |
| Short | 537 | 26.6% | 2.30 | 30.3% | -$10.02 | **-$5,382.58** |

Before accepting "shorts are just weaker," the SL/TP formula itself was checked for a directional asymmetry that could produce this gap mechanically rather than through entry quality. It does not exist: **theoretical R:R computed directly from raw entry/SL/TP3 prices is exactly 2.500 for both directions** (confirms the SL/TP construction is symmetric, no directional bug), and **realized R:R is nearly identical** (2.32 long vs. 2.30 short — a rounding-level difference). The SL and TP levels are placed correctly and consistently regardless of direction.

With R:R effectively equal, the entire result traces to win rate relative to each direction's own breakeven line. Long sits almost exactly at breakeven (30.4% actual vs. 30.2% required, +$0.72/trade — noise, not edge). Short sits meaningfully below its breakeven (26.6% vs. 30.3% required, -$10.02/trade), and that gap compounded across 537 trades accounts for essentially the entire -$5,382.58.

## Conclusion

**fib_retracement_plugin.py is rejected on USD_JPY M30/H4.** Neither direction demonstrates real edge — long is breakeven-adjacent rather than genuinely profitable, and short is a clear net-negative selectivity problem, not a mechanical SL/TP defect. The 61.8% Fibonacci retracement bounce, as designed, does not have sufficient predictive power on this pair/timeframe in either direction. This is a genuine "the idea doesn't work here" result rather than an implementation bug -- no fix (SL convention, TP multiple, etc.) is indicated the way it was for swing_structure_plugin, since the R:R symmetry rules out a structural cause.

---

# Donchian Swing vs. Donchian Intraday — Overlap and Redundancy Analysis

## Status: Swing shown to be a redundant, worse-performing echo of intraday (2026-07-01)

## Motivation

Both `swing` (Daily HTF / H4 LTF) and `intraday` (H4 HTF / H1 LTF) modes run the identical Donchian breakout signal, just at adjacent timeframes, on four shared pairs: GBP_USD, EUR_USD, USD_JPY, AUD_JPY. Following the same overlap-analysis methodology already applied to RSI vs. Donchian (see above), this checks whether running both modes on these pairs is genuine diversification or duplicated exposure to the same directional call.

## Overlap Analysis — 2021-2026 YTD, all 4 shared pairs

Framed relative to swing (the sparser signal), matching the RSI-Donchian convention:

| Finding | Result |
|---|---|
| Swing trading (pair, day) combos | 785 |
| Intraday trading (pair, day) combos | 3,165 |
| Days both fired on the same pair | 662 (**84.3% of swing's trading days**) |
| Same direction on overlap days | **638 of 662 (96.4%)** |
| Opposite direction | 20 (3.0%) |
| Median timing gap between same-direction trades on overlap days | **1.0 hour (100% within 24h)** |

Per pair, the pattern is consistent: overlap ranges 80.9%-87.9% of swing's trading days, same-direction agreement 95.7%-97.6%, median gap 1.0-2.0 hours (GBP_USD, EUR_USD, USD_JPY, AUD_JPY all individually confirmed, not just in aggregate).

**This overlap is far stronger than RSI-Donchian's** (84.3% vs. 54.6% of trading days overlapping; 96.4% vs. 88.9% direction agreement; median 1.0h vs. 9.0h timing gap) — expected, since swing and intraday are the *same* Donchian breakout signal at adjacent timeframes reading overlapping price structure, not two independently-derived signals.

## P&L Comparison on the 638 Same-Direction Overlap Instances

For each of the 638 occurrences, swing's actual trade was compared directly against intraday's first same-direction trade that day (the "would have already been taken" reference entry):

| Metric | Swing | Intraday |
|---|---|---|
| Total P&L (same 638 occurrences) | +$4,590.98 | **+$26,571.28** |
| Avg P&L per trade | +$7.20 | +$41.65 |
| Win rate | 33.4% | 45.9% |

Intraday captured **~5.8x more total profit than swing on the identical occurrences** — confirmed consistent per pair (swing's sum is lower than intraday's for every one of the 4 pairs, and net *negative* for AUD_JPY specifically: -$1,051.68 vs. +$4,023.78 on the same days):

| Pair | n | Swing P&L | Intraday P&L | Swing WR | Intraday WR |
|---|---|---|---|---|---|
| AUD_JPY | 161 | -$1,051.68 | +$4,023.78 | 26.1% | 40.4% |
| EUR_USD | 155 | -$110.08 | +$5,385.90 | 31.6% | 43.2% |
| GBP_USD | 148 | +$2,608.79 | +$9,591.28 | 37.2% | 54.1% |
| USD_JPY | 174 | +$3,143.96 | +$7,570.32 | 38.5% | 46.6% |

**Entry price, checked directly, explains why:** swing got a *worse* price than intraday's first entry 69.3% of the time (avg -18.6 pips, median -12.1 pips worse), versus only 16.1% of the time getting a better price. One assumption corrected in the process: swing was expected to always enter *after* intraday (slower HTF confirmation), but timing order was actually roughly split (swing after intraday's first entry 36.4% of the time, before it 48.6%, simultaneous 15%). The worse P&L is not fundamentally a timing-lag story -- it's that swing's wider Daily/H4-confirmed channel requires a more extended move to break in the first place, so its entry price is typically further from the move's origin regardless of exact entry ordering.

**Outcome correlation is only moderate (0.434), not near-1.0** -- swing is not a pure duplicate at the trade-outcome level. Both win 25.7% of the time, both lose 46.4%, but where they diverge it's asymmetric against swing: swing loses while intraday wins in 20.2% of cases, versus the reverse in only 7.7%.

## Conclusion

**Swing is not capturing a bigger move or a better price that intraday misses -- it is a slower, structurally worse-performing version of the same signal**, at the cost of a second set of spread and a second margin allocation for what is, 96.4% of the time, the same directional bet within about an hour of intraday's own entry. This is a stronger and more one-sided result than the RSI-Donchian overlap finding, which only showed correlated *exposure* without directly quantifying which side of the pair was performing worse on the same occasions.

**Recommendation: retiring swing on these 4 shared pairs (GBP_USD, EUR_USD, USD_JPY, AUD_JPY) in favor of running intraday alone is well-supported by this data.** Two mitigations were built regardless of that decision: `portfolio_state.py`'s `check_currency_exposure_cap()` (concentration cap) and the new `ModeOverlap` detection (flags same-instrument, same-direction positions across modes explicitly in the dashboard's Risk Monitor panel, rather than leaving this redundancy invisible). Whether swing is fully retired on these pairs, or kept only where it doesn't overlap with intraday, remains an open follow-up decision.

## Decision: Swing Retired on GBP_USD, EUR_USD, USD_JPY, AUD_JPY (2026-07-01)

Acting on the recommendation above, `donchian_plugin_swing`'s live pair list is changed from `[GBP_USD, USD_CAD, EUR_USD, USD_JPY, AUD_JPY]` to **`[USD_CAD]` only**. Swing no longer opens new positions on GBP_USD, EUR_USD, USD_JPY, or AUD_JPY -- intraday continues running unchanged on those 4 pairs, now without a redundant, worse-performing sibling process paying a second spread and a second margin allocation for materially the same directional call.

**USD_CAD is kept on swing, unaffected by this decision**, for two independent reasons: (1) it falls outside the overlap analysis entirely -- intraday does not trade USD_CAD (confirmed net negative there, -$6,848, see `donchian_plugin_intraday`'s own validation), so there is no redundant sibling signal to compare against or be capturing a worse version of; (2) swing's USD_CAD result was validated independently in this project's earlier per-pair Donchian testing, on its own merits, unrelated to this overlap question.

Any USD_JPY, GBP_USD, EUR_USD, or AUD_JPY position already open under swing at the time of this change (e.g. the live USD_JPY position, trade ID 37) is unaffected -- OANDA's own standing SL/TP orders manage it to close independently of which pairs the bot scans for new entries going forward.

---

# Intraday vs. Scalp30 (USD_JPY) — Overlap Analysis: Same Structural Non-Independence, Inverted Conclusion

## Status: Checked, no action taken -- structurally non-independent but NOT a worse-echo pattern (2026-07-01)

## Motivation

The swing/intraday finding above raised the same question one level down: intraday (H1/H4) and scalp30 (M30/H4) are both Donchian at adjacent timeframes on USD_JPY specifically -- the exact structural setup that caused swing/intraday's redundancy. This checks whether scalp30 is genuinely adding independent value on top of intraday's USD_JPY signal, or repeating the same pattern.

## Overlap Analysis — USD_JPY, 2021-2026 YTD

| Finding | Result |
|---|---|
| Intraday trading days | 794 |
| Scalp30 trading days | 1,085 |
| Days both fired | 792 (**99.7% of intraday's trading days**) |
| Same direction | 771 (97.3%) |
| Opposite direction | 0 (0.0%) |
| Median timing gap | **0.5 hours (100% within 24h)** |

This overlap is *tighter* than swing/intraday's (99.7% vs. 84.3% of trading days overlapping, 0% vs. 3% opposite-direction, 0.5h vs. 1.0h median gap). Structurally, intraday and scalp30 read almost the identical USD_JPY breakout on almost every trading day -- if anything, less independent than the swing/intraday pairing that was retired above.

## P&L Comparison on the 771 Same-Direction Occurrences -- Conclusion Inverts

| Metric | Intraday | Scalp30 |
|---|---|---|
| Total P&L | +$17,862.16 | **+$24,763.39** |
| Win rate | 38.1% | 41.5% |
| Avg win / avg loss / R:R | $189.64 / -$79.44 / 2.39 | $192.05 / -$81.36 / 2.36 |
| Entry price advantage | -- | better 61.7% of the time (avg +13.3 pips) |

**Unlike swing, scalp30 outperforms the slower sibling on the identical occurrences** -- roughly 39% more total P&L, a higher win rate, and a better average entry price (consistent with M30 catching the same breakout before it extends as far as it does by H1 close). Checked for outlier-driven distortion (the same rigor applied to every finding in this log): excluding each side's top 10 wins, scalp30's sum stays ahead throughout ($22,780 vs. $15,876 with top-10 excluded), and R:R is nearly identical between them (2.36 vs. 2.39), so this is a genuine, broad-based win-rate/entry-quality edge, not a few large trades inflating the total.

## Conclusion

**Structurally, this is the same non-independence pattern as swing/intraday -- arguably more extreme (99.7% vs. 84.3% overlap, 0% vs. 3% opposite-direction days).** But the value comparison inverts: scalp30 is not a slower, worse echo of intraday the way swing was of intraday -- it captures the shared USD_JPY edge *more* completely, not less. Running both is still largely one bet counted twice given the near-total overlap, so this is not independent diversification either -- but the faster/more granular signal is the stronger performer here, not the weaker one.

**No action taken, unlike the swing decision above, for two reasons:** (1) this dataset is the same one that already validated scalp30's USD_JPY edge in the first place (see `donchian_plugin_scalp30`'s entry in strategies.json, +$28,000.34/6yr) -- it is not new independent confirmation, so treating it as fresh grounds for a structural change would be circular; (2) intraday must keep running regardless for GBP_USD, EUR_USD, and AUD_JPY, where scalp30 does not operate at all (scalp30 is an explicitly USD_JPY-specific finding, rejected on GBP_USD and AUD_JPY at the identical configuration) -- so "retiring intraday" is not a clean parallel to retiring swing; at most it would mean excluding USD_JPY specifically from intraday's pair list, a narrower and lower-urgency change than swing's retirement, which is flagged here as a candidate for a future decision rather than acted on now.

## Interpretation Caveat: Descriptive, Not Prescriptive

Explicitly, unlike the swing/intraday finding above: **this comparison should be read as descriptive, not prescriptive.** It describes a real fact -- both modes are reading nearly the same USD_JPY signal, and scalp30's version happened to perform better in the very data that validated scalp30 in the first place. It should NOT be read as grounds to retire intraday's USD_JPY exposure on this basis alone, the way the swing/intraday finding was acted on. The entangled-validation problem ((1) above) means "scalp30 beat intraday here" and "scalp30 is a validated USD_JPY edge" are not two independent facts corroborating each other -- they are substantially the same fact viewed twice. A genuine retirement decision here would need evidence that doesn't share this circularity (e.g. scalp30's edge holding up on data that postdates its own validation window, or an out-of-sample check), not a repeat of the same historical trades already used to justify keeping scalp30 live.

Visibility for this pairing (and any other mode pair that ends up both open on the same instrument+direction) is handled live by `portfolio_state.py`'s `ModeOverlap` detection, which is generic -- grouped purely by (instrument, direction), with no swing/intraday- or intraday/scalp30-specific logic -- so it already flags an intraday+scalp30 USD_JPY overlap the same way it flagged swing+intraday, with no code change required. Confirmed via direct test and a live check against the real account (correctly empty, since only one USD_JPY position was open at check time).

---

# Fibonacci Retracement: Volume-Profile Confluence Gate — Rejected at Both Tested Windows

## Status: REJECTED (2026-07-01)

## Motivation

`fib_retracement_plugin.py` was already rejected on USD_JPY M30/H4 in its ungated form (see "Fibonacci Retracement Bounce Plugin — Rejected, Pure Signal-Quality Failure" above): neither long nor short showed real directional edge over the full 2021-2026 window, and the R:R symmetry check ruled out a mechanical SL/TP cause. Before fully closing out the idea, one more variant was tested: gating the 61.8% touch-and-bounce entry on volume-profile confluence -- only firing if the retracement level also falls inside (or near) a High Volume Node from a rolling M30 volume profile, reusing the same `build_volume_profile()` machinery as `strategy.py`'s built-in filter 5. Everything else (swing detection, SL placement, TP) was kept byte-for-byte identical to the ungated plugin, so any change in results is attributable to the gate alone.

## Results — USD_JPY, M30/H4, 2023, spread included, $80 fixed risk

| | Ungated (baseline) | Gated, window=50 | Gated, window=100 |
|---|---|---|---|
| Trades | 177 | 171 | 176 |
| Win rate | 30.5% | 28.7% | 30.7% |
| Net P&L | +$55.87 | **-$817.99** | +$137.86 |

**Window=50: clear negative.** Diffing the trade logs found the gate disproportionately filtered out *winning* trades rather than losing ones. Of the 12 trades it removed, 6 were "replaced" by a later touch-and-bounce on the same swing structure (an interaction with the re-entry guard: blocking the first touch leaves `_last_used_pair_id` unconsumed, letting a subsequent touch on the same structure fire instead -- roughly P&L-neutral, +$21.72 net). The other 6 were genuinely eliminated with no replacement, and 5 of those 6 were winners -- removing +$895.58 of net-positive P&L. This accounts for essentially the entire -$873.86 swing from baseline.

**Window=100: nominally positive, but the effect is statistically thin.** Only 3 trades removed, 2 added back via the identical cascade mechanism (both near-neutral, +$0.69 and +$0.76 differences). The entire +$81.99 improvement over baseline traces to exactly **one** genuinely-eliminated trade (2023-11-02, long, -$80.53 -- a clean loser removed with nothing lost in its place). One trade out of 177 (1.7% of the population) is not a basis for concluding the gate has real selective power -- it is consistent with "the gate barely touches anything, and this once the coin landed on a loser rather than a winner," which is indistinguishable from noise at this sample size.

## Conclusion

**Volume-profile confluence does not demonstrate real selective power for Fibonacci 61.8% retracement entries on USD_JPY M30/H4, at either tested window.** Window=50 actively hurts (removing winners disproportionately); window=100 shows a technically-positive result driven entirely by a single trade, which is not evidence of a robust edge. Combined with the base plugin's own rejection (no directional edge in either long or short, ruled out as a mechanical bug via the R:R symmetry check), this closes out the Fibonacci retracement approach on USD_JPY M30/H4: the SL/TP construction was structurally sound throughout (correctly symmetric R:R at every stage tested), but no variant of the entry logic tested -- the base 61.8% touch-and-bounce, nor gating it on volume-profile confluence -- produced a real, robust edge.

---

# MA Pullback and Trend-Origin Pullback (GBP_USD) — Both Rejected: Mirror-Image Regime Dependence

## Status: BOTH REJECTED on GBP_USD M30/H4 (2026-07-01)

## The two plugins

Two independent pullback-style candidates, built separately (git: `ma_pullback_plugin.py` at 40f834a, `trend_origin_pullback_plugin.py` at dcfd258 -- no shared lineage, both still in the repo). Structurally different strategies that share only the word "pullback":

| | MA pullback | Trend-origin pullback |
|---|---|---|
| Trend filter | HTF close vs. 50 EMA (indicator) | Consecutive HH/HL or LH/LL swing structure (fractals) |
| Entry trigger | LTF candle touches its own 20 EMA and reclaims it | LTF candle overlaps the zone between the two most recent swing points, closes beyond the trend origin |
| SL | Just beyond the pullback candle's extreme + 2-pip buffer | Beyond the swing point where the current leg began |
| Avg SL width | 13.6 pips (candle-sized) | 64.4 pips (structure-sized) |

## Full-window results — GBP_USD, M30/H4, 2021-2026 YTD, spread included, $80 fixed risk

**MA pullback: 5,459 trades, 32.0% WR, net +$2,593.14.** All year x direction cells clear min-N(10) by wide margins (smallest cell n=172).

**Trend-origin pullback: 1,222 trades, 30.4% WR, net +$1,513.68** (zero-spread +$4,281.78, spread cost $2.27/trade). All cells clear min-N (smallest n=44). Long -$1,576.52 (29.0% WR) vs short +$3,090.20 (31.7% WR) -- note this is the OPPOSITE directional asymmetry from the same plugin's USD_JPY 2023 premise check, where long carried the edge (+$915 long / -$291 short), itself a regime-dependence flag.

| Year | MA pullback net | Trend-origin net |
|---|---|---|
| 2021 | **+$6,307.29** | -$1,325.74 |
| 2022 | **+$4,730.49** | -$2,460.92 |
| 2023 | +$857.09 | -$2,164.30 |
| 2024 | -$3,536.71 | **+$3,866.14** |
| 2025 | -$1,676.24 | **+$2,683.78** |
| 2026 YTD | -$4,088.78 | +$914.71 |
| **Total** | **+$2,593.14** | **+$1,513.68** |

## The key finding: near-perfect mirror images on the same pair

Both plugins post positive full-window totals, and both fail for the same structural reason viewed from opposite ends: **each one's entire net edge lives in one half of the window, and they split the window between them almost exactly.** MA pullback made all its money 2021-2023 and has been negative every year since; trend-origin lost money every year 2021-2023 and has been positive every year since. Neither result is noise-driven -- trend-origin's profitable years pass the concentration check (top-5 wins are only 6.4-6.9% of gross wins in 2024/2025, broad-based), and MA pullback's yearly cells are all n>=172 -- these are real, regime-specific edges, not statistical artifacts.

MA pullback's shape is the more decisively disqualifying of the two: its yearly P&L deteriorates monotonically across the entire window (+$6,307 -> +$4,730 -> +$857 -> -$3,537 -> -$1,676 -> -$4,089 in half a year of 2026), meaning whatever it exploited has been decaying continuously and is most-broken in the most recent data. Trend-origin's recent years are its good ones, which is the better-facing trajectory -- but committing to it means betting the 2021-2023 regime (three consecutive losing years, -$5,951 combined) doesn't return, with no principled reason to believe it won't.

## Conclusion

**Both rejected on GBP_USD M30/H4.** A positive 6-year total is not the validation bar -- consistency across regimes is (the standing benchmark, Donchian scalp30 on USD_JPY, is +$28,000/6yr with zero min-N flags -- CORRECTION 2026-07-01: this sentence originally said "no negative years," which is false; the original validation entry above correctly records 2025 at -$943 and 2026 YTD at -$3,324. The erroneous phrase was introduced in this entry when citing the benchmark from memory, not from the source record. Reconciliation details in the scalp30 record-reconciliation entry below). Two structurally unrelated pullback strategies each capturing exactly one half of the same window is a useful negative result: it suggests GBP_USD's regime shift around 2023/2024 flipped which *kind* of pullback works, and any pullback-family strategy validated on a sub-window of this pair should be presumed regime-dependent until shown otherwise on the full window. Trend-origin pullback remains untested on the full window for USD_JPY (2023-only premise check: +$624.02, 223 trades, 30.5% WR -- long-side-carried), which is the more promising remaining avenue for that plugin.

---

# Trend-Origin Pullback — USD_JPY Full Window: Strong Long-Side Result

## Status: Full-window tested, promising long-side edge; diligence in progress (2026-07-01)

## Results — USD_JPY, M30/H4, 2021-2026 YTD, spread included, $80 fixed risk

**1,185 trades, 34.3% win rate, avg SL 77.5 pips, net +$14,136.28** (zero-spread +$16,199.00; spread cost $2,062.72 total, $1.74/trade -- low, because the wide origin-anchored SL keeps position sizes small under fixed-risk sizing). 2023 reproduces the earlier premise check exactly (+$624.02, n=223). All 12 year x direction cells clear min-N(10) -- zero flags (smallest cell n=31). Git commit dcfd258.

| Year | n | Net P&L | Long n / WR / P&L | Short n / WR / P&L |
|---|---|---|---|---|
| 2021 | 233 | +$1,058.81 | 127 / 37.8% / +$2,182.59 | 106 / 25.5% / -$1,123.78 |
| 2022 | 205 | **+$8,160.39** | 126 / 55.6% / +$9,042.20 | 79 / 26.6% / -$881.81 |
| 2023 | 223 | +$624.02 | 134 / 32.1% / +$915.22 | 89 / 28.1% / -$291.20 |
| 2024 | 204 | +$4,285.44 | 119 / 42.0% / +$3,764.92 | 85 / 31.8% / +$520.52 |
| 2025 | 210 | +$103.01 | 104 / 34.6% / +$1,107.63 | 106 / 25.5% / -$1,004.62 |
| 2026 YTD | 110 | -$95.39 | 79 / 38.0% / +$1,851.13 | 31 / 6.5% / -$1,946.52 |
| **Total** | **1,185** | **+$14,136.28** | **689 / 40.2% / +$18,863.69** | **496 / 26.0% / -$4,727.41** |

## Findings

**The long side is the entire edge, and unlike every regime-split result above, it is consistent across all six years:** long is positive every single year of the window, including the 2021-2023 stretch where this same plugin lost money on GBP_USD and where the aggregate result here is only carried by longs against negative shorts. Short is negative in 5 of 6 years (only 2024 marginally positive) -- the same short-side-weakness pattern as fib_retracement on this pair.

**Robustness checks passed:** 2022 (the +$9,042 long year at 55.6% WR) contributes over half the long side's total, but the concentration check shows it is broad-based, not outlier-driven (top-5 wins are 5.8% of 2022's gross wins; 7.0% for 2024). Excluding 2022 entirely, the long side still earns +$9,821 over the remaining 5 years with every year positive -- the edge does not depend on the single best year.

**Open diligence before any live/Bot-D decision:** (1) a long-only variant would add USD_JPY long exposure that plausibly overlaps with Donchian scalp30's existing validated USD_JPY signal -- an overlap/redundancy check (same methodology as the swing/intraday and RSI analyses above) is required first; (2) per-year Kaufman efficiency ratio for USD_JPY, to establish whether the long edge merely tracks trend-quality years or genuinely survives choppy ones.

## Diligence Results: Overlap vs. Donchian Scalp30, and Kaufman ER (2026-07-01)

**Overlap vs. Donchian scalp30 (USD_JPY, 2021-2026 YTD, same methodology as the RSI and swing/intraday analyses):**

| Finding | Result |
|---|---|
| Trend-origin trading days | 902 |
| Donchian scalp30 trading days | 1,085 |
| Days both fired | 680 (75.4% of trend-origin's days) |
| Same direction on overlap days | **463 (68.1%)** |
| Opposite direction | **193 (28.4%)** |
| Median timing gap (same-direction) | 6.0h |
| Long-only view | 336 of 535 trend-origin long days (62.8%) coincide with a Donchian long day |

Context: the overlaps that killed prior candidates were 88.9% (RSI/Donchian), 96.4% (swing/intraday), and 97.3% (intraday/scalp30) same-direction agreement with 0.5-9h median gaps. **68.1% agreement with 28.4% outright opposite-direction days is meaningfully more independent** -- trend-origin frequently takes the other side of what Donchian is doing on the same day. A long-only variant still shares ~63% of its trading days with a Donchian long, so it is partial diversification, not full independence -- but it is not the "same signal twice" pattern.

**Kaufman efficiency ratio per year (USD_JPY H4 closes, full-year ER) vs. the long side's P&L:**

| Year | ER | Long P&L |
|---|---|---|
| 2021 | 0.0700 (highest) | +$2,183 |
| 2022 | 0.0401 | +$9,042 |
| 2023 | 0.0265 | +$915 |
| 2024 | 0.0393 | +$3,765 |
| 2025 | **0.0021** (lowest by 10x) | **+$1,108** |
| 2026 YTD | 0.0439 | +$1,851 |

**The long edge scales with trend quality but does not depend on it.** The two best P&L years (2022, 2024) are high-ER years -- but 2025, the choppiest year in the window by an order of magnitude (USD_JPY net move 0.83 JPY over a 403-JPY total path), still produced a positive long side (+$1,108). The aggregate 2025 figure (+$103) looked like near-failure, but that was shorts (-$1,005) dragging a healthy long year down. Profiting most in trend years while surviving the worst chop year in the sample is the desired profile: trend quality drives the upside, not the survival.

---

# Bot D Candidate: trend_origin_pullback_long_plugin.py — Post-Hoc Long-Only Variant, Probation Terms

## Status: BUILT, awaiting deployment approval; validation = forward paper performance ONLY (2026-07-01)

## What it is, and what it is not

`trend_origin_pullback_long_plugin.py` is `trend_origin_pullback_plugin.py` with the short branch removed and nothing else changed -- verified by direct test: byte-identical long signals to the parent on identical input (entry, SL, TP all match to machine precision), and returns None where the parent shorts a mirrored LH/LL structure.

**This is explicitly a post-hoc directional selection from the tested long+short design, NOT an independently validated strategy.** The same 2021-2026 history that revealed the long/short asymmetry (long +$18,864, positive every year; short -$4,727, negative 5 of 6) was used to select this variant -- so no backtest of this file on that history can count as validation; it would be reading the answer key. The stated mechanical rationale -- shorts fight the structural yen-weakness backdrop (BoJ policy divergence) that defined the entire window -- is recorded as a HYPOTHESIS, not an established fact. If that backdrop changes (e.g. sustained BoJ tightening), the premise for excluding shorts weakens and the long side's tailwind may too.

**Validation criterion: forward paper performance only**, under the probation terms below, which are defined NOW, before any forward data exists, so the evaluation cannot be moved after the fact.

## Probation Terms (defined 2026-07-01, pre-deployment)

Backtest signal frequency: 689 long trades / 5.5 years ~= 125/year on average, but recent years run lower (2025: 104; 2026 H1: 79, annualizing ~158 but with high variance) -- call it roughly 90-125/year expected forward.

- **Evaluation trigger: 60 closed trades OR 6 months of paper trading, whichever comes first.** At the expected frequency, 60 trades should take roughly 5-7 months, so the two limits are deliberately aligned; the trade-count trigger governs if signal frequency runs hot, the calendar trigger if it runs cold (a cold period itself being informative).
- **PASS: net P&L > 0 (spread included) AND win rate >= 32%.** 32% is the floor of the backtest's yearly long-WR band (32.1%-55.6%, overall 40.2%). Statistical honesty note, recorded up front: at n=60, a true-38% strategy lands anywhere in roughly 26%-50% (2 sigma), so the WR test alone is coarse -- this is why the criterion is conjunctive (profitable AND in-band), and why a pass extends probation-level monitoring rather than granting permanent status.
- **FAIL-AND-REMOVE: net P&L <= 0 at evaluation, OR win rate < 28% (below the 2.5R breakeven line of ~28.6%), OR at any earlier point a drawdown exceeding 15 x $80 = $1,200 from the strategy's own equity peak** (early-kill clause: roughly double the worst losing streak a 38%-WR/2.5R process should plausibly produce in 60 trades). Removal means the fourth process is stopped and the plugin archived with a final write-up, same as every other rejected candidate.
- Ambiguous zone (profitable but WR 28-32%, or unprofitable but WR >= 32%): probation extends one more 60-trade/6-month cycle, once; a second ambiguous result counts as FAIL.

## Deployment status

DEPLOYED 2026-07-01 (task \Rhyme\Rhyme-Pullback30, mode pullback30, 120s logon stagger -- originally deployed as mode "botd"/task Rhyme-BotD and renamed the same day: operational mode strings describe the strategy/timeframe, "Bot D" remains the portfolio-slot name in this log), with the deployment itself producing a material discovery -- see below.

## NFA FIFO Discovery: Cap-2 Stacking Is Broker-Unexecutable on This Account (2026-07-01)

Bot D's very first order (a valid HH/HL long, 22,000 units USD_JPY, permitted by every one of our gates including the newly built position cap of 2 and margin-utilization cap) was created and INSTANTLY CANCELLED by OANDA in the same transaction batch: order 41, cancel 42, reason FIFO_VIOLATION_SAFEGUARD_VIOLATION -- the NFA FIFO compliance rule on this US practice account rejects any second same-instrument open trade carrying its own attached SL/TP while trade 37 held USD_JPY.

**Consequence: the max-2 per-instrument stacking design (built, unit-tested, committed at 202a8f8 the same day) is unexecutable on this account.** MAX_POSITIONS_PER_INSTRUMENT reverted to 1 to match broker reality (eba08ec); the count-based gate implementation is retained so a future account type is a one-line change. Two code fixes came out of the incident: _print_fill previously logged the cancelled order as ">> FILLED @ ? trade_id=?" (now checks for a real orderFillTransaction, logs cancellations with the broker's reason at funnel visibility, and no longer writes cancelled orders to paper_trades.csv -- the one bogus row it had written was removed), and the broker layer gained per-process account parameterization (broker.set_account() / main.py --account).

## Probation Amendment: Isolated Account Required (2026-07-01)

Bot D now runs against the SEPARATE practice sub-account **101-001-39634331-001** (token shared, account ID overridden per process via --account), while the three Donchian modes remain on -002. Rationale: on a shared account, Bot D's USD_JPY orders are FIFO-cancelled whenever any other mode holds USD_JPY, which would make its forward sample FIFO-CONDITIONED -- it could only ever trade when the Donchian modes happened to be flat, a selection bias on top of the strategy's own signal. **The probation clock (60 trades or 6 months, terms above) starts only once Bot D is running against the isolated account** -- specifically once that account is funded: as of deployment, -001 has a $0.00 balance (Bot D correctly sizes to zero and skips: "lot size too small"), so the clock has NOT started. Trades taken before isolation (there were none -- the single pre-isolation order was broker-cancelled) would not have counted.

**CLOCK STARTED 2026-07-01 (~18:35 EDT / 22:35 UTC):** -001 funded to $4,078.96, matching -002 to the cent, verified via AccountSummary on both accounts. Bot D was already running against -001 at funding time (its 18:30 cycle read the pre-funding $0.00; the 19:00:05 cycle is the first against the funded balance). **Probation evaluation is therefore due at 60 closed trades or 2027-01-01, whichever comes first**, under the unchanged terms above.

Known blind spot, accepted deliberately: the cross-mode gates (position cap, margin utilization, currency exposure, global risk cap) are all per-account -- Bot D's process sees only -001 and the Donchian processes see only -002, so no gate spans both accounts. At current sizes this is acceptable (the accounts are independently margined by OANDA); revisit if either account's sizing changes materially.

---

# M30 Stop-Distance Pair Sweep — Search Closed (2026-07-01)

## Status: COMPLETE; no untested candidates remain above the bar

The broad pair sweep begun earlier (filter the full OANDA universe, then run the M30 stop-distance diagnostic across the survivors) is now consolidated and closed. The universe fetch had completed earlier (all 68 currency pairs on this account, live spread + 2021-history check, `oanda_pairs_raw.json`); the diagnostic had only ever run in interactive batches with no saved table. The full consolidated run now lives at `results/stop_distance_sweep_table.csv`.

**Universe: 23 of 68 pairs pass the filter** (spread <= 3.0 pips AND full 2021-2026 history), 8 of them exotics/SGD crosses outside the working list. Diagnostic: median natural M30 stop distance in pips for ATR(14), 20-candle swing edge, and nearest confirmed Williams fractal, over 2023, plus the fraction of candles whose best-method stop exceeds 18 pips (the threshold below which fixed-$80-risk sizing makes spread cost dominate -- the mechanism that killed RSI and buffer-SL swing structure).

**Only three pairs qualify at the pre-set ~30% / 18-pip bar, and all three are already fully tested:**

| Pair | Best median | %>18p | Spread | Status |
|---|---|---|---|---|
| EUR_AUD | 16.6p | 34.0% | 2.9p | Tested at M30 Donchian, rejected (spread-eaten) |
| EUR_JPY | 15.6p | 30.4% | 2.8p | Tested at M30 Donchian, rejected (net negative) |
| USD_JPY | 14.9p | 29.7% | 1.5p | The validated workhorse (Donchian scalp30, pullback30) |

USD_JPY ranks third on raw stop width but first by a wide margin on stop-width-to-spread ratio (~10:1 vs ~5.6-5.7:1 for the two pairs above it) -- consistent with it being the only pair where the M30/H4 configuration ever validated. Everything from USD_CAD (9.9p median, 2.5% >18p) down lives in single-digit-median territory where spread cost dominates fixed-risk sizing. The bottom three exotics (HKD_JPY 1.9p, ZAR_JPY 1.4p, TRY_JPY 1.0p) are artifacts of pip-denomination conventions, not genuinely low-volatility pairs.

**Conclusion: the M30 wide-stop pair search is closed.** No untested pair in the filtered universe offers a structurally better stop-width/spread profile than what has already been mined; future M30 candidates must come from new signal ideas on the already-qualified pairs, not from new pairs.

---

# Trend-Origin Pullback on USD_CAD — Rejected As-Designed; the Cross-Pair Long-USD Hypothesis

## Status: USD_CAD REJECTED, no long-only variant; hypothesis recorded (2026-07-01)

## Results — USD_CAD, M30/H4, 2021-2026 YTD, spread included, $80 fixed risk

**1,219 trades, 31.8% WR, avg SL 49.7 pips, net +$4,077.05** (zero-spread +$8,831.57; spread cost $3.90/trade -- notably higher than USD_JPY's $1.74: tighter structural stops on a wider-spread pair). All 12 year x direction cells clear min-N(10).

| Year | n | Net P&L | Long P&L | Short P&L |
|---|---|---|---|---|
| 2021 | 220 | -$279.63 | +$182.68 | -$462.31 |
| 2022 | 208 | **-$3,028.72** | **-$1,068.32** | -$1,960.40 |
| 2023 | 233 | +$487.84 | +$1,338.63 | -$850.79 |
| 2024 | 228 | +$2,693.74 | +$3,141.70 | -$447.96 |
| 2025 | 234 | +$2,139.08 | +$2,714.83 | -$575.75 |
| 2026 YTD | 96 | +$2,064.75 | +$2,651.42 | -$586.68 |
| **Total** | **1,219** | **+$4,077.05** | **+$8,960.94 (35.9% WR)** | **-$4,883.89 (27.5% WR)** |

**Rejected as-designed: 2 of 6 years negative** (2021 marginal, 2022 badly), failing the consistency bar. **Explicitly, no long-only variant is built for USD_CAD**: it would be a second post-hoc directional selection, with a strictly weaker record than the USD_JPY case that justified pullback30 -- USD_JPY's long side was positive every single year; USD_CAD's long side has a genuine losing year (2022, -$1,068). Repeating the post-hoc carve-out on a weaker record would be curve-fitting with extra steps.

## The Cross-Pair Long-USD Pattern — a Hypothesis, Deliberately Under-Claimed

Across the three pairs now tested with this plugin, the profitable direction is in every case the LONG-USD direction:

| Pair | USD leg | Profitable direction | = USD direction |
|---|---|---|---|
| USD_JPY | base | long (+$18,864 / short -$4,727) | long USD |
| USD_CAD | base | long (+$8,961 / short -$4,884) | long USD |
| GBP_USD | quote | short (+$3,090 / long -$1,577) | long USD |

This reframes pullback30's BoJ-policy-divergence rationale into something broader: the plugin family may simply be a USD-bull-regime instrument, riding the structural dollar strength of the 2021-2026 window, with the "trend-origin" mechanics determining HOW it rides rather than WHETHER there is something to ride.

**Caveat, recorded up front: three pairs sharing one macro window and one USD leg constitute closer to ONE observation than three.** The three results are not independent confirmations -- they are one dollar-strength regime viewed through three lenses. A genuine test of the hypothesis requires either a no-USD-leg pair (where the pattern predicts no stable directional asymmetry -- EUR_JPY run in progress as this is written) or a dollar-weakening period (which no pair in this window can provide historically).

## Probation Amendment for pullback30 (Bot D slot)

**The forward paper period now doubles as a live test of the long-USD hypothesis.** If pullback30's long-USD_JPY edge is substantially a dollar-regime artifact rather than a structure-reading edge, a sustained dollar-weakening stretch is the strategy's true stress test -- and forward performance during such a stretch should be read as evidence about the hypothesis, not just about the strategy. Concretely: if a USD-bear regime arrives during probation and pullback30 degrades badly, that is the expected outcome under the hypothesis and argues for retirement even if the aggregate probation numbers squeak past the pass bar; conversely, surviving a genuine USD-bear stretch would be the strongest possible evidence the edge is structural. Probation terms (60 trades / 6 months / pass-fail criteria) are otherwise unchanged.

## Sweep-Scope Nuance (amending the pair-sweep conclusion above)

The stop-distance sweep's conclusion ("no untested pair offers a better profile") applies to CANDLE-SCALE stop methods -- ATR(14), 20-candle swing edge, nearest fractal -- which is what it measured. Structural-stop strategies price pairs differently: USD_CAD sits far below the sweep's 18-pip bar on candle-scale stops (9.9p median, 2.5% >18p), yet trend-origin's origin-anchored SL averaged ~50 pips there, comfortably escaping the spread-dominance trap the sweep measures. The sweep closes the search for SCALP-style candidates; it does not price the universe for structural-stop designs, which must be evaluated per-strategy.

---

# EUR_JPY Probe — Long-USD Hypothesis Refuted As Stated; Reframed as Persistent-Macro-Trend-Following

## Status: PROBE COMPLETE (2026-07-01). EUR_JPY itself REJECTED (probe, not candidate). Hypothesis refined.

## Results — trend-origin pullback (as-designed), EUR_JPY, M30/H4, 2021-2026 YTD, spread included, $80 fixed risk

**1,220 trades, 33.0% WR, avg SL 79.7 pips, net +$10,222.62** (zero-spread +$12,858.05; spread cost $2.16/trade). All 12 year x direction cells clear min-N(10).

| Year | n | Net P&L | Long P&L | Short P&L |
|---|---|---|---|---|
| 2021 | 220 | +$1,872.50 | +$2,670.60 | -$798.10 |
| 2022 | 238 | **+$7,874.56** | +$7,586.67 | +$287.89 |
| 2023 | 220 | +$2,964.32 | +$2,417.72 | +$546.61 |
| 2024 | 214 | +$3,051.83 | +$1,993.07 | +$1,058.77 |
| 2025 | 227 | **-$3,373.21** | -$9.21 | -$3,364.01 |
| 2026 YTD | 101 | **-$2,167.38** | -$31.64 | -$2,135.73 |
| **Total** | **1,220** | **+$10,222.62** | **+$14,627.19 (37.8% WR)** | **-$4,404.57 (26.9% WR)** |

**EUR_JPY verdict: REJECTED -- this was a hypothesis probe, not a candidate search, and it would fail as a candidate regardless: two consecutive negative recent years (2025, 2026 YTD), with the long edge dying exactly when the yen-weakness trend broke** (long: four strongly positive years 2021-2024, then -$9 and -$32 -- not losses, extinction).

## Hypothesis Refinement

The long-USD hypothesis predicted NO stable directional asymmetry on a no-USD-leg pair. EUR_JPY instead shows the same strong long-side asymmetry as the USD pairs -- **the hypothesis as stated is refuted**. The refinement that fits all four pairs:

| Pair | Profitable direction | = which macro trend |
|---|---|---|
| USD_JPY | long | short-yen |
| EUR_JPY | long | short-yen |
| USD_CAD | long | long-dollar |
| GBP_USD | short | long-dollar |

**Reframed: the trend-origin pullback family is a PERSISTENT-MACRO-TREND instrument -- the profitable direction is the pair's dominant secular trend of the window (yen weakness where there is a yen leg, dollar strength where there is not), and the edge goes to ZERO when that trend structure breaks.** EUR_JPY 2025-2026 is the empirical demonstration: when yen weakness stalled, the long side didn't reverse into losses -- it flatlined (-$9, -$32), because the HH/HL structure the entry requires simply stopped forming. Supporting detail: EUR_JPY shorts were mildly positive 2022-2024, a less one-sided asymmetry than any USD pair -- consistent with trend-following-in-disguise rather than a directional constant.

This is the more general and more concerning framing for pullback30 than the original BoJ/long-USD version: it suggests the plugin (and possibly the whole Donchian family, which the passport retro-fill already flagged as sharing the 2021-2026 macro window) profits wherever a big structural trend existed, and is directionless where it didn't.

**pullback30's falsifying condition, restated (supersedes the dollar-weakening version):** a sustained YEN-STRENGTHENING stretch is the true stress test -- pullback30 trades USD_JPY longs, i.e. short-yen. And the failure mode to watch for is NOT drawdown: per the EUR_JPY preview, it is the edge going to zero (signal frequency and P&L both flatlining as HH/HL structure stops forming). The probation early-kill ($1,200 drawdown) will not catch this mode; the 6-month calendar trigger is the backstop that will.

---

# Scalp30 Record Reconciliation — the "No Negative Years" Claim Was a Citation Error, Not a Data Problem

## Status: RESOLVED (2026-07-01)

## What was reconciled

The GOVERNANCE.md retro-fill flagged an apparent contradiction: RESEARCH_LOG described Donchian scalp30 USD_JPY as "+$28,000/6yr with no negative years," while the backtest CSVs show 2025 at -$942.81 and 2026 YTD at -$3,323.79.

## Findings

**The original validation record was right all along; the contradiction was introduced later by a careless citation.**

1. **Provenance of the CSVs:** all six scalp30 per-year CSVs carry meta.json provenance from git commit `bf9d732`, run 2026-07-01 ~01:40 UTC -- the original validation run itself. The retro-fill and the original validation read the SAME files.
2. **The original validation entry never claimed no negative years.** It states, verbatim: "USD_JPY is positive in 4 of 6 years (2021 +$6,906, 2022 +$15,413, 2023 +$3,376, 2024 +$6,572; only 2025 -$943 and partial 2026ytd -$3,324 negative)." The +$28,000.34 total, 2,719 trades, 33.5% WR, and zero min-N flags are all accurate and reproduce exactly.
3. **The false phrase entered once, later the same day**, in the MA-pullback/trend-origin GBP_USD rejection entry, where the scalp30 benchmark was cited from memory as having "no negative years" instead of from the source record. That sentence is now corrected in place with a dated note.
4. **Fresh re-run at current HEAD reproduces the record exactly:** 2025 -> n=478, net **-$942.81** (identical to the dollar and cent); 2026 to 06-30 -> n=229, net **-$3,323.79** (identical -- note the original run's window ended 2026-06-30, not 07-01; extending one day to 07-01 gives n=232, net -$2,600.46, the difference being July 1's three additional trades). No code change since validation altered the results.

## Mechanism, stated plainly

This was a **citation-drift error**: a summary sentence written from memory upgraded "positive in 4 of 6 years" to "no negative years" while citing a benchmark in passing, and the false version then read as authoritative because it lived in the same log as the true one. No backtest, CSV, or code discrepancy existed at any point. The correct characterization of the standing benchmark is: **+$28,000.34 over 6 years, 33.5% WR, zero min-N flags, positive in 4 of 6 years, with both most-recent periods negative (2025 -$943, 2026 YTD -$3,324) -- a deteriorating recent trajectory that is the flagship's biggest open risk** (as GOVERNANCE.md's passport now records).

Process lesson recorded: benchmark citations in new entries should quote the source entry's numbers, not summarize them from memory -- the retro-fill audit caught this one precisely because it went back to the CSVs instead of trusting prose.

---

# Donchian Swing (USD_CAD) — RETIRED

## Status: RETIRED 2026-07-01 (process stopped, \Rhyme\Rhyme-Swing task deleted)

## Rationale

The GOVERNANCE.md retro-fill showed swing/USD_CAD would fail passport boxes 1-3 if proposed today, and the grandfather review confirmed retirement over hospice:

- **Box 1 (marginal):** +$292.53 total over 6 years on 225 trades (33.3% WR) -- barely positive.
- **Box 2 (fail):** 3 min-N failures (2021/2022/2024 short cells at n=6/4/7).
- **Box 3 (fail):** 3 of 6 years negative; 2025 and 2026's results are single-trade artifacts (top-5 win concentration 91% and 89%).
- **1%-compounding:** -20.3% max drawdown for a 1.01x final multiple -- six years of trading for +1% total equity growth. Its sole portfolio argument (only non-USD_JPY-correlated exposure) is void at that multiple: it diversified into nothing.
- **Box 7 (fail):** third copy of the Donchian breakout behavior; under the persistent-macro-trend reframe, not a distinct behavior at all.

Its "validated independently" status at the time swing was cut to USD_CAD did not survive re-examination under current standards -- the grandfathered exemption is closed rather than extended.

## Retirement convention (adopted here, applies to all future retirements)

**Run-off:** retirement stops new entries immediately (process stopped, scheduled task deleted); existing open positions run to their standing OANDA SL/TP orders and are NOT closed early. Rationale: these bots only ever OPEN positions -- exits are entirely broker-side standing orders placed at entry time -- so early manual closure would inject a discretionary exit the validated design never had, realizing an outcome the strategy would not have produced. The retired strategy's final P&L record therefore includes its run-off exits.

Applied to swing: its one open position (trade 37, USD_JPY 22,000 long @ 162.807 from the pre-retirement 5-pair era, SL 162.102 / TP 164.146) runs off to its standing orders. No other swing positions were open.

## Roster after retirement

Three live processes, all under pre-registered governance, none grandfathered: Donchian intraday (5 pairs, -002), Donchian scalp30 (USD_JPY, -002), pullback30 (USD_JPY, -001, probation). USD_CAD exposure: none (intraday tested it net-negative; no other strategy trades it).

## Addendum (2026-07-02): corrected-harness record — retirement REINFORCED

The record above was produced by the pre-fix harness (warm-up bug, diagnosis 631de22, fix 85e4b67). At swing's D-granularity HTF the bug was at its worst: the per-year warm-up dead zone silenced roughly the first 5 months of every calendar-year segment, so the retirement record saw barely more than half the strategy's actual signals. The corrected-harness record (`corrected_f86d9f4_swing_2021-2026ytd.csv`): **376 trades, 24.7% WR, net −$4,759.73** — a SIGN FLIP from +$292.53/225 — with 4 of 6 periods negative (2022 −$1,624, 2023 −$1,929, 2025 −$1,533), fixed-$80 maxDD −$6,404, 1%-compounding maxDD −56.5% for a **0.53x final multiple**. What actually happened over 2021–2026 was not "six years for +1%"; it was six years for −47% at 1% compounding. No action needed — already retired — but the retirement now rests on a decisively negative record rather than a marginal one, and every box-1/3/4 failure above deepens under the corrected data.

---

# Governance Reconciliation Audit — Inaugural Run (2026-07-01)

## Status: 37 claims checked, 1 DRIFT found and corrected, re-run clean

The recurring reconciliation audit instituted in GOVERNANCE.md ran for the first time via `audit_governance.py` (mechanical re-derivation of every standing quantitative claim from the backtest CSVs and scheduler XMLs -- never from prior prose).

**Claims checked (all PASS unless noted):** scalp30 -- total/n/WR, all six per-year nets, worst-full-year WR baseline, 1%-compounding maxDD; intraday (5 pairs) -- total/n/WR, USD_JPY share, 2026H1 net, worst-year baseline, maxDD; swing USD_CAD (retired record) -- total/n, min-N failing-cell count, maxDD; pullback30 -- parent total, long-side total/n/WR, zero-negative-long-years, maxDD; overlaps -- intraday/scalp30 (99.7%/97.3%) and pullback30/scalp30 (68.1%/28.4%) recomputed from the CSVs; config -- pair lists and account assignments in strategies.json vs the live scheduler XMLs.

**The one DRIFT:** `donchian_plugin_intraday`'s pair list in strategies.json (4 pairs) vs the live task config (5 pairs, EUR_JPY present and backtested at +$3,444/6yr). This was item 4 of the GOVERNANCE retro-fill failure summary, known but not yet fixed -- the audit's first catch was the audit doing exactly its job. Corrected at source with a dated note; re-run reports 0 DRIFT across all 37 claims.

**Manual-section items reviewed by eye this run:** factor-dependence prose current (macro-trend reframe); swing retirement record matches reality (process absent, task deleted, trade 37 in run-off); pullback30 probation clock at 1 closed trade / started 2026-07-01; no review dates passed; roster labels consistent.

---

# Bot E Search — Opening Entry: Quarterly Regime Map and Pre-Registered Pass Criteria

## Status: SEARCH OPENED (2026-07-02). Mean reversion, highest-priority diversification need per GOVERNANCE's one-behavior note.

## Diagnostic: quarterly ER regime map (no P&L involved)

Median rolling ER(20) on daily closes, per quarter, 2021Q1-2026Q2, five pairs. Classification threshold **ER > 0.20 = trending, else ranging**.

**Threshold justification:** 0.20 was chosen because it reproduces the project's independently-established regime calls rather than being fit to anything new: USD_JPY 2022Q2 (the BoJ-divergence monster trend documented in the scalp30 validation) reads 0.417, the highest in the map; USD_JPY 2025Q3 (the chop that the Kaufman ER yearly analysis flagged at 10x below every other year) reads 0.082, the lowest; and EUR_JPY's 2025-2026 pullback edge-death lines up with its R quarters. The map recovers what we already knew from three separate analyses -- that agreement is the threshold's credential.

Full 22-quarter map in the session record; the actionable summary:

**Ranging-quarter counts (of 22):** USD_CAD 13 (59%), EUR_JPY 11, GBP_USD 11, USD_JPY 9, EUR_USD 7 (trends most persistently -- worst MR territory).

**Cleanest ranging stretches:**
1. **USD_CAD 2022Q3-2023Q3 -- 5 consecutive ranging quarters, avg ER 0.176.** The longest sustained range in the universe.
2. USD_JPY 2025Q2-2025Q3 -- deepest chop (avg 0.105, incl. the 0.082 floor).
3. USD_JPY 2021Q2-2022Q1 (4q, avg 0.150); USD_CAD 2024Q1-2024Q2 (0.138); EUR_JPY 2022Q3-2023Q1 (0.155); GBP_USD 2025Q2-2025Q3 (0.150).

**Cross-validation note (corrected from the first draft of this analysis):** USD_CAD's 2022 was MOSTLY RANGING (Q1/Q3/Q4 all R; only Q2 trending) -- so trend-origin pullback's -$3,029 losing year there is the trend family failing in mean-reversion territory, exactly the regime-dependence story the map should tell. The map also independently reproduces USD_JPY 2022's trend year and the 2025 chop that flattened the pullback family's JPY edge.

## Pre-registered pass criteria for any Bot E candidate (defined before any candidate exists)

- **Must be net-positive (spread included) in USD_CAD 2022Q3-2023Q3** -- the crown-jewel ranging stretch.
- **Must be net-positive in at least two of the secondary stretches** (USD_JPY 2025Q2-Q3, USD_JPY 2021Q2-2022Q1, USD_CAD 2024Q1-Q2, EUR_JPY 2022Q3-2023Q1, GBP_USD 2025Q2-Q3).
- **Must be flat-not-negative in trend quarters** (edge-to-zero, mirroring the trend family's failure mode in ranges): in stretches like USD_JPY 2022Q2-Q4, the candidate should stop finding setups, not bleed. Deep losses in trend quarters fail the candidate even if range-period profits are strong.
- **Circularity rule, pre-registered:** ER-based regime gating IS permitted inside candidate designs (e.g. only trade when ER < threshold) -- but the pass criteria above are expressed as profitability within TRADED periods and edge-to-zero behavior in trend quarters, because "profits during ER-ranging periods" would be partly true by construction for an ER-gated design. A candidate cannot pass by defining itself into the test.
- Standard passport boxes apply on top (6yr spread-included, min-N, concentration, both drawdown models, measured overlap vs live strategies, factor documentation, distinct behavior -- MR is the distinct behavior being sought, so box 7 is the point, not a hurdle).

**Design constraints carried in from prior findings:** candle-scale stops die to spread on this account (RSI post-mortem; pair sweep) -- a viable MR candidate likely needs STRUCTURAL stops (e.g. range-edge-anchored: fade the boundary with SL beyond it), which the sweep explicitly does not price. USD_CAD is the natural first home: most ranging territory, currently unoccupied (swing retired, intraday rejected it), and would be the portfolio's only non-USD_JPY-dominant P&L source.

---

# Bot E Candidate v1: range_fade_plugin.py — Pre-Registration (BEFORE any backtest)

## Status: BUILT AND UNIT-TESTED 2026-07-02; committed before the first backtest per convention

## Design (constants CHOSEN, not tuned — not to be optimized against results)

H4 range = zone between the two most recent confirmed fractals (detect_fractals, N=2), valid only when structure is non-trending (NOT consecutive HH/HL and NOT consecutive LH/LL — the exact inversion of trend-origin's condition, making Bot E mechanically complementary to pullback30). M30 entry: touch of the boundary zone (inner 15% of range height) + close back inside — fade, BOTH directions, no directional carve-outs (pre-committed: pullback30's post-hoc long-only selection is not repeated). SL structural: _SL_BUFFER_PCT (0.05) of span beyond the faded boundary. TP at the range MIDPOINT (structural, not a fixed R multiple). Min-R:R 1.2. Non-starving pair-identity re-entry guard. NO ER gate in v1 — the structural non-trend condition does the regime work implicitly; an explicit ER gate is the v2 lever if v1 bleeds in trend quarters, judged under the pre-registered circularity rule.

**Amendment 1 — minimum absolute range size (anti-RSI-death guard):** TP distance must be >= 10x assumed spread (live-measured sweep values, not the backtest charge table). **For USD_CAD at 1.7p spread: TP distance >= 17 pips — implying range span >= ~34p for a boundary-edge entry, >= ~49p for an entry at the interior edge of the 15% zone.** The premise check must report the distribution of range heights actually traded and per-trade spread cost as a fraction of average TP distance.

**Amendment 2 — trade management model, pre-registered:** v1 is fire-and-forget (broker-side SL/TP, no mid-trade exits), consistent with the fleet. **Structural-invalidation exit (closing when a new fractal confirms beyond the faded boundary mid-trade) is a v2 HYPOTHESIS requiring its own validation — explicitly not a tweak to be invented during forward testing.**

## Unit tests (all 7 passed before any backtest)

Range detection correctness against raw fractal data; boundary fade fires with SL beyond the CORRECT (faded) boundary; short side mirrors; SILENCE during consecutive HH/HL (the inversion property); min-R:R skip when the close lands near the midpoint; Amendment-1 rejection of a 13-pip range against the 17-pip USD_CAD floor; no starvation (fresh confirmed fractal re-arms immediately).

## Amendment 3 — pre-committed test sequence (decided NOW, before any run)

1. **Premise check: USD_CAD, M30/H4, 2022Q3–2023Q3 (2022-07-01 to 2023-10-01), spread included, $80 fixed risk. This is a KILL-TEST ONLY.** A fail is decisive — a mean-reversion design that cannot profit in the best MR territory in the regime map has dead mechanics, full stop. **A pass is WEAK evidence** (best-territory performance is selection by construction) **and triggers the full 2021–2026 run regardless.**
2. **The full window is where the pre-registered criteria (bfe44c7) are judged:** net-positive in the crown jewel; net-positive in >= 2 secondary stretches; flat-not-negative (edge-to-zero, not deep loss) in the trend quarters.
3. Standard format throughout: spread included, $80 fixed risk, per-year per-direction, min-N, commit hashes in headers. Constants stay as chosen above.

---

# Bot E Candidate v1: range_fade — KILLED at the Crown-Jewel Kill-Test

## Status: REJECTED 2026-07-02, per the pre-committed test sequence (Amendment 3, b2a9b67). No full-window run; no parameter tuning.

## Kill-test result — USD_CAD, M30/H4, 2022Q3-2023Q3 (the best MR territory in the regime map), spread included, $80 fixed risk, commit b2a9b67

**88 trades, 39.8% WR, realized R:R 1.33, net -$526.33.** The pre-registration was explicit: a fail here is decisive — a mean-reversion design that cannot profit in the map's best ranging territory has dead mechanics. It failed. Per the same pre-registration, the constants are not retuned against this result and the full window is not run.

| | n | WR | Net |
|---|---|---|---|
| Long | 43 | 41.9% | -$88.99 |
| Short | 45 | 37.8% | -$437.35 |
| 2022Q3 | 14 | 42.9% | +$54.51 |
| 2022Q4 | 21 | 57.1% | +$570.11 |
| 2023Q1 | 24 | 41.7% | -$91.07 |
| 2023Q2 | 12 | 33.3% | -$208.21 |
| 2023Q3 | 17 | 17.6% | -$851.68 |

## Why it failed — mechanism, not just numbers

**Not spread.** Amendment 1 did its job: the ranges actually traded were large (median TP distance 34.2p, median implied span ~69p, minimum TP distance 17.2p — the floor held exactly), and the per-trade spread charge was only 3.1% of average TP distance (4.4% at the live-measured 1.7p). This is the first candidate in the project's history whose failure is cleanly NOT a spread story — the anti-RSI-death guard worked, and the mechanics failed anyway.

**The edge itself is absent: 39.8% WR against a 42.8% breakeven at the realized 1.33 R:R.** A 3-point WR shortfall at modest R:R, consistent across both directions (no directional asymmetry to carve — and none would have been carved per the pre-commitment). The quarterly decay is informative: profitable in 2022Q3-Q4, then progressively worse, ending at 17.6% WR in 2023Q3 — the fractal-pair range definition appears to lag: by the time two confirmed fractals define a range inside a 5-quarter ranging period, the range boundaries it fades are stale versions of where price actually turns.

## What survives the kill

- The **regime map and pre-registered pass criteria (bfe44c7) stand** — they are candidate-independent.
- Amendment 1's spread-floor mechanism is validated as a design tool (it successfully removed spread as a confound).
- The failure localizes the problem to the RANGE DEFINITION (stale fractal-pair boundaries), not to the fade concept, the structural-stop approach, or the territory. A v2 exploring a fresher boundary definition (e.g. rolling N-day high/low, or fading only the most recent boundary rather than requiring a full fractal pair) would be a NEW candidate under the same pre-registered criteria — with fresh unit tests and its own kill-test, not a tune of this one.

---

# Bot E Candidate v2: range_fade_v2 — Pre-Registration (BEFORE building)

## Status: PRE-REGISTERED 2026-07-02, prior to any code. Successor to v1 (killed 384982b), addressing its diagnosed failure only.

## The one change from v1

**Range boundaries = rolling N-day extremes of the H4 series (highest high / lowest low over the trailing window, current candle excluded), replacing v1's confirmed-fractal pair.** v1's kill-test diagnosis localized the failure to stale boundaries -- by the time two fractals confirmed a range, price's actual turning zone had moved. Rolling extremes refresh continuously.

**N = 20 trading days (120 H4 candles), CHOSEN ONCE from the regime map, not tuned:** (a) the map's clean ranging stretches run 2-5 quarters, and v1's boundaries demonstrably staled within ~1 quarter -- the boundary definition must refresh several times per stretch; 20 days is ~1/3 of a quarter, refreshing ~3x per ranging quarter; (b) 20 is this project's established structural lookback scale (ER(20), the 20-candle swing lookback, the volume-profile window family) -- using it here is convention, not optimization. N is not to be adjusted against results.

## Everything else unchanged from v1 (verbatim mechanics and amendments)

Structural non-trend gate (NOT consecutive HH/HL and NOT LH/LL, fractal-based, the trend-origin inversion); M30 boundary-zone (inner 15%) touch + close-back-inside fade, BOTH directions, no carve-outs; SL structural at 5% of span beyond the faded boundary; TP at range midpoint; min-R:R 1.2; Amendment-1 spread guard (TP distance >= 10x assumed live spread; USD_CAD floor 17 pips); Amendment-2 fire-and-forget (structural-invalidation exit remains a separately-validated v3 hypothesis); non-starving re-entry guard, identity now = (timestamp of the window's high-setting bar, timestamp of the low-setting bar) -- refreshes whenever a new extreme forms or an old one ages out.

## Pre-registered kill-test — EXPANDED, because v2's design is informed by v1's failure

v2 was designed looking at v1's crown-jewel result, so passing the crown jewel alone is weaker evidence than it was for v1. **The kill-test is therefore TWO stretches, and v2 must pass BOTH; a fail on either is decisive -- no retuning:**

1. **USD_CAD, 2022Q3-2023Q3** (the crown jewel, same window v1 died in).
2. **USD_JPY, 2021Q2-2022Q1** (secondary stretch: the longest in the map at 4 quarters, on a DIFFERENT pair, in a different macro era -- chosen now, before any run).

A double pass triggers the full 2021-2026 window on both pairs, where the bfe44c7 criteria are judged (crown-jewel positivity, >=2 secondary stretches positive, edge-to-zero in trend quarters). Standard format throughout; fresh unit tests before any backtest.

## v2 Kill-Test Results (2026-07-02, commit 3f1bfe5) — DOUBLE PASS

Per the pre-registered sequence (2705540): both stretches, both passed, no retuning performed.

| Kill-test | n | WR | Realized R:R | Breakeven WR | Net |
|---|---|---|---|---|---|
| USD_CAD 2022Q3-2023Q3 (crown jewel) | 53 | 47.2% | 1.56 | 39.1% | **+$851.09** |
| USD_JPY 2021Q2-2022Q1 (secondary, different pair/era) | 22 | 54.5% | 1.49 | 40.1% | **+$627.96** |

Both directions positive in both tests (USD_CAD: long +$486/short +$365; USD_JPY: long +$391/short +$237) -- no directional asymmetry to be tempted by. The rolling-boundary change directly reversed v1's failure signature on the identical crown-jewel window: v1 was 39.8% WR vs 42.8% breakeven (net -$526); v2 is 47.2% vs 39.1% (net +$851), with WR now safely ABOVE breakeven on both tests. Amendment-1 floor comfortably clear (min TP distance 64.8p / 31.9p vs floors of 17p / 15p). Trade frequency is low (~10/quarter/pair) -- min-N in the full window will be the thing to watch; late-2023 quarters (2023Q2/Q3) went mildly negative in the crown jewel, worth attention at full-window judgment.

**Caveat, standing:** a double pass is still weak evidence by construction (the crown jewel informed v1's redesign; the secondary partially inoculates but doesn't eliminate this). The full 2021-2026 windows on both pairs are where the bfe44c7 criteria are judged. Per the pre-committed sequence, the full-window runs are now triggered.

---

# 2026-07-02 — range_fade v2 FULL-WINDOW ADJUDICATION (bfe44c7 criteria) — **FAIL, candidate KILLED**

Plugin commit 3f1bfe5; runs executed at HEAD bcf87cd (per-year 2021–2026ytd, spread included, $80 fixed risk, M30/H4). The original background runs died in the 2026-07-02 power outage mid-2024-segment (see OPERATIONS_LOG); both were relaunched from scratch — the runs are deterministic, only compute time was lost.

## Full-window results (spread included)

| Pair | 2021 | 2022 | 2023 | 2024 | 2025 | 2026ytd | Total n | Total net |
|---|---|---|---|---|---|---|---|---|
| USD_CAD | +$1,660.69 (27) | +$47.30 (43) | −$573.00 (33) | +$868.90 (39) | +$496.16 (26) | −$1,053.73 (19) | 187 | **+$1,446.32** |
| USD_JPY | −$122.87 (30) | −$1,153.69 (42) | −$1,422.46 (45) | −$245.36 (32) | +$513.63 (31) | −$543.88 (17) | 197 | **−$2,974.64** |

Per-direction (full window): USD_CAD long +$862 (79, 45.6% WR) / short +$585 (108, 44.4%). USD_JPY long +$237 (63, 39.7%) / **short −$3,211 (134, 26.9%)** — the USD_JPY bleed is almost entirely shorts fading rallies inside the secular yen-weakening trend.

## Pre-registered stretch adjudication (bfe44c7)

| Criterion | Stretch | n | WR | Net | Verdict |
|---|---|---|---|---|---|
| 1. Crown jewel net-positive | USD_CAD 2022Q3–2023Q3 | 53 | 41.5% | +$147.95 | **PASS** (barely) |
| 2. ≥2 secondary stretches net-positive | USD_JPY 2025Q2–Q3 | 17 | 58.8% | +$567.94 | positive |
| | USD_JPY 2021Q2–2022Q1 | 22 | 45.5% | +$297.48 | positive |
| | USD_CAD 2024Q1–Q2 | 18 | 83.3% | +$1,513.47 | positive → **PASS** (3/3 runnable) |
| 3. Flat-not-negative in trend quarters | USD_JPY 2022Q2–Q4 (the named example) | 40 | 25.0% | **−$1,004.35** | **FAIL** |
| | USD_JPY 2023 | 45 | 22.2% | −$1,422.46 | fail |
| | USD_CAD 2022H1 | 17 | 29.4% | −$403.66 | fail |
| | USD_CAD 2026ytd | 19 | 10.5% | −$1,053.73 | fail |
| | USD_JPY 2026ytd | 17 | 23.5% | −$543.88 | fail |

## Verdict

**Criterion 3 fails decisively, so v2 is killed per the pre-registration** ("Deep losses in trend quarters fail the candidate even if range-period profits are strong"). The failure mode is exactly what the criterion was written to catch: in trend quarters the candidate does NOT stop finding setups — the rolling 20-day window top/bottom keeps being touched by pullbacks, the fractal non-trend gate passes during consolidation pauses, and the fade fights the trend. 40 trades at 25% WR in USD_JPY 2022Q2–Q4 is bleeding, not edge-to-zero. 2026 YTD is the worst stretch for both pairs (combined −$1,598 in six months) — the candidate is failing in the most recent regime, not just in history.

**Diagnosis (for any v3): the boundary-staleness fix worked — the trend-quarter exposure is the unsolved problem.** v1 died of stale boundaries inside ranges; v2 fixed that (criteria 1–2 pass, all five runnable range stretches net-positive). What remains is that the structural non-trend gate (fractal HH/HL–LH/LL) is too weak a regime filter: it goes quiet only during impulsive legs, not during trend-consolidation pauses, which is where the losing fades cluster. A v3 would need a stronger regime gate (the pre-registered circularity rule explicitly permits ER-based gating in designs — pass criteria remain profitability-within-traded-periods). That is a new candidate with a new pre-registration, not a retune of this one.

**Reconciliation note — kill-test vs full-window numbers on identical windows:** the crown jewel read +$851.09 (47.2% WR) in the kill-test but +$147.95 (41.5%) in the full window, both n=53; USD_JPY 2021Q2–2022Q1 read +$627.96 vs +$297.48, both n=22. Cause: the kill-tests were single continuous runs starting at the stretch boundary, while the full window is per-year segments — different warm-up state, different rolling-window/re-entry-guard state at segment boundaries, and year-end truncation of open trades. Same entry counts, different exits/outcomes. Both readings are net-positive so the adjudication of criteria 1–2 is unaffected; noted here because a sign-flip under resampling would have been material, and this sensitivity (±$700 on a 53-trade stretch) is itself evidence of how thin the crown-jewel edge is.

**Bot E search status:** two candidates built, two killed at pre-committed tests, zero constants retuned, regime map → adjudicated-and-killed v2 in under two days. The map's range-stretch calls themselves held up (all five runnable range stretches were net-positive) — the search continues with the trend-quarter gate as the identified frontier.

---

# 2026-07-02 — HARNESS DIAGNOSIS: the +$851 vs +$148 crown-jewel discrepancy, fully traced

Prompted by the reconciliation note above. This is a harness-correctness finding, not a strategy finding — it affects the interpretation of every premise/kill-test vs full-window comparison to date.

## Method

Re-ran the continuous kill-test window (USD_CAD 2022-07-01→2023-10-01, identical parameters incl. `fixed_risk=80`): reproduced +$851.09 / 53 trades / 25 wins EXACTLY — the harness is deterministic. Trade-by-trade diff against the crown-jewel slice of the per-year run (also 53 trades, +$147.95) on entry timestamps.

## Result: 46 entries common, 7-vs-7 divergent; gap of $703.14 = two boundary mechanisms, nothing else

| Mechanism | Trades | Net contribution to gap |
|---|---|---|
| **(b) Warm-up dead zone at run start** — `backtest.py` fetches candles from `start` with NO warm-up prefix, and the plugin is silent until 121 H4 candles exist (`_WINDOW_H4+1` guard). Continuous run silent through July 2022 → missed 7 July trades (net −$375.39) the per-year run took (its 2022 segment was armed since late Jan). Per-year 2023 segment silent through late Jan → missed 7 January trades (net +$261.32) the continuous run took. | 7 + 7 | **+$636.71** |
| **(c′) Year-end truncation** — 2022-12-09 short was still open at the 2022 segment end; per-year force-closed it `end_of_data` at +$65.70 vs +$132.13 at TP in continuous. Not an indexing bug — a policy difference. | 1 | **+$66.43** |
| (a) Equity-dependent sizing | — | **ruled out**: both runs use `fixed_risk=80`; all 45 other common trades have pnl identical to the cent |

The identical n=53 was pure coincidence (7 lost, 7 gained). The 7-vs-7 divergent entries cluster EXACTLY in the two predicted months (2022-07 and 2023-01) — no divergence anywhere else, so no off-by-one/indexing bug at year splits.

## Implications (standing, until the harness is changed)

1. **Every per-year full-window number silently excludes each year's first ~N days of setups**, where N = the plugin's history requirement (~24 calendar days for range_fade v2's 120-H4 window; smaller for EMA-based plugins, `min_candles=110` LTF). Every continuous stretch run is likewise blind for its first N days.
2. **Kill-test (continuous) vs full-window (per-year) numbers on the same calendar window are therefore measurements of overlapping-but-different trade populations.** Comparisons are valid only away from segment boundaries. The ±$700-on-53-trades sensitivity observed here is boundary artifact plus genuinely thin edge, in roughly a 90/10 split ($636.71 + $66.43 boundary vs $0 common-trade drift).
3. **No adjudication is overturned.** Criteria 1–2 passed under both run shapes (a fully-armed union estimate of the crown jewel is ≈ +$540 over 60 trades — still positive). Criterion 3's fail (USD_JPY 2022Q2–Q4, −$1,004/40 trades) sits mid-year in a fully-armed segment — boundary effects cannot rescue it. v2 stays killed.
4. **Proposed harness fix (not yet implemented, needs approval as it changes comparability with all prior results):** `backtest.py` should fetch HTF/LTF from `start − warmup` but evaluate signals only within `[start, end)`; optionally also simulate exits past `end` (or carry positions across per-year segments) instead of `end_of_data` force-close. With that, per-year and continuous runs produce identical trade lists except at the true data edges.

---

# 2026-07-02 — HARNESS WARM-UP BUG: identified and FIXED same day (diagnosis 631de22, fix 85e4b67)

Approved and implemented. `run_backtest` now (1) fetches candles from `start − prefix`, where the prefix is 2× the plugin's declared history requirement (`WARMUP_HTF_CANDLES` module attribute; range_fade_v2 declares 125; undeclared plugins fall back to the old `min_candles=110`) — the first half arms the signal source, the second half is evaluated-but-never-traded so path-dependent plugin state (re-entry guards) rebuilds identically to a continuous run; (2) evaluates/enters signals only within `[start, end)`; and (3) **truncation policy choice (b), stated explicitly:** trades still open at a segment's end simulate to their real SL/TP resolution using data up to 60 days past `end` (`EXIT_SIM_EXTENSION_DAYS`), rather than carrying positions across segments — chosen because `run_backtest` is self-contained per call and the per-year runners invoke it independently; option (a) would have required threading open-position state through every runner's API.

**Regression guard (permanent suite): `test_backtest_boundary_parity.py`** — the exact exposing case, USD_CAD 2022Q3–2023Q3 on range_fade_v2, continuous vs split-at-2023-01-01. **PASSED post-fix: 60 trades identical across run shapes, same entries and PnL to the cent, net +$475.70 both ways** (seg1 n=26, seg2 n=34). This test must pass for the fix to be considered intact; it stays in the suite as a standing guard.

**Audit claim added:** `audit_governance.py` now verifies, for every `*_plugin.py`, that the harness's derived warm-up covers the plugin's minimum-history guard re-derived from its source (12 plugins checked; range_fade_v2: 125 ≥ 121; all others' guards ≤ the 110 default). Post-fix audit: 53 claims, 0 DRIFT.

**Bounded scope, stated explicitly:** this instance was ~$703 on 53 trades (~7% of the window), direction not systematically biased (the two dead zones cut in opposite directions: −$375 of missed losers, +$261 of missed winners), and **no prior verdict is retroactively overturned by this finding alone** — the wide-margin rejections (RSI, MA pullback, range_fade v1, and v2's criterion-3 trend-quarter failure) are far outside this magnitude's ability to flip. The one result closest to this bug's plausible influence is **v2's crown-jewel PASS (+$147.95, already flagged as thin)**: the fully-armed post-fix reading is +$475.70 over 60 trades — still positive, so criterion 1's PASS stands under both harnesses; noted here should it ever need re-examination. Per decision, the historical backtest catalog is NOT re-run against the fixed harness; if a specific thin/close-call result needs re-verification later, re-run that one specifically.

> **CORRECTION (2026-07-02, same day, after the FTMO data collection):** the "~7% of the window" scope claim above was generalized from range_fade's H4 case without checking HTF plugins, and it UNDERSTATED the bug. The effect scales with the plugin's warm-up requirement relative to segment length: at H4 HTF (~120-candle windows) the dead zone is ~4 weeks of a year segment (~7%); at DAILY HTF the 110-candle warm-up is ~5 MONTHS of every year segment (~40%). Corrected-harness reruns: swing **sign-flipped** (+$292.53/225 trades → −$4,759.73/376) and intraday moved −26% (+$39,116/6,884 → +$28,973.51/7,434). "No verdict overturned" survives on the outcomes — swing's retirement is reinforced, not reversed — but the magnitude claim was wrong and is corrected in full in the scope-correction entry below.

**Comparability note:** results produced after 85e4b67 include each window's first ~N days of setups that pre-fix results silently excluded; cross-harness comparisons of the same window will differ near segment starts (that is the fix working). Exact run-shape parity is guaranteed for structure-based plugins (bounded-history signals); EMA-based sources get near-parity (EMA tail-convergence over the prefix).

**Bot E research is PAUSED here** pending direction on next steps (v3 with an ER-based regime gate vs. the volume-profile / liquidity-sweep candidates). No new strategy work started.

---

# 2026-07-02 — FTMO 2-Step compatibility simulation (corrected harness, commit f86d9f4, spread included)

**Method.** Engine extended to record exit timestamps and per-candle worst-case floating-PnL marks, bounded at the stop level per the engine's own fill convention (8f161c3, f86d9f4; boundary-parity test re-passed after each change — marks are purely observational). All four strategies re-run per-year 2021–2026ytd under the corrected harness at $80 fixed risk (one engine pass each; R-multiples and R-marks are sizing-invariant, so the three fixed-fractional levels are exact post-processing). Rules simulated: 5% max daily loss (floating, closed+open, baseline = closed balance at UTC-midnight day start), 10% static overall floor from account open, $100k notional. FTMO-convention approximations documented: UTC (not CE/CEST) day boundary; concurrent trades marked at their own candle's adverse extreme simultaneously (conservative); historical record permits overlapping same-instrument positions that the live gates cap at 1.

**Corrected-harness records vs the governance catalog (catalog NOT re-run, per standing decision — these runs are FTMO-scoped):** intraday +$28,973.51 / 7,434 trades (catalog +$39,116 / 6,884); scalp30 +$26,278.01 / 2,931 (catalog +$28,000 / 2,719); pullback30 long-only +$17,660.37 / 745 (catalog long-side +$18,864 / 689); **swing −$4,759.73 / 376 (catalog +$293.53 / 225)**. Swing's delta is structural: at D-granularity HTF, the pre-fix warm-up dead zone silenced ~5 months of every per-year segment; the fully-armed record is 67% more trades and decisively negative. Swing's retirement verdict is thereby REINFORCED (its passport already failed boxes 1–3; the corrected record is worse than the one it was retired on).

**Results (per strategy × risk level; SURVIVES = zero daily-breach days AND never below the −10% static floor across the full window from a 2021-01-01 open):**

| Strategy | 0.25% | 0.50% | 1.00% | Surviving level |
|---|---|---|---|---|
| intraday | FAIL (floor −16.5%, 2021-01-19) | FAIL (floor −34.4% + 45 daily breaches) | FAIL (floor −65.8% + 278 daily breaches) | **NONE tested** |
| scalp30 | SURVIVES (worst daily −2.07%, min eq −4.22%) | SURVIVES (worst daily −4.15%, min eq −8.32%) | FAIL (23 daily breaches + floor −16.1%) | **0.50%** |
| pullback30 | SURVIVES (worst daily −1.67%, min eq −1.79%) | SURVIVES (worst daily −3.30%, min eq −3.56%) | FAIL (3 daily breaches) | **0.50%** |
| swing (retired, reference) | FAIL (floor −16.7%, 2024-01-05) | FAIL (floor −31.4%) | FAIL (floor −54.8%) | **NONE tested** |

Intraday's failure at even 0.25% is the static floor, not the daily rule (worst day −3.88%, zero daily breaches at 0.25%) — its cumulative R-drawdown is simply too deep for a 10% static budget at any tested size. Swing likewise fails only the floor (slow strategy, worst day −1.05% at 0.25%). No smaller untested level is extrapolated for either.

**Time to +10% (Phase 1) at the surviving 0.50%, fresh $100k starts — START-DATE-DEPENDENT, stated plainly:** scalp30: 2021 62d, 2022 80d, 2023-07 38d, 2024 15d — but fresh accounts opened 2023-01-01 and 2025-01-01 BREACH the static floor before reaching target. pullback30: 2021 62d, 2022 80d, 2023 228d, 2023-07 368d, 2024 177d — a 2025-01-01 start breaches before target. The full-window "survives" verdicts benefit from early-window profit cushion; an account opened at the start of a drawdown regime (2023, 2025) fails. Phase 2 (5%) not separately simulated; ~half the Phase-1 distances. Minimum-4-trading-days: trivially satisfied everywhere.

**Consistency proxy at 0.50%:** scalp30 largest trade 2.7% of period profit; pullback30 1.9% — far inside any competitor firm's concentration rules.

**Standing caveats:** pullback30's historical record is post-hoc directionally selected (probation terms unchanged — forward paper only); the FTMO sim inherits the historical record's same-instrument stacking that live NFA/FIFO gates prohibit; UTC-vs-CET day boundary and simultaneous-worst marking are both documented approximations, the latter conservative.

---

# 2026-07-02 — SCOPE CORRECTION: the warm-up bug was NOT bounded at ~7%; monitoring baselines re-derived from corrected records

## The corrected generalization

The harness-fix entry's bounded-scope note (~$703 / ~7% of the window) was generalized from range_fade's H4 case without checking HTF plugins. The correct statement: **the dead-zone fraction scales with the plugin's warm-up requirement relative to segment length** — per-year segments at H4 HTF lose ~4 weeks (~7%); at DAILY HTF the 110-candle default warm-up is **~5 months of every year segment (~40%)**. The pre-fix per-year catalog systematically under-sampled every strategy, worst for daily/HTF plugins. A dated correction note has been placed in the original entry (correct-at-source convention).

## Corrected-harness records (per-year 2021–2026ytd, spread included, commit f86d9f4; CSVs promoted to `backtests/corrected_f86d9f4_{strategy}_2021-2026ytd.csv`)

| Strategy | Catalog (pre-fix) | Corrected (f86d9f4) | Delta |
|---|---|---|---|
| intraday (5 pairs) | +$39,116.41 / 6,884 / 32.0% WR | **+$28,973.51 / 7,434 / 31.0% WR** | −26% net, +550 trades |
| scalp30 (USD_JPY) | +$28,000.34 / 2,719 / 33.5% | **+$26,278.01 / 2,931 / 32.7%** | −6% net |
| pullback30 long (USD_JPY) | +$18,863.69 / 689 / 40.2% | **+$17,660.37 / 745** | −6% (record remains premise-only, post-hoc) |
| swing (USD_CAD, retired) | +$292.53 / 225 / 33.3% | **−$4,759.73 / 376 / 24.7%** | **SIGN FLIP**; addendum added to the retirement entry |

Material sub-findings in the corrected intraday record: 2023 flips negative (−$4,308.58), so the corrected profile is 3 of 6 periods negative with profits concentrated in 2022 (+$23,330) and 2024 (+$19,978); USD_JPY's share rises to **85%** of net (+$24,581 of +$28,974). Corrected 1%-compounding maxDD −92.0% (final multiple 15.0x, down from the catalog's 57.1x). scalp30's corrected years remain positive 2021–2024; maxDD −68.8% (final 18.3x).

## Monitoring baselines re-derived (pre-registered contract now measures against the true history)

The 2026-07-01 monitoring table's thresholds were computed from the pre-fix validation CSVs. Re-derived from the corrected records, effective 2026-07-02 (forward windows and pre-committed actions UNCHANGED — only the baselines move):

- **scalp30:** overall WR baseline 33.5% → **32.7%**; worst-full-year WR floor (rolling-100 trigger) 28.5% → **27.1%** (2025); ~533 trades/yr. 15% forward-DD trigger unchanged.
- **intraday:** overall WR baseline 32.0% → **31.0%**; worst-full-year WR floor (rolling-300 trigger) 28.8% → **27.7%** (2025); ~1,352 trades/yr. 20% forward-DD trigger unchanged.

Both floors moved DOWN, so the corrected contract is slightly more permissive — recorded explicitly: this is the baselines becoming accurate, not the thresholds being loosened toward recent bad performance (the deterioration mechanism, worst-full-backtest-year WR, is identical; only its input data was corrected). GOVERNANCE.md passports and monitoring table updated with dated notes; audit_governance.py repointed at the corrected CSVs for intraday/scalp30 claims and the swing addendum figures.

---

# 2026-07-02 — FTMO rule sets (reference data for the prop-firm simulation line) + 1-Step simulation results

## Reference: FTMO rule sets as simulated (source: user-provided screenshots of FTMO's account comparison page, 2026-07-02)

| Rule | **2-Step Challenge** (simulated earlier today) | **1-Step Challenge** (this entry) |
|---|---|---|
| Phases | 10% Phase 1 + 5% Phase 2 (Verification) | 10% single phase, no Verification |
| Max daily loss | 5% (floating equity, closed+open, resets at day boundary) | **3%** |
| Max overall loss | 10% STATIC (floor set once at account open, never trails) | 10% **EOD-TRAILING** (floor recalculates as equity rises) |
| Consistency | none formally enforced | **Best Day Rule: no single day > 50% of total profit** |
| Time limit | none; min 4 trading days/phase | unlimited |
| Profit split | (standard) | 90% |

Simulation conventions carried over from the 2-Step pass (same corrected-harness data, f86d9f4): $100k notional, fixed-fractional sizing, UTC day boundary, stop-bounded worst-case floating marks, daily baseline = closed balance at day start. 1-Step trailing floor implemented as 90% of the running peak END-OF-DAY closed balance (peak updates at day end; floor during day d uses peaks through d−1) — EOD closed balance, not intraday floating highs, which is slightly permissive on the floor and documented as such.

## 1-Step results (per strategy × risk level; SURVIVES = zero days ≤ −3% daily AND never below the trailing floor, full window from 2021-01-01)

| Strategy | 0.25% | 0.50% | 1.00% | Surviving level |
|---|---|---|---|---|
| intraday | FAIL (14 daily-3% days; trailing floor first breached 2021-01-19) | FAIL (199 daily; floor −65% worst gap) | FAIL (539 daily) | **NONE tested** |
| scalp30 | FAIL (daily clean, but trailing floor breached from 2021-09-09, worst gap −14.8%) | FAIL (7 daily + floor −34.1%) | FAIL (205 daily + floor −60.4%) | **NONE tested** |
| pullback30 | **SURVIVES** (worst daily −1.67%; closest approach to trailing floor +1.98%; best day 9.7% of profit) | FAIL (1 daily-3% day, 2024-07-11; floor breached from 2021-09-09) | FAIL (24 daily; floor −18.6%) | **0.25% only** |
| swing (retired, reference) | FAIL (trailing floor from 2023-07-30) | FAIL (floor −24.0%) | FAIL (15 daily + floor −47.9%) | **NONE tested** |

**The trailing floor is the binding constraint that separates 1-Step from 2-Step.** scalp30, which survives 2-Step at 0.50%, fails 1-Step at even 0.25%: its 2025–2026 drawdown-from-peak (~15% at 0.25% sizing) is invisible to a static floor cushioned by early profits but fatal to a floor that trails the equity peak. The 3% daily rule also cuts the 2-Step survivor level: scalp30's worst day at 0.50% (−4.15%, 2023-10-03) passes 5% but not 3%.

**pullback30 at 0.25% is the sole 1-Step survivor, and it is TIGHT:** the closest approach to the trailing floor is +1.98% — one bad week at the wrong time takes it out. Time to the 10% target at 0.25% is long (95–661 calendar days depending on start; the 2025 start never reaches target by end of data, though it also never breaches under the unlimited period). Best Day Rule is comfortable everywhere it matters (9.7% of total profit full-window; rule satisfied at every historical target-hit). Standing caveat unchanged and load-bearing: pullback30's historical record is post-hoc directionally selected — these numbers are premise evidence, not validation, and its probation is still running (1 closed trade).

**Plain statement: under 1-Step rules, no Donchian-family strategy survives any tested risk level, and no smaller untested level is extrapolated.** The 2-Step path (5% daily, static floor) remains the only FTMO structure the Donchians fit at any tested size (scalp30/pullback30 at 0.50%, per the earlier entry, with the start-date dependency noted there).

---

# 2026-07-02 — prop_rules.py: parameterized checker operationalized; The5%ers + FundedNext presets added (commit bbc1df7)

The FTMO scratch simulations are now a permanent repo tool, `prop_rules.py`, with three DISTINCT drawdown mechanics — `static`, `trailing_eod`, and `trailing_lock` (the FundedNext MLL that trails EOD balance peaks and locks permanently at initial balance once accumulated profit equals the original buffer; modeled as its own case, not a parameter variant of trailing). Same data, conventions, and approximations as the FTMO entries above; post-processing only, no new backtests.

## Rule verification (firm-published pages only, per instruction; aggregator summaries not relied on)

- **The5%ers High Stakes** (help.the5ers.com general-rules + drawdown FAQ, fetched 2026-07-02): 10% static max loss from initial; 5% daily vs previous day's closing equity/balance (whichever higher) at 00:00 server time; targets **Classic 8%/5%, New 10%/5%** (the handoff's 8%/5% is the Classic variant — encoded as such); no time limit; minimum 3 profitable trading days (a profitable day = closed profit ≥0.5% of initial). **DISCREPANCY vs the handoff, confirmed before encoding: the 30% single-day consistency cap does NOT apply to High Stakes** — it is a per-position rule in The5%ers FUTURES programs (futures-help.the5ers.com). The 3-profitable-days mechanism is encoded instead; no 30% cap is applied.
- **FundedNext** (fundednext.com/general-rules/futures/trading-objectives, fetched 2026-07-02): **Futures Legacy** chosen (clearest stable rules): 100K → target $6,000 (6%), MLL $3,000 (3%) EOD-trailing locking at initial balance, **no daily loss limit**, 40% best-day consistency cap during the challenge phase. Note Bolt has a daily limit ($1,000/50K) and its MLL locks at initial+$100; Legacy's cleaner mechanics were preferred. Futures program — the drawdown mechanic is what is modeled; our data is FX (documented asset-class mismatch).

## Cross-preset survival matrix (highest surviving risk level; survival = drawdown rules only, consistency reported separately)

| Strategy | FTMO 2-Step | FTMO 1-Step | 5%ers High Stakes Classic | FundedNext Futures Legacy |
|---|---|---|---|---|
| intraday | none | none | none | none |
| scalp30 | 0.50% | none | 0.50% | none |
| pullback30 | 0.50% | 0.25% | 0.50% | 0.25% |
| swing (retired, ref.) | none | none | none | none |

The FTMO columns reproduce the earlier dedicated simulations exactly (cross-validation of the unified checker). The pattern is mechanic-driven, not firm-driven: static floors admit scalp30/pullback30 at 0.50% (High Stakes' lower 8% target changes nothing about survival); trailing floors admit only pullback30 at 0.25%, with thin margins — FundedNext's 3% lock-at-initial MLL is the tightest mechanic on the board (pullback30's closest approach +1.21%; at 0.50% it misses by −0.56%). Consistency rules were never the binding constraint for any survivor (best day ≤14% everywhere a survivor exists; 3-profitable-days trivially met).

GOVERNANCE.md gains a prop-firm compatibility section (matrix, sources, preset-on-relevance policy) and each live passport a "Prop-compatible" row — intraday ❌ none / scalp30 ⚠️ static-floor presets only at 0.50% / pullback30 ✅* all four (post-hoc caveat standing).

---

# 2026-07-02 — NEW LINE OPENED: trend-origin pullback (long+short, as-designed) on untested sweep-universe pairs

**Scope:** full-window (per-year 2021–2026ytd, corrected harness f86d9f4-lineage, spread included, $80 fixed risk, M30/H4) tests of `trend_origin_pullback_plugin.py` as-designed on pairs from the closed 23-pair sweep universe not yet run. Already tested and adjudicated: USD_JPY (long-only variant live as pullback30, post-hoc), GBP_USD (rejected, mirror-regime), USD_CAD (rejected, 2/6 years negative), EUR_JPY (rejected, edge-to-zero recent years).

**Pre-registered process, per pair, no shortcuts for volume:** (1) one-line pre-registration before testing; (2) full window directly — no single-year premise check (established: regime-sensitive strategies mislead on short windows); (3) adjudication criteria same category as every prior trend-origin test — majority of years positive, no single-year dependency, concentration check, honest long/short asymmetry read; NO long-only variant unless the as-designed result earns it, and then only logged explicitly as post-hoc (pullback30 rule); (4) prop-compatibility check (prop_rules.py, all four presets) as part of every result — standard for all future candidates from here on; (5) every result logged, pass or fail.

**Queue, sequenced by informativeness (most different in character from tested pairs first), pre-registered now:** 1. EUR_USD (low-volatility benchmark major — nothing like it tested), 2. EUR_GBP (low-vol European cross, no USD leg), 3. AUD_CAD (commodity cross, no USD leg — the only tested commodity exposure is USD_CAD), 4. USD_CHF (safe-haven franc), 5. AUD_USD (commodity dollar), 6. NZD_USD (commodity dollar, thin), 7. EUR_CHF (ultra-low-vol franc cross), 8. AUD_JPY (JPY cross — deliberately LAST: near-duplicate of the EUR_JPY test). One pair reported fully before the next starts.

**Expectation, stated up front:** this project's candidate base rate is ~1-in-5; most of these should fail, and that is the expected outcome, not a disappointment.

**Standing framing reminder (pre-committed so it is never later mistaken):** any pair that validates here adds pair-count and a probationary slot but does NOT reduce portfolio concentration — trend-origin pullback is persistent-trend capture, the same behavior as everything live. A validation on this line grows the one-behavior exposure the 2026-07-01 portfolio note flagged; it is not diversification. The Bot E mean-reversion slot remains the diversification need.

## Pre-registration #1: EUR_USD — next in queue as the archetypal low-volatility major; no tested pair shares its character (GBP_USD is the high-vol major, both JPY tests are yen-regime, USD_CAD is commodity-USD). No criteria beyond the standard category above.

---

# 2026-07-02 — Bot E candidate #3 PRE-REGISTRATION: liquidity-sweep fade (chosen over volume-profile reversion)

## Status: PRE-REGISTERED prior to any code. Third candidate in the Bot E mean-reversion search (v1 killed 384982b, v2 killed a3592f7).

## Candidate choice, with reasoning recorded

Two triaged candidates: volume-profile mean-reversion (value-area/POC reversion, reuses existing VP machinery) vs **liquidity-sweep fade (CHOSEN)**. Deciding factor: criterion 3 — the trend-quarter bleed that killed both range_fade versions. VP reversion shares range_fade's core exposure (price rides outside the value area in trends; fading its edge fights momentum) and would need an ER gate to survive, putting the gate rather than the design under test. The sweep fade's entry REQUIRES a confirmed failure before any signal exists — a breakout must close back inside — and in persistent trends breakouts succeed, so the setup self-gates exactly where the last two candidates bled. **That self-gating property is the design thesis under test; accordingly this candidate carries NO separate regime gate (no fractal non-trend gate, no ER gate — the circularity rule is therefore not engaged).** VP machinery reuse is a convenience argument, not an edge argument.

## Mechanics (constants inherited from project conventions, CHOSEN not tuned)

- **Structure (H4):** confirmed Williams fractals, `_FRACTAL_N=2`. Reference levels: the most recent confirmed fractal HIGH (short setups) and fractal LOW (long setups), provided the level's bar lies within the trailing `_WINDOW_H4=120` (20-trading-day) window.
- **Sweep lifecycle (M30 trigger):** a pending sweep opens when an M30 candle trades beyond the level (high > fractal high, mirror for lows); while pending, the sweep extreme tracks the excursion's extreme; the sweep CONFIRMS on the first M30 candle that CLOSES back inside the level → enter at that close, against the sweep. A single candle that wicks through and closes back qualifies immediately. Pending state drops if a newer confirmed fractal replaces the level or the level ages out of the window.
- **SL:** beyond the sweep extreme by `_SL_BUFFER_PCT=0.05` of the window span (the v2 buffer convention, anchored to the sweep extreme — structural, per the trend-origin origin-anchored principle). **TP:** midpoint of the rolling 120-H4 window, current bar excluded (v2 convention). **Min R:R 1.2.**
- **Inherited safeguards, explicit:** Amendment-1 spread floor (TP distance ≥ 10× assumed live spread, same per-pair table); Amendment-2 fire-and-forget (SL/TP placed at entry, never managed); corrected harness (85e4b67 lineage, `WARMUP_HTF_CANDLES = 125` declared); non-starving re-entry guard, identity = (level timestamp, direction) — each swept level trades at most once, new confirmed fractals arm immediately. Both directions, no carve-outs.
- A runaway excursion that confirms late produces a distant SL → the R:R filter rejects it naturally; no discretionary cap.

## Pre-registered test sequence (stage-gated: report at each stage, no chaining to a verdict)

1. **Fresh unit tests** before any backtest (standing convention).
2. **Kill-test, TWO stretches, both must pass, fail-on-either decisive, no retuning** (the v2 expansion rule inherited — the search has repeatedly seen these windows): USD_CAD 2022Q3–2023Q3 (crown jewel) AND USD_JPY 2021Q2–2022Q1 (secondary, different pair/era). Kill-test only: a fail is decisive; a pass is weak evidence.
3. **Full window (both pairs, per-year 2021–2026ytd) only after the kill-test result is reported**, judged on the bfe44c7 criteria: net-positive crown jewel; net-positive ≥2 secondary stretches; flat-not-negative in trend quarters — criterion 3 is the bar v1 and v2 died on and the specific thing the self-gating thesis must clear.
4. **NEW standard criterion (pre-registered here, informed by today's prop-firm findings): trailing-floor margin reported as part of the standard evaluation** — worst peak-to-trough drawdown as % of account, evaluated with the trailing-EOD mechanics as modeled in prop_rules.py (not just static max drawdown). Preference criterion, not a kill criterion: comparable net with shallower troughs is preferable — a proxy for how much of the edge survives its own worst clusters, which matters for the live portfolio's risk budget independent of any prop-firm plan.
5. **Prop-compatibility check (prop_rules.py, all four presets) as part of the full-window passport** — standard for every future candidate.

---

# 2026-07-02 — Trend-origin untested-pairs line, result #1: EUR_USD — **REJECTED**

Full window (per-year 2021–2026ytd, corrected harness, spread included, plugin 82776d7-era `trend_origin_pullback_plugin.py`, M30/H4, $80 fixed risk): **1,340 trades, 30.1% WR, net +$2,430.86** (long −$4,608.00 / short +$7,038.86).

| Year | n | Net | Long | Short |
|---|---|---|---|---|
| 2021 | 223 | −$586.57 | −$1,680.03 | +$1,093.46 |
| 2022 | 253 | **+$3,431.21** | −$952.57 | +$4,383.78 |
| 2023 | 246 | −$793.91 | +$364.75 | −$1,158.66 |
| 2024 | 262 | +$405.61 | −$820.16 | +$1,225.76 |
| 2025 | 246 | −$1,124.26 | −$547.38 | −$576.88 |
| 2026 | 110 | +$1,098.78 | −$972.63 | +$2,071.41 |

**Adjudication (pre-registered criteria, 37cdcc4):** majority of years positive — **FAIL** (3 of 6). Single-year dependency — **FAIL**: ex-2022 the record is **−$1,000.36**; 2022 alone carries the entire net. Concentration — pass (top-5 share of gross wins 6.0–14.5% per year; the failure is year-level, not trade-level). Long/short asymmetry, honest read: long side is negative five of six years (−$4,608 total); the short side (+$7,039) is the persistent-macro-trend signature (short EUR_USD = long USD) but is itself negative in 3 of 6 years and 2022-dominated — **no short-only variant is earned by this record** (the pullback30 rule: the as-designed result must earn it; a year-dependent, sub-majority record does not). Prop-compatibility (standard): FTMO 2-Step / High Stakes Classic at 0.50%, trailing-floor presets none — moot given rejection, recorded for completeness. **EUR_USD is logged evidence, consistent with the persistent-macro-trend hypothesis (the edge, where it exists, sits on the long-USD side) and with the ~1-in-5 base rate.**

## Pre-registration #2: EUR_GBP — next in queue: low-volatility European cross with NO USD leg — structurally unlike every tested pair (all four tested have a USD or JPY leg; the macro-trend hypothesis has never been probed on a pair where neither leg is the dollar or the yen). No criteria beyond the standard category.

---

# 2026-07-02 — Bot E candidate #3 KILL-TEST RESULT: **FAIL on the secondary stretch — candidate KILLED** (pre-registration ac51eed, plugin 82776d7)

Per the pre-committed two-stretch sequence (both must pass; fail on either is decisive; no retuning):

| Kill-test | n | WR | Realized R:R | Breakeven WR | Net | Verdict |
|---|---|---|---|---|---|---|
| USD_CAD 2022Q3–2023Q3 (crown jewel) | 121 | 24.0% | 3.75 | 21.1% | **+$1,378.28** | pass |
| USD_JPY 2021Q2–2022Q1 (secondary) | 68 | 20.6% | 3.37 | 22.9% | **−$558.79** | **FAIL — decisive** |

**Candidate #3 is killed.** No full window is run (stage-gated sequence; the kill-test did not pass).

**Diagnosis, for the record (not a retuning license):** the failure is NOT the criterion-3 mode that killed v1/v2 — the secondary stretch is a MAPPED RANGING stretch (avg ER 0.150), so the candidate failed in range territory, the terrain it was supposed to own. USD_JPY's 2021 "range" was a stair-step precursor to the 2022 trend: fractal-high sweeps kept confirming on shallow pullback closes and then resolving trendward (the log shows dense sequences of stopped shorts against rising levels). The bleed is mild — −$559 over 68 trades ≈ −7R, WR 20.6% vs 22.9% breakeven, near edge-to-zero rather than deep loss — and the self-gating property did visibly hold in the crown jewel (24.0% WR vs 21.1% breakeven at 3.75R). But the pre-registered bar is net-positive on BOTH stretches, and it wasn't. **What the two data points jointly suggest: sweep-fade viability is pair/range-character-specific — rotational ranges (USD_CAD 2022–23) reward it; drifting stair-step ranges (USD_JPY 2021) kill it by resolving sweeps trendward.** Any v4 exploiting that distinction (e.g., a range-character gate) is a NEW pre-registration.

**Bot E search status: three candidates, three kills (v1 384982b, v2 a3592f7, sweep-fade here), zero constants retuned.** The mean-reversion diversification need stands unmet; the search continues only with a new pre-registered candidate.

---

# 2026-07-02 — PROCESS AMENDMENTS (both open lines): early trailing-floor pre-check; two passport tracks

## Amendment to the untested-pairs line (37cdcc4 process), new step 2.5

**Cheap prop-shape pre-check before the expensive full window:** on the crown-jewel-equivalent stretch — for the trend-origin family, pre-registered here as **calendar-2024** (the most recent full trend year; deliberately not outlier-2022) — compute the trailing-floor-style worst peak-to-trough drawdown at 0.25%/0.50% using prop_rules.py's trailing mechanics (`trailing_precheck()`, committed with this entry). **If the margin is blown by >2× EVERY trailing preset's threshold at BOTH risk levels** (2× the loosest, FTMO 1-Step's 10%, is the binding test), the pair is logged **prop-deprioritized** and its full window is deferred in the queue — **NOT discarded**: it may still run later for portfolio-diversity value, logged explicitly as pursued for the paper fleet rather than the prop track. Close-or-passing pre-checks proceed to the full window as normal, now with a real prop-viability prior. *Timing note: EUR_GBP's full run was already in flight when this amendment landed; its pre-check will be computed retroactively from the 2024 slice at adjudication, and the gate applies prospectively from AUD_CAD (#3) on.*

## Amendment to the Bot E process (ac51eed lineage), criterion 2 becomes an early gate

Trailing-floor margin is now checked on the **kill-test result itself** (crown-jewel window), before any full window. If a future candidate passes the regime-map kill-test but blows the trailing-floor margin by a wide margin (same >2× / both-levels test), that is logged explicitly at kill-test stage and a deliberate decision is made — continue to the full window for portfolio-diversity value alone, or deprioritize — before six years of compute are spent. A full run must never be the first place this property is discovered. (Moot for candidate #3, killed above; binding on candidate #4 onward.)

## GOVERNANCE addition: two passport tracks (added once, applies to all future candidates)

See GOVERNANCE.md "Passport tracks" — **general validation** (the existing seven-plus-prop-compatibility boxes; gates paper-fleet deployment) and **prop-track priority** (the early trailing-floor pre-check; gates research-time allocation toward the prop goal). A strategy can pass one and not the other; both verdicts are logged; neither overwrites the other.

---

# 2026-07-02 — Trend-origin untested-pairs line, result #2: EUR_GBP — **REJECTED**

Full window (per-year 2021–2026ytd, corrected harness, spread included, M30/H4, $80 fixed risk): **1,370 trades, net −$7,762.40** (long −$12,649.60 / short +$4,887.20).

| Year | n | Net | Long | Short |
|---|---|---|---|---|
| 2021 | 255 | **+$926.40** | −$3,512.32 | +$4,438.73 |
| 2022 | 241 | −$2,284.84 | −$1,412.29 | −$872.56 |
| 2023 | 254 | −$4,159.25 | −$3,070.71 | −$1,088.53 |
| 2024 | 250 | −$108.78 | −$3,687.97 | +$3,579.19 |
| 2025 | 242 | −$820.73 | −$262.58 | −$558.15 |
| 2026 | 128 | −$1,315.21 | −$703.73 | −$611.48 |

**Adjudication (37cdcc4 criteria): REJECTED decisively** — 1 of 6 years positive; deeply net-negative; the long side loses −$12,650 (negative every year); the short side (+$4,887) is positive only in 2021 and 2024 and negative the other four — **no variant earned**. Hypothesis-relevant read: this is the first pair with NEITHER a USD nor a JPY leg, and the strategy found nothing — consistent with persistent-macro-trend capture requiring a pair with a dominant secular driver; EUR_GBP spent the window without one.

**Two-track verdicts (first application):** general validation — FAIL (above). Prop-track pre-check (retroactive per the a6254ff timing note, 2024 slice): worst trailing DD −8.12% at 0.25% / −15.66% at 0.50% — blown vs FundedNext's 2×3% bar but NOT vs FTMO 1-Step's 2×10% → verdict **proceed** (not prop-deprioritized). The gate would not have deferred this pair; it failed on edge, not shape — a clean demonstration that the two tracks measure different things. Prop-compatibility matrix: moot given rejection.

**Line status: 2 tested, 2 rejected** (EUR_USD, EUR_GBP) — tracking the ~1-in-5 base rate.

## Pre-registration #3: AUD_CAD — next in queue: commodity cross with no USD leg; both legs commodity currencies. Tests whether the trend edge exists on cross-commodity relative-value trends (the only tested commodity exposure, USD_CAD, had the USD leg as its driver). First pair to run under the step-2.5 gate (2024 pre-check first). No criteria beyond the standard category.

---

# 2026-07-02 — Trend-origin untested-pairs line, result #3: AUD_CAD — **REJECTED** (worst record on the line)

First pair through the live step-2.5 gate: 2024 pre-check read worst trailing DD −9.24% (0.25%) / −17.67% (0.50%) → **proceed** (not blown vs FTMO 1-Step's 2×10%), so the full window ran.

Full window: **1,342 trades, net −$12,474.08** (long −$6,946.95 / short −$5,527.13 — BOTH directions negative, a first for this line). Years: 2021 −$244, 2022 **+$435** (sole positive, barely), 2023 −$1,405, 2024 −$2,446, 2025 **−$6,039**, 2026 −$2,776.

**Adjudication (37cdcc4): REJECTED decisively** — 1 of 6 years positive; deep net loss; no directional asymmetry to even be tempted by (both sides lose). Hypothesis-relevant read: second consecutive no-USD-leg pair with nothing there, and the first where *neither* direction shows any edge — cross-commodity relative value has no persistent secular driver for this design to capture. Prop matrix moot.

**Line status: 3 tested, 3 rejected** (EUR_USD, EUR_GBP, AUD_CAD). The no-USD-leg evidence is now two-for-two against; the remaining queue's USD-leg pairs (USD_CHF, AUD_USD, NZD_USD) become the more informative tests of what's left of the hypothesis space.

## Pre-registration #4: USD_CHF — next in queue: safe-haven franc with the USD leg restored. After two no-USD-leg failures, this tests whether returning the dollar leg (the hypothesis's proposed driver) restores the edge on a pair-character not yet probed (safe-haven flows). No criteria beyond the standard category.

---

# 2026-07-02 — Trend-origin untested-pairs line, result #4: USD_CHF — **REJECTED on single-year dependency** (best record on the line, still fails)

Step-2.5 pre-check: worst trailing DD −5.74% (0.25%) / −11.38% (0.50%) → **proceed** (best prop shape seen on this line). Full window: **1,340 trades, net +$3,404.88** (long +$4,913.08 / short −$1,508.20).

| Year | n | Net | Long | Short |
|---|---|---|---|---|
| 2021 | 250 | −$1,230.40 | −$1,181.75 | −$48.65 |
| 2022 | 259 | **+$4,858.14** | **+$7,075.28** | −$2,217.14 |
| 2023 | 255 | +$1,941.98 | −$701.82 | +$2,643.80 |
| 2024 | 237 | +$2,387.83 | +$2,377.45 | +$10.38 |
| 2025 | 238 | −$4,585.14 | −$2,523.50 | −$2,061.64 |
| 2026 | 101 | +$32.46 | −$132.59 | +$165.05 |

**Adjudication (37cdcc4):** majority of years positive — pass (4 of 6). **Single-year dependency — FAIL, decisive: ex-2022 the record is −$1,453.26** (and the long side ex-2022 is −$2,162.20 — the +$4,913 long total is one year's dollar surge). Concentration — pass at trade level (top-5 share 5.5–16.9%); the dependency is year-level, same failure mode as EUR_USD. Long/short honest read: the long-USD side carries everything and only in 2022; no variant earned. **REJECTED.**

**Hypothesis read, now sharpening across four results:** restoring the USD leg produced the line's only net-positive record, and its profits sit exactly where the macro-trend hypothesis puts them (long-USD, 2022). But EUR_USD and USD_CHF now show the same shape — a 2022 windfall the pair gives back across the rest of the window. Only USD_JPY's trend persisted across years. **The surviving hypothesis is narrowing from "long-USD pairs" toward "the persistent yen trend specifically"** — which the EUR_JPY edge-to-zero probe already previewed from the other side. AUD_JPY (queue #8) becomes the sharper test of that narrowed claim.

**Line status: 4 tested, 4 rejected.** Prop-track note for the record: USD_CHF's pre-check shape was the best on the line — had it validated, it would have been the prop-track priority; the two tracks continue to disagree informatively.

## Pre-registration #5: AUD_USD — next in queue: commodity dollar with the USD leg. Continues the USD-leg-restored series on a different driver mix (commodity beta vs safe-haven). No criteria beyond the standard category.

---

# 2026-07-02 — Trend-origin untested-pairs line, result #5: AUD_USD — **REJECTED**

Step-2.5 pre-check: worst trailing DD −13.93% (0.25%) / −26.01% (0.50%) → **proceed** (0.25% not blown vs FTMO's 2×10%; note 0.50% blown vs both — the closest a pair has come to the gate). Full window: **1,330 trades, net −$3,991.55** (long −$7,357.92 / short +$3,366.37).

Years: 2021 **+$2,272** (short +$4,761 carries it), 2022 −$3,663, 2023 −$1,912, 2024 −$1,651, 2025 +$799, 2026 +$165.

**Adjudication (37cdcc4): REJECTED** — 3 of 6 years positive (fails majority); net deeply negative; ex-2021 the record is −$6,264. Long side −$7,358 (negative 5 of 6). Short side positive overall but 2021-dominated and negative 3 of 6 years — no variant earned. Hypothesis note: unlike EUR_USD/USD_CHF, AUD_USD's one good year is 2021 (AUD weakness), NOT 2022 — the USD-leg pairs don't even fail consistently; each catches a different single year and gives it back. The narrowed yen-specific reading strengthens.

**Line status: 5 tested, 5 rejected.**

## Pre-registration #6: NZD_USD — next in queue per the pre-registered order: second commodity dollar, thinner liquidity/wider spread than AUD_USD. Tests whether AUD_USD's shape replicates on its closest sibling. No criteria beyond the standard category.

---

# 2026-07-02 — Trend-origin untested-pairs line, result #6: NZD_USD — **REJECTED**

Step-2.5 pre-check: worst trailing DD −19.62% (0.25%, a whisker inside FTMO's 2×10% bar) / −35.54% (0.50%) → **proceed** by the letter of the rule — the narrowest pass yet. Full window: **1,320 trades, net −$12,757.88** (long −$13,141.63, negative EVERY year / short +$383.75, i.e. flat).

Years: 2021 −$2,479, 2022 **+$1,450** (sole positive), 2023 −$451, 2024 **−$5,952**, 2025 −$4,309, 2026 −$1,019.

**Adjudication (37cdcc4): REJECTED decisively** — 1 of 6 years positive, tied with AUD_CAD for worst net on the line; the long side loses in all six years; the short side is breakeven-flat, not an edge — no variant remotely earned. AUD_USD's shape did not even replicate on its own sibling (AUD_USD's good year was 2021; NZD_USD's sole positive was 2022) — further evidence these records are single-year noise around zero, not a weak common edge.

**Line status: 6 tested, 6 rejected.**

## Pre-registration #7: EUR_CHF — next in queue: ultra-low-volatility franc cross, no USD leg, SNB-shadowed regime. The lowest-volatility test in the universe — if spread-adjusted trend capture exists anywhere near the vol floor, this is where it must show; expected outcome per the two prior no-USD-leg results is rejection. No criteria beyond the standard category.

---

# 2026-07-02 — Trend-origin untested-pairs line, result #7: EUR_CHF — **REJECTED**

Step-2.5 pre-check: worst trailing DD −4.99% (0.25%) / −9.78% (0.50%) → **proceed** (the best prop shape on the line — low vol produces shallow troughs; shape and edge remain uncorrelated). Full window: **1,388 trades, net −$5,518.84** (long −$5,302.07 / short −$216.77 — both directions negative).

Years: 2021 +$588, 2022 +$338, 2023 −$4,673, 2024 **+$6,909** (positive BOTH directions), 2025 −$6,595, 2026 −$2,085.

**Adjudication (37cdcc4): REJECTED** — 3 of 6 years positive (fails majority); net negative; **ex-2024 the record is −$12,428** — the familiar single-year-windfall shape, this time 2024 (the franc's big directional year). Both directions negative overall; no variant question arises. Third no-USD-leg pair, third rejection.

**Line status: 7 tested, 7 rejected.** Every rejection now fits one of two shapes: nothing at all (EUR_GBP, AUD_CAD, NZD_USD), or one windfall year given back (EUR_USD 2022, USD_CHF 2022, AUD_USD 2021, EUR_CHF 2024). No pair outside USD_JPY has shown cross-year persistence.

## Pre-registration #8 (final in queue): AUD_JPY — deliberately sequenced last as the near-duplicate JPY cross; now ALSO the sharpest test of the hypothesis as narrowed mid-line (from "long-USD pairs" to "the persistent yen trend specifically"). If the narrowed reading is right, AUD_JPY should show USD_JPY-like multi-year short-yen persistence, not a single windfall year. Recorded before the run: intraday already trades AUD_JPY live (Donchian family) — a validation here would add trend-origin exposure on a pair the fleet already holds, compounding rather than diversifying the one-behavior concentration; the standing non-diversification framing applies with extra force. No criteria beyond the standard category.

---

# 2026-07-02 — Trend-origin untested-pairs line, result #8: AUD_JPY — **REJECTED** — and **LINE CLOSED at 8 tested / 8 rejected**

Step-2.5 pre-check: −11.38% (0.25%) / −21.67% (0.50%) → proceed. Full window: **1,339 trades, net +$42.71** — dead flat (long +$8,337.35 / short −$8,294.64).

| Year | n | Net | Long (short-yen side) | Short |
|---|---|---|---|---|
| 2021 | 240 | +$1,297.63 | −$152.46 | +$1,450.09 |
| 2022 | 247 | −$963.61 | +$1,842.52 | −$2,806.13 |
| 2023 | 242 | −$3,554.29 | −$644.95 | −$2,909.34 |
| 2024 | 236 | −$1,076.23 | +$1,847.27 | −$2,923.50 |
| 2025 | 249 | **+$5,206.49** | **+$5,652.23** | −$445.74 |
| 2026 | 125 | −$867.27 | −$207.25 | −$660.02 |

**Adjudication (37cdcc4): REJECTED** — 2 of 6 years positive; net flat. The as-designed result does not remotely earn a variant, and the long side would not qualify anyway: positive 3 of 6 years and 2025-dominated (ex-2025 long is +$2,685 over five years). **Contrast with the pullback30 parent on USD_JPY: long +$18,864, positive EVERY year.**

**The narrowed hypothesis FAILS its sharpest test.** The yen-specific reading predicted USD_JPY-like multi-year short-yen persistence here; AUD_JPY delivered a single windfall year instead — the same shape as every other rejection. Combined with the EUR_JPY edge-to-zero probe, the surviving claim is now maximally narrow: **the trend-origin edge is specific to USD_JPY itself, not to yen crosses, not to long-USD pairs, not to trend capture generally.** This converges with what the Donchian record already showed (scalp30's "USD_JPY-SPECIFIC finding, do not extend" note; intraday's 85% USD_JPY concentration).

## LINE CLOSURE — synthesis

| # | Pair | Net | Years + | Shape | Verdict |
|---|---|---|---|---|---|
| 1 | EUR_USD | +$2,431 | 3/6 | windfall (2022), ex-2022 negative | rejected |
| 2 | EUR_GBP | −$7,762 | 1/6 | nothing | rejected |
| 3 | AUD_CAD | −$12,474 | 1/6 | nothing (both directions negative) | rejected |
| 4 | USD_CHF | +$3,405 | 4/6 | windfall (2022), ex-2022 negative | rejected |
| 5 | AUD_USD | −$3,992 | 3/6 | windfall (2021), ex-2021 negative | rejected |
| 6 | NZD_USD | −$12,758 | 1/6 | nothing (long negative every year) | rejected |
| 7 | EUR_CHF | −$5,519 | 3/6 | windfall (2024), ex-2024 negative | rejected |
| 8 | AUD_JPY | +$43 | 2/6 | windfall (2025), flat | rejected |

**8 tested, 8 rejected — far below even the ~1-in-5 base rate, and informatively so:** every record is either nothing or one windfall year given back. Standing conclusions: (1) trend-origin pullback validates on exactly ONE pair in the 23-pair universe — USD_JPY — and pullback30's probation remains that finding's only live test; (2) the persistent-macro-trend hypothesis survives only in its most pair-specific form, raising the weight on pullback30's yen-strengthening falsifier; (3) no new probationary slots, no change to portfolio concentration — the one-behavior concern and the Bot E mean-reversion need are unchanged and, if anything, sharpened. Prop-track notes: pre-check verdicts 8/8 "proceed" (NZD_USD narrowest at −19.62%); shape and edge uncorrelated (the two best shapes, USD_CHF and EUR_CHF, both failed validation).

---

# 2026-07-02 — Bot E PARALLEL PROTOCOL PRE-REGISTRATION: three candidates, operator-directed

## Status: PRE-REGISTERED before any new code. Operator handoff supersedes the single-candidate sequence.

## Protocol (pre-committed)

Each candidate: own pre-registration (this entry), own unit tests, own kill-test on the **USD_CAD crown jewel 2022Q3–2023Q3** (net-positive spread-included = clear), plus the **trailing-floor pre-check** (criterion-2 early gate, a6254ff) computed on the kill-test window at 0.25%/0.50%. **Structural-stop requirement binds all three** — Amendment-1 spread-cost floor (TP distance ≥ 10× assumed live spread) and a structure-anchored SL; session-breakout is explicitly barred from defaulting to a candle-scale stop. Amendment-2 fire-and-forget everywhere. Kill-test results reported as they land, not batched.

**Pre-registered tie-break, decided now:** if more than one candidate clears its kill-test, ALL clearing candidates proceed to the full 2021–2026 window under the standard bfe44c7-category criteria. If more than one clears the full window, deploy whichever has the LOWER measured overlap (trading-day and direction-agreement) with the live fleet; others are logged **validated-but-benched**, not discarded. Liquidity-sweep and session-fade get an explicit mutual-overlap check — both are failed-move-reversion mechanisms and may be the same strategy in two costumes.

## Candidate A — VP mean-reversion (`vp_reversion_plugin.py`, new)

Volume profile over the trailing `_WINDOW_H4=120` H4 candles (existing `volume_profile.build_volume_profile`, `_BINS=20` module convention). POC = max-volume bin center; **Value Area = standard contiguous 70% expansion around POC** (0.70 is the industry-standard VA fraction, chosen not tuned). Entry keeps the failed-excursion character: an M30 candle trades OUTSIDE the value area (beyond VAH/VAL), pending state tracks the excursion extreme, and the first M30 close back INSIDE confirms → fade toward POC. SL beyond the excursion extreme by `_SL_BUFFER_PCT=0.05` of the profile-window span; TP = POC; min R:R 1.2; spread floor per Amendment 1. Re-entry identity = (profile-window extreme-setting bar timestamps, direction), single-use, non-starving. No regime gate.

## Candidate B — liquidity-sweep fade (`liquidity_sweep_fade_plugin.py`, EXISTING, unchanged — operator-directed re-entry)

**Supersession note, recorded in full:** this design was KILLED today under ac51eed's two-stretch rule (crown jewel PASSED +$1,378.28; USD_JPY secondary FAILED −$558.79; fail-on-either decisive). The operator has explicitly re-entered it under this protocol's single-stretch kill-test. The ac51eed kill STANDS as the record of the two-stretch adjudication; this re-entry is a new pre-registration, not a retune (the plugin is bit-identical, 82776d7). Stated plainly before running: **its crown-jewel kill-test carries no new information — it already passed this window.** Its live tests here are the trailing-floor pre-check (never computed for it) and, if it advances, the full window, where the USD_JPY 2021 weakness that killed it will appear in the 2021 segment. The tie-break's overlap criterion and the full-window trend-quarter criterion are where this candidate can genuinely fail.

## Candidate C — session-breakout Asian-range fade (`session_fade_plugin.py`, new; FADE variant only)

The fade variant specifically — the trend-continuation variant overlaps Donchian and is not a diversification candidate (and London breakout momentum was already rejected, 7–22% WR). **Asian session = 23:00–07:00 UTC** (Tokyo business hours; convention chosen once, not tuned). For each trading day: range = high/low of the session's M30 candles. After 07:00 UTC and before the next session opens (23:00), a breakout beyond either boundary opens pending state tracking the excursion extreme; the first M30 close back INSIDE the range confirms → fade toward the **range midpoint** (TP convention shared with the family). **SL beyond the excursion extreme by 0.05 of the session-range height — structure-anchored, explicitly NOT candle-scale.** Min R:R 1.2; Amendment-1 spread floor (Asian ranges on majors run ~20–60 pips; the floor will filter thin days — that is the floor working). One trade per (session date, direction); identity single-use; silent on days with no session candles (weekends). No regime gate.

All constants across all three: inherited project conventions, chosen-not-tuned. Corrected harness (`WARMUP_HTF_CANDLES` declared where H4 windows are used).

---

# 2026-07-02 — Parallel protocol, Candidate C kill-test result: session fade — **FAIL, killed** (plugin be14468)

Crown jewel (USD_CAD 2022Q3–2023Q3, spread included): **64 trades, 20.3% WR vs 29.7% breakeven, net −$1,857.79** (long −$732 over 29; short worse). FAIL — decisive, no retuning. Trailing pre-check (recorded for completeness): −8.13% / −15.65% → would have been "proceed"; moot.

**Diagnosis, for the record:** the Asian-range fade found only ~4 qualifying trades/month after the spread floor (thin ranges filtered), and the ones that qualified still lost — the realized R:R (2.37) never compensated a 20% WR. The failed-breakout premise that holds at fractal levels (sweep-fade cleared this window at 24.0% WR vs 21.1% breakeven) does NOT transfer to session boundaries on this pair: Asian-range breaks that pull back re-break far more often than swing-level sweeps do. Same costume, different body. The pre-registered sweep-vs-session mutual overlap check is MOOT — session fade is dead before overlap matters.

---

# 2026-07-02 — Parallel protocol, Candidate A kill-test result: VP reversion — **FAIL, killed** (plugin be14468)

Crown jewel (USD_CAD 2022Q3–2023Q3, spread included): **74 trades, 25.7% WR vs 29.9% breakeven, net −$855.76** (long −$652.10 over 30; short also negative). FAIL — decisive, no retuning. Trailing pre-check (completeness): −5.36% / −10.50% → "proceed"; moot.

**Diagnosis, for the record:** the selection-memo concern from candidate #3's choice (12f711e era) materialized exactly as written — value-area excursion fades fight drift even inside the best mapped range: the VA recenters continuously, so during multi-week drift legs within the range (June 2023, August 2023 in the log) the strategy repeatedly faded excursions that were just the range's internal trend, the same bleed signature as range_fade. A failed-excursion confirmation at a *statistical* boundary (VA edge) is weaker than at a *structural* one (fractal level): the log's losing clusters are consecutive same-direction fades against moving value. Mean reversion at VP boundaries without a regime gate is now a tested-and-dead idea in this project, not a triaged one.

---

# 2026-07-02 — Parallel protocol, Candidate B kill-test result: sweep-fade — **CLEAR** (sole clearer); full windows triggered

Crown jewel: **121 trades, 24.0% WR vs 21.1% breakeven, net +$1,378.28** — bit-identical to the ac51eed-era run (deterministic reproduction confirmed; as pre-stated, no new information in the pass itself). **New information — trailing pre-check: −6.11% (0.25%) / −11.88% (0.50%) → proceed** (comfortably inside the FTMO 2× bar; the criterion-2 early gate does not deprioritize).

**Protocol state after all three kill-tests: session fade KILLED, VP reversion KILLED, sweep-fade CLEARS alone.** The tie-break's multi-clearer branch is moot; the mutual-overlap check is moot. Per the pre-registered sequence, sweep-fade proceeds to the full 2021–2026 window (USD_CAD + USD_JPY, per-year, marks collected for the prop passport), judged on the standard bfe44c7-category criteria. **Honesty note, recorded before the runs:** the ac51eed record already shows this design losing the USD_JPY 2021Q2–2022Q1 stretch (−$558.79) — that stretch is one of the full window's pre-registered secondary stretches, so criterion 2 starts with one likely miss; the full window is where the operator-directed re-entry gets its real adjudication.

---

# 2026-07-02 — Parallel protocol FULL-WINDOW ADJUDICATION: sweep-fade — **FAIL on criteria 2 AND 3, KILLED. Protocol closed: all three candidates dead.**

Full windows (per-year 2021–2026ytd, corrected harness, spread included): **USD_CAD 523 trades, net −$641.06** (2021 +$816, 2022 +$991, 2023 +$581, 2024 −$447, 2025 −$848, 2026 −$1,735); **USD_JPY 439 trades, net −$7,779.75** (long +$2,034 / short **−$9,813.66**). Combined −$8,420.81.

| Criterion | Stretch | n | WR | Net | Verdict |
|---|---|---|---|---|---|
| 1. Crown jewel positive | USD_CAD 2022Q3–2023Q3 | 121 | 24.0% | +$1,378.28 | pass (bit-identical to the continuous kill-test — run-shape parity holding end-to-end, a live validation of the 85e4b67 fix) |
| 2. ≥2 secondaries positive | USD_JPY 2025Q2–Q3 / USD_JPY 2021Q2–2022Q1 / USD_CAD 2024Q1–Q2 | 44/68/35 | 18.2/20.6/45.7% | −$676 / −$559 / +$2,661 | **FAIL (1 of 3)** |
| 3. Flat-not-negative in trend quarters | USD_JPY 2022Q2–Q4 | 56 | **8.9%** | **−$2,872.24** | **FAIL — deep bleed, decisive** |
| | USD_JPY 2023 / USD_JPY 2026ytd / USD_CAD 2026ytd | 88/46/49 | 14.8/8.7/12.2% | −$2,391 / −$2,216 / −$1,735 | all fail |

**KILLED.** The operator-directed re-entry resolves the same way ac51eed did, now with complete evidence and a sharper mechanism read: in the yen trend, fractal-high sweeps confirm on shallow pullbacks and resolve trendward — USD_JPY shorts ran 5–9% WR in 2022/2023/2026. The self-gating thesis (failure-confirmation entries go quiet in trends) is now REFUTED at full scale: the design does not go quiet in trends, it gets systematically trapped by them. The crown-jewel edge is real but is a USD_CAD-2022-range artifact plus one good USD_CAD half-year (2024H1); everything else bleeds.

## PARALLEL PROTOCOL CLOSED — Bot E search state

**Five mean-reversion designs tested this project, five dead, zero constants ever retuned:** range_fade v1 (stale boundaries), range_fade v2 (trend-quarter bleed), liquidity-sweep fade (killed twice — two-stretch kill-test AND full window on operator re-entry), session fade (premise doesn't transfer to session boundaries), VP reversion (fades internal drift at statistical boundaries). The prop-track pre-checks were never the constraint — every kill was an edge kill. **The mean-reversion slot remains open, and the accumulated evidence now points at a specific structural conclusion: on this account's spread structure and these timeframes, unGATED mean reversion has failed in every costume tried; any candidate #6 likely needs an explicit regime gate (ER-based is permitted by the standing circularity rule) or a different timeframe/venue premise entirely.** No candidate is proposed here — next steps are the operator's call.

---

# 2026-07-02 — Bot E candidate #6 PRE-REGISTRATION: ER-gated sweep-fade — **THE LAST DESIGN IN THIS LINE**

## Status: PRE-REGISTERED before any code. Operator-directed, framed explicitly as the closing test of the mean-reversion line, not a routine next attempt.

Five prior designs failed via structurally different mechanisms (v1 stale boundaries; v2 trend-quarter bleed; sweep-fade trend-trapped at scale; session fade non-transferring premise; VP reversion statistical-boundary drift). The one well-motivated lever never yet pulled is an EXPLICIT regime filter. This is that test.

## Design (`ergated_sweep_fade_plugin.py`)

**Chassis: liquidity-sweep fade, mechanics verbatim from 82776d7** (confirmed-fractal levels, sweep lifecycle, excursion-extreme SL + 5%-of-span buffer, TP at the 120-H4 window midpoint, min R:R 1.2, Amendment-1 spread floor, Amendment-2 fire-and-forget, single-use non-starving identities). Chosen because it is the only mechanic that cleared the crown jewel outright (+$1,378.28) before dying of trend-quarter bleed — precisely the failure mode a regime gate addresses.

**The one addition — the ER gate:** trades fire only when trailing **Kaufman ER(20) on the H4 closes < 0.20** at the confirmation candle (the regime map's metric and threshold, 0.20 per its original three-independent-calls justification; applied per-trade rather than per-quarter — the natural trade-time version of the map's quarterly reading). Gate placement pre-registered: evaluated at sweep CONFIRMATION; a confirmation arriving during ER ≥ 0.20 consumes the sweep event without trading (same consumption convention as the R:R/spread filters — no better-late re-fires when the gate reopens). Pending/extreme tracking runs regardless of gate state.

**Circularity rule, restated as binding:** pass criteria are traded-period profitability and non-degenerate trade frequency — "profits during ER-ranging periods" is partly true by construction for an ER-gated design and counts for nothing by itself. **Non-degenerate frequency, pre-registered: kill-test requires n ≥ 30** (the min-N convention's ≥10/cell scaled to a 5-quarter stretch); a gate that passes by barely trading fails on frequency.

## Pre-registered sequence

Unit tests (chassis behavior preserved when gate open; gate blocks when ER ≥ 0.20; gated confirmation consumed) → kill-test on the USD_CAD crown jewel 2022Q3–2023Q3 (CLEAR = net-positive spread-included AND n ≥ 30) + trailing pre-check (criterion-2 early gate) → full window (both pairs) only if the kill-test clears, judged on the standard bfe44c7-category criteria — where criterion 3 (trend quarters) is the specific thing the gate exists to fix.

## PRE-REGISTERED STOPPING RULE, decided now

**If candidate #6 fails at either stage, the Bot E mean-reversion line CLOSES formally** — with the same finality as the 23-pair sweep closure: mean reversion at M30/H4 on this account's spread structure, tested across six structurally distinct designs, found non-viable. **No candidate #7 without new information** (different timeframe, different venue, or a genuinely new mechanism class — stat-arb, positioning-based contrarian). This is not an evergreen queue. If #6 passes both stages, it earns exactly the standard treatment — full passport, full prop-track evaluation, and standard skepticism toward a design that finally worked after five failures.

---

# 2026-07-02 — Candidate #6 KILL-TEST RESULT: **CLEAR** (plugin f3f6dab) — full windows triggered

Crown jewel (USD_CAD 2022Q3–2023Q3, spread included): **61 trades (n ≥ 30 frequency floor met), 29.5% WR vs 24.1% breakeven, realized R:R 3.15, net +$1,117.46.** Trailing pre-check: **−2.88% (0.25%) / −5.69% (0.50%) — not blown against EITHER trailing preset at either level, the cleanest prop shape of any design tested today.**

**What the gate did, mechanically:** removed 60 of the ungated chassis's 121 trades and kept 81% of its profit (+$1,117 vs +$1,378), raising WR from 24.0% to 29.5% and cutting the worst trailing trough roughly in half (−5.69% vs −11.88% at 0.50%). The trades it removed were, on net, the unprofitable ones — inside the best mapped range, which is the friendly case for an ER gate. Standard skepticism stands: the crown jewel is where this gate SHOULD look good by construction (the circularity rule exists for exactly this reason), and the pass criteria remain traded-period profitability on the full window. **The decisive question is criterion 3 on USD_JPY — whether the gate actually keeps the design out of the 2022/2023/2026 yen trends that killed the ungated chassis at 5–9% WR.** Full windows (both pairs, per-year, marks) triggered per the pre-registered sequence.

---

# 2026-07-02 — Candidate #6 FULL-WINDOW ADJUDICATION: **FAIL on criterion 3 — KILLED. THE BOT E MEAN-REVERSION LINE IS FORMALLY CLOSED.**

Full windows (per-year 2021–2026ytd, corrected harness, spread included): **USD_CAD 234 trades, net +$2,085.85** (4 of 6 years positive; 2021 +$1,184, 2023 +$2,217, 2026 −$1,508); **USD_JPY 193 trades, net −$69.30** — flat, a $7,710 improvement over the ungated chassis's −$7,780.

| Criterion | Stretch | n | WR | Net | Verdict |
|---|---|---|---|---|---|
| 1. Crown jewel positive | USD_CAD 2022Q3–2023Q3 | 61 | 29.5% | +$1,117.46 | pass (bit-identical to the kill-test; parity holding) |
| 2. ≥2 secondaries positive | USD_JPY 2025Q2–Q3 / USD_JPY 2021Q2–2022Q1 / USD_CAD 2024Q1–Q2 | 18/25/15 | 33.3/28.0/60.0% | +$744.73 / **+$74.87** / +$1,457.67 | **PASS — 3 of 3, the first design ever to pass criterion 2** (the gate flipped the stretch that killed the ungated chassis from −$559 to +$75) |
| 3. Flat-not-negative in trend quarters | USD_JPY 2022Q2–Q4 | 26 | **11.5%** | **−$1,265.81** | **FAIL — deep bleed, decisive** (v2 precedent: −$1,004/40 was ruled bleeding; this is worse per trade) |
| | USD_JPY 2023 / USD_JPY 2026ytd / USD_CAD 2026ytd | 37/20/18 | 18.9/10.0/**0.0**% | −$728 / −$992 / −$1,508 | all fail; USD_CAD 2026 is 0-for-18 |

**KILLED, and per the pre-registered stopping rule (cc2bb99) the line closes with it.**

**What the gate did and didn't do — the line's final mechanism finding:** the ER(20) gate cut trend-quarter exposure roughly in half (26 trades vs 56 in USD_JPY 2022Q2–Q4) and fixed criterion 2 outright, but the trades that leaked through still ran 0–12% WR. A trailing 20-candle efficiency ratio lags regime turns: stair-step trends intermittently read below 0.20 during their consolidation pauses — which are precisely the moments sweep confirmations fire — so the gate is systematically open at the design's worst moments. The gate helps; it cannot help enough at this timeframe. That is a structural finding about trailing regime filters at M30/H4, not a threshold-tuning problem (and retuning is forbidden anyway).

## FORMAL CLOSURE — Bot E mean-reversion line (same finality as the 23-pair sweep closure)

**Mean reversion at M30/H4 on this account's spread structure was tested across SIX structurally distinct designs — range_fade v1 (fractal-pair boundaries), range_fade v2 (rolling extremes), liquidity-sweep fade (structural-level failure confirmation; killed twice), session fade (session-boundary failure confirmation), VP reversion (statistical-boundary excursion fade), and ER-gated sweep-fade (explicit regime filter on the best chassis) — and found NON-VIABLE.** Every kill was an edge kill, never a prop-shape kill; zero constants were ever retuned; every criterion was pre-registered before its test. The failure mechanisms were each different, and the last one is the most general: even an explicit regime gate cannot make M30/H4 mean reversion survive trend quarters, because trailing regime measures open exactly when trend-pullback structure looks like range structure.

**No candidate #7 without new information** — a different timeframe, a different venue, or a genuinely new mechanism class (stat-arb, positioning-based contrarian signals). This is not an evergreen queue; the line is closed, not paused. The portfolio-level consequence stands unchanged and unsolved: the live roster remains effectively one behavior (persistent-trend capture, USD_JPY-centric), and the diversification the mean-reversion slot was meant to provide must now come from a different research direction entirely — when new information justifies opening one.

---

# 2026-07-02 — NEW LINE OPENED: statistical arbitrage groundwork, PHASE 1 ONLY (cointegration screen)

## Status: PRE-REGISTERED before any analysis. Opened under the Bot E closure's new-information trigger — stat-arb is a genuinely new mechanism class (relative-value spread reversion across instrument PAIRS), not a seventh single-instrument mean-reversion costume. **No strategy code in this phase**: no entry/exit logic, no sizing, no spread-trading plugin. Phase 2 is contingent on Phase 1 finding real, regime-stable cointegration.

## Method (pre-registered)

1. **Data:** daily log-price closes, 2021-01-01 → 2026-07-01, all 23 pairs of the closed sweep universe (`results/stop_distance_sweep_table.csv`), aligned on common dates.
2. **Coarse filter:** pairwise correlation matrix of log-price levels. **Logged explicitly: correlation is NOT cointegration** — two trending series correlate spuriously; the matrix produces a candidate shortlist ONLY, never a result. Shortlist threshold |ρ| ≥ 0.90 (chosen now; coarse by design).
3. **Formal tests:** Engle-Granger two-step on the shortlisted combinations (statsmodels `coint`: OLS on log prices → ADF on the spread residual, MacKinnon critical values). **Reported: test statistic, p-value, 1%/5%/10% critical values** — never "looks stationary." New dependency logged: statsmodels 0.14.6 installed into the venv for this line.
4. **Regime-stability requirement (the project's regime-honesty treatment, binding):** every full-window cointegration is re-tested on sub-windows — each calendar year 2021–2026H1, plus pre/post the 2024-01-01 break (the project's own regime findings: the Donchian family's records deteriorate from 2024–2025 onward). **Pre-registered stability bar: full-window EG p < 0.05 AND p < 0.05 in BOTH the pre- and post-break halves AND p < 0.10 in at least 4 of 6 calendar-year windows** (yearly n≈260 has low power — the looser per-year bar is a power concession chosen now, not after results). A combination that cointegrates 2021–2023 and decorrelates after is a FAIL, exactly like every single-window relationship this project has rejected this week.
5. **Deliverable:** one consolidated report on the correlation structure of the whole universe plus a ranked shortlist of genuinely cointegrated, regime-stable combinations — **with zero qualifying combinations stated in advance as a legitimate outcome, not a failure to find one.**

## Explicit open item — logged now, resolved later, does NOT gate Phase 1 or 2

Any resulting strategy holds two instruments simultaneously in opposing directions on net spread exposure. **FTMO's forbidden-practices rules (and likely comparable rules at other firms) restrict opposing positions on highly correlated instruments within one account.** Before this line is ever evaluated on the prop track, that needs firm-specific verification and possibly a synthetic-instrument execution design (trading the spread as one derived signal with net directional risk, not two literal opposing legs). This is a prop-compatibility question, not a research-validity question — Phase 1/2 proceed on their own merits for the paper fleet exactly like every other strategy. Recorded here so it cannot be forgotten at Phase 2 evaluation time.

---

# 2026-07-02 — Stat-arb PHASE 1 RESULT: **ZERO regime-stable cointegrated combinations. Phase 2 does not proceed.**

Consolidated result (per pre-registration 3275e30; artifacts: `backtests/statarb_phase1_results.pkl`; panel = 1,418 common daily closes × 23 pairs, 2021-01-01→2026-07-01).

## The correlation structure (coarse shortlist layer — not results)

253 pairwise combinations: 6 at |ρ|>0.95, 38 at ≥0.90 (the shortlist), 71 at >0.80. The high-correlation set is dominated by shared-leg families (JPY crosses moving on the yen; CHF/SGD crosses moving on the franc/dollar complex) — mechanically expected, and exactly why correlation was pre-registered as a shortlist, not a finding.

## Engle-Granger results on the 38 shortlisted combinations

- **17 of 38 are full-window cointegrated at p < 0.05** (best: EUR_CHF/NZD_SGD p=0.0011, t=−4.52 vs 5% crit −3.34).
- **Every single one fails the pre-registered regime-stability bar.** The dominant failure signature is a clean split at the 2024 break: significant PRE24 and dead POST24 (NZD_USD/USD_JPY 0.004→0.243; EUR_CHF/USD_JPY 0.032→0.561; HKD_JPY/NZD_USD 0.008→0.455) or the mirror (SGD_CHF/USD_CHF 0.226→0.038; CAD_SGD/NZD_SGD 0.397→0.005). Full-window "cointegration" here is largely an artifact of averaging two different regimes — the exact pathology the stability requirement was pre-registered to catch.
- **Closest miss: EUR_CHF/TRY_JPY** (full p=0.0070, PRE24 p=0.047, POST24 p=0.015 — passes all three window tests) but only 2/6 calendar years at p<0.10, below the ≥4 bar; and it carries a lira leg whose spread/carry costs would be prohibitive for spread-trading regardless. **EUR_USD/GBP_USD**, the most tradeable candidate economically, misses on POST24 (p=0.055) and 1/6 years.
- Honesty notes: 38 non-independent tests (shared legs) inflate the full-window hit count; the yearly sub-window bar was pre-registered loose (p<0.10) precisely because n≈260 has low power — even so, no combination managed better than 3/6 years.

## VERDICT

**Zero combinations qualify. This is the pre-stated legitimate outcome, not a failure to find one.** FX pairwise cointegration in this universe is regime-dependent on exactly the timescale this project's other findings predicted (the 2024 break splits nearly every full-window relationship), which is disqualifying for a strategy family whose entire premise is spread stationarity. **Phase 2 (strategy design) does not proceed — its contingency was not met.** The stat-arb line concludes at Phase 1; it reopens only with a materially different universe (non-FX legs, e.g. metals/indices if ever available), a different timescale premise, or a time-varying-hedge methodology (Kalman/rolling-beta) that is a genuinely different research design with its own pre-registration — not a re-run of this screen with looser bars. The prop opposing-legs open item is moot for now and stays logged for any future reopening.

---

# 2026-07-02 — Stat-arb line REOPENED under its pre-registered trigger: time-varying-hedge methodology (Kalman / rolling beta). PRE-REGISTRATION before any analysis.

## Premise and priority pair

Phase 1 found real but regime-unstable cointegration; the dominant failure mode was a hedge ratio that held pre-2024 and broke after — consistent with a persisting relationship whose LEG RATIO drifts, which a fixed-window Engle-Granger test cannot see by construction. **Priority pair, stated before any results: EUR_USD/GBP_USD** — Phase 1's most economically coherent candidate (two G7 majors, shared macro drivers), which failed specifically on the post-break window (p=0.055) and yearly stability (1/6) under the fixed-ratio assumption. This tests whether adaptive beta rescues a wrongly-rejected pair or confirms the relationship is genuinely gone.

## Method (pre-registered, chosen-not-tuned)

- **Estimator 1 — rolling OLS beta, window 90 trading days** (one quarter; matches the project's regime-map granularity; not to be adjusted against results). First 89 days burn-in, excluded.
- **Estimator 2 — Kalman-filtered dynamic beta** (random-walk state [α, β]; observation ln EUR_USD = α + β·ln GBP_USD + ε; delta = 1e-5, the pairs-trading-literature convention, chosen not tuned). First 60 days burn-in, excluded.
- **Stability battery: identical to Phase 1**, run on the ADAPTIVE-beta spread: ADF full-window p < 0.05 AND both pre/post-2024 halves p < 0.05 AND ≥ 4 of 6 calendar years p < 0.10. (Methodological note, logged: ADF criticals on adaptively-estimated residuals are approximate; the battery is used as the comparative standard against the fixed-beta baseline, which is the decision-relevant comparison.)
- **Anti-chasing guard, pre-registered:** a sufficiently fast adaptive filter makes ANY pair look stationary by chasing the spread — residual stationarity alone is therefore not a pass. **Pass additionally requires a sane beta path: same sign throughout post-burn-in, and coefficient of variation (rolling std / |mean|) < 0.5.** A wildly swinging beta is curve-chasing, not a relationship.

## Kill threshold, decided now

**PASS = at least one estimator's adaptive spread meets the full Phase-1 stability battery on EUR_USD/GBP_USD AND passes the beta-sanity guard.** If not — including marginal or ambiguous improvement over fixed-beta — **this reopening closes too**, logged with no spread-trading logic built. One real shot, not a tuning search. If it passes: extend the same method to the other 37 Phase-1 shortlisted combinations (reusing the existing |ρ|≥0.90 shortlist, NOT restarting the 253-combination screen), still with NO strategy/entry-exit code — Phase 2 boundary unchanged. One consolidated report either way.

---

# 2026-07-02 — Adaptive-beta RESULT: priority pair **PASSES**; Phase 2 contingency met — with the discrimination caveat doing real work

Artifacts: `backtests/statarb_adaptive_priority.pkl`, `statarb_adaptive_extension.pkl`.

## Priority pair (EUR_USD/GBP_USD): PASS per the pre-registered rule

- **Kalman:** battery 6/6 years, all windows p≈0.0000; beta guard PASS (mean +0.682, CV 0.148, same-sign) → meets the pre-registered pass outright.
- **Rolling-90 (the conservative estimator):** battery **PASS** — full p=0.0000, PRE24 p=0.0001, POST24 p=0.0014, **5/6 years** — the fixed-beta version of this pair failed POST24 (0.055) and managed 1/6 years; the adaptive version is a decisive, not marginal, improvement on the harder estimator. Its guard missed only on a transient beta sign-touch (CV 0.259, healthy; mean +0.832).
- **Conclusion: the EUR_USD/GBP_USD relationship persists with a drifting ratio — the fixed-window rejection was the ratio-constancy assumption failing, not the relationship.**

## The caveat that must lead any Phase 2 use of these results

**The Kalman battery passed 38 of 38 combinations at p≈0.0000 — including economically meaningless ones. It is non-discriminating**, exactly as the pre-registration's anti-chasing note predicted (filter innovations are near-white by construction). Under the Kalman estimator ALL discrimination lives in the beta-sanity guard; the headline "27/37 extension passes" is therefore a guard-only screen and must not be read as 27 real relationships. The discriminating instrument is the rolling-90 battery + guard.

## Ranked shortlist (by strength of evidence, not Kalman p-values)

- **Tier 1 — pass battery AND guard on the conservative rolling-90 estimator:** **NZD_USD/USD_CAD** (roll90: 4/6 years, guard CV 0.426; Kalman clean) and **USD_CHF/USD_SGD** (roll90: 4/6 years, guard CV 0.473; Kalman clean). Both economically coherent (commodity-dollar inverse; USD-bloc franc/sing).
- **Tier 1-adjacent — the priority pair:** EUR_USD/GBP_USD (roll90 battery 5/6 — the strongest yearly profile of all 38 — guard missed on a transient sign-touch only; Kalman clean). The most tradeable spread economically (two G7 majors, tightest legs).
- **Tier 2 — Kalman-clean with sane betas but roll90-battery fails:** ~24 combinations, dominated by shared-leg families and exotic legs (TRY/HKD/SGD). Weak evidence individually; several are cost-prohibitive to trade regardless (TRY carry/spread; HKD_JPY duplicates USD_JPY through the peg).
- 10 combinations fail outright even under Kalman (degenerate betas — CV up to 259 on near-zero means; these were never relationships).

## Standing verdict

**The reopening's kill threshold is cleared; the Phase 2 contingency is MET.** No strategy code has been written (phase boundary held). Phase 2, if/when directed, should start from the three named candidates (EUR_USD/GBP_USD, NZD_USD/USD_CAD, USD_CHF/USD_SGD), price the legs' spread costs into any spread-trading premise before design, and carries the standing prop opposing-legs open item logged at the line's opening. The 27/37 Kalman number is recorded but explicitly NOT the shortlist.

---

# 2026-07-02 — Stat-arb LEG-COST PREMISE CHECK (Phase 2 prerequisite, operator handoff): **all three candidates pass; ranking unchanged**

Method: two-leg round-trip spread cost (leg spreads from the live-calibrated sweep table; second leg weighted by |β̄| from the rolling-90 fit) expressed in log-spread units against the roll90 spread's own excursion scale — 1σ primary, 2σ (the canonical enter-at-2σ-exit-at-mean amplitude) also reported. Amendment-1-analog flag at 10% of a typical tradeable excursion, per the operator's pre-committed threshold.

| Candidate | Leg spreads | \|β̄\| | Two-leg cost | Spread σ | Cost/1σ | Cost/2σ | Verdict |
|---|---|---|---|---|---|---|---|
| EUR_USD/GBP_USD | 1.5p / 1.8p | 0.83 | 2.52 log-pips | 92.7 | **2.7%** | 1.4% | ok |
| NZD_USD/USD_CAD | 2.4p / 1.7p | 1.35 | 5.62 | 177.9 | **3.2%** | 1.6% | ok |
| USD_CHF/USD_SGD | 1.6p / 2.9p | 1.35 | 4.69 | 121.9 | **3.8%** | 1.9% | ok |

**No candidate is remotely near the 10% flag** — spread movement dwarfs two-leg execution cost on all three, the structural opposite of the RSI post-mortem (where cost ≈ alpha). Cost-adjusted ranking preserves the evidence ranking: EUR_USD/GBP_USD (cheapest AND strongest battery), NZD_USD/USD_CAD, USD_CHF/USD_SGD.

**EUR_USD/GBP_USD beta sign-touch, characterized precisely:** 3 observations of 1,337 (0.2%), a single run 2021-05-06 → 2021-05-10, minimum β −0.146, immediately post-burn-in in early 2021. It does NOT coincide with the 2023–2024 regime break (30 months earlier) or any dated event in this project's record; β's 1st percentile excluding it is +0.466 and the path is otherwise strictly positive (median +0.821). **Verdict: a genuine transient in the estimator's noisiest early window, not a regime signature — EUR_USD/GBP_USD's top ranking stands.**

**Phase 2 design (entry/exit logic) is now unblocked on the cost premise but NOT started** — awaiting direction, per the report-before-proceeding instruction.

---

# 2026-07-02 — NEW LINE OPENED: OANDA client positioning as a contrarian sentiment signal — PHASE 1 (groundwork), PRE-REGISTRATION

## Status: PRE-REGISTERED before any API probing or analysis. A genuinely distinct mechanism class — sentiment/flow, not price-pattern trend capture, not price-pattern mean reversion, not cross-instrument statistics. No strategy code this phase; Phase 2 contingent on Phase 1 establishing a real, characterizable relationship.

## Pre-registered sequence

1. **Data availability FIRST, stated up front, not discovered mid-build:** what OANDA's API exposes (aggregate long/short positioning per instrument — the positionBook endpoint family), at what granularity (snapshot cadence), and how far back historical snapshots reach. **If history falls materially short of the project-standard 2021–2026 window, that is a named constraint reported before any premise work** — a shorter window means weaker regime coverage (the 2021–2023 vs 2024–2026 split has mattered in every line this week) and the premise check's conclusions get scoped accordingly.
2. **Premise characterization (descriptive, regime-map-analog — NOT strategy design):** on this project's live-universe pairs, does extreme positioning skew (pre-registered extremes: ≥70/30 and ≥80/20 long/short) precede reversals, continuations, or nothing? Measured as forward return distributions (1d/5d/20d) conditional on skew state vs unconditional baselines. Both directions of the contrarian hypothesis tested; no thresholds tuned after seeing results.
3. **Free diagnostic, pre-committed:** do positioning extremes show anything distinctive around the 2023–2024 regime break that five other lines have independently hit this week?
4. **One consolidated report. A null result — positioning predicts nothing usable — is a legitimate, valuable outcome, stated in advance.**

---

# 2026-07-02 — Positioning PHASE 1 RESULT: **NULL — the pre-registered extremes do not exist in this data. Line concludes at Phase 1.**

Artifacts: `backtests/positioning_daily.csv` (14,290 snapshots; 11,382 pair-days after price alignment — daily 12:00Z positionBook aggregates, 10 pairs, 2021-01-01→2026-07-01; history verified available back to at least 2018, so depth was NOT the constraint).

## Data availability (step 1): fully sufficient — that part passes

positionBook supported on all 10 project-relevant pairs, 20-minute snapshot cadence, historical snapshots to ≥2018. The 2021–2026 standard window is fully covered.

## Premise (step 2): NULL by non-occurrence

**OANDA aggregate long% across 11,382 pair-days spans 52.7–64.9 (mean 60.5, σ 2.3).** The pre-registered extremes — ≥70/30, ≥80/20, in either direction — occur **ZERO times** on any pair in 5.5 years. Every conditional bucket is empty; the forward-return analysis is undefined, not merely insignificant. The retail-sentiment-lore thresholds this premise imported are structurally unreachable in this dataset: the aggregate is a near-constant ~60% long everywhere, drifting up ~2 points over four years. **Diagnosis, logged:** the positionBook aggregates the STOCK of all open positions across ~600 price buckets (including long-stale ones), not fresh flow — a stock measure is structurally variance-damped, which is exactly what the σ=2.3 says. Per the pre-registration, thresholds are NOT retuned after seeing results (no post-hoc z-score extremes get run under this pre-registration).

## Regime-break diagnostic (step 3): also null

Quarterly mean long% 2022Q4→2024Q4 is a smooth monotone drift on every pair — no inflection at the 2023–2024 break that five price-based lines independently found. Most telling: **USD_JPY held 62.9–64.3% long through the entire yen collapse and its 2024 reversal** — a 30-yen round trip that moved retail aggregate positioning by ~1 point. The measure is insensitive to the largest regime event in the window.

## VERDICT

**Phase 2 contingency NOT met; the line concludes at Phase 1.** This is the pre-stated legitimate null — and a cheap one: one collection pass settled it. Reopening requires a genuinely different design with its own pre-registration: (a) a flow-sensitive or relative transform (e.g., long% z-scored against its own history — plausible, but that is a NEW premise with new thresholds, not this one retuned); (b) the order book rather than the position book, or per-bucket structure rather than the aggregate; or (c) an external positioning source (e.g., CFTC futures COT) with different construction. The sentiment mechanism class remains untested in general — what is now tested and dead is specifically "OANDA aggregate position-book skew at absolute extreme thresholds."

---

# 2026-07-02 — Stat-arb PHASE 2 PRE-REGISTRATION: spread-trading kill-test, three candidates in parallel (operator handoff)

## Status: PRE-REGISTERED before any code. Parallel-protocol discipline (Bot E precedent): identical mechanics across all three candidates, one report per candidate as each lands, pre-committed tie-break.

## Shared mechanics, decided now, CHOSEN NOT TUNED

- **Spread:** Phase 1's confirmed rolling-90 OLS adaptive-beta log-price spread, daily closes — no new estimator.
- **Signal:** z-score of the spread vs its own rolling 90-day mean/std (window matched to the beta window for consistency). **Entry at |z| ≥ 2.0** (standard non-optimized threshold, stated as such): z ≥ +2 → short spread (sell y, buy β·x); z ≤ −2 → long spread. **Exit at |z| ≤ 0.5** (partial retrace, not full mean). **Stop at |z| ≥ 3.5** continuing against entry — thesis invalidated; the structural-stop requirement's spread-trading equivalent. No mid-line retuning of any threshold.
- **Trade-idea sizing (single risk unit, NOT per-leg):** fixed $80 risk (project convention) on the aggregate two-leg position. Adverse span entry→stop = 1.5σ of the spread at entry ⇒ y-leg notional N = $80 / (1.5·σ_entry) in log-spread units; x-leg = β_entry·N. **Legs frozen at entry** (β does not rebalance mid-trade); trade P&L = ±N·[(y_t − y_e) − β_e(x_t − x_e)] − two-leg cost.
- **Per-trade cost check at entry-time sizing (pre-committed):** two-leg round-trip cost as % of the $-risk-to-stop reported per trade; must stay under the 10% Amendment-1-analog bar per candidate (aggregate check said 1.8–2.5%; the per-trade distribution is verified, not assumed).
- **Execution granularity, documented:** daily closes — exits/stops fill at the first close crossing the threshold (no intraday stop precision); exit z reads the evolving spread while P&L realizes on frozen legs (small basis, documented).

## Kill-test and adjudication, decided now

**Full 2021–2026 window directly** (established: regime-sensitive designs mislead on short windows). Per candidate: (1) **majority of years net-positive** (trade assigned to entry year); (2) **no single-year dependency** (ex-best-year still positive; standard top-5 concentration reported); (3) **pre/post-2024 stability of realized P&L consistent with Phase 1's stability finding** — a strategy that only works pre-2024 despite a stability-confirmed relationship is itself a notable, reportable finding, adjudicated as a fail on this criterion. Low expected trade counts (~2σ entries on daily data) — min-N flagged per cell rather than papered over.

**Pre-registered tie-break (Bot E rule):** all passers get full prop-track (with the close-based-marks caveat documented) and portfolio-overlap evaluation; deployment priority to the strongest full-window adjudication; others validated-but-benched.

## Risk-layer engineering flags — logged now as required, NOT forced into the existing gates

New sizing logic (`risk.spread_trade_units`) is legitimate to add; the following existing single-instrument assumptions do NOT cleanly extend and are flagged rather than worked around: (1) **`MAX_POSITIONS_PER_INSTRUMENT` treats legs independently** — spread trades need a trade-idea group identity so gates evaluate the pair atomically; (2) **two-leg entry must be atomic against the currency-exposure and margin gates** (project BOTH legs jointly before either fills) — the dangerous failure is leg-1 filled, leg-2 gated, leaving naked directional exposure the strategy never intended; (3) **NFA/FIFO account conflict:** EUR_USD/GBP_USD legs collide with intraday's live EUR_USD and GBP_USD positions on -002 — any deployment of that candidate requires an isolated sub-account (pullback30 precedent) or the conflict-free candidates (NZD_USD/USD_CAD, USD_CHF/USD_SGD legs are not traded by the fleet); (4) margin for the idea = sum of both legs' `required_margin_usd`. Items (1)–(3) are deployment engineering, built only if a candidate passes.

## Candidate pre-registrations

- **2A: EUR_USD/GBP_USD** — Phase 1 rank #1 (strongest battery, cheapest legs, 2.7%/1σ cost). Note the FIFO flag above applies to deployment, not the kill-test.
- **2B: NZD_USD/USD_CAD** — rank #2 (conservative-estimator Tier 1, 3.2% cost); fleet-conflict-free legs.
- **2C: USD_CHF/USD_SGD** — rank #3 (Tier 1, 3.8% cost, widest σ); fleet-conflict-free legs.

---

# 2026-07-02 — Stat-arb PHASE 2 KILL-TEST RESULTS: **ALL THREE CANDIDATES PASS** — with a min-N reservation logged front and center

## Per-candidate adjudication (full 2021–2026 window, daily closes, spread included per trade)

**2A EUR_USD/GBP_USD:** 19 trades, 68.4% WR, **net +$471.22**. Years positive **6/6** ✓; ex-best(2021) +$258.00 ✓; PRE24 +$328.09 / POST24 +$143.13 — both positive, stability consistent with Phase 1 ✓; zero stops hit; per-trade cost median 2.9% / max 4.4% of risk-to-stop ✓. Top-5 win share 56.5% (13 wins total — high by construction at this n).

**2B NZD_USD/USD_CAD:** 24 trades, 75.0% WR, **net +$813.89**. Years positive 5/6 (the miss, 2022, is −$2.75 — breakeven, not a losing year) ✓; ex-best(2025) +$562.26 ✓; PRE24 +$237.58 / POST24 +$576.31 ✓ (strengthens post-break); 3 stops in 24; costs 3.4%/7.0% ✓; top-5 share 42.6% (lowest).

**2C USD_CHF/USD_SGD:** 21 trades, 71.4% WR, **net +$559.36**. Years positive **6/6** ✓; ex-best(2024) +$423.92 ✓; PRE24 +$208.64 / POST24 +$350.72 ✓; 4 stops; costs 3.4%/7.0% ✓; top-5 share 49.4%.

## Tie-break evaluation (all passers, per the pre-registered rule)

**Prop-track (close-based-marks caveat standing):** the strongest matrix of any strategy family tested — all three survive FTMO 2-Step, High Stakes, and FundedNext at **1.00%** (2C at 0.50% on FundedNext), and FTMO 1-Step at 0.50–1.00%: worst daily drawdowns −0.6% to −4.6% at 1%, trailing floors never touched at ≤0.50%. First designs in the project to survive the trailing mechanics at meaningful size. (5%ers' 3-profitable-days consistency needs ≥0.50% sizing to register 0.5%-of-initial days — a sizing footnote, not a survival issue.)

**Portfolio overlap — the finding of the day:** monthly P&L correlation vs the combined live fleet (corrected records): **2A r = −0.049, 2B r = +0.013, 2C r = −0.030.** Effectively zero. This is the FIRST P&L source in the project's history that is structurally uncorrelated with persistent-trend capture — the diversification the one-behavior note has flagged since 2026-07-01 and six mean-reversion designs failed to provide. Instrument-level: 2B/2C legs are not traded by the fleet (structurally clean); 2A's legs collide with intraday's EUR_USD/GBP_USD (FIFO flag stands for deployment).

**Deployment priority (pre-registered: strongest full-window adjudication): 2B NZD_USD/USD_CAD** — highest net, strongest POST24, lowest concentration, most trades, conflict-free legs. **2C validated-but-benched** (second; conflict-free, would pair with 2B only after correlation-between-spreads is checked). **2A validated-but-benched** (thinnest sample, weakest POST24, FIFO-conflicted legs).

## Reservations, logged with the pass — not buried

1. **min-N:** 19–24 trades per candidate over 5.5 years (~4/year). Every year-cell is below the passport's min-N 10; the WR confidence intervals are wide (75% on n=24 is 53–89% at 95%). The pre-registered kill-test criteria are met, but the evidence weight is a fraction of the Donchian validations (thousands of trades) — the passport's box-2 will show ❌ honestly, and any deployment is probation-first with a long clock (trade accrual at ~4/year makes a 60-trade probation a multi-year horizon; the probation design will need calendar-based terms).
2. **Execution granularity:** daily-close fills, no intraday stop precision; close-based prop marks understate intraday troughs.
3. **Deployment engineering prerequisites unbuilt** (pre-registered flags): atomic two-leg gates, trade-idea grouping, sub-account placement. No live deployment until built and tested.
4. Same-family caution: 2B and 2C share the "USD-bloc cross vs USD major" character; deploying both would need their spread-P&L cross-correlation checked first.

**Phase 2 verdict: the stat-arb line has produced the project's first validated, uncorrelated, prop-shape-clean strategy family. Next decisions (operator's): probation design for 2B (calendar-based terms given ~4 trades/year), deployment engineering build, and account placement.**

---

# 2026-07-02 — Stat-arb DEPLOYMENT DESIGNS (operator handoff): atomic execution spec, risk-layer grouping (built + tested), 2B probation terms, account placement. **REPORTED BEFORE ANY ORDER-PLACEMENT CODE.**

## 1. Atomic two-leg execution design (SPEC ONLY — no order code written)

**Mechanism: sequenced fill-or-kill with unwind-on-partner-failure.** OANDA v20 has no cross-instrument atomic order type, so broker-level atomicity is impossible; the design minimizes and bounds the non-atomic window instead:

1. **Joint gates first** (built, below): combined currency projection, both-leg collision check, summed two-leg margin — the idea is approved or rejected WHOLE before any order exists.
2. **Leg 1 = the less-liquid leg** (NZD_USD for 2B — the harder fill decides), placed as a FOK market order. FOK forbids partial fills by construction. No fill → the idea aborts with nothing open.
3. **Leg 1 filled → leg 2 FOK immediately.** Fill → idea open; both legs tagged `clientExtensions "spread:<idea_id>"`.
4. **Leg 2 fails (reject or 5s timeout) → immediate IOC market unwind of leg 1**, up to 3 attempts with backoff. Unwind success → idea aborted, cost = spread + slippage on one round trip, logged as an incident.
5. **Unwind fails → CRITICAL alert, strategy suspends new entries**, the naked leg is bounded by the emergency hard SL (below); the 1-hour unresolved-naked-leg early-kill clock starts.
6. **Emergency hard SL on each leg at entry** (~2× the spread-stop-equivalent distance): catastrophe insurance only. Necessary because **spread exits are SOFTWARE-managed (z-based) — a new operational class for this fleet**: unlike every live strategy's broker-side fire-and-forget SL/TP, this process must be ALIVE to exit properly. The crash-recovery design (logon triggers, pidfile guard) is the mitigation; the hard SL is the backstop.
7. **Startup reconciliation:** scan open trades for `spread:` tags missing their partner → unwind orphans immediately. Covers process crash between fills.

**§1a — Signal staleness across the execution window (added 2026-07-02 on operator review, before build):** two distinct staleness windows exist and get opposite treatments:

- **Decision-to-leg-1 (the real exposure — potentially HOURS):** the z-signal computes from daily closes; the process executes at its scheduled evaluation time, so the price generating the signal and the price at execution can differ materially. **Pre-flight staleness check, now in the spec: immediately before leg-1's FOK, recompute z with live mids as the current observation; proceed only if |z_live| ≥ 2.0 — the SAME pre-registered entry threshold, evaluated at the moment of commitment. No new constant is introduced (no "1.75σ grace band" to tune later). A decayed signal skips cleanly; the next daily evaluation decides fresh.**
- **Leg-1-fill-to-leg-2 (seconds):** **NO signal re-check, by design — hedge completion is unconditional.** Once leg 1 is filled, an unhedged leg is strictly worse than a marginally stale spread: the only acceptable states are fully-hedged or fully-flat, and re-litigating the signal mid-sequence would add a third (voluntarily naked). Magnitude honesty: at 2B's spread σ (~1.8% over 90 days), a sub-10-second window moves z by ≪0.1σ outside intervention-class conditions; a fill that lands 0.1σ stale is still deep inside the designed risk envelope (stop 1.5σ away, sizing set at entry σ). The intervention-class tail is the same accepted residual already listed under failure mode (b), bounded by the 5s timeout, the unwind path, and the emergency SLs.
- **Verification loop:** the 3-month engineering review compares realized entry z (at fill prices) against signal z per trade — if the staleness gap systematically erodes entries, that is machinery evidence for the review, not a license to retune thresholds mid-probation.

---

# 2026-07-02 — Stat-arb 2B BUILD COMPLETE (46a7af8); deployment staged, blocked on -003 token access

Built per the approved designs: `spread_signal.py` (Phase 2 mechanics verbatim + §1a `live_z`), `spread_execution.py` (sequenced FOK / unwind-on-partner-failure / emergency SLs / idea tags / startup orphan reconciliation; broker ops injected for testability), `spread_trader.py` (standalone process — hourly loop acting once per completed daily close, joint gates, trade-idea sizing, software-managed exits, persistent naked-leg suspension, per-account floor check, fleet banner/pidfile conventions, refuses to start if its account NAV is unreadable), `test_spread_execution.py` (permanent suite, **6/6**: leg-2 failure → unwind; unwind failure → NAKED_LEG + suspend; leg-1 no-fill clean abort; orphan reconciliation; §1a staleness-skip semantics; happy path with leg-order and tagging asserted). `scheduler/Rhyme-Spread2B.xml` staged (S4U, logon trigger, 150s stagger — fleet convention). Practice account only, per the approval.

**Deployment blocker, discovered at verification:** the **-003 sub-account exists** (visible in AccountList) **but the API token is FORBIDDEN from reading it** (AccountSummary 403) — the standing token predates the sub-account. **Operator unblock: regenerate the v20 token at OANDA** (and confirm ~$4k funding). Remaining deployment steps, in order, once unblocked: (1) verify `get_nav_for(-003)` and funding; (2) add -003 to `main.py RESEARCH_ACCOUNTS` (floor coverage — deliberately NOT added while the token 403s, to keep the other bots' floor checks quiet); (3) register `\Rhyme\Rhyme-Spread2B` and launch via `schtasks /run` (deny-list approval gate applies); (4) verify banner (commit, account, NAV, PID = pidfile); (5) GOVERNANCE roster flips 2B to live-on-probation and the 24-month clock starts.

---

# 2026-07-03 — SPREAD2B DEPLOYED: live on probation, account -003. Fleet is now FOUR processes. One real bug caught at deployment verification.

**Sequence executed (operator regenerated the token and funded -003 at $4,000):** new token verified against all three accounts → -003 added to `RESEARCH_ACCOUNTS` (4e750a1) → full fleet restart REQUIRED and performed (the regenerated token invalidated the old one held in the three bots' memory; `schtasks /end` + elevated kill + `schtasks /run`, staggered) → all three banners verified on 4e750a1 with PIDs matching pidfiles, position caps correctly seeing the open -002 trades, floor checks now sweeping all THREE accounts → `\Rhyme\Rhyme-Spread2B` registered (elevated, S4U) and launched.

**Bug caught at deployment verification — the negative-beta hedge sign (fixed 45b0017 before any trade could fire):** the first live eval printed **β = −0.968**. NZD_USD/USD_CAD are inversely related — exactly what Phase 1 measured (β̄ −1.35, same-sign-negative guard) — but `try_entry` had hardcoded the positive-beta x-leg sign, which would have made the hedge leg DOUBLE the exposure instead of hedging it. The kill-test simulator was sign-correct (it traded the spread value directly; P&L math carries β's sign), so no backtest result is affected — the bug lived only in the live leg-construction translation. Fixed via `spread_signal.leg_signs()` (x-leg sign = −sgn·sign(β)); unit test locks all four direction×sign cases; spread2b restarted on the fix. **This is precisely the class of defect the 3-month engineering review exists for, caught at hour zero — and a reminder that a sign-correct simulator does not imply a sign-correct order constructor.**

**Verified live state:** banner `commit 45b0017 | PID 41436` (= pidfile), account -003 NAV $4,000.00, startup orphan reconciliation clean, first daily eval 2026-07-01 close: z=0.11 (flat — correctly no entry), β −0.968, σ 0.00937. **The 24-month probation clock runs from 2026-07-03**; engineering review due 2026-10-03; first quarterly cointegration battery due 2026-10-01. GOVERNANCE roster and strategies.json flipped.

**The fleet is now four processes on three accounts:** intraday + scalp30 (-002), pullback30 (-001, probation), spread2b (-003, probation) — three behaviors, one of them structurally uncorrelated with the other two for the first time in the project's history.

**Failure modes this CANNOT fully protect against, stated plainly:** (a) the between-legs window is irreducible (~sub-second typically; an API outage inside it leaves a naked leg until unwind/SL); (b) unwind slippage is unbounded in principle in fast markets (trivial at our sizes, but the yen-intervention days in our own record are the counterexample class); (c) leg-2 margin rejection after leg-1 consumed margin — mitigated by pre-checking the SUM, a residual race remains; (d) weekend/halt gaps while holding — the z-stop cannot fill through a gap and the emergency SLs gap too (same class as fleet gap risk, on two legs); (e) the unwind itself pays the spread — repeated leg-2 failures would bleed by aborting (mitigated: 3 aborted ideas in a week = engineering suspend, folded into the incident accounting).

## 2. Risk-layer trade-idea grouping — BUILT and TESTED (no order placement involved)

`portfolio_state.py` gains `project_spread_exposure` (joint projection, shared currencies net exactly once), `check_spread_currency_exposure_cap` (atomic worsening-only cap check on the combined projection — rejects the WHOLE idea), `check_spread_position_cap` (either-leg collision → whole idea rejected; the FIFO-safety gate), and `group_positions_by_idea` (legs tagged `spread:<id>` count as ONE risk unit — deployed-risk accounting cannot double-count the idea). **`test_spread_grouping.py` (permanent suite, 5 tests) verifies both mis-count directions the handoff named:** shared-USD nets once (no double-count), gross NZD/CAD legs fully counted (no under-count via netting-away), plus the decisive atomicity case — a state where leg 1 ALONE passes the single-instrument gate but the joint projection correctly rejects the idea. Standing collision rule added to GOVERNANCE (any instrument that is a leg of a live spread must be collision-checked before any future deployment).

## 3. 2B probation terms — designed for the thin-sample reality (full terms in GOVERNANCE)

24-month minimum calendar horizon (expected forward n ≈ 9 — stated honestly as validating MACHINERY and absence-of-collapse, not statistical significance, which no near-term horizon can deliver at 4 trades/yr); 3-month engineering review (slippage/unwind/fill quality); **quarterly Phase-1 stability-battery re-run as the mechanical falsifier — battery failure is an early-kill regardless of P&L**; early-kills at −$400 (≈5R), any >1.5×-design-risk single loss (engineering kill), unresolved naked leg > 1h; 24-month pass = net > 0 AND WR ≥ 45% (deliberately below the CI floor — tight thresholds at n≈9 are noise theater) AND zero unresolved incidents. GOVERNANCE carries the explicit structural-thinness statement covering all three candidates.

## Account placement: **isolated third sub-account (-003)** — decided and justified

(a) **FIFO-proofing as a class, not per-incident:** isolation removes leg collisions against the current fleet AND future fleet changes; (b) **forward-sample purity** — the pullback30 precedent directly; (c) **blast-radius containment for the new operational class** (software-managed exits; an execution bug on -003 cannot touch -002's Donchians or -001's probation sample); (d) the per-account $800 floor extends naturally — -003 joins `RESEARCH_ACCOUNTS`, breach on ANY account still suspends the whole fleet. **Requires operator action: create and fund the -003 sub-account** (same $4k convention as -001 would make floor semantics uniform).

**STATUS: designs reported, order-placement code NOT written. Build proceeds only on review/approval: order-placement module implementing spec §1, the spread plugin, unit tests including the §1 failure-mode paths (leg-2 failure → unwind; unwind failure → suspend; startup orphan reconciliation), then scheduler/S4U/logging deployment per fleet convention. 2C and 2A benched passports are in GOVERNANCE now.**

---

# 2026-07-03 — Grid cells 1–2: mechanics specs, logged BEFORE first run (registration aaf7882/20ee8d5)

## Cell 2 — Donchian midpoint-stop, M5, USD_JPY: ZERO new code

"Donchian midpoint-stop" is the existing `donchian_plugin.py` VERBATIM — its SL has always been the channel midpoint (with 2.5R TP, 20-period channel, H4 EMA20/50 trend filter, close-back-inside re-arming). The cell runs that plugin unchanged at an M5 signal timeframe (mode mapping "m5" = H4 HTF / M5 LTF, the scalp30 pattern one rung down). The strongest possible form of chosen-not-tuned: not one constant is new.

## Cell 1 — fvg_nested, M5 entry / 4H anchor, GBP_USD + USD_JPY: spec (constants from project conventions, chosen-not-tuned)

- **4H anchor:** most recent UNFILLED 4H fair-value gap within the trailing 120-candle structural window (project convention). FVG = classic 3-candle imbalance: bullish when `low(i) > high(i-2)` → zone `[high(i-2), low(i)]`; bearish mirror. Unfilled = no subsequent 4H candle has traded through the zone's far edge since formation.
- **Nested M5 trigger:** while M5 price is INSIDE the active 4H zone, an M5 FVG forms in the anchor's direction → enter at that M5 third candle's close. (The nesting is the mechanism: the 4H gap says where, the M5 gap says when.)
- **SL:** far edge of the 4H zone + 5% of zone height (structural anchor invalidation; the project's 5% buffer convention). **TP: 2.5R** (trend-continuation family convention — FVG retrace-and-go is continuation, so it inherits the trend-origin/Donchian target, not the range family's midpoint).
- **Amendment-1 spread floor** (TP distance ≥ 10× assumed live spread); one trade per 4H-FVG identity (formation timestamp — non-starving, new gaps arm immediately); both directions; `WARMUP_HTF_CANDLES = 121`.

Quick-checks run 2023 only, $80 fixed risk, spread included, corrected harness, against the REGISTERED kill criteria verbatim (cell 1: <15 trades combined / median stop <15 pips / expectancy negative on both pairs; cell 2: median stop <15 pips / expectancy negative / <20 trades). A pass grants a full-window test only, per the multiplicity note.

---

# 2026-07-03 — Grid cells 1–2 QUICK-CHECK VERDICTS (2023, registered criteria verbatim)

## Cell 2 — Donchian midpoint-stop, M5, USD_JPY: **KILLED on two of three registered criteria**

2,991 trades, 28.8% WR, net **−$14,212.98**, expectancy **−$4.75/trade** (registered kill: negative ✗), median stop **14.2 pips** (registered kill: <15 ✗); trade count fine (≥20 ✓). **Per the closure rule, Donchian midpoint-stop × M5 × USD_JPY closes permanently** (reopening bar: structurally different stop or estimation mechanism only). Mechanism read: at M5 the channel midpoint sits ~14p from entry — the 1.5p spread is >10% of the stop, the exact regime the median-stop criterion was registered to catch, and 2,991 spread payments did the rest. The same plugin's M30 record (scalp30) remains what it was; this kill is timeframe-specific by construction.

## Cell 1 — fvg_nested, M5 entry / 4H anchor, GBP_USD + USD_JPY: **PASSES its quick-check**

| Pair | n | WR | Net | Expectancy | Median stop |
|---|---|---|---|---|---|
| GBP_USD | 87 | 27.6% | −$575.48 | −$6.61 | 22.0p |
| USD_JPY | 99 | 35.4% | **+$1,485.57** | **+$15.01** | 19.9p |
| Combined | 186 | — | +$910.09 | +$4.89 | 20.8p |

Registered criteria: ≥15 trades combined ✓ (186); median stop ≥15p ✓ (20.8p); expectancy negative on both pairs? **NO** — USD_JPY positive (35.4% WR vs ~28.6% breakeven at 2.5R). **PASS → grants the full 2021–2026 window ONLY** (multiplicity note standing: with 9 cells registered, one spurious quick-check pass is expected by chance — this could be it, and the full window plus concentration check is where that gets settled). Pattern note, familiar: USD_JPY carries, GBP_USD bleeds — the project's USD_JPY-specificity signature appearing at M5 on its first read. Full-window per-year runs (both pairs, standard passport process) launched.

---

# 2026-07-03 — Grid cell 1 FULL-WINDOW ADJUDICATION: **FAILS the concentration check — cell CLOSED. The multiplicity note called it.**

Full windows (per-year 2021–2026ytd, M5/4H, spread included, corrected harness):

**GBP_USD: 429 trades, net −$3,103.65** (2/6 years positive; both directions negative) — rejected outright, confirming its negative quick-check expectancy at scale.

**USD_JPY: 497 trades, net +$2,491.31** (4/6 years positive; long −$848 / short +$3,339) — and the decomposition kills it:

- **The single 2023-SHORT year×direction cell made +$2,790.05 — MORE than the entire six-year net.** Excluding that one cell, the record is **−$298.74.** Trade-level concentration is clean (top-5 win share 3.2%); the dependency is structural at the year×direction level, which is precisely what the passport's per-year per-direction lens exists to expose, and it is the registered concentration fail ("any cell whose full-window result depends on a single year fails the concentration check as usual") in its a-fortiori form.
- **2025 + 2026 combined: −$2,513.93** — the two most recent periods both negative, the same deterioration signature as the whole trend family.
- Fixed-$80 maxDD −$2,990 on a +$2,491 six-year net — return-to-drawdown below 1.

**Verdict: cell 1 FAILS the standard passport at the concentration check. Per the closure rule, fvg_nested × M5/4H × (GBP_USD, USD_JPY) closes permanently** (reopening bar: structurally different stop or estimation mechanism).

**The instructive part, worth naming plainly: the quick-check sampled exactly the carrying year.** 2023 — the registered quick-check window for every grid cell — happens to be the one year whose short side pays for this mechanism's whole record. The 2023 expectancy (+$15.01/trade) was real but maximally unrepresentative, and the multiplicity note's predicted one-spurious-pass-in-nine appears to have been this cell. The registration's design worked end to end: the quick-check pass granted only a full window, the full window's concentration check caught the fragility, and no deployment decision was ever at stake.

**Grid status: cells 1 and 2 both CLOSED (2 of 9 adjudicated). Cells 3–9 remain.**

---

# 2026-07-03 — Grid cells 3–5: timeframe mappings, logged before first run (zero new constants in all three)

- **Cell 3 — Donchian midpoint-stop, M15, USD_JPY:** `donchian_plugin.py` VERBATIM at **H4 HTF / M15 LTF** — the scalp30 family pattern (H4 filter, signal TF one rung down), consistent with cell 2's mapping. (The legacy "scalp" mode's H1/M15 mapping is NOT used: the cell tests the validated family's structure at M15, not a new filter combination.)
- **Cell 4 — Trend-origin pullback, H1, USD_JPY:** `trend_origin_pullback_plugin.py` (long+short, as-designed) VERBATIM at **H4 HTF / H1 LTF** — the existing intraday mapping.
- **Cell 5 — Trend-origin pullback, H4, USD_JPY:** same plugin VERBATIM at **D HTF / H4 LTF** — the existing swing mapping.

Quick-checks: 2023 only, $80 fixed risk, spread included, corrected harness, registered kill criteria verbatim (cell 3: median stop <15p / expectancy negative / <20 trades; cell 4: expectancy negative / <15 trades; cell 5: expectancy negative / <8 trades). Registration note (a) standing: pullback30's M30 probation status is evidence, not grounds to skip cells 4–5.

---

# 2026-07-03 — Grid cells 3–5 QUICK-CHECK VERDICTS

## Cell 3 — Donchian midpoint-stop, M15, USD_JPY: **KILLED (expectancy negative)**

1,008 trades, 29.5% WR, net −$476.79, expectancy **−$0.47/trade** (registered kill ✗); median stop 26.3p ✓; n ✓. **Cell closes permanently.** The cross-timeframe gradient is now measured and monotone for this exact mechanism on this pair in 2023: **M5 −$4.75/trade → M15 −$0.47 → M30 +$4.25** (scalp30's 2023). The family's edge crosses zero between M15 and M30 — the spread-cost-vs-stop-width story quantified in one line, and independent confirmation that scalp30's M30 sits just above the viability floor rather than comfortably.

## Cell 4 — Trend-origin pullback, H1, USD_JPY: **passes — barely, and flagged as such**

239 trades, 29.3% WR, net +$62.29, expectancy **+$0.26/trade** (not negative → registered pass); median stop 65.2p. Stated plainly: +$0.26/trade on n=239 is statistically indistinguishable from zero — this pass is the weakest kind the binary criterion admits, and the lesson note applies. Full window granted only.

## Cell 5 — Trend-origin pullback, H4, USD_JPY: **passes cleanly**

46 trades, 34.8% WR, net +$571.05, expectancy **+$12.41/trade**; median stop 188.6p (spread = 0.8% of stop — the best cost profile of any grid cell). Full window granted only.

Both full windows (per-year 2021–2026, USD_JPY, registered mappings) launched.

---

# 2026-07-03 — Grid cell 5 FULL-WINDOW ADJUDICATION: **PASSES the passport — the grid's first survivor** (validated-but-benched; deployment not granted)

**Trend-origin pullback, D/H4, USD_JPY, per-year 2021–2026, spread included: 239 trades, 34.3% WR-ish by year, net +$2,747.04** (long +$4,191.17 / short −$1,444.13).

| Year | n | Net | | Year | n | Net |
|---|---|---|---|---|---|---|
| 2021 | 44 | +$465.62 | | 2024 | 42 | **−$770.59** |
| 2022 | 38 | +$1,057.54 | | 2025 | 48 | **+$1,382.53** |
| 2023 | 46 | +$571.05 | | 2026 | 21 | +$40.89 |

**Passport boxes:** (1) 6yr spread-included positive ✓; (2) min-N: full-year year×direction cells all ≥12 ✓, partial-2026 short n=7 flagged; (3) concentration: **ex-ANY-single-year positive** (worst ex-2025 +$1,364.51), top-5 win share 7.1% — the cleanest concentration profile of any grid cell ✓; (4) DD: fixed-$80 −$2,040.91, 1%-compounding −22.8% (final 1.37x — modest growth, survivable trough) ✓; (5) overlap vs live: NOT yet measured (required before any deployment discussion); (6) factor dependence: trend-family, but note **2025+2026 = +$1,423.42 POSITIVE** — the only trend-family record on the books that is positive through the deterioration window that bleeds every live Donchian and trend-origin M30; documented, not explained; (7) distinct behavior ❌ — same mechanism as pullback30 one rung down (M30, on probation); registration note (a) makes the probation outcome evidence across this cell, and any deployment decision must confront the box-7 redundancy plus the overlap measurement.

**Prop overlay (registered process):** FTMO 2-Step **1.00%**, High Stakes Classic **1.00%**, FTMO 1-Step **0.25%**, FundedNext Legacy **0.25%**. Zero daily breaches at any tested level (worst day −4.53% at 1%); static floors never touched.

**Standing outcome: validated-but-benched.** The grid grants adjudication + prop row, never deployment. Honest flags carried with the pass: n=239 (~40/yr) is a thin annual sample; the short side loses (−$1,444) while the as-designed total passes on its own (no post-hoc variant proposed, per the pullback30 rule); and the H1 sibling (cell 4) is still running — its result bears on whether cell 5's structure is robust or a rung-specific artifact.

---

# 2026-07-03 — Grid cell 4 FULL-WINDOW ADJUDICATION: **FAILS — cell CLOSED**

**Trend-origin pullback, H4/H1, USD_JPY: 1,280 trades, net +$8,804.93** (long +$16,500.37 / short −$7,695.44) — and the structure fails the passport:

- **3 of 6 years positive — fails the majority criterion** (2021 −$252, 2022 **+$7,335**, 2023 +$62, 2024 +$3,890, 2025 −$1,624, 2026 −$606).
- **2022 is 83% of the net.** Ex-2022 the record is +$1,470 — technically positive, but the year profile is the familiar windfall shape.
- **2025+2026 combined negative** (−$2,230) — the trend-family deterioration signature present at H1, exactly where it is ABSENT at H4.
- Long side +$16,500, positive EVERY year — the M30 parent's long-side signature reappears at H1. Recorded, not acted on: the as-designed result is what's adjudicated (pullback30 rule), and an H1 long-only would be a second post-hoc directional selection of the same kind already on probation at M30.

**Per the closure rule, trend-origin pullback × H1 × USD_JPY closes permanently.**

**Cross-rung synthesis (cells 4–5 + the M30 parent):** at every rung the long side is positive (M30: every year; H1: every year; H4: 5/6) and the short side bleeds — but only H4's as-designed total survives adjudication, because its short-side bleed is small (−$1,444) where H1's is fatal (−$7,695). Higher timeframe = fewer, wider-stopped shorts = less bleed per unit of long edge. Cell 5's pass is consistent with structure, not a rung-specific fluke — but that consistency argument is exactly what a benched record is for; it earns nothing beyond the bench.

**Grid scoreboard: cells 1, 2, 3, 4 CLOSED; cell 5 validated-but-benched; cells 6–9 remain.**

---

# 2026-07-03 — Grid cells 6–9 VERDICTS: **THE GRID IS COMPLETE, 9 of 9 adjudicated**

## Cell 7 — stat-arb OLS, H4 estimation, NZD_USD/USD_CAD: **KILLED at quick-check**

Half-life stable (74h vs the pre-logged 1,167h threshold) but **expectancy −$3.85/trade** (29 trades, −$111.54) → registered kill. Closed.

## Cell 6 — stat-arb OLS, H4 estimation, EUR_USD/GBP_USD: quick-check pass (barely) → **full window FAILS — CLOSED**

Quick-check: HL 60h (vs 875h) stable; 22 trades, expectancy **+$0.22/trade** — the same statistically-zero pass shape as cell 4, flagged as such at grant time. Full window: **147 trades, net −$1,101.36** (4/6 years nominally positive but 2025 −$940, 2026 −$463; **PRE24 +$238 / POST24 −$1,340**). Fails outright. **The instructive mirror: the DAILY-estimated chassis on this same pair-family strengthens post-2024 (2B POST24 +$576) while the H4-estimated version dies there** — a 90-bar window at H4 holds 15 calendar days of memory vs 90 at daily, and the shorter memory chases post-break noise (2025 stop-outs: 9 of 31 trades). Estimation-granularity is not a free parameter; the validated chassis's daily memory is load-bearing. Second live instance of the lesson-note pattern (near-zero quick-check pass failing at scale).

## Cells 8–9 — stat-arb OLS, daily estimation: **adjudicated entirely from existing Phase-2 artifacts** (confirmed covering the registered criteria)

Both needed the pre-authorized 2021–2023 extension (2023 round-trips: cell 8 n=3, cell 9 n=4 — both <10): **cell 8** extended n=10, expectancy **+$32.81** → quick-check pass; **cell 9** extended n=12, **+$19.80** → pass. Their granted full windows ARE the Phase-2 full-window adjudications, already complete: **cell 8 = candidate 2A** (passed, validated-but-benched, FIFO-flagged legs); **cell 9 = candidate 2B** (passed, deployed, live on probation on -003). No new compute; chains closed from artifacts.

## GRID FINAL SCOREBOARD (9/9)

| Cell | Mechanism × timeframe | Outcome |
|---|---|---|
| 1 | fvg_nested M5/4H | closed at full window (2023-short cell = whole net) |
| 2 | Donchian midstop M5 | closed at quick-check (spread-eaten, −$4.75/trade) |
| 3 | Donchian midstop M15 | closed at quick-check (−$0.47/trade) |
| 4 | trend-origin H1 | closed at full window (2022 = 83% of net) |
| 5 | trend-origin D/H4 | **PASSED — validated-but-benched** |
| 6 | stat-arb H4-est EUR/GBP | closed at full window (POST24 −$1,340) |
| 7 | stat-arb H4-est NZD/CAD | closed at quick-check (−$3.85/trade) |
| 8 | stat-arb daily EUR/GBP | = 2A: passed, benched (pre-existing) |
| 9 | stat-arb daily NZD/CAD | = 2B: passed, deployed (pre-existing) |

**What the grid actually bought, in four findings:** (1) the Donchian timeframe gradient is measured and monotone — the edge crosses zero between M15 and M30, so scalp30 sits just above the viability floor; (2) trend-origin's long edge exists at every rung while its short bleed scales inversely with timeframe — D/H4 is the one rung where the as-designed total survives, and it is the grid's single new validated record (benched, box-7-flagged against pullback30); (3) stat-arb's estimation window is load-bearing in CALENDAR time — H4 estimation dies post-2024 where daily estimation strengthens; (4) the registered pipeline held under fire twice — both near-zero quick-check passes (cells 4, 6) failed at full window, and both were flagged as suspect at grant time. Multiplicity accounting closes at two spurious-shaped passes out of nine cells against one predicted — both caught downstream, zero deployment decisions ever at stake.

---

# 2026-07-03 — DIAGNOSTIC PRE-REGISTRATION: session-concentration analysis of validated records

**Question:** does any validated edge concentrate in specific trading sessions, or is it uniform across the clock? **Records:** the corrected-harness trade records for scalp30, intraday, pullback30 (the deployed long-only variant's corrected record — the corrected harness was never run on the long+short parent; noted, not silently substituted), spread2b (Phase-2 NZD/CAD record), and the benched trend-origin D/H4.

**Bucket convention, chosen now:** five DISJOINT UTC buckets — Asian 00:00–08:00, London 08:00–13:00, London/NY overlap 13:00–16:00, New York 16:00–21:00, rollover 21:00–24:00. Disjoint buckets handle the London/NY overlap by making it its own bucket rather than double-counting. Entry time stamps the bucket.

**Pre-registered interpretation rules:** (a) **diagnostic only — no session-filtered variant gets built or backtested in this pass regardless of findings**; (b) a concentration finding is a CHARACTERIZATION, with the explicit caveat that post-hoc session filtering is the same selection move as a directional carve-out — any session-filtered variant is a new candidate requiring its own pre-registration and forward validation (the pullback30 long-only rule); (c) a uniform result closes the question permanently for these records. **Known structural artifacts, flagged up front:** spread2b's entries are daily-close-timed by design — its session distribution measures its evaluation schedule, not an edge; reported for completeness only. Similarly, D/H4 entries land on 4-hour boundaries.

## RESULT (same day): one real characterization, two uniform closes, two structural artifacts

| Strategy | Asian 00–08 | London 08–13 | Overlap 13–16 | NY 16–21 | Rollover 21–24 | Read |
|---|---|---|---|---|---|---|
| scalp30 (n=2,931) | +$7.76 ×1156 | +$12.42 ×640 | +$6.53 ×495 | +$4.04 ×416 | +$19.84 ×224 | **uniform-positive → CLOSED (rule c)** |
| intraday (n=7,434) | +$4.89 ×2454 | +$4.00 ×1889 | **−$1.15 ×1442** | +$5.83 ×1126 | +$8.62 ×523 | **one negative bucket — characterized (rule b)** |
| pullback30 (n=745) | +$24.46 ×200 | +$30.07 ×113 | +$44.22 ×121 | +$10.70 ×135 | +$14.63 ×176 | **uniform-positive → CLOSED (rule c)** |
| spread2b (n=24) | 100% of trades | — | — | — | — | structural artifact as pre-flagged (daily-eval timestamps) |
| D/H4 (n=239) | ×3 | ×1 | ×3 | ×1 | **×231** | structural: signals cluster on the 21:00 UTC H4 bar — the first bar after the DAILY HTF candle updates; mechanism timing, not session edge |

**The one real finding — intraday's London/NY overlap bucket is a drag:** expectancy −$1.15/trade over n=1,442 (−$1,654 net, −5.7% of total) while all four other buckets are positive (+$4.00 to +$8.62). Cells are fat enough that this is not thin-sample noise. **Per rule (b), this is a characterization only:** no session filter gets built; "intraday-ex-overlap" would be a post-hoc selection exactly like a directional carve-out, and would require its own pre-registration and forward validation to exist. Recorded as review-relevant context (it is P&L-shape information for the 2026-08-15 dossier's readers), nothing more.

**Closures per rule (c):** the session question is permanently closed for scalp30 and pullback30 — both uniformly positive across all five buckets (scalp30's weakest bucket +$4.04, pullback30's +$10.70). The D/H4 observation is worth one sentence beyond its artifact status: the mechanism effectively trades the daily-candle update through an H4 lens, which is consistent with its D/H4 design and explains its low trade frequency.

---

# 2026-07-03 — NEW LINE OPENED: CFTC COT positioning (sentiment/flow), PHASE 1 GROUNDWORK ONLY — PRE-REGISTRATION

## Status: PRE-REGISTERED before any data is touched. This is the reopening path explicitly named when the OANDA position-book line nulled (5b6be73: "an external positioning source (e.g., CFTC futures COT) with different construction"). New pre-registration, new thresholds — NOT the position-book premise retried.

**Stated up front: this line can never be a volume engine.** COT is weekly; any eventual strategy trades a handful of times per year, like stat-arb. Its value case is diversification only — a sentiment/flow P&L source structurally distinct from trend capture and spread reversion.

## Step 1 — availability (before premise work)

Source: CFTC's free public reporting (weekly Commitments of Traders; the Socrata public API and/or published historical files — no paid feed). **Futures→spot mapping, stated now:** CME currency futures are quoted XXX/USD, so net positioning maps DIRECTLY for EUR_USD, GBP_USD, AUD_USD, NZD_USD and INVERTED for USD_JPY (6J yen futures), USD_CAD (6C), USD_CHF (6S). Crosses (EUR_JPY, AUD_JPY) would require leg differencing and are excluded from Phase 1 (imperfect construction; noted, not fudged). History requirement: 2021–2026 evaluation window PLUS a trailing 3-year percentile lookback → data needed from ≥2018. If depth or coverage falls short, that is a named constraint reported before premise work.

## Step 2 — premise characterization (descriptive only; no entry/exit logic)

**Extremity measure, defined before computing:** weekly net NON-COMMERCIAL position (longs − shorts, contracts) as a percentile of its own trailing 156-week window. **Extremes: ≤10th and ≥90th percentile** (thresholds stated now). Conditional-outcome tables: forward SPOT returns at 1w/4w/12w horizons conditional on extreme state vs unconditional baselines, per pair, both directions of the contrarian hypothesis (extreme-long → reversal-down? continuation-up? nothing?). Same descriptive shape as the regime map and the position-book analysis.

## Step 3 — the free diagnostic

Does COT positioning show anything distinctive around the 2023–2024 regime break five other lines have independently found?

## Pre-registered outcomes

A null closes the line at Phase 1 with position-book finality. A real relationship grants **a Phase 2 design DISCUSSION only — not a build.** No strategy code in this pass.

---

# 2026-07-03 — COT PHASE 1 RESULT: **a real, symmetric contrarian relationship exists — Phase 2 design discussion granted (not a build)**

## Step 1 — availability: PASSES (with one resolved quirk)

CFTC Socrata public API, free, no auth. All seven mapped contracts cover 2018→current at weekly cadence; GBP and NZD required unioning pre/post-2022-02 name variants (BRITISH POUND STERLING→BRITISH POUND, NEW ZEALAND DOLLAR→NZ DOLLAR — a rename, not a gap). Depth requirement met exactly: 156-week percentile lookback from 2018 makes extremes evaluable from 2021.

## Step 2 — premise: pooled contrarian signature, monotone and symmetric (1,918 currency-weeks, 2021+)

| State | n | 1w fwd | 4w fwd | 12w fwd | (unconditional) |
|---|---|---|---|---|---|
| Extreme LONG (≥90th pctl) | 208 | **−23.7 bps** | **−68.1** | **−123.1** | (−4.4 / −14.5 / −44.6) |
| Extreme SHORT (≤10th) | 309 | **+9.0** | **+38.7** | **+95.8** | |
| Middle (40–60th) | 346 | −1.1 | −29.4 | −101.7 | ≈ unconditional |

Currencies that non-commercials are extremely long UNDERPERFORM at every horizon; extremely-shorted currencies OUTPERFORM — a ~220 bps spread between extremes at 12 weeks, in the classic fade-the-crowded-spec direction. Per-currency: the extreme-long side is negative at 4w in **7 of 7** currencies; the extreme-short side positive at 4w in 6 of 7. **The exception is instructive: JPY** — extreme yen shorts still lost absolutely (−16 bps at 4w) because the secular yen trend swamped the contrarian effect, but even there the bucket beat the unconditional drift (−63) by ~47 bps. The contrarian effect on JPY is real only RELATIVE to trend; absolute fading of the yen trend would have lost.

**Honesty caveats, prominent:** (1) forward windows OVERLAP (weekly observations, 12-week horizons) — the bucket n's are not independent samples and naive significance would be overstated several-fold; the monotonicity across horizons and consistency across 6–7 currencies is the evidence, not the raw counts; (2) thin cells flagged: CHF ≥90th n=5, EUR ≤10th n=17, CAD ≥90th n=18; (3) release-lag convention: signals dated from the Friday release, no lookahead.

## Step 3 — the break diagnostic: **COT saw the 2024 yen event that the OANDA position book was blind to**

JPY net non-commercials: −152k average in 2024Q2, hitting −173,900 contracts (1st percentile) on 2024-06-25 — record crowded shorts — then the July–August 2024 carry unwind snapped it to +66k (100th percentile) by 2024-09-24. The single most violent positioning round-trip in the dataset sits exactly at the regime break five other lines found — where the retail position-book aggregate moved ~1 point through the same event. External futures positioning carries regime information the broker-book stock measure structurally cannot. Also instructive: yen shorts sat at the 1st percentile through most of 2023 while the trend kept paying — the extreme ALONE was not a timing signal; it marked the fuel, not the ignition.

## VERDICT: Phase 2 design DISCUSSION granted — nothing more

Per the pre-registration: no strategy code exists, none gets built from this entry. What a design discussion would need to confront, recorded now: the JPY-exception (contrarian-fade loses absolutely against a persistent trend — the exact regime this portfolio's whole history warns about); the overlap-inflated sample; weekly cadence (~handful of trades/year — diversification-only value case, stated at registration); and the pullback30-style temptation catalog (no post-hoc pair/side carve-outs). The line PAUSES here awaiting the operator's design discussion.

---

# 2026-07-03 — COT PHASE 2 RESOLUTION (design discussion held): fade ruled out, filter deferred, instrumentation built

**Option 1 — direct contrarian fade: RULED OUT PERMANENTLY.** Reasoning logged with the ruling: the failure mode is overdetermined. Phase 1's own JPY exception shows a pure fade losing absolutely against a persistent trend — and the closed mean-reversion line established across SIX structurally distinct designs that fading persistent moves on this account's timeframes dies precisely there. A COT-triggered fade is the same bet with a slower clock. No reopening bar is stated because none is intended: this option does not come back.

**Option 2 — positioning filter on existing edges: DEFERRED, not ruled out.** A filter that, e.g., de-risks trend strategies when positioning reaches fuel-marking extremes cannot be designed against a single observed regime transition (the 2024 yen event is n=1). **Reopening bar: meaningful forward evidence spanning more than the one 2024 event** — additional positioning-extreme→transition episodes accumulating in the forward record. Until then, no filter design, no backtest of one.

**Option 3 — weekly COT instrumentation: PROCEEDS, built this entry.** `cot_snapshot.py`: net non-commercial percentile (156-week window, Phase 1's exact measure) for all seven mapped currencies, yen prominent, refreshed from CFTC's weekly release with a local cache, available as a one-command report and appended as a standing context block to BOTH review dossiers. **Instrumentation only, stated in the code and here: no gate, no order path, no strategy status — and explicitly NOT a validation path for Option 2** (watching the dial is not accumulating design evidence; Option 2's bar is forward EPISODES, which the log will record as they occur, not dial-watching).

---

# 2026-07-03 — FAILURE DATABASE built: the kill record as a queryable structure (`failure_db.json`)

**What was built.** Every kill in this log distilled to one structured entry — 29 entries in `failure_db.json` (JSON chosen over CSV: nested-free, greppable, and `jq`/pandas-queryable without quoting headaches). Fields per entry: `id`, `hypothesis` (one line), `class` (mechanism/behavior), `kill_stage` (quick-check / full-window / crown-jewel kill-test / concentration / other), `numeric_reason` (the kill-deciding numbers, quoted), `lesson_tag` (controlled vocabulary), `lesson` (the generalizable takeaway in prose), `date`, `log_ref`. The database is the skeleton; this log remains the full record — an entry there always points back here.

**Coverage:** the six pre-Rhyme-discipline archive kills (RSI, MACD+RSI, London breakout, order blocks, MA pullback, fib retracement), the full mean-reversion line (range_fade v1/v2, both sweep-fades, session fade, VP reversion, ER-gated candidate #6), all 8 pair-expansion rejections, the 6 closed grid cells, swing's retirement (with its corrected-harness sign-flip addendum), and the positioning-data null.

**Lesson-tag tally (the requested clustering):**

| lesson_tag | n | members |
|---|---|---|
| **windfall-year** | 7 | pair_eur_usd, pair_usd_chf, pair_aud_usd, pair_eur_chf, pair_aud_jpy, grid_cell1_fvg, grid_cell4_trend_origin_h1 |
| **no-edge** | 6 | macd_rsi, london_breakout, fib_retracement, pair_eur_gbp, pair_aud_cad, pair_nzd_usd |
| **trend-bleed** | 4 | range_fade_v2, sweep_fade_2_reentry, vp_reversion, ergated_sweep_c6 |
| **regime-non-transfer** | 4 | sweep_fade_1, session_fade, grid_cell6_statarb_h4_eurgbp, grid_cell7_statarb_h4_nzdcad |
| **spread-eaten** | 3 | rsi, grid_cell2_donchian_m5, grid_cell3_donchian_m15 |
| **min-N-starvation** | 2 | order_blocks, swing_retirement |
| **stale-mechanism** | 2 | ma_pullback, range_fade_v1 |
| **measurement-uninformative** | 1 | oanda_positionbook |

**Reading the clusters.** All four expected clusters materialized, and their relative sizes are themselves a finding. (1) **Windfall-year is the single largest failure mode (7)** — more strategies died of one-good-year dependency than of having no signal at all. Anything that looks validated on a full-window net should be presumed windfall-shaped until the ex-best-year number is shown; this is now the first question, not a late check. (2) **Trend-bleed (4) and regime-non-transfer (4) together (8) are the mechanism-level cluster**: designs whose local edge was real but whose exposure outside the home regime was fatal. Every mean-reversion death is in one of these two — the line's closure is visible as a cluster, not just a decision. (3) **Spread-eaten (3)** is small but carries the sharpest quantitative rule in the database: the M5→M15→M30 gradient bounds it — spread near ~10% of stop distance kills regardless of signal quality. (4) The singleton **measurement-uninformative** (position book) is worth its own tag: the hypothesis was never tested because the measure couldn't move — a different death than no-edge, and the tag preserves that distinction.

**Standing rule:** every future kill adds an entry to `failure_db.json` in the same adjudication that writes its log entry. The database never loses entries — reopened lines get NEW ids, the old kill stays.

---

# 2026-07-03 — SORTINO added as passport box 8: convention registered FIRST, then computed (`sortino.py`)

**Order of operations, on the record:** the full convention (1%-compounding curve, exit-time ordering, ISO-week returns with flat weeks as 0%, MAR=0 full-sample downside deviation, √52 annualization) was written into GOVERNANCE and committed (8731be6) BEFORE the first Sortino was computed — the convention is chosen, not tuned to make any strategy look good.

**Why Sortino over Sharpe (the requested rationale):** this book's edge is trend-following asymmetry — many small losses, rare large wins. Sharpe charges those rare large wins to the risk denominator; on a payoff shape like intraday's (+$29k carried by tail wins), a symmetric volatility penalty punishes exactly the behavior being paid for. Sortino's denominator is downside-only, which is the quantity the portfolio risk tolerance actually constrains.

**Ranked table (roster, corrected f86d9f4 records):** pullback30 3.38 > scalp30 2.31 > intraday 2.04 > spread 2C 1.03 > spread 2B 0.97 > trend-origin D/H4 0.94 > spread 2A 0.89. Full table with weekly means/downside devs lives in GOVERNANCE under the box-8 convention.

**Readings.** (1) **pullback30 tops the book** — long-only trend-origin makes less than intraday in dollars but its downside weeks are 5× shallower; per unit of realized downside it is the most efficient thing on the roster. Consistent with everything known about the short-side bleed: removing shorts removes most of the downside dispersion. (2) The three Donchian-family strategies cluster at 2–3.4; the three spreads and D/H4 cluster at ~0.9–1.0. The spread cluster's number is dominated by the flat-week convention (5–6 losing weeks in ~240; the strategies are flat most weeks by construction) — their ~1.0 says "thin but clean," not "half as good as scalp30." Stated in GOVERNANCE next to the table. (3) trend-origin D/H4's 0.94 with 76 losing weeks is the honest benched profile: real downside dispersion, modest mean — the validated-but-benched decision looks right in Sortino terms too.

Standing tool: `sortino.py` (one command, whole roster, convention hard-coded). Box 8 is part of the passport template from today; future candidates compute it at validation.

---

# 2026-07-03 — FACTOR OVERLAP MAP: where the book co-loses, and how many real bets it holds (`factor_overlap.py`)

**Conventions (chosen before running, in the tool's docstring):** losing week = ISO week with net fixed-$80 P&L < 0 (fixed-risk, sizing-free); matrix asymmetric — M[A→B] = share of A's losing weeks in which B also lost; regime clock = USD_JPY quarterly ER(20) mean, trending ≥ 0.20 (the Bot E regime-map convention, applied book-wide since USD_JPY is the primary instrument for 5 of 7 strategies).

## [1] Shared-losing-week matrix (row → col: % of row's losing weeks where col also lost)

|  | intraday | scalp30 | pullback30 | spread2b | spread2a | spread2c | d_h4 | n |
|---|---|---|---|---|---|---|---|---|
| intraday | — | 67.7 | 58.5 | 1.8 | 2.4 | 1.2 | 24.4 | 164 |
| scalp30 | 75.0 | — | 62.2 | 0.7 | 2.0 | 1.4 | 27.0 | 148 |
| pullback30 | 68.1 | 65.2 | — | 2.1 | 0.7 | 2.1 | 28.4 | 141 |
| spread2b | 50.0 | 16.7 | 50.0 | — | 0.0 | 16.7 | 16.7 | 6 |
| spread2a | 66.7 | 50.0 | 16.7 | 0.0 | — | 0.0 | 16.7 | 6 |
| spread2c | 40.0 | 40.0 | 60.0 | 20.0 | 0.0 | — | 0.0 | 5 |
| d_h4 | 52.6 | 52.6 | 52.6 | 1.3 | 1.3 | 0.0 | — | 76 |

**Raw co-occurrence is meaningless without base rates**, so the reading is in LIFT (co-loss rate ÷ the column strategy's unconditional losing-week rate: intraday 57.1%, scalp30 51.6%, pullback30 49.1%, d_h4 26.7%, spreads ~2.0–2.6%):

- **The Donchian cluster is one loss profile.** intraday→scalp30 67.7% is 1.31× chance; scalp30→intraday 75.0% is 1.31×; pullback30 pairs at 1.19–1.27×. When one bleeds, the others bleed measurably more often than chance, both directions.
- **D/H4 co-loses at CHANCE rates with that cluster** — intraday→d_h4 24.4% vs 26.7% base (0.92×), d_h4→cluster 52.6% vs 49–57% bases (0.9–1.07×). This is the map's surprise: despite box-7 signal redundancy with pullback30 (68.1% same-direction days), its **weekly loss timing is statistically indistinguishable from independent** — the D-timeframe holding period decouples when it loses from when the intraday cluster loses.
- **The spreads are independent of everything** — cluster→spread cells 0.7–2.4% against ~2.0–2.6% bases (lift ≤1), and the spreads' own row values (16–67% on n=5–6) are single-week noise. Notably 2A∩2B = 0 and 2C∩2A = 0: the three spreads never co-lose pairwise except one 2B/2C week.

## [2–3] Shared-losing-REGIME: honestly, the quarterly ER clock does not discriminate here

The USD_JPY clock classifies 17 of 22 quarters trending (only 2021Q2–Q3 and 2025Q2–Q3 range). Every strategy's losing-week regime composition (77–83% trending) simply matches the calendar base rate of trending quarters. **Finding recorded as a finding:** at book level, weekly co-losses are NOT concentrated in one ER regime class beyond exposure — the regime axis of this map adds no separation on this clock. The known regime sensitivity (the 2023–2024 break five lines found) lives at finer resolution (estimation-window calendar-memory, quarterly P&L signs) than a two-state quarterly ER label.

## [4] Temporal clustering

18 weeks in 5.5 years where ≥4 of 7 strategies lost together; 13 of 18 in trending quarters. The co-losing set is almost always the same: {intraday, scalp30, pullback30, d_h4} — the USD_JPY-trend-family superset. **No week ever had 5+ of 7 losing:** the spreads never joined a cluster drawdown week. Worst stretches cluster where expected: late 2021 (yen trend ignition), 2022 trend quarters, and the 2025Q3 ranging bleed (2025-08-15/22 back-to-back).

## HEADLINE: the book holds ~3 genuinely independent loss profiles

1. **The USD_JPY Donchian/pullback cluster** (intraday + scalp30 + pullback30) — one bet. Mutual co-loss lift 1.2–1.3× both directions; they share pair, timeframe band, and trend-capture mechanism.
2. **Trend-origin D/H4** — a second, weaker-than-expected-to-be-redundant profile. Same family on paper, but weekly loss timing at chance lift vs the cluster. Counted as distinct **for loss-timing purposes only** — its box-7 signal redundancy stands unchanged, and in the 18 heavy weeks it IS usually the fourth member, so it degrades toward the cluster exactly in the tails (the moments diversification is for). Call it half-independent: distinct in ordinary weeks, correlated in the worst ones.
3. **The stat-arb spreads** (2A/2B/2C jointly) — cleanly independent of the cluster (lift ≤1 everywhere) and of each other so far, but with 5–6 losing weeks apiece there is no statistical basis to count them as three separate profiles; conservatively one.

Reasoning shown: count = clusters in the lift matrix, not rows in the roster. Seven strategies ≈ **3 real bets (2.5 if D/H4's tail-convergence is weighted)** — consistent with, and now quantifying, the standing one-behavior concern. Standing tool: `factor_overlap.py` (one command, conventions hard-coded).

---

# 2026-07-03 — MEAN-REVERSION LINE REOPENED under its own bar: candidate #7, Anchored-VWAP fade (spec pre-registered BEFORE code)

**The bar and why it is met (operator determination):** the line closed 2026-07-02 with reopening conditional on a genuinely NEW mechanism class. Anchored VWAP qualifies on two axes none of the six dead designs had: (1) a **volume dimension** — every prior boundary (fractal pairs, rolling extremes, session ranges, value-area edges) was price-only; (2) a **deterministic hard-reset anchor** — the reference recomputes from scratch at every daily UTC open, structurally immune to v1's staleness failure mode (boundaries lagging the regime) because no state survives 24 hours.

## Pre-registered spec (constants CHOSEN not tuned; committed before the plugin exists)

- **Anchor:** daily 00:00 UTC. Session VWAP over M30 candles from the anchor: VWAP_t = Σ(tp_i·v_i)/Σ(v_i), tp = (H+L+C)/3, v = OANDA tick volume (stated plainly: tick count, not true traded volume — it is the deterministic volume proxy this data source has).
- **Bands (formula + lookback stated here, per handoff):** σ_t = sqrt( Σ v_i·(tp_i − VWAP_t)² / Σ v_i ) — volume-weighted standard deviation of typical price around the CURRENT session VWAP. Lookback = session-anchored cumulative (all M30 candles since 00:00 UTC); there is no rolling window to tune. Bands: VWAP ± 2σ (entry), VWAP ± 3σ (stop).
- **Eligibility:** ≥ 6 M30 session candles (3 hours) before any signal — σ needs mass; a 1-candle σ is degenerate.
- **Entry:** M30 CLOSE beyond the 2σ band → fade at that close toward VWAP. Both directions. One trade per (session date, direction); a confirmed-but-filtered signal consumes the identity (single-use, as every Bot E candidate).
- **Stop:** the 3σ band on the entry side, FROZEN at entry (structural, band-width-derived). **TP:** VWAP itself, FROZEN at entry. Fire-and-forget (Amendment 2 inherited): no trailing, no re-evaluation, no time exit — positions resolve at SL or TP only.
- **Amendment-1 spread floor inherited:** skip if TP distance (|entry − VWAP|) < 10× assumed live spread — i.e., spread above ~10% of the entry-to-VWAP distance. Same assumed-spread table as the prior candidates.
- **Min R:R 1.2:** reward = |entry − VWAP|, risk = |stop − entry|; skip below 1.2.
- No regime gate, no pair carve-outs, no session carve-outs.

## Pre-committed gates

- **Kill-test (stage 1):** USD_CAD crown jewel 2022Q3–2023Q3 (2022-07-01 → 2023-10-01), corrected harness, $80 fixed risk, per-pair spread. Gate: **net-positive AND n ≥ 30**, plus the amended-protocol trailing-floor prop pre-check (`prop_rules.trailing_precheck`) reported with the verdict.
- **Full window (stage 2, only if stage 1 clears):** net-positive in the crown jewel; ≥ 2 of 3 secondary stretches positive; and the decisive criterion — **flat-not-negative (no deep bleed) in trend quarters, specifically USD_JPY 2022Q2–Q4**, the stretch that killed v2 (−$1,004/40) and #6 (−$1,266/26).
- **Stopping rule, pre-committed:** failure at EITHER stage makes this the seventh dead mean-reversion design and the closure stands REINFORCED — no candidate #8 without another genuinely new mechanism class (different asset class, different data source, or equivalent). This entry is the record of that commitment.

---

# 2026-07-03 — CANDIDATE #7 (Anchored-VWAP fade) KILLED at crown-jewel kill-test; mean-reversion closure REINFORCED

**Result (USD_CAD 2022Q3–2023Q3, corrected harness, $80 fixed risk):** n=178, net **−$19,321.90**, WR **17.4%** — against a breakeven near 33% at the design's ≥2:1 structural R:R. Gate (net-positive AND n≥30): **FAIL**, by the widest margin of any candidate in the line's history. Artifact: `corrected_f86d9f4_avwap_fade_killtest.csv` (commit f288868 lineage).

**The kill is not regime-shaped — it is uniform.** Every one of five quarters negative, including the 2023 ranging quarters that were supposed to be the design's home turf (2023Q1 −$515/39, 2023Q2 −$2,411/26). Long 17.4% WR, short 17.4% WR — symmetric failure, no direction to carve out even if carve-outs were allowed (they are not). The staleness immunity worked as designed and it did not matter: **a close beyond 2σ of the session-anchored volume-weighted distribution marks intraday momentum, not exhaustion** — by the time price is 2σ from a fair value that itself drags toward the move (VWAP follows volume-weighted price), the fade is fighting a move strong enough to have overcome its own anchor. The sixth design's lesson generalizes past its gate: the failure of MR on this account's timeframes is not staleness, not session choice, not boundary type, not a missing regime gate, and now not a missing volume dimension — the underlying M30-scale reversion premium does not exist net of this cost structure.

**Two honesty notes.** (1) One trade (2023-09-20) lost $1,895 on a 0.1-pip stop distance — a near-3σ entry passed the ≥1.2 R:R filter with degenerate sizing; a min-stop-distance floor would have blocked it. Not fixed, not re-run: excluding it entirely the net is ≈ −$17,400 at 17.4% WR — the verdict is unchanged and retuning a dead candidate is tampering. Logged as a spec lesson for any future design: R:R floors do not bound absolute stop distance. (2) The trailing-floor prop pre-check requires floating marks, which the kill-test run did not collect; on a candidate dead at stage 1 the pre-check is moot and was not computed.

**Stopping rule executes (pre-committed e211a17):** this is the SEVENTH dead mean-reversion design. The line's closure stands **reinforced** — no candidate #8 without another genuinely new mechanism class (different asset class, different data source, or equivalent). Entry added to `failure_db.json` (avwap_fade_c7, lesson tag: no-edge).

---

# 2026-07-03 — NEW-IDEA TRIAGE: NY-close/Sydney-open liquidity trough — mechanism CONFIRMED, tradeability PAIR-SPECIFIC (USD_JPY only, upper-bound); NOT killed, NOT advanced — parked pending portfolio decision

**Status framing:** pre-scoping triage of a brand-new idea, not a reopening of the closed mean-reversion line. The distinction that had to hold (per the triage handoff): the hypothesized edge is a **liquidity-calendar fact** (predictable thin book, 17:00–19:00 ET daily rollover), not a price pattern — if it had collapsed into "price mean-reverts after a session-fade-shaped move," it would be MR #8 and dead under the standing closure bar. It did not collapse: both gates measured liquidity variables, not price patterns.

## Gate 1 — mechanism falsification (liquidity_trough_check.py / .png)

12mo M5 (2025-07-01 → 2026-07-01), AUD_USD/NZD_USD/USD_JPY, minute-of-day buckets in ET (IANA tz, per-date DST), ET Sundays excluded (weekly open ≠ daily rollover). **Cross-pair anomaly confirmed on all three pairs:** window tick volume 0.30x/0.39x/0.64x of flanking hours (JPY/AUD/NZD), bar range 0.64–0.90x, while return stdev fell only to 0.70–1.02x — i.e. **per-print volatility elevated ~1.6–2.3x on all three pairs**, the thin-book-amplification signature. Passed its pre-committed continue criterion (cross-pair consistency).

**DST spot-check (validation of gate 1, scratchpad script, not committed):** 4 dates hand-verified against fixed UTC offsets computed from the written US statutory rule (not tzdata) — summer baseline 2025-08-06, fall US/EU gap 2025-10-29, spring gap 2026-03-11, winter baseline 2026-01-14. All 4 exact-set PASS (24/24 bars, zero wrongly in/out). The trough is not a DST-misalignment artifact.

## Gate 2 — overshoot vs REAL execution cost (trough_overshoot_check.py / .png)

Definitions fixed pre-run, N grid {2,3,4} reported in full, nothing tuned. Baseline = 16:55 ET close; overshoot = window extreme ≥ N× pair median M5 range; reversion = extreme → 20:55 ET close (continuations counted negative); cost = 2× same-day mean REAL bid/ask spread in the window (OANDA price=MBA candles — **actual quoted spread, the bar-range-proxy caveat does not apply**).

**The spread curve is the finding:** quoted spreads ~1.3–1.6 pips all day → **8–10 pips at the 17:00 rollover spike**, 3–6 pips through the window. Cost is worst exactly when the dislocation occurs — the canonical liquidity-edge failure mode.

| pair | N=3 events/yr | mean rev (pips) | mean RT cost | rev/cost | %events>cost |
|---|---|---|---|---|---|
| AUD_USD | 44 | 6.0 | 5.9 | 1.02 | 52% |
| NZD_USD | 100 | 6.5 | 7.0 | 0.93 | 49% |
| USD_JPY | 73 | 12.9 | 8.3 | 1.55 | 56% |

Stable across the whole N grid: AUD 0.97–1.04, NZD 0.89–0.97, JPY 1.11–1.55. **AUD_USD and NZD_USD: dead — reversion statistically indistinguishable from cost.** USD_JPY clears, but 1.55x is an **upper bound**: reversion is measured from the exact window extreme, which no execution catches, and only 56% of events clear cost at all (mean carried by a fat right tail).

## Disposition — the pre-registered third bucket (pair-specific), recorded without resolution

Not killed: the pre-committed kill condition (cost dominates on ALL three pairs, or events too rare) was not met — **no failure_db.json entry**, deliberately, per the gate's own terms. Not advanced: the cross-pair consistency that justified continuing after gate 1 is gone at the cost line, and a USD_JPY-only residual (a) reproduces the pair-expansion failure signature the triage pre-flagged as disqualifying context, and (b) would stack more USD_JPY exposure on a book already ~85% USD_JPY-concentrated with its trend cluster measured as one bet (see the factor-overlap map, this date). **Whether an upper-bound-1.55x USD_JPY-only edge justifies real scoping is a fleet-portfolio judgment, parked for the operator.** Any future scoping must first tighten the reversion measurement to an executable entry (the extreme-entry generosity is the number's weakest link now that spread is real), and falls under passport box 9 (absolute min stop distance) like everything else.

**Addendum (2026-07-03, later same day) — line CLOSED by operator decision:** the parked portfolio question above is resolved: REJECTED on portfolio-concentration grounds (USD_JPY-only residual duplicates the fleet's ~85% USD_JPY concentration; same mechanism-generalizes/payoff-doesn't signature as the pair-expansion line). The "no failure_db.json entry" statement above described the state at gate time and is superseded: entry `liquidity_trough_nyclose_sydneyopen` added, recorded as a PARTIAL REJECT (not a flat kill — the pre-declared kill condition was never met) with an explicit reopen bar: cross-pair tradeable residual after real spread cost, measured from an executable entry, clearing on AUD_USD or NZD_USD, not just USD_JPY.

---

# 2026-07-08 — RETRO-LOG: prop-firm multi-asset expansion line opened; Gate 0 (instrument inventory) COMPLETE — work done 2026-07-03, committed (adaaff6) but not logged; gap closed today

**Honesty note first:** the Gate-0 work below was built and run on 2026-07-03 (evening) and committed as `adaaff6` with a full commit message, but no RESEARCH_LOG entry was written — a violation of this log's own convention (every line opening and gate result gets a dated entry). Nothing here is reconstructed from memory: every claim below is re-derived today from the committed artifacts (`inventory_instruments.py`, `inventory_instruments_mt5.py`, `mt5_client.py`, `instrument_inventory.csv`, `mt5_instrument_inventory.csv`). Retro-logged 2026-07-08.

## The line and its motivation

Systematic survey of what instruments prop firms actually allow, feeding two standing needs at once: (1) the **unmet diversification need** — the GOVERNANCE portfolio note's one-behavior concern, with the M30/H4 FX mean-reversion route formally closed; the MR closure's own reopen bar names "different asset class, different data source" as the qualifying new information, and this line is exactly that; (2) the **prop-track goal** — FTMO/The5%ers/FundedNext presets are already encoded (`prop_rules.py`), and their platforms offer asset classes this project's OANDA account does not.

**Gate structure (as designed 2026-07-03):** Gate 0 = instrument inventory (what exists, what history depth, what prop eligibility). Gate 1 = cheap data/mechanism checks on price data. Cost-sensitive tradeability gates come later and are BLOCKED on data fidelity (below).

## The second data source: MT5 (Phase A) and its fidelity contract

The OANDA v20 practice account turns out to offer **only forex — 68 instruments, zero CFDs** (`instrument_inventory.csv`: 68/68 classified forex). Multi-asset data therefore required a second source: `mt5_client.py`, a MetaTrader 5 client against a portable terminal (`D:\mt5_phaseA\terminal64.exe`) logged into a generic-LP demo (source tag `mt5_potrade_demo`). Kept fully separate from the OANDA pipeline; every DataFrame carries a `source` column so the two can never silently mix.

**Fidelity contract (stated in the client, restated here as the line's governing constraint):**
- Price/OHLC data: usable for Gate 0 and Gate 1.
- **Spread/cost data: NOT trustworthy.** A generic demo's quoted spreads do not represent any prop platform's live conditions. Any tradeability/cost gate waits for a broker-matched demo behind the specific target firm's challenge platform (operator signup when a firm is chosen — the preset-on-relevance policy applies to data sources too).
- Timestamps are broker-server time (UTC+2/+3 with DST), NOT UTC like OANDA — every session/date-sensitive computation downstream must convert explicitly (same hazard class the liquidity-trough DST spot-check existed to catch).

## Gate 0 results (both CSVs, 2026-07-03 19:18 run)

- **OANDA:** 68 instruments, all forex, with M5 history depth and per-firm eligibility columns.
- **MT5:** 245 symbols — raw classifier output: 70 forex, 152 `cfd_other` (flagged for manual review, never dropped), 11 crypto, 6 indices, 4 metals (XAU/XAG/XPT/XPD), 2 energy (XNGUSD natural gas, UKBRENT).
- History depth on the non-FX classes: best is ~4.8y of M5 (XAUUSD, XAGUSD, BTC/ETH/LTC/XRP — back to ~late 2021); the major index cash CFDs (SPX, CAC, FDAX, FTSE) have ~4.3y; the rest 2.9–3.2y. **No symbol reaches Jan-2021**, so the fleet's standard 2021–2026 window is NOT fully available on this source — the usable window per symbol is a Gate-1 output, not an assumption.
- Static prop-firm category table cross-referenced per symbol (REFERENCE ONLY, per the table's own warning — symbol-level verification against the chosen firm's current list is required before anything is filtered by it).

## Manual review of the 152 `cfd_other` symbols (done today, closing the flag Gate 0 left open)

By broker category path: **125 single-stock CFDs** (NYSE 60, NASDAQ 34, Euronext/EPA 31), **21 `_otc` synthetic forex** (broker's off-market/weekend feeds), **6 real indices the classifier missed** (IBEX35, NQ, ASX200, NI225, SX5E, YM — names outside the hint set). One classifier bug in the other direction: **`#NIKE` (Nike Inc, a NYSE stock) was classified `indices`** — the "NIK" Nikkei name-hint matched it. The classifier bugs are recorded, not fixed in code: the CSV is a one-shot artifact and the corrected classification lives here and in the Gate-1 universe below.

**Dispositions:**
- 21 `_otc` synthetics: **EXCLUDED** — not real market data; nothing tested on them transfers.
- 125+1 single-stock CFDs: **EXCLUDED from this line** (not "tested and failed") — per-symbol idiosyncratic risk, earnings gaps, and prop-firm stock restrictions make them a different research program, not an extension of this one.
- 6 misclassified indices: **RECLASSIFIED into the universe.**

**Gate-1 candidate universe (final): 11 indices** (SPX, NQ, YM, FDAX, CAC, FTSE, SX5E, IBEX35, NI225, ASX200, HK50), **4 metals**, **2 energy** — 17 symbols. **Crypto (11) recorded but deprioritized** pending symbol-level eligibility verification with a chosen firm (weekend sessions and firm-specific crypto rules make it the least portable class). The 70 MT5 forex symbols are not candidates (FX is already the fleet's home turf) but serve as OANDA-overlap cross-check instruments for data-quality validation.

---

# 2026-07-08 — GATE 1 PRE-REGISTRATION: data-quality + indicative-cost audit of the 17-symbol universe (spec and criteria fixed BEFORE the script exists)

**Scope discipline:** Gate 1 draws NO strategy conclusions and NO trustworthy cost conclusions (Phase A fidelity contract). It answers exactly: is each symbol's price data deep enough, clean enough, and correctly timestamped to support Gate-2 mechanism work — and is any symbol so obviously cost-hostile that even untrustworthy-fidelity spread data disqualifies it cheaply.

## Checks (per symbol; all M30, full available history to 2026-07-01)

1. **Usable window:** earliest M30 bar → 2026-07-01, in years.
2. **Weekly completeness:** bars per ISO week vs the symbol's own modal weekly bar count; a week is *deficient* below 80% of modal. Weeks containing the symbol's known market holidays are not exempted (we don't have per-exchange calendars) — the threshold below absorbs a normal holiday rate.
3. **Broker-time offset verification:** on the two OANDA-overlap cross-check instruments (EURUSD↔EUR_USD, USDJPY↔USD_JPY), align M30 closes against OANDA UTC data at candidate offsets 0/+1/+2/+3h over the last 12 months; the true offset must be unique with close-series correlation > 0.999, and is measured separately in a January month and a July month to expose DST behavior. The result applies source-wide (one server clock).
4. **Indicative cost profile:** current spread snapshot (`symbol_info`) and median M30 high-low range over the last 12 months; report spread as % of median M30 range. Explicitly tagged `mt5_potrade_demo` fidelity.

## Pre-committed criteria

- **EXCLUDE (window):** usable M30 history < 3.0 years → out of Gate 2 (multi-regime checks impossible; the fleet's 2021-start standard is already known to be unavailable on this source — the per-symbol usable window becomes the symbol's own backtest ceiling, recorded).
- **EXCLUDE (quality):** > 5% of complete-market weeks deficient → out of Gate 2 (feed unreliable).
- **SOURCE-LEVEL FAIL:** time-offset verification finds no unique >0.999 offset on the FX cross-checks → the entire MT5 Phase A source is unfit and the line pauses on data, regardless of any other result.
- **PROVISIONAL EXCLUDE (cost):** indicative spread ≥ 25% of median M30 range → parked, marked re-checkable at broker-matched-demo fidelity only. Rationale: every candle-scale FX post-mortem in this log died at far better ratios; a symbol failing this even at demo fidelity is not worth Gate-2 compute now. NOT a kill — demo spreads are the number known to be untrustworthy, so this bucket is reversible by construction.
- **PASS** otherwise → eligible for Gate 2 (mechanism checks, to be registered separately when this gate's survivor list exists).

**Artifacts:** `gate1_data_audit.py` (script, committed before results), `gate1_data_audit.csv` (results), verdict entry in this log. No failure_db entries from this gate (data exclusions are not mechanism kills).

---

# 2026-07-08 — GATE 1 VERDICTS: source clock verified clean; 2 PASS (XAUUSD, NQ), 4 provisional-cost, 10 quality-excluded, 1 window-excluded — with two spec lessons logged honestly

**Run:** registration commit 38d02fd, run same evening (~23:30 EDT), artifact `gate1_data_audit.csv`.

## Source-level clock: PASS, and a useful fact

Unique offset **+2h from UTC in BOTH January and July**, correlation ≥ 0.999972 on both cross-check pairs in both months — the broker server is fixed UTC+2 year-round (NOT EET with DST, the common broker default the spec was braced for). Simple constant conversion downstream; no DST logic needed for this source. The Phase A source is fit for price-data purposes.

## Verdicts (registered criteria applied verbatim)

- **PASS → Gate 2 eligible: XAUUSD** (4.8y, 4.5% deficient weeks, indicative spread **3.67%** of median M30 range — comfortably the best number on the board and FX-like) and **NQ** (4.27y, 4.0%, 14.57%).
- **PROVISIONAL_EXCLUDE_cost (reversible at Phase B fidelity only): SPX** (73.1%), **XPTUSD** (33.4%), **XPDUSD** (25.6%), **XNGUSD** (166.7%).
- **EXCLUDE_quality (>5% deficient weeks): all remaining indices** (ASX200 11.2%, CAC 24.8%, FDAX 10.1%, FTSE 16.2%, HK50 32.1%, IBEX35 7.2%, NI225 5.1%, SX5E 15.7%, YM 5.1%) **and XAGUSD** (5.0% displayed, >5.000% raw).
- **EXCLUDE_window: UKBRENT** (2.89y < 3.0y).

## Two spec lessons, logged not retro-fixed (criteria applied as registered; retuning after seeing results is tampering)

1. **The 5% deficient-week threshold was implicitly FX-calibrated.** Exchange-traded index CFDs have far richer holiday/half-day calendars than FX (ASX, HK, European exchanges), so some of the 10 quality excludes — especially the borderline YM/NI225 at 5.1% and XAGUSD at 5.0% — plausibly reflect genuine exchange calendars, not feed defects. The registered criterion stands and the excludes are recorded as registered. **If the operator wants these symbols back, the path is a NEW registered criterion (holiday-calendar-aware completeness), not an exception** — logged as the explicit reopen bar for this bucket.
2. **The indicative-spread snapshot was taken ~23:30 EDT** — rollover-adjacent, off-session for every index on the board. Index demo spreads at that hour are inflated vs regular trading hours (SPX at 73% of median range is almost certainly this, on top of generic-demo fidelity). Harmless by construction — the cost bucket was pre-declared provisional and reversible — but any Phase B cost measurement must sample spreads across the session, not at one timestamp. Logged as a spec requirement for the Phase B cost gate.

## Standing state of the line after Gate 1

**Gate-2 candidate list: XAUUSD, NQ** — one metal, one index, both prop-eligible on all three encoded firms, usable windows 4.8y/4.27y (backtest ceilings recorded; the fleet's 2021-start standard is not available on this source). Gate 2 (mechanism checks) requires its own pre-registration before any run, including which mechanisms are tested — noting that XAUUSD on M30 with structural stops is the first concrete instance of the MR closure's reopen bar (different asset class) actually being reachable, and that any trend-capture design on NQ/XAUUSD must be checked against the book's existing trend-cluster concentration (factor-overlap map, 2026-07-03) before deployment could ever be considered. **Open items:** Phase B broker-matched demo (operator signup when a target firm is chosen) blocks all cost-sensitive gates; the 4 provisional-cost symbols wait on it.

---

# 2026-07-08 — GATE 2 PRE-REGISTRATION: the two live-validated trend mechanisms on XAUUSD and NQ, plugins UNMODIFIED, zero new constants (spec fixed BEFORE any run)

**Mechanism choice (recommendation, recorded with its reasoning):** the two mechanisms with live validated records, run exactly as designed — `donchian_plugin.py` and `trend_origin_pullback_plugin.py`, both in the H4/M30 (scalp30) configuration, unmodified. Rationale: Gate 2's question is "does the mechanism's edge transfer to the new asset class," and the cleanest test of transfer is the exact artifact that validated on FX — any modification would make a fail uninterpretable (mechanism vs tuning). A NEW mechanism designed for these instruments (including the MR-reopen candidate on XAUUSD, now reachable under the closure bar) is a separate, later registration — not smuggled into this one.

## Harness and conventions (all registered here, before first run)

- **Harness:** corrected `backtest.py`, unmodified. `scalp30` TF mapping injected via the same `TF_MAP.setdefault("scalp30", ("H4","M30"))` the permanent parity test uses. Data: MT5 Phase A M30/H4, broker-time converted to UTC by the Gate-1-verified fixed −2h, served through the harness's own fetch seam; enrichment (`add_emas(detect_fractals(...))`) is the harness's, untouched.
- **Risk:** $80 fixed risk per trade (fleet quick-check standard). Pip conventions for the two non-FX symbols are arbitrary-but-self-consistent (the harness's dollar arithmetic cancels the convention), chosen only so 0.01-lot rounding distorts risk ≤~2%: XAUUSD pip=0.01, pip-value $0.10/lot/pip; NQ pip=1.0 point, pip-value $0.10/lot/pip.
- **Spread:** included, from the Gate-1 indicative snapshot — XAUUSD 37 pips ($0.37), NQ 5.8 pips (5.8 points). Fidelity caveat carried forward: Phase A spreads are untrustworthy; they are used because running cost-free would be worse, and because Gate 2's verdicts are mechanism-shaped. **Any PASS from this gate is provisional on Phase B cost data by construction** — validated-but-benched is the ceiling; deployment is impossible regardless (no live venue for these instruments in this project).
- **Quick-check (stage 1):** calendar 2023, both symbols × both plugins (4 runs). **Kill criteria per run (grid-cell convention): expectancy negative OR n < 20 OR median stop distance < 10× the assumed spread** (box-9 lesson: R:R floors don't bound absolute stop distance). A kill is decisive for that (symbol, mechanism) cell; no retuning, no variant proposals.
- **Full window (stage 2, only for quick-check survivors):** earliest available data + warm-up → 2026-07-01 (ceilings: XAUUSD ~4.8y, NQ ~4.3y — recorded as the record's own limit, not equivalent to the fleet's 6y standard). Passport-track adjudication with the thin-window caveat explicit.
- **Portfolio framing, pre-committed (same discipline as the trend-origin untested-pairs line):** both mechanisms are trend capture. A validation here diversifies by ASSET CLASS only if the instrument's trend regime is shown uncorrelated with the book's USD_JPY cluster — a factor-overlap extension that must run before any deployment-adjacent conversation. Absent that, a pass adds prop-track options, not diversification.

**Artifacts:** `gate2_killtest.py` (runner, committed before results), per-run CSVs `gate2_<symbol>_<plugin>_2023.csv`, verdict entry in this log.

---

# 2026-07-09 — GATE 2 VERDICTS: quick-checks 4/4 CLEAR, full windows split cleanly by INSTRUMENT — NQ kills both mechanisms, XAUUSD passes both; trend-origin pullback on XAUUSD is the expansion's first validated-but-benched candidate

**Runs:** registration 0445ded, quick-checks + full windows same night. Artifacts: `gate2_*_{2023,full}.csv`, `gate2_XAUUSD_pullback_trailing_precheck.json`.

## Stage 1 (2023 quick-checks): all four CLEAR

XAUUSD×donchian n=453 exp +$0.65 (barely); XAUUSD×pullback n=249 exp +$8.95; NQ×donchian n=548 exp +$9.19; NQ×pullback n=250 exp +$11.13. All median stops clear the 10×-spread floor. Per registration, all four proceeded to full windows.

## Stage 2 (full windows): the split is by instrument, not mechanism

| run | n | net | exp/trade | WR | yearly |
|---|---|---|---|---|---|
| NQ × donchian | 2,233 | **−$2,978** | −$1.33 | 30.2% | −6,046 / +5,038 / +2,523 / −5,901 / +1,407 |
| NQ × pullback | 985 | **−$903** | −$0.92 | 29.7% | −553 / +2,783 / +654 / −606 / −3,182 |
| XAUUSD × donchian | 2,058 | +$13,052 | +$6.34 | 32.0% | −3,813 / +295 / −1,146 / **+10,180 / +7,536** |
| XAUUSD × pullback | 974 | **+$13,755** | +$14.12 | 34.7% | −1,087 / +2,228 / +5,752 / +3,624 / +3,239 |

- **NQ: BOTH KILLED** (expectancy negative). The 2023 quick-check pass was the single good year on both — the exact USD_CHF signature from the pair-expansion line, now reproduced on an index. `failure_db.json` entries `nq_donchian_m30_gate2`, `nq_trend_origin_pullback_m30_gate2` (lesson: regime-non-transfer; the transfer boundary is the instrument's trend character, not the entry style — gold trended persistently 2024–2026, NQ chopped).
- **XAUUSD × donchian: numeric CLEAR, REJECTED at adjudication on concentration** — 3 of 5 periods ≈flat/negative, profits entirely in 2025–2026H1 (+$17,716 of +$13,052 net, i.e. the earlier years are net-negative). This is the no-single-year-dependency box, applied as it was to USD_CHF ("best record on the line, still fails"). Not a failure_db mechanism kill (the mechanism is live-validated elsewhere; this is a per-instrument adjudication reject) — recorded here.
- **XAUUSD × trend-origin pullback: PASSES adjudication — validated-but-benched** (the registration's pre-committed ceiling). 4 of 5 periods positive (sole negative is the 2022 partial year, −$1,087), largest single period +$5,752 = 42% of net (no single-period dependency), WR 34.7% vs a 28.6% breakeven at the design's ≥2.5R structure. **Trailing-floor prop pre-check (amended protocol): verdict `proceed`** — worst trailing-style DD −8.9% at 0.25% risk / −17.3% at 0.50%; not blown-2× on FTMO 1-Step-shape at either level (FundedNext's 3% lock is blown at both, as it is for everything but pullback30-on-FX at 0.25%).

## Standing caveats on the pass (all pre-declared, none new)

1. **Phase A cost fidelity:** the 37-pip XAUUSD spread assumption is a generic-demo snapshot; the pass is provisional on Phase B broker-matched cost data. This is the binding open item.
2. **Window ceiling:** 4.6y (2021-12 → 2026-07), not the fleet's 6y standard.
3. **Factor dependence:** the record rides the 2024–2026 gold bull — long-gold persistent-trend capture, the same class of macro-regime dependence as the fleet's long-USD/JPY concentration. Whether XAU trend regime is *uncorrelated enough* with the USD_JPY cluster to count as diversification is a factor-overlap-map extension that must run before any deployment-adjacent conversation (pre-committed in the registration).
4. Deployment is impossible regardless (no live venue here for CFDs) — this candidate exists for the **prop track**.

## Factor-overlap extension — REGISTERED before the run (2026-07-09, same night)

Executing the pre-committed prerequisite from the Gate-2 registration: the XAUUSD pullback record joins the standing factor-overlap map. **Zero new constants, zero convention changes** — `factor_overlap.py`'s registered conventions (ISO losing weeks at fixed-$80, flat ≠ loss, asymmetric co-loss shares, USD_JPY ER(20) quarterly regime clock) apply verbatim; the only change is the roster row `xau_pullback` → `gate2_XAUUSD_trend_origin_pullback_full.csv`. Window caveat registered up front: the XAU record starts 2021-12 (MT5 ceiling), so its co-loss shares are computed over a slightly shorter span than the FX records; the flat≠loss convention handles the absent weeks mechanically. **What would count as meaningful:** the map's own benchmark — the USD_JPY trend cluster shows mutual lift 1.2–1.3×, the spreads ≤1×. The verdict framing (does XAU add a genuinely independent loss profile?) is reported as measurement; whether it justifies a slot remains the operator's.

## Factor-overlap extension — RESULTS (run same night, registration commit first)

**Headline: XAUUSD pullback is pairwise-independent of the USD_JPY trend cluster in ordinary weeks, but joins the book's worst weeks well above chance — the d_h4 "half-independent" profile, slightly stronger on both ends.**

Numbers (map conventions verbatim; xau base rate 51.6% losing weeks over its 221-week record):
- **Cluster → xau co-loss lifts all AT or BELOW chance:** intraday→xau 40.9%/51.6% = **0.79×**, scalp30→xau **0.76×**, pullback30→xau **0.73×**, d_h4→xau **0.89×**. Reverse direction: xau→intraday **1.03×**, →scalp30 **0.99×**, →pullback30 **0.94×**, →d_h4 **1.15×**. Benchmark: the cluster's own mutual lifts are 1.2–1.3×; the spreads sit ≤1×. By the map's own standard this is a genuinely distinct weekly loss profile — the first non-spread strategy to show one.
- **Tail convergence, logged with equal weight:** heavy weeks (≥4 of the now-8 strategies losing together) number 51, and xau appears in **41 of 51 (80% vs its 51.6% base, ≈1.56× tail lift)**. Mechanical caveat attached: conditioning on ≥4 losers inflates participation of any high-base-rate strategy, so 1.56× is an upper-ish read — but the direction matches d_h4's known pattern: independent in ordinary weeks, correlated in the worst ones. Diversification that evaporates exactly in the tails is worth roughly half its headline value (the d_h4 precedent, applied unchanged).
- Regime composition: 84.2% of xau's losing weeks fall in trending quarters (n=114) — within the calendar base rate band (77–83%) that the original map showed for everything; adds no separation, as before.

**Measurement stands; the slot question stays parked for the operator** (pre-committed framing): what this changes is that the XAU candidate is now the only validated non-spread strategy whose ordinary-week losses don't co-move with the cluster — and what it does NOT change is the tail behavior and the Phase B cost gate, both still open.

## Line state after Gate 2

---

# 2026-07-09 — PHASE B SOURCE LIVE (FTMO US trial via OANDA infrastructure) + COST-GATE PRE-REGISTRATION (spec fixed before any spread number is looked at)

**The source:** FTMO 14-day free trial, account 1600158217 on `OANDA-Demo-1` (OANDA Corporation, demo trade-mode, $100k virtual). Context recorded: FTMO completed its acquisition of OANDA 2025-12-01; FTMO's US product runs on OANDA infrastructure, so this IS the broker-matched challenge platform for a US trader — the Phase B definition is met. Attach path: the OANDA MT5 terminal (`C:\Program Files\OANDA MetaTrader 5\terminal64.exe`); the Phase A potrade-branded terminal could not authorize on OANDA's access servers (operator resolved by installing OANDA's own terminal). Source tag for every frame: `ftmo_us_sim`. Note: the MetaTrader5 python module holds one terminal connection per process, so Phase B fetches live in the gate script itself rather than alongside Phase A in `mt5_client.py` — the never-mix guarantee is the source tag plus separate terminals.

**Universe facts (availability, not results):** 49 symbols, all suffixed `.sim`. Present: 42 FX, US100/US500/US30, XAUUSD, XAGUSD, USOIL, BTCUSD. **ABSENT: platinum, palladium, natural gas — the three are hereby resolved EXCLUDED for this line** (not cost-parked: the target platform does not offer them; no cost question exists). US100 = the NQ already mechanism-killed at Gate 2 — no cost run needed. M30 history with a PER-BAR spread column (points): XAUUSD.sim and US500.sim back to 2022-04; EURUSD.sim only to 2025-05 (sufficient for clock checks).

## Pre-registered cost-gate spec (before looking at any spread value)

1. **Clock check first** (Gate-1 method verbatim, re-run for this server): EURUSD.sim + USDJPY.sim M30 closes vs OANDA v20 UTC, January-2026 month and July-2025 month, unique offset with correlation > 0.999 required per month. If the two months differ (EET DST expected), the offset is applied piecewise using European DST boundaries. Fail → source unfit, gate aborts.
2. **XAUUSD re-adjudication (the binding test):** for each of the 974 trades in `gate2_XAUUSD_trend_origin_pullback_full.csv`, replace the assumed 37-pip round-trip cost with the REAL spread at the trade's entry bar (`.sim` per-bar spread, points × 0.001 price units; cost arithmetic identical to the harness's: cost = spread-in-pips × units × pip-value/100k with the registered XAUUSD conventions, pip 0.01 / pip-value $0.10). Trades before 2022-04-12 (no .sim bar) and any missing bars use the hour-of-day MEDIAN spread from the full .sim history — registered fallback. **Criterion: the Gate-2 pass STANDS iff full-window net stays positive under real per-trade costs. Net ≤ 0 → candidate KILLED as spread-eaten (failure_db entry), the Gate-2 pass superseded with a dated note.** Reported alongside, honesty row: median and p90 real spread vs the 37-pip assumption, and the count of fallback-priced trades.
3. **US500 final cost screen:** Gate-1's registered threshold applied to real data — median .sim spread as % of median M30 range; < 25% unparks it (Gate-2 eligibility), ≥ 25% converts the provisional exclude to FINAL.
4. Nothing else runs. XAGUSD/BTCUSD/USOIL are out of scope of every open line; recorded as available for future registrations only.

**Artifacts:** `phaseB_cost_gate.py` (committed before results), `phaseB_xau_cost_readjudication.csv`, verdict entry below when run.

**AMENDMENT (same date, before any verdict is accepted):** the first run exposed a data artifact the spec didn't anticipate — the `.sim` per-bar spread column is 100% ZEROS for 2022–2025 and only populated from 2026-01 (~5,900 bars). Zero-spread bars are unpopulated history, not real quotes; the first run's verdicts (computed mostly on zeros) are VOID and not logged as results. Amended handling, registered before the re-run: bars with spread == 0 are treated as MISSING → every affected trade prices at the hour-of-day median from the populated 2026 window only. Consequence stated plainly: the re-adjudication applies the platform's CURRENT (2026) spread structure to the whole trade record — which is the fidelity Phase B exists to measure (what a challenge taken now would pay), but it is not a historical spread series, and that limitation is permanent for this source. XAUUSD 2026 facts: spreads vary per bar (50–2,500+ points observed) but the hourly median is 250 points (= 25 pips in the registered convention) at every hour; US500 is effectively fixed at 4–5 points (0.4–0.5 index points).

## COST-GATE VERDICTS (amended spec, run 2026-07-09)

- **Clock:** unique offsets +2h (January) / +3h (July), correlations ≥ 0.999956 — EET with European DST; piecewise conversion applied per registration. Source fit.
- **XAUUSD re-adjudication: THE GATE-2 PASS STANDS.** 974 trades; 115 priced at their real entry-bar spread, 859 (pre-2026 entries) at the 2026 hour-of-day median per the amendment. Real spread at entries: median 25.0 pips, p90 25.0 (the platform's flat hourly-median structure) vs the 37-pip Gate-2 assumption — **the assumption was conservative by ~a third.** Full-window net moves +$13,755.37 → **+$14,509.09** under real costs. Standing caveats: the 2026-structure extrapolation (above) and everything from the Gate-2 pass (window ceiling, gold-bull factor dependence, tail convergence).
- **US500: UNPARKED → Gate-2 eligible.** Real median spread 0.5 index points vs 6.5-point median M30 range = **7.7%**, well under the registered 25% limit (the Gate-1 provisional exclude was an off-session Phase A snapshot artifact, as suspected). Any Gate-2 run on US500 requires its own registration — noting up front that its sibling index US100/NQ killed both fleet trend mechanisms, so priors are poor and a US500 trend run must justify itself against that record.
- Bookkeeping: XPT/XPD/XNG resolved EXCLUDED (not offered on the target platform — recorded in the source entry above); the Phase A → Phase B spread comparison for XAUUSD (37 assumed / 25 actual) is the first measured fidelity gap between the two demo tiers.

**Prop-firm expansion line state after Phase B:** XAUUSD × trend-origin pullback is now validated-but-benched with REAL platform costs confirmed — every gate this line defined has been run. What remains before any challenge decision is operator territory: whether to run a live-paced forward test on the trial account (14-day clock), and the standing tail-convergence/factor-dependence judgment. US500 sits Gate-2 eligible, unregistered.

---

# 2026-07-09 — FTMO TRIAL FORWARD TEST: registration BEFORE first armed cycle (operator-directed; bot `ftmo_trial/ftmo_gold_bot.py`)

**Operator direction:** run the validated XAUUSD × trend-origin pullback candidate live-paced on the 14-day FTMO free trial (demo 1600158217, OANDA-Demo-1, $100k virtual, 2-Step rule set). Risk level operator-selected: **0.5% of current equity per trade** (the level this mechanism family passed FTMO 2-Step at in the prop sims; gold's trailing pre-check also survived 0.5%).

**Phase framing, pre-committed on zero live results (the personal-live convention):** at the record's ~4 signals/week, 14 days ≈ 8–10 trades. **Nothing about strategy performance gets concluded from this run** — n<10 is noise, and the 10% trial profit target is arithmetically out of reach at 0.5% risk (~8 trades × 2.5R best case ≈ +10R = +5%). What this run exists to measure: execution mechanics on the actual challenge platform — fills vs signal prices, slippage, spread paid vs the 25-pip cost-gate number, SL/TP placement behavior, MT5 order-path reliability, guard behavior. The artifact doubles as the bot a real paid challenge would use.

*Correction (2026-07-09, operator-caught, same day):* the trial's actual profit target is **$5,000 = 5%** (the free trial halves the paid 2-Step Phase-1 10% target; the 10% figure above was the paid-challenge number). At 0.5% risk that is NOT arithmetically out of reach — e.g. 6W/3L at 2.5R = +6% clears it — just improbable (~binomial tail around the mid-30s% win rate at n≈9). The phase framing is unchanged: mechanics remain the purpose; a lucky pass would be recorded as luck, not validation.

---

# 2026-07-09 — DIVERSIFICATION CAMPAIGN (operator-directed, top priority): more validated slots on the FTMO trial. TRACK 1 PRE-REGISTRATION: US500 Gate 2

**Campaign registered as a whole (tracks in priority order, each with its own registration before its runs):** (1) US500 Gate 2 — this entry; (2) second trial slot from the shelf: pullback30's long-only variant on USDJPY.sim via a multi-slot refactor of the trial bot; (3) US500 slot if Track 1 passes; (4) the MR reopen on XAUUSD (fresh registration when reached); (5) standing broad-discovery program across the full tradeable universe, dual-adjudicated against prop presets and personal-account feasibility. Constraint governing all of it: FTMO's −5% daily / −10% total are account-level and SHARED across slots; per-slot risk stays 0.5% with an aggregate open-position cap.

## Track 1 spec (fixed before any run)

Identical protocol to the 2026-07-08 Gate-2 registration (0445ded), applied to **US500** (Phase A symbol `SPX`, 4.27y M30): both live-validated trend mechanisms, plugins unmodified, zero new constants. Stage 1: calendar-2023 quick-check, $80 fixed risk, grid-cell kill criteria verbatim (expectancy negative OR n<20 OR median stop < 10× spread). Stage 2 for survivors: full window 2022-07-01 → 2026-07-01, passport-track adjudication.

- **Sizing conventions (registered now):** pip = 0.1 index points, pip-value $0.10/lot/pip (self-consistent convention, rounding distortion ≤~2% at $80 risk given typical index stop distances).
- **Spread: 5 pips (= 0.5 index points at the 0.1-point pip).** Source: the REAL Phase B cost gate (median 0.5 points on the actual FTMO feed) — an upgrade over the Phase A indicative snapshots the XAU/NQ runs used, available because the cost gate ran first this time.
- **Honest prior, stated before the run:** the sibling index (NQ/US100) killed BOTH mechanisms at full window after a 2023-only quick-check pass. A US500 pass must survive the no-single-year-dependency box specifically; a 2023-carried pass is the expected failure shape.
- Any passer: factor-overlap extension (map conventions verbatim, row added) and trailing pre-check before any deployment slot is considered.

**Artifacts:** `gate2_killtest.py` extended with the US500 entry + a symbol-filter argument (committed before results), CSVs `gate2_SPX_*`, verdict entry below when run.

## Track 2 registration (same date): second trial slot — pullback30's long-only variant on USDJPY.sim; multi-slot bot architecture

**What deploys:** the trend-origin pullback plugin, unmodified, LONG-ONLY (the pullback30 fleet-probation variant — best prop-preset profile on the board: all four presets pass), on USDJPY.sim at 0.5% risk. This is a shelf deployment (validated + on live fleet probation since 2026-07-01), not new research. **Honest portfolio note carried from the campaign registration:** this slot is the fleet's USD_JPY trend cluster — it diversifies the trial account only modestly vs the gold slot (gold↔cluster pairwise lift 0.73–1.03, but tail-convergent). It is accepted because the trial's goal is shots-on-target within 13 days, and it is capped at one cluster member (scalp30 and D/H4 explicitly skipped).

**Architecture (registered):** ONE process, N slots — `ftmo_gold_bot.py` refactored to a SLOTS table rather than N processes contending for the terminal IPC. Per slot: own symbol, own risk (0.5%), own one-position cap, own magic number, and — critically — **its own plugin module instance via importlib** (the harness's `_load_plugin` pattern), because the plugin's re-entry guard (`_last_used_pair_id`) is module-global and interleaved trades on a shared module could wipe each other's zone identity (bug caught at design, test-covered). Shared, account-level (FTMO's rules are account-wide): the −$2,000 daily circuit breaker, the $93,000 equity floor, and an aggregate cap of 3 open positions. Worst-case concurrent exposure at 2 slots: 1.0% of initial vs the −5% daily line. Data check: USDJPY.sim has the full 230-H4/400-M30 live warm-up depth.

**Tests:** 11/11 — the prior suite plus slot isolation (per-slot cap blocks only its own slot), long-only filter (blocks jpy shorts, leaves xau shorts), aggregate cap, plugin-state isolation (two module instances, independent `_last_used_pair_id`), shared guards halting all slots.

**What changes for the record:** the trial's forward observations now cover two slots; the jpy slot's fills are mechanics data for the SAME plugin the fleet has on probation — a useful cross-venue execution comparison (OANDA v20 practice vs FTMO .sim), explicitly NOT probation evidence (different account, sizing, and venue).

## TRACK 1 VERDICTS (2026-07-09, same night): US500 splits by mechanism exactly as XAUUSD did — donchian REJECTED, trend-origin pullback PASSES

**Quick-checks (2023):** both CLEAR (donchian n=535 exp +$7.33; pullback n=259 exp +$12.75) — as the registered prior warned, 2023 clears everything on US indices; the full windows did the real work.

**Full windows (2022-07 → 2026-07, real 5-pip spread):**
- **US500 × donchian: numeric CLEAR (+$2,898/2,163, exp $1.34), REJECTED at adjudication** — profits confined to 2023–24 (+$9,371 combined), while 2025 + 2026H1 sum **−$6,096**; the most recent 18 months bleed against a net smaller than either good year. Same reject shape as XAUUSD × donchian (concentration + deterioration). Recorded here; no failure_db mechanism entry (per-instrument adjudication reject; the mechanism stays live-validated on USD_JPY).
- **US500 × trend-origin pullback: PASSES adjudication — validated-but-benched.** n=990, net **+$6,631**, WR 31.6% (breakeven 28.6% at ≥2.5R), exp $6.70/trade. Yearly −$715 / +$3,303 / +$1,754 / +$2,732 / −$442: **ex-best-year net +$3,328 still positive** (the box that killed NQ and USD_CHF), 3 of 5 periods positive, the two negatives are the partial years. Flag carried honestly: 2026H1 is slightly negative (−$442, ~7% of net) and the pass is weaker than gold's on every metric (WR, expectancy, Sortino unrun) — a thinner edge, priced accordingly.

**Factor-overlap extension (map conventions verbatim, spx_pullback row added; base 52.4% losing weeks):** the cleanest profile on the whole map — cluster→SPX lifts **0.57–0.73**, SPX→cluster 0.78–1.00, and **SPX↔gold 0.89/0.93 — below chance against the OTHER trial slot**, so the two candidate slots diversify each other, not just the fleet. Tail participation: 45 of 81 heavy weeks (56% vs 52.4% base ≈ **1.06× tail lift — near-chance even in the tails**, far better than gold's 1.56×). Mechanical caveat as before: the ≥4-of-9 conditioning inflates the week count; the participation ratio is the comparable number.

**Trailing pre-check: `proceed`** — worst trailing-style DD −9.2% at 0.25% risk / −17.7% at 0.5%; not blown-2× on FTMO 1-Step-shape at either level (FundedNext's 3% lock blown at both, as for every non-pullback30-FX strategy). Artifact `gate2_SPX_pullback_trailing_precheck.json`.

**TRACK 3 EXECUTED (same night): `spx` slot added to the trial bot** — US500.sim × trend-origin pullback, both directions (the as-adjudicated variant), 0.5% risk, magic 20260711. The trial account now runs three slots whose pairwise weekly co-loss lifts are ALL at or below chance (gold↔cluster 0.73–1.03, SPX↔cluster 0.57–1.00, SPX↔gold 0.89/0.93) — as diversified as the validated shelf currently allows. Worst-case concurrent exposure 1.5% of initial vs the −5% daily line; shared guards unchanged.

---

# 2026-07-09 — TRACK 4: MEAN-REVERSION LINE REOPENED under its own bar — candidate #8, AVWAP fade on XAUUSD (spec pre-registered BEFORE any run)

**The bar and why it is met:** the line closed 2026-07-02 (six designs) and its reinforcement after candidate #7 (2026-07-03) says: no candidate #8 without a genuinely new mechanism class — **"different asset class, different data source, or equivalent."** XAUUSD is both: a different asset class AND a data source (MT5) that did not exist when the line closed. The FX post-mortem's terminal conclusion was cost-structural ("the underlying M30-scale reversion premium does not exist **net of this cost structure**") — gold's measured cost structure is categorically different: real spread 25 pips against a $10.07 median M30 range (3.7%), the best spread-to-range ratio ever available to this line.

## Candidate #8 spec (registered before any run)

**The DESIGN is candidate #7's, verbatim — `avwap_fade_plugin.py`, every registered constant unchanged** (entry 2σ, stop 3σ frozen, TP=VWAP frozen, min R:R 1.2, TP ≥ 10× spread, ≥6 session candles, one trade per session-direction, fire-and-forget, no gates, no carve-outs). What changes is only what MUST change for the instrument, plus the one pre-committed lesson from #7's own kill:

1. **Instrument parameterization (not tuning):** XAUUSD pip = 0.01 (the registered Gate-2 convention); assumed spread = **25 pips** (the REAL Phase B platform median, not an FX table entry). Injected via a thin wrapper module (`avwap_fade_xau_plugin.py`) that delegates to the unmodified core.
2. **Box-9 minimum stop distance** (spec lesson logged AT #7's kill: "R:R floors do not bound absolute stop distance", the $1,895/0.1-pip-stop trade): signals with stop distance < **10× spread = 250 pips ($2.50)** are rejected. Constant CHOSEN (10× mirrors the Amendment-1 TP floor), not tuned.
3. Session anchor stays daily 00:00 UTC (data served in UTC via the Gate-1-verified conversion); volume = MT5 tick volume (the same proxy class the spec names).

## Pre-committed kill-test — TWO stretches, BOTH must pass, fail-on-either decisive (the harder-test rule: this design has seen seven prior failures)

- **Stretch A (ranging-ish home turf): 2023-01-01 → 2024-01-01.**
- **Stretch B (the MR killer class — gold's strongest persistent-trend year): 2024-07-01 → 2025-07-01.** Pre-registered as decisive precisely because trend-quarter bleed is what killed v2 (−$1,004) and #6 (−$1,266); a gold MR design that cannot survive the gold bull is dead on the fleet's actual calendar.
- Gate per stretch: **net-positive AND n ≥ 30** at $80 fixed risk, 25-pip spread included, corrected harness, Phase A M30 data via the gate2 fetch seam.
- **Stopping rule, pre-committed:** failure at either stretch makes this the EIGHTH dead design; the closure is then re-reinforced with the bar raised to "different mechanism class AND different asset class simultaneously" — the asset-class door alone will have been tried and shut. No retuning, no variant, no carve-out.
- Only if BOTH pass: full window (2021-12 → 2026-07) with passport adjudication + trailing pre-check, per convention.

**Artifacts:** `avwap_fade_xau_plugin.py` (wrapper, committed before results), `c8_killtest.py` (runner), CSVs `c8_xau_avwap_{A,B}.csv`, verdict entry below.

---

# 2026-07-09 — CANDIDATE #8 KILLED at the kill-test: fail-on-either executed on stretch A. THE MEAN-REVERSION CLOSURE IS RE-REINFORCED WITH THE BAR RAISED

**Results (registered criteria verbatim, $80 fixed risk, real 25-pip spread):**
- **Stretch A (2023, ranging-ish): n=35, net −$239.15, WR 28.6% — FAIL** (net-positive required).
- Stretch B (2024-07→2025-07, the gold bull): n=103, net +$923.15, WR 30.1% — passed, and is hereby recorded as the weak evidence it is (a pass after a decisive fail adjudicates nothing).

**The kill's shape is the line's cruelest data point yet:** the design SURVIVED the persistent-trend stretch that killed v2 and #6, and died in the ranging year MR is supposed to own — with the best cost structure the line has ever had (25-pip spread vs $220-class winners; this is NOT spread-eaten). The 2σ-close-marks-momentum-not-exhaustion lesson from #7 holds even on gold, even in ranging regimes: the fade edge simply is not there at M30 scale. `failure_db.json` entry `avwap_fade_xau_c8` (lesson: no-edge).

**Stopping rule executes as pre-committed:** eighth dead design. The closure stands re-reinforced with the bar RAISED: reopening now requires a **different mechanism class AND a different asset class/data source simultaneously** — the asset-class door alone has been tried and shut. The diversification need the GOVERNANCE portfolio note names remains real and unmet by mean reversion; the fleet's uncorrelated exposure continues to come from the spreads and (per the extended overlap map) the index/metal trend slots.

---

# 2026-07-09 — TRACK 5 OPENED: standing discovery program — protocol + LINE 1 REGISTRATION (tradeable-universe completion)

## Program protocol (standing)

Candidates are (mechanism × symbol) cells drawn from the OPERATOR-TRADEABLE universe only — the FTMO `.sim` set and the OANDA live set; symbols with no execution venue are out of scope regardless of data (this retires the 8 quality-excluded European/Asian indices from the queue: no FTMO-US venue exists for them). Every cell runs the existing gate protocol (data screen → registered mechanism kill-test → full-window passport → overlap + trailing pre-check), and every validated candidate is adjudicated on BOTH tracks: prop fitness (`prop_rules.py` presets) and personal-account feasibility (`account_feasibility.py` at the live account's actual NAV, checked at adjudication time). One registered line at a time; kills get failure_db entries; design priors carry forward (current standing prior: trend-origin pullback transfers across asset classes, donchian does not — 2 instruments of evidence each way).

## Line 1 registration (before any run): complete the tradeable-universe data screen

Four symbols the operator can trade that have never cleared (or never received) a data screen:

1. **YM/US30 re-screen** (Gate-1 quality-excluded at 5.1% deficient weeks) and **XAGUSD re-screen** (excluded at 5.0%) — under the **registered Gate-1 v2 completeness criterion** (the reopen path the Gate-1 verdicts entry required): a week is deficient only below **60% of the symbol's modal weekly bars** (tolerates a holiday plus a half-day; the original 80% flagged single-holiday weeks by construction), share limit unchanged at 5%. Phase A data, same windows as Gate 1.
2. **USOIL and BTCUSD first screens** — never screened (absent from Phase A's candidate classes). Data: `.sim` M30 history (2022-04+). Same v2 criterion; usable window ≥ 3.0y; cost check uses the REAL `.sim` spread (2026 populated bars, median as % of median M30 range, 25% limit — the amended cost-gate convention).
3. Survivors become Gate-2 eligible (both trend mechanisms, per protocol — donchian's 0-for-2 transfer record is a prior, not a pre-emptive exclusion). MR candidates stay with Track 4's process.

**Artifacts:** `gate1v2_rescreen.py` (committed before results), verdict entry below.

## Line 1 VERDICTS (run same morning): 4 of 4 PASS — the v2 criterion confirms the Gate-1 quality excludes were calendar artifacts

| symbol | window | deficient (v2, 60% floor) | spread vs median M30 range | verdict |
|---|---|---|---|---|
| YM (US30) | 4.3y | 0.5% (was 5.1% at the 80% floor) | 12.50% indicative | **PASS** |
| XAGUSD | 4.8y | 1.0% (was 5.0%) | 18.83% indicative | **PASS** |
| USOIL.sim | 4.2y | 0.0% | 11.49% REAL | **PASS** |
| BTCUSD.sim | 4.0y | 0.0% | 0.57% REAL | **PASS** |

All four are Gate-2 eligible. **YM + XAGUSD Gate 2 registered now** (Phase A data, protocol identical to the prior Gate-2 registrations, both mechanisms, conventions: YM pip 1.0 point / pip-value $0.10 / spread 6.6 pips indicative; XAGUSD pip 0.001 / pip-value $0.10 / spread 58 pips indicative — both from the Gate-1 snapshot, the honest number available on this source). **USOIL/BTCUSD Gate 2 QUEUED** — their only history is the `.sim` feed, which needs a small backtest fetch seam (EET-DST-piecewise conversion, not Phase A's fixed −2h) built and registered before any run; not smuggled into this one.

## Line 1 Gate-2 VERDICTS (same morning): XAGUSD killed at quick-check, YM killed/rejected at full window — nothing new deploys; the "pullback transfers" prior is DEAD

- **XAGUSD × both mechanisms: KILLED at the 2023 quick-check** — expectancy negative (donchian −$14.23/trade n=292; pullback −$9.99 n=156) AND median stops (165/268 pips) sit BELOW the 580-pip box-9 floor. Silver reproduces the FX geometry: structural stops smaller than 10× spread. failure_db ×2 (`xagusd_*_m30_gate2`, spread-eaten). **Lesson worth its own sentence: gold passes and silver dies on identical mechanisms — spread-to-range geometry, not asset class, is the cost variable.**
- **YM × trend-origin pullback: KILLED at full window** (n=850, net −$3,377, WR 28.4%; yearly −231/+2,085/−2,543/−1,822/−865 — the NQ shape: 2023-only). failure_db `ym_trend_origin_pullback_m30_gate2` (regime-non-transfer).
- **YM × donchian: numeric CLEAR (+$3,871/1,793) but REJECTED at adjudication on the windfall box** — the 2022 partial year is +$3,726 of the +$3,871 net (96%); ex-best-year ≈ +$145 ≈ zero. Textbook windfall-year, the failure_db's largest cluster. Adjudication reject, recorded here (mechanism positive elsewhere; no failure_db kill entry, per the XAU/SPX-donchian precedent).
- **Prior correction (honesty over tidiness):** last night's note said pullback transfers across asset classes while donchian doesn't. With YM in, the tally is pullback 2-of-4 non-FX instruments (XAU ✓ SPX ✓ NQ ✗ YM ✗), donchian 0-of-4. **There is no mechanism-level transfer law — transfer is instrument-specific** and must be tested per instrument, which is exactly what the gate protocol does. The prior is retired from Track 5's design assumptions.

**Line 1 state:** deployed slots unchanged (xau/jpy/spx remain the validated set). USOIL + BTCUSD Gate 2 still queued behind the registered `.sim` fetch seam — the next Track 5 work unit. BTCUSD's 0.57%-of-range real spread is the most interesting untested number on the board.

## Line 1 continuation — USOIL/BTCUSD Gate 2 REGISTRATION (operator-directed, before any run)

**The `.sim` backtest seam (registered build):** a fetch adapter for the FTMO/OANDA terminal serving UTC frames via the MEASURED piecewise clock (winter +2h / summer +3h, European DST boundaries — the Phase B cost-gate verification), self-contained in the runner (one terminal per process; the Phase A harness path is untouched). Data is real `.sim` M30 price history, 2022-04+ (USOIL) / 2022-06+ (BTCUSD).

**Protocol identical to every prior Gate-2 registration** (both mechanisms unmodified, 2023 quick-check with the grid kill criteria, full windows for survivors, $80 fixed risk). Conventions registered from measured values:
- **USOIL:** pip 0.01, pip-value $0.10/lot/pip, spread **3 pips** (real median $0.03 on 6,547 populated bars). Full window 2022-07-01 → 2026-07-01.
- **BTCUSD:** pip 1.0, pip-value $0.10/lot/pip, spread **2 pips** (real median $2.00 on 6,883 populated bars; 0.57% of the $247 median M30 range). Full window 2022-10-01 → 2026-07-01. Weekend sessions included as the venue trades them.
- Priors, stated: no transfer law exists (retired this morning); donchian is 0-for-4 on non-FX, pullback 2-for-4. Both still run — the protocol tests instruments, not priors.

**Artifacts:** `gate2sim_killtest.py` (committed before results), CSVs `gate2sim_*`, verdict entry below.

## USOIL/BTCUSD VERDICTS (same day): the mechanism/instrument matrix splits AGAIN — and BTCUSD × donchian is the expansion's second validated slot

**Quick-checks (2023):** USOIL×donchian KILLED (n=527, −$6.64/trade); USOIL×pullback CLEAR (+$8.64); BTCUSD×donchian CLEAR (**+$29.65/trade**, the strongest quick-check ever recorded here); BTCUSD×pullback KILLED (n=228, −$12.92 — on the cheapest cost structure ever measured, so cost is NOT the killer). failure_db ×2.

**Full windows:**
- **USOIL × pullback: KILLED** (n=1,007, net −$297, the 2023-only shape: −2,270/+2,039/−743/−34/+711). failure_db `usoil_trend_origin_pullback_m30_gate2`. Oil is fully closed.
- **BTCUSD × donchian: PASSES adjudication.** n=1,631, net **+$17,139**, WR 32.4%, exp $10.51/trade. Yearly +193/+10,912/+3,768/−3,087/+5,353: **ex-best-year +$6,227 positive**, 4 of 5 periods positive, 2026H1 is the second-best period (no deterioration tail). Concentration flag carried: 2023 is 64% of net.
- **Overlap (map conventions, `btc_donchian` row, base 56.1%):** clean — cluster→btc 0.65–0.73, btc→cluster 0.94–1.07, btc↔xau 0.81/0.88, btc↔spx 0.89/0.95. All at/below chance vs the fleet AND both trial slots.
- **Trailing pre-check: `proceed`, with a sizing signal** — worst trailing DD **−35.8% at 0.5% risk** (twice the book's profile) vs **−19.4% at 0.25%**. Deployment sizing is therefore **0.25%**, matching the pre-check's registered lower level — a risk-structure match, not a tune.

**DEPLOYED: `btc` slot** (BTCUSD.sim × donchian, both directions, 0.25%, magic 20260712) — the trial bot's fourth slot and the first non-pullback deployment. Multi-slot bot gains per-slot plugin files (fresh module per slot, both plugins covered by the isolation test). Mechanism/instrument tally after the full sweep: donchian 1-for-5 non-FX (BTC only), pullback 2-for-5 (XAU, SPX) — every cell decided by its own test, never by a prior. Worst-case concurrent exposure across 4 slots: 1.75% of initial.

---

# 2026-07-09 — BOOK PROP-SIM REGISTRATION (operator question: does the 4-slot book clear +10% under FTMO 2-Step mechanics?) — spec fixed before any path is simulated

**Design (registered):** Monte Carlo of the combined 4-slot book through FTMO 2-Step rule mechanics. Inputs: the four validated trade records at DEPLOYED risk (xau/spx gate2 fulls and jpy = fleet pullback30 corrected record at 0.5%; btc gate2sim full at 0.25%), R-multiples = pnl/$80. **Joint weekly block bootstrap** over the common coverage window (2022-10 → 2026-07): each simulated week draws ONE historical calendar week and replays all four streams' trades from that week day-by-day — preserving measured cross-slot co-movement and within-stream clustering (iid trade resampling would fake away exactly the tail co-losses the overlap map documents). Dollar P&L per trade = R × risk% × equity at week start. Rules from `prop_rules.py` FTMO_2STEP constants: daily loss floor −5% of initial per calendar day, static max loss −10% of initial, target +10%; path ends at target, breach, or 90 days. 10,000 paths. Secondary run at the trial horizon (13 days, +5% target) to check the hand-estimate given in chat (~15–20%).

**Honesty rows, registered up front:** (1) selection haircut sensitivity — the book is 4 survivors of 10 tested cells, so results are also reported with every stream's mean per-trade R shaved 25% and 50%; (2) block bootstrap from a historically favorable window inherits that window's regimes (gold bull, 2023 crypto); (3) this simulates records, not live execution — the trial's forward data is the check on that gap.

**Artifacts:** `book_prop_sim.py` (committed before results), results JSON, verdict below.

## BOOK PROP-SIM RESULTS (10,000 paths per cell, seed 20260709)

| scenario | P(+10% before breach, 90d) | P(breach) | median days | P(+5% in 13d trial) |
|---|---|---|---|---|
| as-measured | **74.2%** | 12.1% | 31 | **36.0%** |
| 25% expectancy haircut | 66.2% | 17.5% | 31 | 33.6% |
| 50% expectancy haircut | 57.2% | 25.2% | 32 | 30.7% |

- **Registered sanity check surfaced a real discrepancy:** gold-only at the trial horizon simulates to 14.3%, vs the ~5% crude binomial hand-estimate given in chat. Explanation: the binomial assumed fixed trade count and independent outcomes; real weeks have variable counts and clustered winners, which the block bootstrap preserves. The simulation is the better estimator — AND the same clustering means the headline numbers inherit the favorable-window caveat with full force (the bank of resampled weeks IS 2022-10→2026-07, gold-bull and 2023-crypto included).
- Trial-horizon breach risk is near zero (0.4–1.1%) — the floors bind on the 90-day challenge horizon, not in 13 days at these sizes.
- **Plain-language verdict, recorded:** under FTMO 2-Step mechanics the book as measured passes Phase 1 roughly 3 times in 4 within 90 days, and roughly 3 in 5 even if live expectancy comes in at HALF the backtests — but "as measured" is a selection-effect-inflated, regime-favorable record, which is why the haircut rows are the honest planning range and the live trial forward data is the arbiter.

**PROMOTED TO STANDING TOOL (operator-directed, same day):** `book_prop_sim.py` joins the standing instrumentation (`factor_overlap.py`, `prop_rules.py`, `sortino.py`). **Re-run trigger (registered):** whenever a slot is added, removed, or resized on the challenge book, or a slot's underlying record is corrected — the pass/breach numbers are book-shaped and go stale silently otherwise. Added to the audit's manual checklist. Conventions (joint weekly block bootstrap, seed policy, haircut rows) are fixed as registered above; changing them is a new registration, not an edit.

---

# 2026-07-09 — TRACK 5 PHASE 2 OPENED (operator-directed): new mechanism classes + sub-M30 timeframes. PHASE 0 REGISTRATION: the sub-M30 cost/data screen

**Why sub-M30 was never touched, restated as the testable claim it is:** "candle-scale stops die to spread" was measured on FX at OANDA retail spreads. It is a spread-to-range fact, not a timeframe law — and the FTMO universe's measured costs (BTC 0.57% of M30 range) make the sub-M30 door a per-instrument data question. Campaign lines (each gets its own registration): **Phase 0** this screen; **Line A** stat-arb phase-1 extension to XAU–XAG / US500–US30 / US500–US100 / BTC–XAU (validated methodology verbatim, analysis only); **Line B** opening-range breakout on index/gold RTH opens (new class: session-anchored MOMENTUM — distinct from the killed session FADE); **Line C** validated mechanisms at M15 where Phase 0 clears.

## Phase 0 spec (registered before running)

Per (instrument × timeframe) for M15 and M5 over the FTMO-tradeable survivors (XAUUSD, US500, US100, US30, BTCUSD, USOIL, plus EURUSD/USDJPY as FX reference rows), on the `.sim` feed (the deploy venue, real spreads): (1) **real median spread as % of median candle range** — the standing 25% ceiling; (2) usable history depth (report; ≥3y preferred, shorter reported not hidden); (3) completeness under the v2 criterion. Output: the eligibility matrix that gates Lines B/C timeframes. Prior stated before the run: BTC clears both rungs, indices/gold clear M15 only, FX clears neither. Artifact: `gate1_subM30_screen.py` + printed matrix logged here.

## Phase 0 VERDICTS (run same day) — the registered prior was WRONG in the good direction: cost excludes NOTHING; depth is the binding constraint

| cell | spread % of median range (real .sim) | .sim depth |
|---|---|---|
| BTCUSD M15 / M5 | **0.77% / 1.50%** | 2.0y / 0.7y |
| XAUUSD M15 / M5 | 5.56% / 5.09% | 2.1y / 0.7y |
| US30 M15 / M5 | 5.88% / 9.09% | 2.1y / 0.7y |
| US100 M15 / M5 | 6.92% / 9.37% | 2.1y / 0.7y |
| US500 M15 / M5 | 10.00% / 14.29% | 2.1y / 0.7y |
| USOIL M15 / M5 | 18.75% / 23.08% | 2.1y / 0.7y |
| EURUSD M15 / M5 | **1.89% / 3.70%** | 1.1y / 0.7y |
| USDJPY M15 / M5 | **2.44% / 2.44%** | 1.1y / 0.7y |

- **Every cell clears the 25% ceiling** — completeness 0% deficient everywhere. The sub-M30 door is open on cost across the whole universe.
- **Depth rules the design:** .sim M15 reaches only ~mid-2024, M5 only ~late-2025 — no 2023 quick-check is possible on .sim sub-M30 data. **Resolution (the established two-source pattern, as used by every Gate 2):** backtests run on Phase A depth (M5 history: XAUUSD 4.8y, SPX 4.3y, per the original Gate-0/1 probes) with the REAL `.sim` spread constants above. Cells whose Phase A depth is also short are reported with their actual window, never silently.
- **Flagged, not opened: the FX rows.** EURUSD/USDJPY at 1.9–3.7% of sub-M30 range on this feed contradicts the OANDA-retail cost math that closed FX candle-scale trading. If real, FTMO-venue FX at M15 is a reopenable door — but the .sim FX spread column is exactly the kind of number the Phase B fidelity history says to distrust until cross-checked, and the fleet's FX post-mortems were venue-specific. Logged as a future line requiring its own registration and a spread cross-validation; NOT pursued in this campaign.

## LINE A REGISTRATION (before any analysis): stat-arb phase 1 on the new universe

**Method = the FX line's discriminating instrument, verbatim:** rolling-90 OLS adaptive beta on daily log closes; ADF battery on the adaptive spread — full-window p < 0.05 AND both pre/post-2024-01-01 halves p < 0.05 AND p < 0.10 in ≥ two-thirds of available calendar-year windows (scaled from the FX line's 4-of-6 because these records start 2021-09/2022-04; scaling registered now); beta-sanity guard unchanged (same sign post-burn-in, CV < 0.5). **Kalman is NOT run** — the 2026-07-02 result records it as non-discriminating (38/38 pass; all discrimination lived in roll90 + guard); running it again would only manufacture false confirmations. NO strategy code in this phase; a pass grants Phase 2 design discussion only.

**Pairs (registered):** XAU–XAG (classic precious-metals ratio), US500–US30 (large-cap index pair), US500–US100 (broad-vs-tech), BTC–XAU (exploratory, weakest economic prior, stated as such). Data: Phase A daily closes (depth 4.3–4.8y per symbol; common window per pair reported).

**Parity check, registered as the gate on the tool itself:** before any new-universe number is read, the script must reproduce the FX line's published EUR_USD/GBP_USD roll90 result on OANDA daily data (target: full p≈0.0000, PRE24 p≈0.0001, POST24 p≈0.0014, 5/6 years, beta mean ≈ +0.83, CV ≈ 0.26). Material deviation → fix the tool, not the target.

**Carried forward:** the standing prop opposing-legs open item (opposing positions on correlated instruments within one FTMO account; synthetic-execution design question) applies with extra force to index–index pairs and gates any deployment conversation, not this analysis.

**Artifacts:** `statarb_newuniverse_phase1.py` (committed before results), verdict entry below.

## LINE A RESULT: **ZERO regime-stable relationships — 0 of 4 pairs pass; the line concludes at Phase 1**

- **Parity check PASSED first** (the registered gate on the tool): EUR_USD/GBP_USD roll90 reproduces the published record — battery 0.0000/0.0001/0.0015 vs published 0.0000/0.0001/0.0014, beta +0.823 vs +0.832, CV 0.259 exact, including the same transient sign-touch guard miss. The new-universe numbers below are therefore trustworthy.
- **XAU–XAG: FAIL** (pre-2024 half p=0.121; 0/3 years; guard sign-touch + CV 0.475). The classic metals ratio is not regime-stable on this window.
- **SPX–YM: FAIL, the near-miss** (3/3 years pass, guard clean CV 0.236 — but pre-2024 p=0.115). Recorded as the only economically coherent residual; per the registered bar a miss is a miss.
- **SPX–NQ: FAIL** (pre24 p=0.184, 2024 p=0.440). **BTC–XAU: FAIL** decisively (guard CV 1.800, sign flips — never a relationship; the exploratory label earned).
- Common failure shape: the pre-2024 half — the same era-instability that killed the FX fixed-beta round, now failing UNDER the adaptive estimator that rescued EUR/GBP. No further estimator rescue exists in the registered toolkit; inventing one post-hoc would be tuning. **Line concludes; failure_db entry `statarb_newuniverse_phase1_null`.** The fleet's uncorrelated-behavior need remains served only by the FX spreads.

## LINE B REGISTRATION (before any code): opening-range breakout — session-anchored momentum, with the entry-timing question as a REGISTERED A/B

**Mechanism class:** session-anchored MOMENTUM — trades WITH the post-open move off the US RTH open's price discovery. Distinct from the killed session FADE (which traded against session extremes) and from the structure/channel trend mechanisms (no fractals, no EMAs, no multi-day state — the anchor is today's opening auction). Instruments: US500, US30, XAUUSD (gold trades the US-open clock; registered on that stated basis).

**Spec (all constants chosen, not tuned):**
- Session clock: US RTH open 09:30 ET, ET derived from UTC by the US statutory DST rule (second Sunday of March / first Sunday of November — the liquidity-trough line's hand-verified method). Opening range (OR) = high/low of 09:30–10:00 ET (two M15 bars). Signal window 10:00–15:30 ET.
- **Entry, TWO registered variants adjudicated separately per instrument (the operator's intra-candle question, made a testable design axis):** (1) `close` — first M15 CLOSE beyond the OR extreme (close-confirmed, the fleet convention); (2) `touch` — entry AT the OR extreme on the first bar whose range crosses it (models a resting stop-entry order; fill convention registered: booked at the OR level on the crossing bar, trade resolution starts next bar — same-bar post-touch SL hits are unmodeled, bias direction mixed, stated).
- Stop: the opposite OR extreme (structural). Box-9 floor: stop distance ≥ 10× spread (real .sim medians registered: US500 0.5 pts, US30 2.0 pts, XAUUSD $0.25). TP: 2× OR height from entry. One trade per (session date, direction), single-use identities. Both directions.
- **Fire-and-forget to SL/TP (registered deviation from classic day-flat ORB, stated plainly):** the harness's validated trade simulator resolves SL/TP only; adding a time-exit would mean harness surgery under every standing record. The `.sim` market trades ~23h/day, so positions resolve across the session break — this variant is "ORB entry, swing resolution," and it is adjudicated as such.
- Harness: mode `scalp` (H1/M15 — existing rung), Phase A M15 data (depth 4.3–4.8y) via the gate2 fetch seam, real .sim spread constants, $80 fixed risk, standing pip conventions (US500/US30 pip 0.1, XAU pip 0.01, pip-value $0.10).

**Kill-test (per instrument × entry-variant cell, 6 cells): the two-stretch rule — 2023 AND 2024-07→2025-07, BOTH net-positive with n ≥ 30, fail-on-either decisive.** Survivors → full window → passport → overlap/pre-check per protocol. Fresh unit tests BEFORE any backtest (standing convention): DST boundary dates hand-checked, OR construction, one-per-day identity, window gating, box-9 floor, touch-vs-close entry divergence.

**Artifacts:** `orb_plugin_core.py` + `orb_close_plugin.py`/`orb_touch_plugin.py` wrappers, `test_orb_plugin.py`, `orb_killtest.py`, verdicts below.

## LINE B KILL-TEST VERDICTS: **12 of 12 cells PASS** — the strongest sweep in the line's history, recorded with matching skepticism

Two engineering faults preceded the clean run, both caught and committed: (1) tz-naive DST boundaries vs the harness's tz-aware frames — a TypeError the harness logs per-candle but which my output filter hid, producing 12 zero-trade cells (regression test added; lesson: grep run logs for `Plugin error` before reading any n=0 as a verdict); (2) an O(n²) session scan that stalled full-year runs (bounded to the frame tail).

Clean results ($80 fixed risk, real spreads): every (instrument × entry-variant × stretch) cell net-positive — SPX close +$2,272/+$2,096, SPX touch +$677/+$4,619, YM close +$1,240/+$481, YM touch +$1,730/+$3,435, XAU close +$2,291/+$516, XAU touch +$2,941/+$1,200; n=190–373 per year-stretch; WR 35.4–45.7% at ~2R structure. **Skepticism registered before the full windows:** a 12/12 sweep across a 6-cell batch invites the multiplicity concern more, not less — the ex-best-year box, full-window distributions, cross-cell overlap (six ORB cells on correlated instruments are NOT six bets), and the touch-variant's registered fill-optimism all still stand between this and any deployment. Full windows now run for all six cells.

## LINE B FULL-WINDOW ADJUDICATION: 5 of 6 cells pass the passport boxes — the first NEW mechanism class validated since the stat-arb spreads

| cell | n | net | ex-best-year | yearly shape | adjudication |
|---|---|---|---|---|---|
| **XAUUSD × touch** | 1,458 | **+$10,718** | **+$7,555** | ALL 5 periods positive | **PASS — strongest** |
| XAUUSD × close | 1,198 | +$7,197 | +$4,503 | 4/5 (2024 −$1,065) | PASS |
| SPX × close | 1,245 | +$7,180 | +$4,857 | 4/5 (2026H1 −$738) | PASS |
| SPX × touch | 1,443 | +$6,070 | +$2,836 | 2026H1 **−$2,604** | PASS, deterioration flag |
| YM × touch | 1,232 | +$4,433 | +$2,074 | 4/5 (2022 −$605) | PASS, thinnest |
| YM × close | 1,057 | +$70 | −$1,519 | sign-alternating | **REJECT — no edge** |

**The A/B answer to the operator's entry-timing question, adjudicated honestly:** touch beats close on raw numbers everywhere except SPX-recent — BUT the touch variant's registered fill convention books entry AT the level with no stop-entry slippage, an optimism worth roughly $2–3/trade at gold's spread-to-stop geometry ≈ **$3–4k over the window — approximately the entire touch-vs-close margin on XAUUSD**. The bias band swallows the apparent advantage. **Deployment preference therefore goes to CLOSE variants (bias-clean, matches the fleet's confirmation convention); touch cells are validated-but-benched pending live stop-entry slippage data** (the trial's mechanics phase can measure exactly this later).

**Deployment shortlist (one cell per instrument, close variant): SPX × close and XAUUSD × close.** YM benched (Dow's edge is thin and variant-fragile). Before any slot goes live, the standing protocol still owes: cross-cell/book overlap rows (ORB-XAU shares an instrument with the pullback xau slot — different mechanism, same symbol: the bot's per-symbol position cap makes them mutually exclusive in practice, a deployment-design fact), trailing pre-checks, prop-sim re-run, and multi-timeframe slot support in the trial bot (M15 cycles). That is the next work unit; nothing in it needs operator input except the standing slot-count/risk sanity.

---

# 2026-07-09 — EXIT-RULE STUDY (operator-directed, run under the operator's 3-gate framing): the ~1R giveback is real, the mechanism is coherent, and every tested exit rule still fails — fire-and-forget confirmed near-optimal at bar-level fidelity

**Question:** trades run to near-TP and give it back; can an exit rule capture more? **MFE analysis (11,110 fleet backtest trades, marks paths):** median giveback (peak unrealized R − closed R) ≈ **1.01R on all three strategies**; 40–50% of trades touch +1R; **24–26% of those round-trip to the stop** (a 2R swing each). **Mechanism (Gate 0, passed):** the fixed 2.5R target demands full trend-leg extension in every regime; in weak regimes legs exhaust at +1–1.5R near prior structure and fire-and-forget rides the reversion back — the persistent-macro-trend reframe applied to exits.

**Three rules tested (constants chosen not tuned; design 2021–23 / held-out 2024–26; 0.03R exit costs):** breakeven-after-+1R, 50% partial at +1.25R, 0.75R ratchet trail. **All fail Gate 1** — partial decisively (−0.06 to −0.12R held-out), trail and BE marginal-negative. **Both reopen paths then tried same day:** (1) bar-accurate replay on true OANDA M30 highs/lows (347k bars) made it WORSE — true-high triggers fire more often, so more eventual winners get breakeven'd out (BE-always held-out deltas −0.046 to −0.088R); (2) regime-gating (rule active only at daily ER(20) < 0.20, standing convention) **halved the damage everywhere — the mechanism is real — but crossed zero nowhere** (best: pullback30 +0.002R ≈ wash).

**Standing conclusion for the bag:** the giveback is the price of the 2.5R tail that funds the entire expectancy; whipsaw tax ≥ giveback savings even in the regime the mechanism targets. failure_db entries 42–43. **Reopen bar: entry-time regime SIZING (risk less when the regime says legs are short) — avoids path-based stops entirely; own registration when picked up.**

---

# 2026-07-09 — ORB DEPLOYMENT REGISTRATION: slots 5–6 (`ospx`, `oxau`) at 0.5%, M15 cadence; the trial book goes to SIX slots

- **Overlap (map conventions, rows `orb_spx`/`orb_xau`, bases 47.6%/46.2%):** mostly-new bets. Same-instrument lifts vs the pullback slots: spx_pullback→orb_spx 1.13×, xau_pullback→orb_xau 1.20× (one direction each; reverse directions 1.13×/0.97×) — mild, well under the FX cluster's 1.2–1.3× mutual redundancy. ORB↔ORB 1.04–1.10×; everything else at/near chance.
- **Trailing pre-checks: both `proceed` with the gentlest profiles on the book** — SPX −4.9%/−9.6% at 0.25%/0.5%; XAU −7.0%/−13.7% (day-session structural stops keep drawdowns shallow). **Sizing rule applied: 0.5% both** (within the ≈−20% book profile). Artifact `orb_close_trailing_prechecks.json`.
- **Bot changes (tests 14/14):** per-slot timeframe (`tf`/`cycle_s`; main loop wakes every M15 boundary, M30 slots scan every other wake), **per-slot position caps now magic-filtered** (pullback-xau and orb-xau share XAUUSD.sim without blocking each other — the symbol-level cap would have serialized them), aggregate cap 3→4. Worst-case concurrent exposure: 6 slots × per-slot cap 1, aggregate 4 → max 4 × 0.5% = **2.0% of initial** vs the −5% daily line (btc at 0.25% makes the realistic worst case 1.75%).
- **Prop-sim re-run (standing trigger, 6-slot book):** challenge P(+10% before breach, 90d) **74.2% → 78.9%** (breach 12.1% → 14.9%); trial P(+5%, 13d) **36.0% → 47.9%**; haircut-50 row: 62.0% challenge / 39.6% trial. The diversification is arithmetic, not vibes.
- Same protocol as every deployment: registration commit → dry-run cycle → armed relaunch (WMI) → native verification past the next M15 boundary → observation-log entry. ORB slots run the close variant (bias-clean); the touch variants stay benched pending live stop-entry slippage measurements.

## ORB extension cell REGISTERED (same day): US100 × ORB close — the 7th-slot candidate

US100/NQ killed both TREND mechanisms (Gate 2), but ORB is a different class and was never run on it; the ORB spec transfers with zero constant changes. Cell: close variant only (the adjudicated A/B answer), Phase A `NQ` M15 data, real `.sim` spread **1.8 index points = 18 pips** at the 0.1-point pip (measured, 50k-bar median), pip-value $0.10, ORB core spread table gains `NQ`/`US100.sim` = 1.8. Kill-test: the registered two stretches (2023, 2024-07→2025-07), both must pass; survivor → full window 2022-07→2026-07 → passport/overlap/pre-check/prop-sim → slot decision. Honest prior: the instrument's trend-mechanism kills say nothing about session momentum either way; the 12/12 Line-B sweep says the class is strong on US-open instruments; the wider spread (18 pips vs SPX's 5) is the number most likely to kill it — the box-9 floor (OR height ≥ 180 pips) will bind on quiet days.

## US100 × ORB VERDICT: passes everything — and is **VALIDATED-BUT-BENCHED on family redundancy** (the highest overlap lift on the map)

- Kill-test: both stretches PASS (2023 +$1,357/297; 2024H2–25H1 +$321/321, thin, flagged). Full window: n=1,201, **+$6,207**, WR 41.1%, **ALL five periods positive**, ex-best-year +$4,263 — distributionally the cleanest ORB record. Trailing pre-check `proceed` (−6.6% worst DD at 0.25%; day-session shallow like its siblings).
- **Overlap is the decider: orb_nq ↔ orb_spx mutual co-loss lift 1.44× BOTH directions** — the highest pairwise number ever measured on the map, above the FX trend cluster's 1.2–1.3×. Two same-session ORB cells on two ~0.9-correlated US indices are one bet in two costumes. Versus everything else it's clean (≤1.10×).
- **Disposition (BTC-M15 precedent applied): BENCHED.** Deploying it beside `ospx` would be size-up dressed as diversification. Recorded as the index-ORB family's second member and the preferred **swap** candidate: its all-periods-positive distribution is better shaped than orb_spx's (2026H1 −$738), so if orb_spx's live record disappoints, the swap is pre-adjudicated. The trial book stays at six slots.

---

# 2026-07-09 — FX-ON-FTMO COST VERIFICATION LINE (registered before any measurement is trusted)

**The claim under test:** Phase 0 measured `.sim` FX spreads at 1.9–3.7% of sub-M30 candle ranges — cheap enough to reopen the FX candle-scale door the OANDA-retail post-mortems closed. **The registered suspicion:** FTMO's FX pricing is raw-spread PLUS per-lot commission, and the spread column structurally cannot carry commission — so the Phase 0 numbers likely understate true FX cost by the commission's pip-equivalent (indices/metals are typically commission-free, so THEIR Phase B numbers stand).

**Verification protocol (all three legs required):**
1. **Absolute spread stats** per FX major from the populated 2026 `.sim` bars (median, p75, in pips).
2. **Live feed cross-check:** sample real-time tick spreads over ≥20 minutes and compare to the column's contemporaneous values — the column is trusted only if live ticks match it.
3. **Commission from FTMO's published schedule** (cited, fetched — never assumed), converted to pip-equivalent per pair; **effective cost = spread + commission-equivalent.**
4. Recompute the cost-vs-median-range table at M15/M30 with effective cost; the standing 25% ceiling adjudicates. **Verdict per (pair × timeframe): eligible / excluded.** Eligible cells do NOT auto-open strategy lines — each gets its own registration after.

**Artifacts:** measurement script output logged here; commission source cited inline.

## FX-VERIFICATION RESULTS — and the finding that mattered was about BITCOIN

**Leg 1 (bar-column absolutes):** raw-feed pricing — EURUSD/GBPUSD/USDCAD median 0.1 pips, USDJPY 0.2, AUDUSD 0.4, EURJPY 0.3 (50k-bar medians).
**Leg 3 (commission, from the account's OWN FILLS — better than any published page):** USDJPY charged **$2.50/side/lot** (FX pays commission, +0.5 pips effective RT on majors); US500 charged **zero** (indices free — the index/gold cost gates stand); **BTCUSD charged $20.57/side/lot = $41.14 round-trip = 41.1 pips-equivalent — a cost the BTC gate never modeled** (it used the 2-pip spread alone). Published corroboration: FTMO raw pricing lists ~$2.50/side/lot FX+metals, indices commission-free. Gold's commission (~5 pips-equiv at $2.50/side) is inside the XAU pass margins (original pass assumed 37-pip cost; true ≈ 30); confirm on the first live gold fill.
**Leg 2 (live tick cross-check): FAILED AT SAMPLING TIME** — live medians 3.2/11.9/27.5 pips (EURUSD/USDJPY/GBPUSD) vs the column's 0.1–0.2. Confound documented: the 20-min sample landed in the 17:00–18:00 ET rollover window, the measured worst-spread hour (the liquidity-trough finding). **Verdict: the FX bar-spread column is UNTRUSTED; the FX door stays SHUT pending a session-hours re-sample** (registered follow-up; if session ticks match the column, only the rollover hours are toxic and FX M15 reopens with session carve-outs to consider — which the no-carve-out conventions would need to address explicitly).

## CORRECTION (correct-at-source, same day): the BTC commission voids the deployed btc slot's validation — SLOT RETIRED

Re-run of the BTCUSD × donchian full window with commission-inclusive cost (43.1 pips-equiv vs the 2 used at Gate 2): net **+$17,139 → +$6,616 (−61%)**; decisively, **ex-best-year +$6,227 → +$300 ≈ zero** — the windfall shape that rejected YM×donchian (+$145). 2023 carries 95% of the corrected net; 2022 and 2025 negative. The Gate-2 pass (2026-07-09, earlier today) is **superseded**: under true costs this record fails the no-single-year-dependency box. Artifact preserved separately (`gate2sim_commadj_BTCUSD_donchian_full.csv`); the uncorrected record retained for the audit trail. The benched BTC-M15 rung is simultaneously upgraded to cost-dead (41-pip commission vs 467-pip median stops ≈ 0.088R/trade against 0.025R expectancy). **The `btc` slot is retired from the trial book** — no new entries; its open position (0.47 lots) runs off to broker-side SL/TP per the retirement convention. failure_db entry `btcusd_donchian_commission_windfall`. **Standing lesson: the cost gate must read COMMISSION off a real fill (or the published schedule converted per-lot) for every new asset class — spread columns never carry it.**

Phase 0 cleared BTC at every sub-M30 rung (0.77% of M15 range — real). Cell spec: donchian unmodified at mode `scalp` (H1 confirm / M15 trigger — the existing rung), Phase A BTCUSD data (depth ~4.8y), real 2-pip spread, standing BTC conventions (pip 1.0, pip-value $0.10). Quick-check 2023 (grid criteria verbatim: expectancy negative OR n<20 OR median stop < 10× spread → KILL) → full window 2021-12→2026-07 for a survivor → passport/overlap/pre-check per protocol. Prior stated: the M30 validation is favorable context but rung-transfer is exactly what the grid taught us NOT to assume (cells 1–4 died on rung specifics). Artifacts: `linec_btc_m15.py`, CSVs `linec_*`, verdicts below.

## LINE C cell 1 VERDICT: passes the passport, **VALIDATED-BUT-BENCHED — deployment denied on redundancy** (the intraday/scalp30 precedent, applied before deployment this time)

- Quick-check 2023 CLEAR (n=982, +$4.28/trade). Full window 2021-12→2026-07: n=5,146, net **+$10,205**, WR 29.5%, exp $1.98/trade; yearly −666/+3,749/+4,201/+2,085/−1,199/+2,035; **ex-best-year +$6,003** ✓.
- **Overlap vs the DEPLOYED btc M30 slot — measured before any deployment thought: 97% shared trading days, 78.0% same-direction, weekly co-loss lift 1.23× both ways.** Same mechanism, same instrument, nested rungs = one bet at two granularities. Deploying both would be size-doubling dressed as diversification — the exact failure the 2026-07-01 roster note documents on intraday/scalp30, this time caught at the gate instead of after.
- Disposition: **benched.** The M30 slot keeps the book position (5× the per-trade expectancy, $17,139 vs $10,205 on comparable windows). The M15 record is available if the operator ever prefers trade-frequency over per-trade edge (e.g., a short-deadline challenge) — a swap, never both.

**The emerging pattern, worth recording:** on both non-FX instruments tested, donchian breakout fails to transfer while trend-origin pullback passes — the pullback mechanism (structure-anchored entries, origin-anchored stops) appears to be the more portable of the two, consistent with the persistent-macro-trend reframe (pullback entries demand a confirmed trend structure; breakout entries fire on any channel violation). Three instruments is still anecdote, not a law; noted for Track 5's design priors.

**Registered mechanics (all in the committed bot, none tunable mid-run):**
- Signal: `trend_origin_pullback_plugin.generate_signal` imported unmodified; fleet enrichment (`add_emas(detect_fractals(...))`) applied to H4(230)/M30(400) frames of `XAUUSD.sim`; last (forming) bar dropped.
- Orders: market with broker-side SL/TP attached, single TP = plugin tp[0] (2.5R; all three identical for this plugin anyway). Fire-and-forget, no trailing. One position max.
- Sizing: lots = 0.5% × current equity / (stop-distance × contract size), floored to `volume_step`, skip below `volume_min` (current-equity convention = `prop_rules.build_curves`' f×balance).
- **Guards, new-entries-only (never touch an open position):** daily circuit breaker at day P&L (server-day closed + floating) ≤ −$2,000 (3-point buffer inside FTMO's −5% line, because an open position can keep bleeding to its SL after the halt); total floor at equity ≤ $93,000 (buffer above the $90k static line; run-off convention applies).
- Safety rails: demo-mode + expected-login hard assert at connect; `--armed` gate (dry-run default); pidfile guard.
- **Structural notes, accepted and recorded:** plugin re-entry-guard state is in-memory (a restart forgets the last-used zone identity — same property as the fleet); `.sim` H4 boundaries are EET-with-DST vs the validated record's fixed UTC+2 Phase A boundaries (identical in winter, 1h apart in summer — the record was NOT re-run on shifted boundaries); the terminal session (OANDA MT5, operator's GUI login) is the connection dependency.
- Isolation: same class as the personal-live experiment — no scheduler task (manual WMI launch; a host outage is a test outage, known cost), not in RESEARCH_ACCOUNTS/portfolio_state/audit. Observation log: `ftmo_trial/RESEARCH_LOG.md`.

**Deployment protocol:** tests green (9/9 boundary-mocked, real-plugin seam covered) → this registration committed → isolation grep verified → dry-run cycle verified clean → armed relaunch → deployment-facts entry in the observation log. Verdicts at trial end (or expiry): a mechanics report — slippage/spread/fill statistics vs the cost-gate assumptions — and the forward trades listed without performance claims.

---

# 2026-07-09 — METHODS NOTE: float64 validated for this project's arithmetic; the real hazard is increment rounding — one latent bug found and fixed (`risk._round_lots`)

**Question (operator):** does the "never use float/double for money" rule apply here? **Answer, quantified:** no for P&L/price arithmetic, yes at broker-increment boundaries.

- **P&L accumulation error measured, not asserted:** the corrected intraday record (7,434 trades) summed with `decimal.Decimal` vs float64 differs by **3.64e-12 dollars** — ~13 orders of magnitude below the dollars-per-trade uncertainty of the spread/slippage models the sums feed. No float32 downcasts exist anywhere in the pipeline (grep-verified). float64 stands as the project convention; no decimal migration is warranted.
- **The real hazard, demonstrated twice tonight:** binary-float dust at increment rounding. (1) The FTMO bot's `floor(raw/step)*step` produced `0.41000000000000003` lots (product dust — caught by its test suite pre-deployment). (2) The adversarial test then exposed the second face in the fleet's `risk._round_lots`: **quotient dust** — `0.57/0.01 = 56.99999999999999`, flooring a whole step LOW (0.56 for 0.57). Direction conservative (undersizes by ≤1 micro-lot in rare boundary cases), so no standing record is affected — `test_backtest_boundary_parity.py` re-run post-fix: 60 trades identical, net +$475.70 unchanged.
- **Fix:** `round()` on both sides of the floor in `risk._round_lots` and `ftmo_gold_bot.size_lots` (inner `round(_,9)` clears quotient dust, outer `round(_,8)` product dust). Regression guard: `test_rounding.py` (adversarial dust values must land exactly on the step grid; floor-direction preserved). All suites green (test_pnl 4/4, parity, spread execution 6/6, grouping 5/5, FTMO bot 9/9). The armed trial bot was restarted onto the fixed code (old PID 26608 → 26936, zero positions held, clean first cycle).

One validated-but-benched candidate: **trend-origin pullback on XAUUSD, H4/M30, as-designed** — the same mechanism on probation at pullback30, which failed to transfer to 8 FX pairs but transfers to gold; the pair-expansion line's "mechanism generalizes, payoff doesn't" verdict now has its first counterexample, at asset-class rather than pair granularity. **Next steps, in order:** (1) Phase B broker-matched demo (operator signup, chosen firm — FTMO is the natural first target given the pre-check profile) → re-price the spread assumption → cost-gate the benched candidate; (2) factor-overlap extension XAU-vs-fleet before any slot discussion; (3) the deferred MR-reopen candidate on XAUUSD (different mechanism class, own registration) remains available but is NOT opened here.

---

# 2026-07-09 — REGISTRATION: entry-time regime-sizing line (reopen bar of the exit-rule giveback study) — committed BEFORE any results

**Provenance:** the banked exit-rule study (failure_db 42–43) killed every path-based exit but registered this reopen bar verbatim: *"entry-time regime SIZING (risk less when the regime says legs are short) — avoids path-based stops entirely; own registration when picked up."* The Gate-0 mechanism (regime-dependent leg exhaustion) survived; only its in-flight-exit form failed. This line tests the sizing form.

**Rule (all constants chosen, not tuned — no sweeps will be run):**
- At entry, Kaufman ER(20) on the instrument's OWN daily closes, **completed days only** (a daily bar counts iff its open time + 24h ≤ the entry time on the same clock — no lookahead). ER < 0.20 (standing convention, `ergated_sweep_fade_plugin._kaufman_er` period/threshold) → risk multiplier **0.5×**; else 1.0×. Insufficient history (<21 completed days) reads as trending → 1.0× (the standing gate-closed convention).
- Daily series mirror the record's source: OANDA D candles (`data.fetch_candles(pair, "D")`) for the FX records; Phase A MT5 D1 (`mt5_client.get_history(sym, "D", …)`, fixed UTC+2) for XAUUSD/SPX. Entry times are UTC; the +24h completed-bar rule is applied after converting to the daily series' clock.

**Records:** the exact prop-sim book streams (`book_prop_sim.STREAMS`: xau, jpy, spx pullbacks + ORB SPX/XAU close) are the DEPLOY evidence. The three fleet records (intraday/scalp30/pullback30, n≈11k) run as mechanism corroboration only. Split: design 2021–2023 / held-out 2024–2026 (standing).

**Gates (fail decisive → failure_db, no bot change):**
1. **Gate M (mechanism, design window):** pooled book mean-R on ranging-regime entries must sit at least **0.05R below** trending-regime mean-R, and the fleet corroboration set must show the same ordering. Otherwise the mechanism doesn't transfer to this book — KILL.
2. **Gate H (held-out 2024–2026, trial book):** the fixed-$80 book curve with the 0.5× ranging multiplier must improve **return/maxDD by ≥10%** over baseline. Below that — KILL.
3. **Prop-sim deploy check (only if M+H pass):** joint bootstrap re-run with per-trade multipliers on R. Deploy iff **P(breach) falls AND P(challenge 10%) drops ≤ 2 points absolute** — the rule trades speed for survival and must not materially cost pass odds.

**Artifacts:** `regime_sizing_study.py` (committed this time — the exit study's no-git operator constraint does not apply), sidecar `regimeflag_<slot>.csv` per stream, tables below this registration after the run. Deployment (if reached) = `regime_mult` at the bot's single sizing call site + tests + prop-sim/audit refresh + WMI restart.

## VERDICT (same day): entry-time regime sizing KILLED at both gates — the exit-study reopen bar is now fully closed

Run per registration (ab18f69), no constants touched, `regime_sizing_study.py` + `regimeflag_<slot>.csv` sidecars committed.

- **Gate M FAIL, and not marginally — the ordering INVERTS on the deploy evidence.** Book pooled design window: ranging entries **+0.153R** vs trending **+0.063R** (gap −0.090R against a required +0.05R). The fleet corroboration set kept the expected ordering (+0.104R vs +0.144R), which is precisely the point: the leg-exhaustion regime penalty was a property of fleet FX M30 trend entries, and it does not exist on the gold/index pullback + ORB book. Worse, per-slot orderings flip sign between windows (xau: design ranging +0.28/trending −0.13; held-out ranging +0.05/trending +0.50) — a dial that flips sign across windows cannot size anything.
- **Gate H FAIL:** held-out fixed-$80 book curve ret/maxDD 11.91 → 12.05 with the multiplier — **+1.2%** vs the required +10%. (Design window it actively hurts: 2.68 → 2.19.) The net cost of the rule held-out: −$3,293 of return bought −$303 of drawdown.
- **Disposition:** failure_db entry 45 (`regime_sizing_entry_time_2026_07`, `regime-non-transfer`). No bot change; prop-sim check never reached. **The exit-rule study's reopen bar is closed at both ends: path-based exits dead (42–43), entry-time regime sizing dead (45). Fire-and-forget at fixed fractional risk stands as this book's complete, tested trade-management answer.**

---

# 2026-07-09 — REGISTRATION: Diversification Campaign 2 (new mechanism classes + strategy-intake triage) — committed BEFORE any results

**Why:** the book is 5 trial slots + fleet + spread-2B at P(challenge +10%) ≈ 77%; each additional UNCORRELATED mechanism class raises pass odds. The kill map (45 entries) leaves specific open lanes; everything below is either a genuinely new mechanism class on a cost-viable venue or an explicitly registered reopen bar. Trial expires ~07-22 — validations target the paid challenge book and the personal account; trial deployment is a bonus, not the goal.

**Standing gates apply to every track** (Gate-1 data → Gate-2 2023 quick-check + full-window passport w/ ex-best-year box → cost gate with REAL commission AND financing → overlap → trailing pre-check → prop-sim). Kill criteria per cell are the grid-cell standards verbatim: quick-check kills on expectancy negative OR n<20 OR median stop < 10× spread.

## Track A — Opening-gap dynamics, US indices (new class: auction imbalance). US500/US100/US30, Phase A depth, $0 commission, real .sim spreads (SPX 5.0 / NQ 18.0 / US30 = measure at registration of the cell). ONE structural rule, chosen not tuned: gap opening INSIDE the prior RTH day's range → fade toward prior close (target prior close, stop the gap extreme's far side = opening price ± the gap size, i.e., symmetric risk); gap opening OUTSIDE the prior range → continuation, ORB-style stop/2×TP. No numeric gap thresholds — the prior day's range IS the classifier. Session boundaries: 09:30/16:00 ET via the ORB core's `_us_dst_offset` machinery. **Honesty note, pre-stated:** the fade arm is mean-reversion-adjacent; it clears the raised MR bar (new mechanism class AND new asset class simultaneously) because auction-imbalance-at-the-open is not level-fading and the venue/asset class (US index CFDs) is not FX/XAU where the 8 deaths occurred. A fail on the fade arm counts toward the MR ledger.

## Track B — Volatility-compression breakout, XAUUSD + US500 (new class: volatility cycle). Trigger: prior D1 bar is an inside day OR the narrowest range of the last 5 days (structural, no parameters); entry on M30 close beyond that compression bar's high/low; stop at its opposite extreme; TP 2.5R (house convention). Pre-stated distinction: Donchian = fixed-lookback channel (no vol conditioning), ORB = clock-anchored; this = volatility-STATE-conditioned. A fail closes the volatility-cycle class, not "breakouts."

## Track C — Overnight index drift (new class: session risk premium) — financing read FIRST. The commission lesson generalized: overnight designs die on swap, never spread. Gate-0-cost: read swap_long/swap_short + swap mode off the .sim index symbols and compute per-night drag BEFORE any backtest. Only if financing leaves the documented overnight premium alive does a US500 16:00→09:30 ET hold get tested.

## Track D — Liquidity-trough reopen, AUD_USD/NZD_USD (registered bar, PERSONAL account). Bar verbatim from failure_db: "cross-pair tradeable residual after real spread cost, with reversion measured from an EXECUTABLE entry (not the window extreme), clearing cost on AUD_USD or NZD_USD." Design: entry at the first bar open after the trough-window signal; OANDA spread model; `account_feasibility.py` adjudication. Not an FTMO candidate.

## Track E — STANDING PROTOCOL: strategy-intake triage. Any externally-sourced strategy (video, article, forum) is triaged, not researched: (1) map to mechanism class; (2) failure_db + closed-line lookup; (3) verdict — dead-class (cite the entry), open-lane (register as a track), or already-live-equivalent. The 45-entry kill map is the asset; triage is a lookup that costs minutes. Adopted as of this registration.

**Shelf notes (no new research):** grid cell 5 (trend-origin D/H4, benched on prop-shape not edge) queued for a PERSONAL-account re-adjudication; orb_nq remains the pre-adjudicated ospx swap; touch variants stay benched pending live slippage.

**Execution order:** A (with C's financing read same-day) → B → D. Kills → failure_db with controlled tags. Survivors → overlap rows, pre-check, prop-sim if book-touching. Deployment decisions operator-gated. Audit + push at each track boundary.

## CAMPAIGN 2 — TRACKS A + C VERDICTS (same day): both KILLED at the cheapest possible stage

**Track A (opening gap, indices): KILLED, all 6 cells at the 2023 quick-check.** Expectancy negative in every cell and BOTH arms — SPX cont −$33.87/tr (n=102) / fade −$20.51 (n=142); NQ −$25.99/−$41.91; YM −$27.74/−$26.61. Fading in-range gaps and chasing out-of-range gaps lose simultaneously, so the prior-day-range gap classifier carries no directional information at this venue/resolution. SPX median stops (9.05–9.50) sit at ~2× spread — spread-hostile on top of edgeless. The fade arm's death is logged against the MR ledger (ninth): the raised bar (new mechanism class AND new asset class) was met and the class still failed. failure_db 46. No full-window run (stage-1 kill is decisive by the grid criteria).

**Track C (overnight index drift): financing read PASSED Gate 0, then KILLED on the windfall box.** .sim financing is INTEREST_CURRENT: long US500 −2.53%/yr (≈1.0bp/night), US100 −6.07, US30 −6.16 (shorts on US100/US30 are PAID +1.07/+1.16). The raw premium is real (+2.5 to +4.1 bp/night) and survives costs on SPX/NQ (+0.53/+0.70 bp/night net) — but **ex-best-year is negative on all three** (SPX −1,144bp, NQ −1,290bp, YM −1,884bp): 2024 carries everything, 2022 is deeply negative, and the risk shape is unstoppable gap risk (worst nights −398 to −535bp, p1 −168 to −261bp — daily-line poison at any meaningful size). failure_db 47. The generalized commission lesson worked as designed: the financing read cost one query, the kill one measurement pass, zero strategy code.

Artifacts: `gapline_killtest.py` (both tracks; deterministic rerun off Phase A data). Caution noted: US30.sim spread snapshot read 4.0 price units vs the registered 2.0 median — irrelevant to these kills (YM lost at 2.0; wider spread only worsens), but re-measure before any future US30 cell.

## CAMPAIGN 2 — TRACK B VERDICT: volatility-compression breakout — SPX KILLED at quick-check; **XAUUSD PASSES the full passport → VALIDATED, deployment operator-gated**

- **SPX: KILL** at the 2023 quick-check (−$11.20/tr, n=44); full window run only as context (−$0.38/tr, ex-best −$704) — the stage-1 kill stands on its own.
- **XAUUSD: PASS.** Full window 2022-01→2026-07: n=136, net **+$2,682**, exp **+$19.72/tr**, WR 36.0% at 2.5R, median stop 21.99 vs 2.5 floor. Yearly −510/+825/+1,172/+1,437/−242; **ex-best-year +$1,245** ✓ (no windfall). Commission arithmetic: gold ~$5 RT/lot ≈ 0.05 price units → total cost 0.30 ≈ 1.4% of median stop — immaterial (pending the standing first-fill confirm).
- **Overlap (adjudicating lifts, common-span both-ways):** vs xau_pullback **1.31×** — top of the 1.2–1.3 cluster benchmark, below the 1.44× that benched orb_nq; vs orb_xau **1.06×**, orb_spx 1.09×, spx_pullback 1.12×, fleet ≤1.16×, spread2b ~1.0×. Read: one genuinely new bet that shares the gold-trend factor with the pullback slot at cluster-boundary strength. Row added to `factor_overlap.py`.
- **Pre-check (trade-level; marks-level bound required before any deployment):** 0.5% compounding maxDD **−5.7%** (0.25%: −2.9%) — inside the book profile.
- **Prop-sim what-if (variant run, `book_prop_sim.py` untouched):** book+volcomp at 0.5% → challenge **76.5%→79.0%** (breach 13.3%→12.3%), trial 13d **41.9%→44.4%**; haircut-50 challenge 60.1%→61.3% with breach 35.6%→26.0%. Improves both axes at both haircuts.
- **Disposition: VALIDATED — first survivor of Campaign 2 and the first new mechanism class validated since ORB.** Registered distinction upheld: the volatility-STATE trigger passed where fixed-lookback channel (donchian) and clock-anchored (ORB SPX) variants on the same instruments failed or benched. Deployment to the trial book (needs a `volcomp` plugin for the bot + marks-level pre-check) is an operator decision; primary target is the paid challenge book. Artifacts: `volcomp_killtest.py`, `volcomp_XAUUSD_full.csv`.

## CAMPAIGN 2 — TRACK D VERDICT: liquidity-trough reopen attempt FAILS — the bar is unmet, the line stays closed

Executable redesign per registration: signal read at window END (17:00–19:00 ET, N× median-M5-range grid), entry at the first 19:00 ET bar OPEN (real quoted spread there: 1.37–1.85 pips — the rollover spike fully normalized), exit 20:55 ET, 24 months M5 MBA, Mon–Thu. **Net per event NEGATIVE in all 9 cells** (pairs × N grid): AUD_USD −0.49/−1.06/−1.73 pips, NZD_USD −1.51/−1.80/−0.51, and decisively the USD_JPY reference — which cleared 1.55× measured from the window extreme — is **−1.75/−3.19/−2.51** from an executable entry. The reversion the 2026-07-03 triage measured lives entirely inside the untradeable spike: by the first executable moment, it has already happened. The original caveat ("the extreme-entry generosity is the number's weakest link") is confirmed as the whole story. failure_db 48. **This also retires the USD_JPY-only residual as a fleet question — it does not survive executability either.**

## CAMPAIGN 2 — CLOSE-OUT SCOREBOARD (registered 9d510ee, all verdicts same day)

| Track | Class | Verdict |
|---|---|---|
| A opening gap (SPX/NQ/YM × fade/cont) | auction imbalance | KILLED, 6/6 cells at quick-check (failure_db 46; fade arm = 9th MR death) |
| B vol-compression breakout | volatility cycle | SPX killed; **XAUUSD VALIDATED** (first new class since ORB) — deployment operator-gated |
| C overnight index drift | session risk premium | KILLED on the windfall box after the financing read passed (failure_db 47) |
| D liquidity-trough reopen | liquidity calendar | reopen bar UNMET, line stays closed (failure_db 48) |
| E strategy-intake triage | protocol | ADOPTED (standing) |

failure_db now 48 entries. The book's odds if volcomp_xau deploys at 0.5%: challenge 79.0% (breach 12.3%), trial-13d 44.4%; robustness improves at haircut-50 (breach 35.6%→26.0%).

## DEPLOYMENT REGISTRATION (operator-approved): `vxau` slot — volatility-compression breakout, XAUUSD.sim, 6th trial slot

Operator: "lets deploy it just so we start getting some information on it." Forward information is the stated goal; at ~2.7 trades/month the trial-window sample will be small — the record accrues primarily for the paid-challenge decision.

**Registered mechanics (committed before armed relaunch):**
- Signal: `volcomp_plugin.py`, mechanism EXACTLY as killtested — last completed server day inside OR NR5 → first M30 close of the next day beyond that day's range enters; SL at its opposite extreme; TP 2.5R; fire-and-forget. Re-entry guard: one signal per compression day; a missed break (earlier bar today already beyond the range — e.g. bot down or slot occupied) marks the day spent, never chases.
- Slot: `vxau`, XAUUSD.sim, 0.5% (marks-bound pre-check −6.19% at 0.5% — `proceed` under the registered sizing rule), magic 20260715, M30 cadence, per-slot instance, magic-filtered cap. Three slots now share XAUUSD.sim (xau/oxau/vxau) — the magic-filtered caps are the isolation.
- Guards unchanged: daily −$2,000 halt, $93,000 floor, aggregate cap 4 (six slots contend for four positions — unchanged from the six-slot btc-era book; worst-case concurrent exposure 4 × 0.5% = 2.0% initial risk).
- **Structural notes, accepted and recorded:** validated record used Phase A fixed-UTC+2 day boundaries; the live plugin resamples the bot's .sim M30 frames to EET-DST server days (1h apart in summer — same accepted class as the xau slot). Bot M30 fetch (400 bars ≈ 8–9 trading days) comfortably covers the plugin's 7-day requirement. Gold commission (~$2.50/side assumed) still awaiting first-fill confirmation — now likelier to arrive sooner with three gold slots.
- Tests: 16/16 (volcomp seam tests added: breaking-close signal with killtest SL/TP levels, re-entry guard, no-compression / missed-break / short-history flats).
- Prop-sim (standing trigger, 6-slot book committed): challenge **79.0%** target / 12.3% breach; trial-13d **44.4%** / 0.8% breach; haircut-50: 61.9% / 26.1%.

**Protocol:** this registration committed → dry-run cycle clean → armed WMI relaunch → native verification past the next boundary → observation-log entry.

## TRACK E TRIAGE #1 (2026-07-09): TJR TikTok liquidity-sweep sequence — DEAD CLASS, not opened

Source: tiktok.com/@tjr/video/7660190438770461966 (18s, narration-only; transcribed via the new video pipeline, tools/watch_video.py in the workspace). Rules as stated: HTF liquidity sweep → M5 break-of-structure or inverse-FVG (reversal direction) → wait for an M1 BOS *against* the target (pullback) → M1 BOS or IFVG toward the target → execute, TP at "other draws on liquidity."

Mechanism-class mapping: this is a **liquidity-sweep FADE with structure confirmation** (the confirmation stack — M5/M1 BOS + IFVG — is confirmation dressing, not a mechanism). Direct failure_db hits: `sweep_fade_1` (−$559/68 on a mapped ranging stretch), `sweep_fade_2_reentry` (8.9% WR, −$2,872/56; combined −$8,421), `ergated_sweep_c6` (trend leak 0–12% WR even ER-gated — closed the FX MR line), plus the IFVG component = `grid_cell1_fvg` (windfall: one 2023 short cluster was the whole net). The MR ledger stands at nine deaths; the standing reopen bar ("new mechanism class AND new asset class simultaneously") explicitly blocks re-testing sweep-fades on any venue, and today's gapline fade arm already spent the new-class-AND-new-asset attempt for auction-imbalance fades. Sub-M5 execution adds the timeframe-grid spread lesson (M5 donchian died at −$4.75/trade on stops ~14 pips; M1 structure stops are smaller still). **Verdict: dead class — not opened, no research spent.** Honest note: the only adjacent thing that survives in this shop is session-momentum (ORB), which trades WITH the post-open move rather than fading swept levels.

## TRACK E TRIAGE #2 (2026-07-09): "9am CR Model" (tiktok @massimotsr) — DEAD CLASS, not opened

Rules (transcribed + chart frames): mark the 9:00 AM candle's high/low; a sweep of the 9am high → short via inverse-FVG entry, target the 9am low; sweep of the 9am low → long via IFVG, target the 9am high. Mechanism class: **clock-anchored range sweep-fade with an FVG trigger** — a level-specific re-skin of triage #1. Direct failure_db hits: the sweep-fade family (`sweep_fade_1`, `sweep_fade_2_reentry`, `ergated_sweep_c6`), `session_fade` (fade of a failed clock-range breakout toward the range — the same trade shape on the Asian range: 20.3% WR vs 29.7% BE, −$1,858/64), and `grid_cell1_fvg` for the IFVG trigger (windfall). MR ledger nine deaths; raised reopen bar (new mechanism AND new asset class) blocks. Note the house contrast: the validated ORB slots trade the 09:30 range in the BREAKOUT direction; this model fades false breaks of the 09:00 candle against the move — the losing side of the same session structure by this shop's own measurements. **Verdict: dead class — not opened.**

---

# 2026-07-09 — REGISTRATION: Campaign 3 (fast/medium untested classes, H4-and-down) — committed BEFORE any results

**Operator scope constraint, recorded:** H4 timeframe and down, no swing trading — holds of hours to a few days. Three otherwise-open lanes are **out-of-scope by operator constraint, not research verdicts** (slow TSM, turn-of-month, COT extremes — all multi-night/multi-week holds; no failure_db entries, available if the constraint changes).

## Track A — Intraday cross-sectional index momentum (new class: relative strength, day-neutral). Each US trading day at 09:30 ET: rank SPX/NQ/YM by trailing 20-trading-day return (20 = house convention, no free parameter). Long the top, short the bottom, from the 09:30 M30 open; exit both at the 16:00 ET close; protective stop 1× ATR(20d) from entry (box-9 applies normally). Flat overnight — zero financing, zero gap risk. Each leg one recorded trade, 1R = $80 on ATR(20d). Costs: registered .sim spreads (SPX 0.5 / NQ 1.8 / YM 2.0), $0 commission. Distinction pre-stated: nothing in the roster trades RELATIVE strength; the dead stat-arb line is the reverting cousin (its reopen bar untouched). Gates: 2023 quick-check (grid criteria verbatim) → full-window passport → overlap (esp. vs spx_pullback/ospx) → prop-sim what-if.

## Track B — Line C continuation: sub-M30 rungs of VALIDATED mechanisms on gold/indices, 3 cells. Plugins unmodified at mode scalp (H1 confirm / M15 trigger, the existing rung convention): (1) XAUUSD × trend-origin pullback M15; (2) US500 × trend-origin pullback M15; (3) XAUUSD × donchian M15. **Prior stated: rung transfer is what grid cells 1–4 died on; favorable M30 context predicts nothing. Cell 3 is the long shot (donchian 0-for-5 non-FX).** Quick-check 2023 per cell → full window for survivors. Box-9 is the live threat at M15 stop scale. Two-source convention (Phase A depth, real .sim spread constants) per the Phase 0 registration.

## Track C — London-open ORB on XAUUSD (ORB family extension, M15). Identical close-variant mechanics, conventions unmodified: OR = 08:00–08:30 **London time** (UK statutory DST rule: last Sunday March 01:00 UTC → last Sunday October 01:00 UTC — implemented beside the US rule, 4 boundary dates hand-verified before results count), M15-close entry, opposite-extreme stop, 2× OR-height TP, 10× spread floor, one trade/(session,direction), fire-and-forget. **Pre-adjudicated bench threshold: weekly co-loss lift ≥ 1.35× vs the live oxau → BENCH regardless of passport** (the orb_nq precedent, stated before the run).

**Execution:** A → B → C; kills to failure_db with controlled tags; survivors get the volcomp-grade package (passport, both-ways lifts, marks-bound DD, prop-sim what-if; book_prop_sim untouched until a deployment decision). Deployment is a separate operator-gated unit (Track A would need paired-entry + timed-exit bot support; B/C fit the existing M15 slot machinery). Audit + push at track boundaries.

## CAMPAIGN 3 — TRACK A VERDICT: intraday cross-sectional index momentum KILLED at the 2023 quick-check

Combined stream (the registered construction): n=342, **−$1.54/trade** → KILL by the grid criterion. Decomposition: long leg +$2.21/tr, short leg **−$5.30/tr** — the US index family is too cointegrated at day horizon for a 20d ranking to carry relative information, and the short leg fights the shared drift it was supposed to hedge. **Honesty note (adjacent, not pursued):** the positive long leg alone would be a post-hoc amputation of a failed design — not a candidate without its own registration, and tainted by this observation. failure_db 49. Cross-sectional momentum class closed at this venue/horizon.

## STANDING WATCH ITEM RESOLVED (2026-07-09 evening): gold commission read off the first live fill

xau slot filled 0.06 lots XAUUSD.sim long @ 4127.34; commission −$0.17 = **$2.83/side/lot ≈ 5.7 pips-equiv RT** (assumed ~$2.50/side / ~5 pips). Every gold cost gate carried ≥7 pips of headroom over the commission-free assumption (37 assumed at Gate 2 vs ~30.6 true all-in) — **all gold validations stand as adjudicated.** The commission-lesson ledger is now fully verified across the book's asset classes: FX $2.50/side (measured), indices $0 (measured), gold $2.83/side (measured), crypto $20.57/side (measured, class dead).

## TRACK E TRIAGE #3 (2026-07-09, batch): operator's 13-idea list — one open lane, twelve closed

Verdicts against the kill map (full reasoning in session; one line each): (1) vol-risk-premium — no options/VIX instrument on any venue, NOT VIABLE; (2) GARCH-timed vol-cycle entries — already-live-equivalent (volcomp is the structural version; estimator upgrade on a validated design = retune); (3) overnight/intraday split — tested (failure_db 47 + the book IS the intraday segment); (4) round-number clustering — dead-class expressions (MR fade / level breakout); (5) spread-widening filter — historical spread data proven untrustworthy + overlay class; (6) **currency-strength divergence — OPEN: cross-sectional momentum on 8-currency composites, registrable with the index-kill distinction pre-stated (indices = one factor + shared drift; FX cross-section = neither); target PERSONAL OANDA account**; (7) commodity-currency reconvergence — stat-arb class, reopen bar unmet; (8) yield-curve regime filter — overlay class + no data; (9) prior-period-extreme anchoring — collapses to dead classes; (10) weekend gap split — covered by failure_db 46 (Mondays included; a Monday-only slice = post-hoc); (11) news NLP — no historical corpus, not viable; (12) Kalman hedge ratios — same time-varying-beta family the new-universe line already killed, bar unmet; (13) entropy/autocorrelation gating — regime-overlay class (the sign-flip disease is estimator-independent).

**Post-Campaign-3 queue (operator-agreed): (1) IB-width ORB variant cell (pre-adjudicated swap/bench vs live ORB slots); (2) currency-strength divergence, personal account; (3) HMM regime-TRANSITION trades (fixed hyperparameters, walk-forward, lowest prior given 4 regime-overlay deaths).**

## TRACK E TRIAGE #4 (2026-07-09, batch): operator's second 9-idea list — zero open lanes

(1) session-open stop-hunt fade — sweep-fade family + failure_db 48 (dislocation reverts inside the untradeable window); (2) rate-differential momentum — no OIS/STIR data + swing scope; (3) options skew/risk reversals — no options data on any venue; (4) risk-on/off basket rotation — no bond/credit data + regime-overlay class + swing; (5) k-means/DBSCAN states — regime estimator variant (sign-flip disease is estimator-independent); transition-trade salvage already queued under HMM; (6) reaction-weighted fib — fib dead + circular in-sample weighting, methodologically forbidden; (7) order blocks — killed by name (`order_blocks`, min-N starvation); (8) ARIMA pre-filter — overlay class; (9) CB tone-shift scoring — data obtainable but ~8 events/yr/bank = min-N starvation + days-to-weeks drift horizon (swing scope). Standing pattern note: triage failures cluster as conditioning dials / data-not-on-venue / already-buried entry patterns; survivors are standalone return streams on available data.

## TRACK E TRIAGE #5 (2026-07-09, batch): operator's third 9-idea list (macro-flavored) — zero open lanes

(1) economic-surprise momentum — no consensus-history data + swing; (2) real yield differentials — no TIPS/breakeven data + swing; (3) CB balance-sheet flows — public data but weeks-scale liquidity regime = overlay + swing; (4) ETF AP flows — data inaccessible from retail stack; (5) Google Trends — unbounded term-selection tuning surface + granularity too coarse; (6) freight/BDI lead-lag — no feed + swing + stat-arb-adjacent; (7) political/fiscal seasonality — single-digit events = min-N; (8) holiday thin-liquidity windows — liquidity-calendar class + ~2 events/yr + avoidance-filter form closed by the session-of-day ruling; (9) correlation-breakdown reversion — generalized spread reversion; the new-universe study measured the non-reversion directly; bar unmet. Operator handed the 4-question pre-screen (data-on-venue / standalone-stream / hours-to-days & n>=100 / not-a-fade-in-disguise). Day tally: 33 external ideas triaged, 1 open lane (currency-strength divergence).

## TRACK E TRIAGE #6 (2026-07-09, batch): operator's fourth list (price/volume-native) — one conditional open lane

(1) tick-delta divergence — tick-history depth weeks-months vs 4y windows, not viable (+ exhaustion-fade adjacency); (2) calibrated wick rejection — statistically-dressed pin-bar fade, MR class + tuning-on-record; (3) streak reversion — MR class; (4) hour-bucket trend/reversion classification — session-of-day question formally closed + 24-bucket mining; (5) rolling VWAP z-score fade — killed by name (avwap_fade #7/#8); (7) prior-bar midpoint filter — overlay at an arbitrary level; (8) bar-count time symmetry — no statable mechanism, fails Gate 0; (9) CLV persistence — short-lookback momentum trigger, expected redundancy with the live trend cluster (bench-expected cell, not opened). **(6) triple-swap Wednesday rollover positioning — CONDITIONALLY OPEN, measurement-first: do Wednesday pre-rollover session-hours returns on swap-extreme pairs differ from the same hours other weekdays? Lives BEFORE the rollover window, dodging the liquidity-trough kill by construction; OANDA price data only; n≈200+/window; low prior, registrable.** Queue now: IB-width ORB cell → currency-strength divergence → Wednesday swap-flow measurement → HMM transitions. Day tally: 42 ideas triaged, 2 open lanes.

## CAMPAIGN 3 — TRACKS B + C VERDICTS AND CLOSE-OUT

**Track B (M15 rungs), full-window adjudication:**
- **spx_pullback_m15: KILLED on the windfall box** — the clear 2023 quick-check (+$11.11/tr) WAS the windfall: full window +$0.09/tr, ex-best-year **−$7,781**, 2024/25/26 all negative. The rung-transfer warning fires with a new face: a quick-check can pass because the quick-check year is the outlier year; the passport caught it. failure_db 50.
- **xau_pullback_m15: PASSES the passport** (n=3,529, +$5.96/tr, ex-best +$5,040) — **VALIDATED-BUT-BENCHED.** 92% shared trading days with the live xau M30 slot (same mechanism, nested rung — the BTC-M15 precedent verbatim: a swap for trade-frequency, never both).
- **xau_donchian_m15: PASSES the passport** (n=4,249, +$5.45/tr, ex-best +$4,856 — donchian's first non-FX survival, at the rung below where its M30 sibling failed) — **VALIDATED-BUT-BENCHED on gold-factor concentration.** 81% same-direction days with the live xau slot; 90-98% shared days across the gold cluster.
- **The prop-sim adjudicated the bench decisively:** adding either cell at 0.5% to the 6-slot book CRASHES challenge odds — pb_m15: P(+10%) 79.0%→66.8%, breach 12.3%→**32.9%**; don_m15: 79.0%→59.3%, breach →**40.6%** (0.25%: still 23.6% breach). The joint weekly bootstrap prices what the direction-agreement numbers show: a 4th gold-coupled stream is a size-up on one factor, and FTMO's account-level loss lines punish exactly that. Trial-13d P rises (more shots short-term) — the challenge book is the deployment target and it says no.
- Overlap rows added (`xau_pb_m15`, `xau_don_m15`); artifacts: linec2_*.csv.

**Track C (London ORB, XAUUSD): KILLED** — both stretches negative (A2023 −$1,067 / B24H2 −$493, WR ~40% vs 2×-height targets). Session-momentum is a property of the US equity open, not of session opens generally. UK DST clock hand-verified 8/8 before the run. failure_db 51.

**CAMPAIGN 3 SCOREBOARD (registration c1dd8c2, all same-day):** A xsmom KILLED (49) · B: spx-M15 KILLED (50), xau-pb-M15 + xau-don-M15 VALIDATED-BUT-BENCHED (prop-sim concentration adjudication) · C London-ORB KILLED (51). failure_db at 51. The live book is UNCHANGED at 6 slots — the campaign's product is two benched gold M15 passports (swap candidates if any live gold slot retires) and three clean class closures. Next in queue: IB-width ORB variant cell, currency-strength divergence (personal acct), Wednesday swap-flow measurement, HMM transitions.

## TRACK E TRIAGE #7 (2026-07-09, batch): operator's fifth list — zero open lanes; convergence note

(1) S/R test-count decay — breakout-timing dial (fade form = MR grave); (2) fractal swing-count exhaustion — streak MR at swing granularity; (3) MA slope-persistence filter — dial + calibrate-on-record; (4) cumulative range expansion — volatility-cycle re-skin of live volcomp (tunable threshold vs structural trigger); (5) multi-TF pivot confluence — level-reaction + confluence dressing; (6) skew/kurtosis regime filter — regime-overlay estimator #6; (7) swap-rate trend signal — the near-miss: venue-unique field but NO historical swap series exists to backtest, + carry horizon = swing; (8) N-bar positional z-score — donchian with a soft threshold (momentum form) / MR (fade form); (9) inside-bar sequencing — volcomp's own trigger at bar granularity, shelf-noted as family variant. **Convergence note: external idea-streams are now independently re-deriving the book's three validated classes (ORB/donchian/volcomp) — the remaining untested space is venues, sessions, and cross-sectional constructions, not candle logic.** Day tally: 51 ideas triaged, 2 open lanes.

## TRACK E TRIAGE #8 (2026-07-09, batch): sessions/cross-sections/venues list — zero open lanes; session dimension now fully mapped

(1) overlap calibration — session-of-day question closed + live ORB already trades the overlap start; (2) Asian-compression London breakout — retune of killed london_breakout (magnitude form = dial); (3) NY->Asian handoff — signal window = the rollover trough, dead on execution (fdb 48 territory); (4) multi-session state machine — combinatorial regime overlay; (5) currency-cluster lead-lag — triangular arbitrage welds shared-leg pairs at sub-bar timescales, mechanism implausible at venue latency; (6) beta-adjusted cluster spreads — the adaptive-beta estimator already failed the stat-arb bar; (7) basket dispersion reversion — fade-side mirror of the QUEUED strength-divergence study (reversion form blocked; the queued momentum study will report dispersion stats as context); (8) cross-venue quote lead-lag — unreachable at retail latency AND latency arbitrage = FTMO-prohibited practice, do-not-touch on prop accounts; (9) cross-broker spread differential — no historical spread data + dial. **Map note: the session dimension is closed — US open validated, London open killed, Asian open execution-toxic, overlap = live ORB, handoffs untradeable.** Day tally: 60 ideas triaged, 2 open lanes.

## TRACK E TRIAGE #9 (2026-07-09, batch): sessions/cross-sections/venues list 2 — ONE open lane (London 4pm fix flow)

(1) session vol rotation / (3) class rotation / (8) tick-volume divergence — dials; (4) home-session global XSMOM — non-US indices excluded at Gate 1, collapses to killed fdb-49 cell; (5) bloc rotation — coarser cut of the queued strength study + session dial; (6) tz-weighted strength — weighting variant of the queued study, not opened (parameter surface before the flat version runs); (7) index rebalance flow — 4-8 events/yr = min-N; (9) cross-broker swap divergence — no historical swap series. **(2) WM/Reuters London 4pm fix flow — CONDITIONALLY OPEN, measurement-first: documented institutional benchmark flow at a public clock time sitting at 11:00 NY = the LIQUID window (cleanly distinct from the trough kill's illiquid-window lesson); OANDA M5, ~250 events/yr, minutes-hours scale. Only the flow-drift arm is registrable (post-fix reversal = MR-shaped, bar applies). Prior low-moderate (post-2013 reforms shrank fix effects).** Queue: IB-width ORB → strength divergence → Wednesday swap-flow → London-fix measurement → HMM transitions. Day tally: 69 ideas triaged, 3 open lanes.

## TRACK E TRIAGE #10: DST-desync weeks + single-country holiday thinness — both closed; the signed-flow criterion articulated

(1) DST transition desync — no signed mechanism (miscalibrated fixed-clock algos are noisier, not directional), ~9 windows in-depth = min-N; filter form = dial. Real value is OPERATIONAL and already banked: US statutory rule (ORB core), UK rule (London plugin, 8 boundary dates hand-verified), piecewise-EET data seam — the desync weeks are exactly what those were built for. (2) Single-country holiday partial liquidity — workable n but thinness is UNSIGNED; all expressions land on dead shelves (avoid=dial, fade=MR bar, condition=overlay). **Standing triage criterion, distilled from the calendar-idea record: a calendar/liquidity idea is registrable only if some participant is FORCED to trade in a KNOWABLE direction at that time (fix flows, rebalance flows, swap-date positioning have a payer; thinness/desync/overlap conditions do not).** Tally: 71 ideas, 3 open lanes.

---

# 2026-07-10 — REGISTRATION: Campaign 4 (the triage-sourced queue) — committed BEFORE any results

Tracks in operator-agreed order. Standing gates; kills to failure_db; measurement tracks close on their pre-stated criteria without strategy code.

## Track A — IB-width ORB variant (SPX + XAUUSD, M15). Declared a VARIANT COMPARISON of the live ORB slots, never a parallel deployment: OR = 09:30–10:30 ET (four M15 bars) instead of the live 09:30–10:00; signal window 10:30–15:30 ET; all other conventions verbatim from `orb_plugin_core` (close entry, opposite-extreme stop, TP 2× OR height, 10×-spread floor, one trade/(session,direction), fire-and-forget). Line-B kill criteria (both stretches A2023/B24H2 net-positive AND n≥30) → full window. **Pre-adjudicated: regardless of passport, the ONLY possible disposition is swap-candidate-or-bench vs the live width** — expected overlap is near-total; if either passport is materially stronger than the live width's, the operator gets a swap decision, not an addition.

## Track B — Currency-strength divergence (personal OANDA account target). 8 majors (USD/EUR/GBP/JPY/AUD/NZD/CAD/CHF); strength score per currency = flat-weighted mean of its pairs' trailing 20-trading-day returns, sign-adjusted (20 = house convention, flat weights chosen not tuned). Daily at 12:00 UTC (liquid, far from rollover): trade the single tradeable pair pairing the strongest vs weakest currency, direction long-strong/short-weak; exit next day 12:00 UTC; protective stop 1× ATR(20d). Costs: per-pair median quoted spread at the 12:00 UTC hour measured from OANDA MBA candles (12mo sample), + OANDA financing per held night (published rates, small at 1-night holds). Gates: 2023 quick-check (grid criteria) → full window 2021–2026 → `account_feasibility.py` adjudication. Distinction from killed fdb-49 (index XSMOM): 8-currency cross-section with no shared drift; distinction from stat-arb: momentum direction, divergence not reconvergence.

## Track C — Wednesday swap-flow MEASUREMENT (no strategy code unless signed effect found). Pairs pre-stated: AUD_JPY, USD_JPY, EUR_JPY, GBP_JPY (carry-heavy) + EUR_USD (control). Window: 12:00–17:00 ET Wednesday (pre-triple-rollover session hours) vs the same clock window Mon/Tue/Thu. OANDA H1 mids, 2021–2026. Criterion: a signed Wednesday-specific mean return distinct from control days AND control pair, consistent in direction across the carry pairs. No effect → track closed, one log entry.

## Track D — London 4pm fix MEASUREMENT (no strategy code unless signed flow found). Pairs: EUR_USD, GBP_USD, USD_JPY. OANDA M5 MBA 2022–2026. Windows (London clock, UK statutory rule from `orb_london_plugin._uk_dst_offset`, already 8/8 hand-verified): pre-fix 15:30–16:00, post-fix 16:00–16:30, control = the same-length windows at 14:00–14:30/14:30–15:00. Pre-registered breakdown: month-end days (last trading day) vs ordinary days — documented month-end rebalancing flow is the signed-flow candidate. Criteria: |mean signed return| in pre-fix window distinct from controls, and/or post-fix reversal conditional on pre-fix move; month-end split reported in full either way. Only a signed, liquid-window effect can open a design phase; the post-fix-reversal arm alone cannot (MR bar).

## Track E — HMM regime-TRANSITION trades: registered separately if and when reached (fixed hyperparameters + walk-forward mandatory; lowest prior — 4 regime-overlay deaths stand).

Execution: A runs on Phase A MT5; B/C/D run on OANDA REST and proceed in parallel with A's compute. Audit + push at track boundaries.

## CAMPAIGN 4 — TRACKS A, C, D VERDICTS (same day as registration)

**Track A (IB-width ORB variant): KILLED** — SPX fails A2023 (−$734), XAU fails B24H2 (−$889); each instrument fails one stretch where the live 30-minute width passed both on both. The deployed OR width is vindicated by direct comparison; OR-width is now a measured constant. failure_db 52.

**Track C (Wednesday swap-flow): CLOSED, no effect** — the 12:00–17:00 ET drift in yen crosses is positive on EVERY weekday (Wednesday t-stats weaker than Monday's; EUR_USD control flat) — it is the known 2021–26 yen-trend factor, not rollover positioning. No signed Wednesday-specific effect exists. One script, no strategy code built.

**Track D (London 4pm fix): ordinary days NULL; MONTH-END EFFECT CONFIRMED — design phase OPENED.** Ordinary days: pre-fix signed returns ≈ 0, activity ≈ controls. Month-end (last trading day, n=48/pair): pre-fix activity ~2× controls (|ret| 15–20p vs 8–12p) and a consistent cross-pair signed story — GBP +6.9p (t+1.9), EUR +2.4p, USD_JPY −6.2p (t−1.8) = **USD sold into the month-end fix**, with partial post-fix reversal. Pre-registered pooled statistic (all three pairs as USD-direction, normalized by ordinary-day vol): **n=144, t=+2.72**. Per the registered criterion (signed, liquid-window effect) the flow-drift arm opens a design phase — own registration to follow (last-trading-day 15:30→16:00 London, long-USD-weakness expression; venue = personal OANDA unless the FTMO FX door reopens; ~12 events/yr/pair, n≥40 floor per the ToM-style substitute rule; the post-fix reversal arm stays closed under the MR bar).

## CAMPAIGN 4 — TRACK B VERDICT + MONTH-END FIX DESIGN ADJUDICATION + CLOSE-OUT

**Track B (currency-strength divergence): KILLED at the quick-check, confirmed full-window** — 2023 −$5.44/tr (n=259); full window −$7.05/tr, WR 43.6%, negative EVERY year (ex-best −$8,069). The widest 20-day strength gap selects the most-stretched carry cross exactly when it snaps back at 1-day horizon. Cross-sectional momentum is now closed at both venues tested (indices intraday fdb-49, FX daily fdb-53) — the failure mode is horizon, not the index-drift confound the registration pre-stated.

**Month-end fix DESIGN (Track D follow-up, constants chosen not tuned):** last trading day, hold the measured 15:30→16:00 London window, equal-weight short-USD basket (long EUR_USD + GBP_USD, short USD_JPY), cost = per-pair median fix-hour spread from MBA. Result: **+3.52p/event net (n=48, t=+1.47), ex-best-year +60p, worst event −31.8p; 2024 negative (−94p).** Passes the registered gate (net-positive, no windfall) — but weakly: the measurement's pooled t=2.72 becomes t=1.47 in the tradeable basket. **Disposition: VALIDATED-WEAK, BENCHED — available as a ~12-event/yr micro-sleeve on the personal account at operator discretion; not a deploy recommendation at this evidence strength.** failure_db 53 (Track B).

**CAMPAIGN 4 SCOREBOARD (registration 1e1d1b1, closed same day):** A IB-width variant KILLED (52 — live OR width vindicated by direct comparison) · B strength divergence KILLED (53) · C Wednesday swap-flow NULL (yen-trend artifact, no strategy code built) · D London fix: ordinary days null, month-end effect CONFIRMED (pooled t=+2.72) → design validated-weak, benched · E HMM transitions NOT REACHED (remains queued; own registration mandatory when picked up). failure_db at 53. Live book unchanged at 6 slots.

## REGISTERED FOLLOW-UP RESOLVED (2026-07-10): session-hours FX tick re-sample — **the FX bar-spread column is VERIFIED; the FTMO FX door REOPENS with a rollover carve-out condition**

Method upgrade over the failed 2026-07-09 sample: full tick stream from the terminal's own history for the 2026-07-09 London/NY overlap (13:00–16:00 UTC), n=8,328/10,230/17,165 ticks. Medians: **EURUSD 0.20 / USDJPY 0.40 / GBPUSD 0.30 pips** (p90 0.30/0.50/0.50) — the bar column (0.1–0.4) is confirmed as real session pricing. The 3.2/11.9/27.5-pip readings were entirely the rollover-hour confound, exactly as the liquidity-trough finding predicted. **Standing condition on any FTMO FX design, pre-stated now: entries and holds must either avoid or explicitly model the 17:00–18:00 ET spike (the no-carve-out convention is amended for this venue-measured hazard, not for signal-shopping).** Commission-inclusive FX cost on FTMO: spread + $2.50/side ≈ 0.7–1.0 pips-equiv RT on majors — cheap. Unlocked and now OPENABLE with own registrations: the Phase-0-flagged EURUSD/USDJPY sub-M30 rungs; FX cells for validated mechanisms on the .sim venue.

---

# 2026-07-10 — REGISTRATION: HMM regime-TRANSITION trades (Campaign 4 Track E, picked up) — committed BEFORE any results

**The one registrable HMM form** (per the standing triage: regime CONDITIONING is dead 4× over; the TRANSITION as a standalone event is the untested class). All hyperparameters FIXED here, none tunable after results:

- **Model:** 2-state Gaussian HMM (`hmmlearn.GaussianHMM`, `n_components=2`, `covariance_type="full"`, `random_state=20260710`, `n_iter=100`) on ONE feature: daily log-returns. States sorted by variance (0 = quiet, 1 = turbulent) after each fit.
- **Walk-forward, no lookahead:** refit at each month boundary on the trailing 500 completed trading days; between refits, state inference uses only data through day t (filtered posterior via `predict` on the history prefix — the day-t label never sees day t+1).
- **Transition event:** the argmax state on day t differs from day t−1. Direction (the signed-flow question, answered structurally): **enter next day's open in the SIGN of the transition day's return** — the thesis is that regime flips mark the start of a persistent move, so the flip-day's direction is the move's direction.
- **Exit:** opposite transition OR 5 trading days, whichever first (H4-and-down scope: holds of days, bounded). Protective stop 1× ATR(20d). One position per instrument.
- **Instruments:** XAUUSD + SPX (Phase A D1+M30... daily bars for model and ATR; entries/exits at daily opens from D1 data — execution granularity daily open, costs = registered .sim spreads + gold commission).
- **Gates:** 2023 quick-check (grid criteria: expectancy ≤0 OR n<20 → KILL) → full-window passport (ex-best-year box) → standard gauntlet if passed. **A fail closes the regime-transition class** — the last HMM-shaped door, with regime-conditioning already 4× dead.

## HMM REGIME-TRANSITION VERDICT (same day): KILLED on min-N starvation — the regime shelf is closed at both ends

Honesty note first: the registered 2023 quick-check was **structurally unevaluable** — the registered 500-day walk-forward warmup consumes 2022–2023 of Phase A's D1 depth (XAU data begins 2021-12), a registration/depth conflict discovered at run time and adjudicated on the registered criteria over the evaluable window rather than re-registered. Results: XAUUSD n=17 (< the 20 floor), ex-best-year −$146; SPX n=4, 0% WR. Daily 2-state transitions fire ~8×/yr/instrument — the event rate times the evaluable window lands under min-N before the edge question is even askable, and shortening the fit window to manufacture events would be post-hoc tuning. failure_db 54. **Regime-conditioning: 4 deaths. Regime-transitions: dead on starvation. The regime shelf is fully closed absent a genuinely new data depth.**

---

# 2026-07-10 — REGISTRATION: Campaign 5 — validated mechanisms × FTMO FX (the reopened door) — committed BEFORE any results

**Scope honesty first:** "all strategies vs FX" is mostly already adjudicated — donchian-FX is the live fleet; pullback-FX is the live jpy slot (USD_JPY) plus the CLOSED 8/8-rejected pair-expansion line (not re-run, ever). The genuinely new cells are the two mechanism classes validated after the fleet era, never tested on FX:

## Track A — volcomp × {EUR_USD, USD_JPY, GBP_USD} (M30 execution, OANDA data, FTMO costs)
Mechanism verbatim from the validated gold design (inside-day OR NR5 → first M30 close beyond the compression day's range; opposite-extreme stop; 2.5R TP; fire-and-forget; one signal per compression day). Daily bars = OANDA D candles (17:00 NY alignment — stated, not tuned). **Rollover carve-out (standing condition): signal bars whose ET time falls in [17:00,18:00) are skipped — no entries in the spike; broker-side SL/TP fills crossing the spike are accepted slippage risk, noted.**

## Track B — US-open ORB (close variant) × {EUR_USD, USD_JPY, GBP_USD} (M15, OANDA data, FTMO costs)
Mechanics verbatim from the live index design (`orb_plugin_core`: OR 09:30–10:00 ET, signal to 15:30 ET, opposite-extreme stop, 2× OR TP, 10×-spread floor, one trade/(session,direction)). Session-momentum priors both ways, pre-stated: US-open transferred within equities and to gold but the LONDON open failed on gold — whether the US-open impulse exists in FX is exactly the open question. Line-B criteria (both stretches A2023/B24H2 net-positive AND n≥30) → full window.

**Costs, verified this morning (spread median + $2.50/side commission ≈ 0.5p):** EUR_USD 0.7 / USD_JPY 0.9 / GBP_USD 0.8 pips-equiv RT. Data: OANDA (deep, 2021→). Gates: standing (quick-check → full passport → overlap vs the FULL roster incl. fleet FX rows → prop-sim what-if for any survivor — note the book already carries FX exposure via jpy + the fleet, so overlap vs pullback30/intraday/scalp30 is the decisive lift). Kills → failure_db. Deployment operator-gated as always.

## CAMPAIGN 5 — VERDICTS AND CLOSE-OUT: the reopened FX door is now fully mapped — no new FX slot exists

**Track A (volcomp × FX): ALL THREE KILLED.** USD_JPY (−$4.52/tr) and GBP_USD (−$9.08/tr) at the quick-check; EUR_USD cleared 2023 then failed the passport (full +$0.66/tr, ex-best-year −$460 — 2023 was the record). failure_db 55.
**Track B (US-open ORB × FX): ALL THREE KILLED** at the Line-B stretches — every pair fails at least one (USD_JPY both). failure_db 56. The 09:30 impulse is an equity-auction phenomenon; FX has no auction there.

**The complete FX-on-FTMO answer, one paragraph:** the door reopened and the answer behind it was already on the books. FX belongs to the mechanisms that were born there — donchian (fleet, live) and pullback (USD_JPY only; the live jpy slot) — and neither post-fleet validated class (volcomp, ORB) transfers in. The pair-expansion line stays closed (8/8), the MR bar stands, the M15 FX rungs remain openable but rung-transfer precedent is 1-for-4. **No FX addition to the challenge book exists at current evidence.** failure_db at 56.

---

# 2026-07-10 — REGISTRATION: Campaign 6 — FX-native untested classes (CB drift, session handoff, weekend gap) — committed BEFORE any results

Pairs for all tracks: EUR_USD, USD_JPY, GBP_USD (verified all-in FTMO costs 0.7/0.9/0.8 pips). OANDA data. Kills → failure_db; measurement-first where an execution hazard exists.

## Track A — FOMC announcement drift (event momentum; the signed-flow criterion is met by the release itself). Events: scheduled FOMC decision days 2021-01→2026-06, statement 14:00 ET (2026 dates from the Fed's published schedule — noted). **Step 1, spread-spike measurement:** median MBA spread by 5-min bucket 13:30–16:00 ET on FOMC days — the entry time must sit where spreads have renormalized; the design's 15:00 ET entry is CHOSEN now and the measurement only verifies it is not inside a spike (if 15:00 ET is still spiked, the track closes on execution, not redesign). **Design (constants chosen):** impulse = 14:00→14:55 ET M5 return; direction = its sign; enter 15:00 ET; exit next day 11:00 ET (~20h, holds through rollover — no transaction in the spike, broker-side stop-fill risk noted); stop 1× ATR(20d). Pooled adjudication across pairs (per-bank samples are thin by construction): 2023 quick-check (pooled n≈24 ≥ 20 floor) → full window, ex-best-year box.

## Track B — London→NY session-flow continuation. Signal: London-morning move = 03:00→09:30 ET return (M30); direction = its sign; enter 09:30 ET open; exit 16:00 ET close (day-neutral); stop 1× ATR(20d); one trade/pair/day. The one session handoff that lives entirely in verified-liquid hours. Decisive post-passport check if it survives: overlap vs the fleet FX rows (it must not be the trend factor in disguise). 2023 quick-check → full window.

## Track C — Weekend-gap continuation, Monday-London entry (the executable design; fade arm barred by MR closure). Gap = Sunday-open first M30 open vs Friday last M30 close; direction = gap sign; NO magnitude filter (chosen); enter Monday 03:00 ET open (London, liquid — the Sunday hours are the trough and are not touched); exit Monday 16:00 ET close; stop 1× ATR(20d). ~52 events/yr/pair. 2023 quick-check → full window.

Expectation stated for the record: three clean closures is the base-rate outcome; Track A is the best-documented untested mechanism remaining on these venues.

## CAMPAIGN 6 — VERDICTS AND CLOSE-OUT: two kills, two validated survivors (both benched pending deployment machinery)

**Track A (FOMC drift): VALIDATED-WEAK.** Spread measurement first: FOMC-day 15:00 ET spreads run 1.6–1.9p (~4× session norm, far below rollover toxicity) — the sim was re-adjudicated at these measured event-day costs plus commission, an in-flight cost correction in the BTC-lesson spirit. At honest costs: pooled n=132, **+$6.62/tr**, 2023 quick-check +$6.72, **ex-best-year +$146** (positive but thin — 2025 carries most). Overlap: clean vs the challenge book (0.4–1.2×) but **1.53× vs pullback30** (the jpy slot's record — both are USD-event streams; small-n caution, only 20 losing weeks) and 2.41× vs spread2b (fleet-only). Prop-sim what-if: 79.0%→79.5%, breach ~flat. **Disposition: validated-weak, BENCHED** — ~24 events/yr; deployment needs event-clock bot machinery; candidate for the challenge book at operator discretion.

**Track B (London→NY handoff): ALL THREE KILLED** at the passport — expectancies are pennies and ex-best-year is negative on all three. The handoff question is closed at both ends (Asian-open = execution-dead, liquid-window = merit-dead). failure_db 57.

**Track C (weekend gap): JPY + GBP KILLED (fdb 58); EUR_USD VALIDATED** — n=196, **+$6.57/tr**, ex-best +$685, 5/6 years positive, and **the cleanest overlap profile measured since spread2B: every lift 0.59–1.11× against the entire roster.** Prop-sim: breach 12.3%→11.7% at flat odds. 1-of-3 survival noted as a multiple-comparisons caution. **Disposition: VALIDATED, BENCHED pending deployment machinery** (Monday-clock timed entry/exit — simple but new bot capability); ~50 events/yr; genuine diversifier by construction (Monday-day-window trades).

**CAMPAIGN 6 SCOREBOARD (registration 4e370ab, closed same day):** A FOMC drift validated-weak/benched · B handoff killed ×3 (57) · C weekend gap: EUR validated/benched, JPY+GBP killed (58). failure_db at 58. Book unchanged at 6 slots; the bench now holds: 2 gold M15 passports, month-end fix, FOMC drift, EUR weekend gap — five pre-validated candidates awaiting either a slot vacancy, deployment machinery, or the paid-challenge build-out.

## DEPLOYMENT REGISTRATION (operator-approved): `gap` slot — EUR weekend-gap continuation, 7th trial slot — and the bot's first TIMED-EXIT capability

Operator: deploy the suggested survivor ("it won't hurt" — the prop-sim agrees: breach 12.3%→11.7% at flat odds). FOMC drift stays BENCHED per the same recommendation (weak ex-best + 1.53× pullback30 coupling).

**Registered mechanics (committed before armed relaunch):**
- Signal: `wkndgap_plugin.py` — Monday 03:00–03:30 ET window only (M30 boundary wake), direction = sign of the weekend gap (first post-break open vs last pre-break close), SL = 1× ATR(20 completed ET days), one entry per Monday. TP parked at 5× ATR (order-path requirement; structurally unreachable intraday) — the REAL exit is timed.
- **NEW BOT CAPABILITY — timed-exit pass:** runs EVERY wake, BEFORE the entry guards (risk-reducing actions must fire even when the breaker halts entries; tested). Rule: a `timed_exit` slot's position may live only during Monday before 16:00 ET (US statutory clock, the hand-verified rule — not derived from the EET offset, which diverges in desync weeks); any other time it is market-closed at the first wake, which also covers downtime recovery. `close_slot_position` uses the position-ticket close path (magic-filtered).
- Slot: `gap`, EURUSD.sim, 0.5%, magic 20260716, M30 cadence, `ltf_count` 1100 (~23 trading days for the plugin's ATR; per-slot fetch-depth override added — needs_htf-False M30 slots also stop fetching a wasted H4 frame).
- Tests: **19/19** (gap window/direction/one-per-Monday, timed-exit rule incl. downtime recovery, exit-pass-before-breaker).
- Prop-sim (standing trigger, 7-slot book committed): challenge **79.2% / breach 11.7%**; trial-13d 44.6%.
- Live expectation: ~1 trade per Monday; 1–2 fills before trial end. Guards unchanged (aggregate cap 4 stands — 7 slots contend).

**Protocol:** registration commit → dry-run → armed WMI relaunch → verification past the next boundary → observation-log entry.

---

# 2026-07-10 — REGISTRATION: trendline-break cell (operator-requested; the one untested item from the FVG/ICT/OB list — the rest were tested and killed, receipts in fdb 4/13/sweep-fade entries) — committed BEFORE results

**Rule (structural, chosen not tuned):** an UP-trendline = the line through the two most recent confirmed fractal swing lows with the second higher than the first (fleet `detect_fractals` convention); projected forward by bar count. A DOWN-trendline mirrors (two most recent swing highs, second lower). **Break = M30 close beyond the projected line → enter in the break's direction** (trend-change momentum — the BOUNCE arm is level-fade-shaped and stays closed under the MR bar). SL at the most recent opposing fractal (structural); TP 2.5R (house); fire-and-forget; one trade per line identity (the anchor pair). Honesty note: this is breakout-family-adjacent (diagonal vs the tested horizontal structures) — a fail counts toward that family's record.

**Cells:** XAUUSD + SPX (Phase A data, costs 30 / 5.0 pips-equiv commission-inclusive) and USD_JPY (OANDA data, 0.9 pips all-in — the reopened FX door's verified cost). Mode scalp30 (H4 confirm frame present, plugin ignores it; M30 trigger). Gates: 2023 quick-check (grid criteria verbatim) → full window → standard gauntlet for survivors.

---

# 2026-07-10 — METHODS CORRECTION (correct-at-source): the harness's every-signal convention quantified — book odds are now stated as BOUNDS

**How it surfaced:** the trendline-break cell's full windows came back implausibly strong (USD_JPY +$51k, 3–4× the best record in project history) — the too-good-to-trust reflex triggered a forensic pass, which found ~45% of its entries opening while the prior trade was still open. The same check against the LIVE slots' own records: **xau 524/974 entries overlap, jpy 432/745, spx ~similar, ORB slots 232/1245 and fewer, volcomp and gap zero.** Harness source confirms: `run_backtest` simulates every signal independently against future candles — no open-position tracking exists. The prop-rules study (2026-07-05) acknowledged this in one sentence ("historical record permits overlapping same-instrument positions that the live gates cap at 1") but its magnitude was never measured. Measured today (`onecap_replay.py`, greedy chronological filter = the LOWER bound; live re-signaling after flat recovers some skipped trades, so truth lies between):

| record | full net | 1-cap net | delta |
|---|---|---|---|
| xau pullback | +$13,755 | +$32 | −99.8% |
| jpy pullback30 | +$17,660 | +$4,252 | −76% |
| spx pullback | +$6,631 | +$1,331 | −80% |
| ospx ORB | +$7,180 | +$6,131 | −15% |
| oxau ORB | +$7,197 | +$5,872 | −18% |
| vxau volcomp / gap | — | — | 0% (naturally sequential) |

The mechanism of the damage is adverse selection under the cap: winners hold for days and block the slot; stopped losers free it quickly — so the greedy subset skews toward losers, hitting the multi-day pullback family hardest and the intraday designs barely.

**Corrected book odds, stated as bounds (prop-sim on both stream sets): challenge P(+10%) ∈ [49.0%, 79.4%], breach ∈ [4.8%, 11.9%], trial-13d ∈ [13.2%, 44.8%].** The truth is interior; the live trial record is the estimator that narrows it (every forward fill is now doubly valuable).

**Standing rules from this correction:** (1) every future validation record reports its 1-cap replay beside the full record, and adjudication quotes both bounds; (2) no existing slot is retired on the lower bound alone — the records measure signal quality honestly, the capture rate is what's uncertain, and the ORB/volcomp/gap slots (the book's majority) are barely touched; (3) the trendline cells' adjudication is PARKED pending this convention's ruling — noting their 1-cap lower bounds remain the strongest on the map (USD_JPY +$11,122 at n=1,507, +$7.38/tr AT the lower bound); (4) trial-end mechanics report gains a records-vs-live capture-rate section.

## CAPTURE-RATE FRAMEWORK ADOPTED (operator-directed, same day as the methods correction)

1. **Third replay mode built (`onecap_replay.py --queued`):** signals queue while the slot is occupied; on freeing, the earliest queued trade whose recorded exit is still in the future is taken at its recorded outcome. **Stated bias: optimistic** (late entries credited with full outcomes; alive-selection favors long-lived winners). With greedy as the pessimistic model, truth sits between two MECHANISTIC models rather than between a model and the raw record — and notably the queued nets can EXCEED the record (ORB SPX +$14.3k vs +$7.2k) because the cap-world never takes clustered losers that die while the slot is blocked: the record is not the live upper bound.
2. **Per-record replay table (record / greedy / queued, implied r):** xau pullback +13,755 / +32 / +5,754 (r .05) · jpy +17,660 / +4,252 / +6,995 (.06) · spx +6,631 / +1,331 / +7,150 (.05) · ospx +7,180 / +6,131 / +14,297 (.32) · oxau +7,197 / +5,872 / +10,425 (.27) · trendline JPY +51,144 / +11,122 / +44,042 (.11) · trendline XAU +26,138 / +10,019 / +33,759 · trendline SPX +9,652 / +6,493 / +18,635.
3. **Adjudication rule (operator-ratified): gate by bound SPREAD, not point estimate.** ORB/volcomp/gap: tight — trusted as-is. jpy/spx pullback: wide but lower bound clearly positive — stay live, counted at the LOWER number until live capture data narrows it. **xau: reclassified UNGATED, DATA-COLLECTION-ONLY** — lower bound ≈ $0 means its recorded edge could be entirely a concurrency artifact; it stays live on demo capital specifically to measure r, and is excluded from pass-probability math until it clears.
4. **Decision-grade book odds (xau excluded, greedy↔queued): challenge P ∈ [49.4%, 81.7%], breach ≤ 3.3% under BOTH models** (the cap removes the concurrent pyramiding that was the breach risk), trial-13d ∈ [12.6%, 25.2%].
5. **Live r measurement deployed: SHADOW SCANNING** — blocked slots now evaluate their plugin every wake and LOG signals (never trade); this also aligns live plugin state with the harness's every-candle convention. Tests 19/19 (blocked-slot shadow test replaces the old no-scan assertion). Trial-end report computes per-slot r from (shadow signals, taken signals, recoverable-under-queued).
6. Trendline USD_JPY: still parked for deployment, but its pessimistic bound (+$11.1k, +$7.38/tr, n=1,507) remains the strongest lower bound on the map — the operator's framing stands: committing before r is measured is a smaller bet than xau's all-or-nothing.

## DEPLOYMENT REGISTRATION (operator-approved): `tl` slot — trendline-break, USDJPY.sim, 8th trial slot

The first deployment adjudicated ENTIRELY under the capture-rate framework: record +$51,144 / greedy +$11,122 / queued +$44,042 (implied r=.11) — the pessimistic bound alone is the strongest lower bound on the map (+$7.38/tr, n=1,507). Gauntlet: overlap lifts ≤1.18× (vs pullback30, same instrument; ≤1.0× vs the challenge book — genuinely distinct from the pullback family despite sharing USDJPY); 1cap marks-bound −18.8% @0.5% (inside the ≈−20% registered sizing bar → 0.5% per the rule, borderline noted); **prop-sim improves at BOTH decision bounds: lower 49.4%→59.5%, upper 81.1%→96.5%** (breach 9.9%/0.4%, both under the old record-book's 11.9%).

Mechanics: `trendline_plugin.py` unmodified from the killtest (two-fractal line, break-close entry, opposing-fractal SL, 2.5R TP, one trade per line identity, fire-and-forget). Slot: USDJPY.sim, 0.5%, magic 20260717, M30, per-slot instance, magic-filtered vs the jpy slot. Structural notes: OANDA record executed on .sim (the jpy-slot precedent); live frequency expectation ~1–1.5 trades/day (the queued model's rate) — this becomes the book's most active slot and the richest shadow-scan r data source. Cost 0.9p all-in verified. Tests extended (trendline seam), suite green required before relaunch.

---

# 2026-07-10 — REGISTRATION: capture-engineering study (k-cap replay) — committed BEFORE results

**Question:** how much of the record-vs-live capture gap closes if a slot may hold **k concurrent positions at risk/k each** (k=1,2,3 — worst-case per-slot exposure constant at 0.5%)? Method: greedy chronological replay per record, taking a trade whenever open positions < k; per-trade R scaled by 1/k in the prop-sim (risk dict 0.005/k). This compares the PESSIMISTIC bound as a function of k — apples to apples with the standing k=1 lower bound. Records: the wide-bound slots (jpy, spx, ospx, oxau, tl) + xau (data-only, informational); vxau/gap have no overlaps and are unaffected. Decision metric: the k that maximizes the book's LOWER-bound P(challenge) at breach not worse than the k=1 record-book's 11.9%. Deployment (if any k>1 wins) = per-slot cap k + sizing/k in the bot — a separate operator-gated unit; aggregate-cap implications restated there.

## K-CAP STUDY RESULTS (uniform k, per registration) + PRE-STATED MIXED-K FOLLOW-UP

**Uniform-k verdict (registered metric: max lower-bound P(challenge), breach ≤ 11.9%):** k=1 P=.597/breach .103 · k=2 P=.595/breach **.005** · k=3 P=.444. On the registered metric k=1 and k=2 tie within noise — **no uniform k raises the floor odds; k=2 is a SAFETY trade (breach 10.3%→0.5% at equal P), not an odds trade.** Mechanism, from the per-slot capture curves: ORB slots already capture 82–85% at k=1 (k>1 just halves their size); the overlap-heavy slots (tl 22%→36% at k=2, spx 20→31%) are where extra caps pay.

**Mixed-k follow-up, derivation rule pre-stated BEFORE the run:** per slot, choose the k∈{1,2,3} that maximizes that slot's OWN risk-adjusted capture (net/k) — a mechanical per-record rule, not a book-level search. Derived config: jpy k=1, spx k=3, ospx k=1, oxau k=1, tl k=2 (xau stays data-only). ONE prop-sim run of this single derived configuration; adjudication vs k=1 on the same metric.

**MIXED-K VERDICT (single derived config, one run): challenge P=0.688, breach=0.033, trial-13d 0.232 — the pessimistic FLOOR rises +9.1 points over k=1 (0.597) with breach cut to a third (10.3%→3.3%).** The study's registered metric is decisively won by the mixed configuration: jpy k=1 · spx k=3 (0.167%/position) · ospx k=1 · oxau k=1 · tl k=2 (0.25%/position); vxau/gap unaffected; xau data-only. This is capture ENGINEERING paying exactly where the framework predicted: extra concurrency only where a slot's own record shows blocked-signal value (tl, spx), none where capture is already high (ORB).

**Deployment implications (operator-gated, restated honestly):** per-slot `max_pos` + risk/k sizing in the bot (moderate change + tests); worst-case concurrent exposure rises from the current cap-4 × 0.5% = 2.0% to a theoretical 4.0% if all slots max simultaneously (each slot still capped at 0.5% total) — the simulated breach at 3.3% prices that exposure and remains well under the record-book's 11.9%. Artifacts: kcap_study.py, mixedk_*.csv.

## DEPLOYMENT REGISTRATION (operator-approved): MIXED-K capture engineering live on the trial bot

Per the k-cap study's derived config (rule pre-stated, one run): **spx max_pos 3 @ 0.167%/position, tl max_pos 2 @ 0.25%/position; all other slots max_pos 1 @ 0.5% — every slot's TOTAL worst-case risk unchanged at 0.5%.** Bot changes: per-slot `max_pos` with per-position risk = risk_pct / max_pos (sizing + shadow threshold + log line); **aggregate cap 4 → 11** (the sum of per-slot maxima — exposure control now lives in the per-slot caps; account-level guards remain the daily −$2,000 breaker and the $93,000 floor). Worst-case simultaneous exposure 4.0% of initial vs the −5% daily line, priced by the study at breach 3.3% on the pessimistic bound. Tests **21/21** (mixed-k trade-below-cap at risk/k + shadow-at-cap; aggregate backstop re-pointed at the constant). Decision-grade book bounds after this deployment: **challenge P ∈ [68.8%, ~96.5%], breach ∈ [3.3%, 0.4%].**

---

# 2026-07-10 — CODE REVIEW (operator-requested) → CORRECTION CYCLE: two live-critical clock/seam bugs, two voided validations, five hardening fixes

Two independent review passes over the live bot + research tooling. Findings and dispositions:

**CRITICAL-1 (live, fixed): the fetch seam fed SERVER-time (EET) frames to plugins whose backtest seams always fed UTC.** Every session-anchored plugin's clock was shifted +3h (summer): the live ORB slots formed their "09:30–10:00 ET opening range" from real 06:30–07:00 premarket bars (live evidence: the one oxau fill entered at real 07:30 ET), and the gap slot would have debuted at Monday midnight ET instead of 03:00. FIX: `fetch_frame` now converts per-bar to UTC; volcomp's day grouping moved to an explicit +2h shift = EXACTLY its Phase A record convention (better than before). **The two mis-clocked live ORB fills (ospx none, oxau −$482.54 on 07-09) are marked NON-CONFORMING in the trial record — excluded from mechanics/capture comparisons.**

**CRITICAL-2 (research, gap slot SUSPENDED): the Track C backtest never measured the weekend gap** — `days[i-1]` before Monday is OANDA's SUNDAY partial session, so the "gap" was Monday-00:00-open minus Sunday-23:30-close: adjacent-bar noise, not the registered Friday→Sunday repricing. The deployed `gap` stream's validation is VOID. Slot suspended (no position ever held; caught before its first trade). Fixed killtest (true Friday-close→first-post-weekend-bar gap + Sunday-free ATR) re-running; re-adjudication decides reinstate/retire.

**HIGH (tl slot SUSPENDED): trendline_plugin used UNCONFIRMED fractals** — center-of-5 marks within 2 bars of the window edge need future bars; the harness's full-enrich-then-slice let the plugin anchor lines AND place SLs on them (systematically fewer immediate stop-outs = inflated record; live frames can't even see those marks). Also fixed: first-break-only rule (kills restart double-entries and late chasing). Scope contained: the fleet pullback plugin has an explicit confirmed-fractal cutoff — fleet/slot pullback records CLEAN. Fixed killtest re-running; mixed-k's tl arm suspended with the slot (spx max_pos 3 stands).

**MODERATE (live, fixed): the daily breaker's server-day window started 2–3h early** (UTC-instant bound vs server-rendered deal epochs), blending late-prior-day P&L into "today" — precisely why the breaker held all morning on yesterday evening's losses. Fixed to server-naive midnight; the breaker released immediately on restart, correctly.

**Hardening (fixed):** timed-exit pass exception-wrapped per slot; fill-price fallback magic-filtered on shared symbols; strength-divergence killtest's ATR lookahead noted for the record (cell already dead — record even deader); prop-sim approximations documented (flat-week absence, entry-day P&L booking, EOD-only breach detection — mixed directions); FOMC-cost hardcode noted. onecap/kcap/queued replay logic traced CLEAN by review (one caveat logged: queued mode's full-outcome crediting is the stated optimistic bias).

**Standing rule added: any NEW plugin must pass a session-clock seam test (frame timestamps as the bot actually delivers them) and a confirmed-indicator audit before deployment.** Book pending re-runs: 6 active slots (xau data-only, jpy, spx@k3, ospx, oxau, vxau) — ORB slots now correctly clocked for the first time. Tests 21/21.
