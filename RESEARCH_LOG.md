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

The PORTFOLIO.md retro-fill flagged an apparent contradiction: RESEARCH_LOG described Donchian scalp30 USD_JPY as "+$28,000/6yr with no negative years," while the backtest CSVs show 2025 at -$942.81 and 2026 YTD at -$3,323.79.

## Findings

**The original validation record was right all along; the contradiction was introduced later by a careless citation.**

1. **Provenance of the CSVs:** all six scalp30 per-year CSVs carry meta.json provenance from git commit `bf9d732`, run 2026-07-01 ~01:40 UTC -- the original validation run itself. The retro-fill and the original validation read the SAME files.
2. **The original validation entry never claimed no negative years.** It states, verbatim: "USD_JPY is positive in 4 of 6 years (2021 +$6,906, 2022 +$15,413, 2023 +$3,376, 2024 +$6,572; only 2025 -$943 and partial 2026ytd -$3,324 negative)." The +$28,000.34 total, 2,719 trades, 33.5% WR, and zero min-N flags are all accurate and reproduce exactly.
3. **The false phrase entered once, later the same day**, in the MA-pullback/trend-origin GBP_USD rejection entry, where the scalp30 benchmark was cited from memory as having "no negative years" instead of from the source record. That sentence is now corrected in place with a dated note.
4. **Fresh re-run at current HEAD reproduces the record exactly:** 2025 -> n=478, net **-$942.81** (identical to the dollar and cent); 2026 to 06-30 -> n=229, net **-$3,323.79** (identical -- note the original run's window ended 2026-06-30, not 07-01; extending one day to 07-01 gives n=232, net -$2,600.46, the difference being July 1's three additional trades). No code change since validation altered the results.

## Mechanism, stated plainly

This was a **citation-drift error**: a summary sentence written from memory upgraded "positive in 4 of 6 years" to "no negative years" while citing a benchmark in passing, and the false version then read as authoritative because it lived in the same log as the true one. No backtest, CSV, or code discrepancy existed at any point. The correct characterization of the standing benchmark is: **+$28,000.34 over 6 years, 33.5% WR, zero min-N flags, positive in 4 of 6 years, with both most-recent periods negative (2025 -$943, 2026 YTD -$3,324) -- a deteriorating recent trajectory that is the flagship's biggest open risk** (as PORTFOLIO.md's passport now records).

Process lesson recorded: benchmark citations in new entries should quote the source entry's numbers, not summarize them from memory -- the retro-fill audit caught this one precisely because it went back to the CSVs instead of trusting prose.

---

# Donchian Swing (USD_CAD) — RETIRED

## Status: RETIRED 2026-07-01 (process stopped, \Rhyme\Rhyme-Swing task deleted)

## Rationale

The PORTFOLIO.md retro-fill showed swing/USD_CAD would fail passport boxes 1-3 if proposed today, and the grandfather review confirmed retirement over hospice:

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
