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
