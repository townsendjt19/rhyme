# Rhyme — Governance

The rules and rulings the portfolio operates under: strategy passports, pre-registered monitoring contracts, and retirement records.

> **Guiding principle: Rhyme is a portfolio of independently validated market behaviors, unified by a single risk engine.**
>
> The unit of account is the *behavior* (a repeatable market phenomenon with a measured edge), not the bot. Processes, modes, and accounts are plumbing; the roster below is organized by what each strategy actually exploits.

---

## Strategy roster by market behavior

| Market behavior | Strategy / config | Pairs | Status |
|---|---|---|---|
| **Channel breakout (trend initiation)** | Donchian, intraday (H1/H4) | GBP_USD, EUR_USD, USD_JPY, AUD_JPY, EUR_JPY | **Validated, live** (account -002) |
| **Channel breakout (trend initiation)** | Donchian, scalp30 (M30/H4) | USD_JPY | **Validated, live** (account -002) |
| **Channel breakout (trend initiation)** | Donchian, swing (H4/D) | USD_CAD | **RETIRED 2026-07-01** — failed passport boxes 1–3, 1.01x/6yr, no distinct behavior; open position in run-off to standing SL/TP |
| **Trend pullback (continuation)** | trend-origin pullback, long-only, pullback30 (M30/H4) | USD_JPY | **Probation** (isolated account -001; 60 trades / 6 months from 2026-07-01) |
| **Mean reversion** | — | — | **CLOSED 2026-07-02** — six structurally distinct designs tested and killed under pre-registration (range_fade v1/v2, sweep-fade ×2, session fade, VP reversion, ER-gated sweep-fade; RSI earlier); non-viable at M30/H4 on this account's spread structure. Reopens only with new information (different timeframe, venue, or mechanism class) — see RESEARCH_LOG formal closure |
| **Retracement-level confluence** | — | — | **Closed** — Fibonacci 61.8% bounce rejected as-designed and with volume-profile gating (see RESEARCH_LOG) |
| **Supply/demand zone retest** | — | — | **Blocked on architecture** — order blocks rejected due to single-pending-block starvation; requires multi-pending rebuild to revisit |
| **Session/time-of-day** | — | — | **Closed** — London breakout rejected (WR 7–22%) |
| **Volatility regime / carry / news** | — | — | **Future** — unexplored |

**Live roster as of 2026-07-01 evening: three processes — Donchian intraday (-002), Donchian scalp30 (-002), pullback30 (-001, probation) — all under pre-registered governance (monitoring table below for the Donchians, probation terms for pullback30), none grandfathered.** Two exploit the same behavior (Donchian breakout, 97–99% measured overlap on USD_JPY); under the macro-trend reframe the portfolio may be effectively one behavior — see the portfolio-level note below.

---

## Strategy passport (template)

Every candidate must pass every box before production. Measurable criteria only — no "improves overall portfolio" language.

| # | Box | Standard |
|---|---|---|
| 1 | **6+ years backtested, spread included** | Full 2021–2026-YTD window (or maximum available), per-pair spread from the SPREAD_PIPS table, $80 fixed risk |
| 2 | **Min-N met** | Every year × direction cell ≥ 10 trades (per pair where multi-pair) |
| 3 | **No single-year dependency** | Concentration check passed: top-5 wins a small share of gross wins per profitable year; result survives excluding the best year |
| 4 | **Acceptable drawdown** | Max drawdown stated on BOTH models — fixed-$80 dollar curve AND 1%-compounding percent-of-equity — and accepted explicitly; not left uncomputed |
| 5 | **Measured overlap vs. every live strategy** | Trading-day overlap % and direction-agreement % from the standard overlap analysis, per live strategy — numbers, not conceptual estimates |
| 6 | **Regime/factor dependence documented** | Not "has none" — "we know what it is and it is written down," with the falsifying condition named |
| 7 | **Adds a distinct market behavior** | The behavior is not already exploited by a live strategy (or the redundancy is measured, bounded, and accepted in writing) |

---

## Passports — live strategies (retro-filled 2026-07-01)

Retro-filled from RESEARCH_LOG and the backtest CSVs. Where a box wasn't formally satisfied at validation time, it is filled with what we know **now** — failures are marked ❌, not papered over.

### 1. Donchian intraday (H1/H4) — GBP_USD, EUR_USD, USD_JPY, AUD_JPY, EUR_JPY

*(Figures corrected 2026-07-02 to the corrected-harness record `corrected_f86d9f4_intraday_2021-2026ytd.csv` — the pre-fix catalog record was +$39,116.41 / 6,884 trades / 32.0% WR; see RESEARCH_LOG scope-correction entry, same date.)*

| Box | Status | Evidence |
|---|---|---|
| 6yr spread-included | ✅ | **7,434 trades, 31.0% WR, +$28,973.51** (corrected harness, per-year 2021–2026 YTD) |
| Min-N | ✅ | Zero failures across all pair × year × direction cells |
| No single-year dependency | ⚠️→❌ | **Corrected record is 3 of 6 periods negative** (2023 −$4,309, 2025 −$5,968, 2026H1 −$10,546) with profits concentrated in 2022 (+$23,330) and 2024 (+$19,978); and **pair-concentrated: USD_JPY is +$24,581 of the +$28,974 (85%)** — the other 4 pairs average ~+$1,098 each *(2026-07-02: both concentrations worsened under the corrected record)* |
| Drawdown | ❌ | Fixed-$80 curve: **-$18,413**. 1%-compounding: **-92.0% of equity** (final multiple 15.0x — corrected from the catalog's 57.1x). Never computed at validation; the 1% number assumes every signal taken concurrently at 1% each, which live 1-position-per-instrument throttling prevents — but neither number was ever explicitly accepted |
| Overlap vs live | ❌→✅ | vs scalp30 on USD_JPY: **99.5% trading-day overlap, 97.0% same-direction, 0.5h median gap** *(recomputed 2026-07-02 vs corrected records; was 99.7/97.3 — conclusion unchanged)* — measured only after validation; the redundancy is now documented and deliberately accepted (scalp30 outperforms on the shared days; see RESEARCH_LOG "inverted conclusion") |
| Factor dependence | ⚠️ | Shared caveat: validated entirely within the 2021–2026 macro window; USD_JPY (its dominant P&L source) is long-USD-direction-carried, tying it to the long-USD hypothesis logged 2026-07-01 |
| Distinct behavior | ❌ | Same behavior as scalp30 (Donchian breakout); on USD_JPY specifically, largely the same *trades* |
| Prop-compatible (2026-07-02) | ❌ | **None — fails all four encoded presets at every tested risk level** (static floors breached from Jan 2021 even at 0.25%); see the prop-firm compatibility section |
| **Doc discrepancy** | ❌ | **strategies.json lists 4 pairs; the live process trades 5 (EUR_JPY included, +$3,444/6yr backtested).** Needs reconciliation |

### 2. Donchian scalp30 (M30/H4) — USD_JPY

*(Figures corrected 2026-07-02 to the corrected-harness record `corrected_f86d9f4_scalp30_2021-2026ytd.csv` — the pre-fix catalog record was +$28,000.34 / 2,719 trades / 33.5% WR; see RESEARCH_LOG scope-correction entry, same date.)*

| Box | Status | Evidence |
|---|---|---|
| 6yr spread-included | ✅ | **2,931 trades, 32.7% WR, +$26,278.01** (corrected harness) |
| Min-N | ✅ | Zero failures |
| No single-year dependency | ✅ | 2022 is the best year (**+$14,631** corrected) but every 2021–2024 year remains positive without it |
| Drawdown | ❌ | Fixed-$80 curve: **-$8,901**. 1%-compounding: **-68.8% of equity** (final multiple 18.3x, corrected from 23.3x). Never computed at validation; same acceptance gap as intraday. The -68.8% is dominated by the ongoing 2025–2026 stretch |
| Overlap vs live | ✅ (post-hoc) | vs intraday: 99.5%/97.0% *(recomputed 2026-07-02 vs corrected records)* (accepted — this is the stronger side of the pair); vs pullback30: 68.1% same-direction / 28.2% opposite (and now cross-account) |
| Factor dependence | ⚠️→❌ | **The "no negative years" claim in RESEARCH_LOG/strategies.json is false per the CSVs: corrected 2025 is -$2,869 and 2026 YTD is -$2,569 — the two most recent periods are both negative and deteriorating.** Long-USD-direction exposure per the 2026-07-01 hypothesis. This is the portfolio's flagship and its recent trajectory is its biggest open risk |
| Distinct behavior | ❌ | Same behavior as intraday (see above); kept because it's the *better* expression of it |
| Prop-compatible (2026-07-02) | ⚠️ | **FTMO 2-Step and 5%ers High Stakes Classic at 0.50%; fails every trailing-floor preset** (the 2025–2026 drawdown-from-peak is fatal to trailing mechanics); start-date-dependent — 2023/2025 fresh starts breach before target |

### 3. Donchian swing (H4/D) — USD_CAD — **RETIRED 2026-07-01**

Retired per the grandfather review (RESEARCH_LOG entry, same date): fails boxes 1–3, 1.01x/6yr at 1% compounding, no distinct behavior under the macro-trend reframe. Process stopped, `\Rhyme\Rhyme-Swing` task deleted, open trade 37 in run-off to its standing SL/TP (retirement convention adopted and logged). Passport preserved below as the record it was retired on.

*(Dated note, 2026-07-02: the record below came from the pre-fix harness, whose warm-up dead zone at DAILY HTF silenced ~5 months of every per-year segment. The corrected-harness record — `corrected_f86d9f4_swing_2021-2026ytd.csv` — is **376 trades, 24.7% WR, net −$4,759.73, a sign flip**, with 4 of 6 periods negative, fixed-$80 maxDD −$6,404, and a 0.53x final multiple at 1% compounding. Retirement REINFORCED; see the addendum on the RESEARCH_LOG retirement entry. The passport numbers below are preserved unchanged as the record the decision was made on.)*

| Box | Status | Evidence |
|---|---|---|
| 6yr spread-included | ⚠️ | 225 trades, 33.3% WR, **+$292.53 total over 6 years** — barely positive |
| Min-N | ❌ | **3 failing cells** (2021/2022/2024 short: n=6, 4, 7) |
| No single-year dependency | ❌ | 3 of 6 years negative; 2025 (-$1,522) and 2026 (+$863) have **top-5 concentration of 91% and 89%** — single trades decide recent years |
| Drawdown | ⚠️ | Fixed-$80 curve: -$1,719. 1%-compounding: **-20.3% of equity, with a final multiple of 1.01x — six years of trading for +1% total equity growth**. Proportionally survivable but the return-to-drawdown ratio is effectively zero |
| Overlap vs live | ✅ | Structurally zero: no live strategy shares USD_CAD (intraday excluded it as net negative) |
| Factor dependence | ⚠️ | Same 2021–2026-window caveat; USD-base pair (long-USD side of the hypothesis) |
| Distinct behavior | ❌ | Same Donchian breakout behavior a third time |
| **Verdict flag** | ❌ | **Would not pass the passport today.** It survived swing's retirement-to-USD_CAD because its USD_CAD record was described as "validated independently" — the retro-fill shows that validation would fail boxes 2, 3, and arguably 1 under current standards |

### 4. pullback30 — trend-origin pullback, long-only (M30/H4) — USD_JPY — **PROBATION**

| Box | Status | Evidence |
|---|---|---|
| 6yr spread-included | ✅* | Parent (long+short) design: 1,185 trades, +$14,136; long side +$18,864, positive every year. *The long-only variant itself is post-hoc — historical results are premise evidence, not validation (recorded at creation) |
| Min-N | ✅ | Zero failures (parent run) |
| No single-year dependency | ✅ | 2022 top-5 concentration 5.8%; long-ex-2022 still +$9,821 with every year positive |
| Drawdown | ✅ (defined) | Probation early-kill at **$1,200** drawdown from strategy equity peak — the only live strategy with an explicit, pre-committed drawdown bound. Backtest reference (parent long side, 1%-compounding): **-30.5% of equity**, final multiple 9.6x — the best DD-to-return profile of any strategy on the board |
| Overlap vs live | ✅ | vs Donchian scalp30: **68.1% same-direction / 28.2% opposite / 6.0h median gap / 62.8% long-day overlap** *(opposite-% recomputed 2026-07-02 vs corrected records; was 28.4)* — measured before deployment; materially more independent than the 88.9–97.3% overlaps that killed prior candidates. (Not separately measured vs intraday's USD_JPY; intraday≈scalp30 at ~97% makes scalp30 a fair proxy) |
| Factor dependence | ✅ | **Persistent-macro-trend dependence (supersedes the long-USD framing after the EUR_JPY probe, 2026-07-01): the profitable direction is the pair's dominant secular trend — short-yen for USD_JPY.** Falsifier restated: a sustained **yen-strengthening** stretch is the true stress test. **EUR_JPY 2025–2026 is the live preview of the failure mode: edge-to-zero, not losses** (long P&L -$9 and -$32 after four strongly positive years — HH/HL structure stops forming, so signals and P&L flatline). Note: the $1,200 drawdown early-kill will NOT catch this mode; the 6-month calendar trigger is the backstop |
| Distinct behavior | ✅ | Trend *pullback/continuation* — entry on retracement into structure with origin-anchored stop — vs the Donchians' breakout entries. The one genuinely distinct behavior added since Donchian |
| Prop-compatible (2026-07-02) | ✅* | **All four encoded presets: 2-Step / High Stakes Classic at 0.50%; 1-Step / FundedNext Legacy at 0.25%** — the only strategy surviving trailing-floor mechanics, with thin margins (+2.94% / +1.21% closest approach). *Same post-hoc caveat as box 1: premise evidence, not validation |

---

## Portfolio Risk Tolerance (decided 2026-07-01)

- **Total research budget: $3,279.** **Floor: $800 PER ACCOUNT** — each research account's marked-to-market NAV (-001 and -002, including open positions) is checked independently against $800. Decided 2026-07-01. *(Dated note, per the correct-at-source convention: the initial implementation earlier the same evening checked COMBINED equity against $800; corrected same-day to per-account to match the decided intent — a research vehicle hitting the floor is a portfolio-level event demanding full review regardless of where it happens, and a combined check would have let one account be wiped while the other's balance masked it.)*
- **If EITHER account touches the floor, the ENTIRE fleet suspends new entries pending full review** — not just that account's processes. Enforced in code, not just prose: every bot runs `check_equity_floor()` (main.py) once per cycle before any scanning — per-account NAV via `broker.get_nav_for()`; a breach on any account skips the cycle's entries entirely, logs at CRITICAL naming the breached account(s), and prints the breach in the cycle output. Since every process runs the same check, a breach suspends the whole fleet within one candle interval of each mode. Existing positions remain managed by their standing SL/TP (run-off convention). Fails open on transient API errors, matching the per-trade gates' convention.
- **The monitoring table's suspend/retire triggers below are RESEARCH-EFFICIENCY thresholds, not capital bounds** — they exist to detect that a strategy is *dead* (evidence its edge is gone), not to protect capital. The drawdown budget above deliberately accommodates the strategies' historical worst cases at 1% sizing; a strategy hitting its efficiency trigger while the portfolio is far from the floor is a research finding, and the floor breaching while every strategy is within its triggers would be a portfolio-level event the per-strategy monitoring cannot see. The two layers are independent by design.
- **Horizon clause: this tolerance applies at current R&D scale only** — practice accounts, ~$8k combined, 1–2% sizing. It must be **re-decided from scratch** before any capital increase or any live-money transition; nothing here carries over by default.

## Pre-registered forward monitoring — Donchian modes (defined 2026-07-01, before forward data)

Forward windows start 2026-07-01. All thresholds are against each mode's own backtest baseline. *(Baselines re-derived 2026-07-02 from the corrected-harness records `corrected_f86d9f4_*.csv` — the originals were computed from the pre-fix validation CSVs (bf9d732 lineage) whose warm-up dead zones under-sampled every year; forward windows, trigger dates, DD thresholds, and pre-committed actions are UNCHANGED. Both WR floors moved DOWN (28.5→27.1, 28.8→27.7): this is the baseline becoming accurate, not a loosening toward recent performance — the mechanism, worst-full-backtest-year WR, is identical; only its input data was corrected. Swing's column is preserved as-written; it never activated.)* Deterioration is measured on the forward record only; the pre-committed actions below were decided at definition time, not at review time. WR thresholds use each mode's worst FULL backtest year (partial 2026 noted separately). The forward "1%-sizing curve" = equity from compounding 1% risk per closed forward trade (R = pnl/$80-equivalent).

| | scalp30 (USD_JPY) | intraday (5 pairs) | swing (USD_CAD) |
|---|---|---|---|
| Backtest baseline *(corrected 2026-07-02)* | 32.7% WR overall; worst full year 27.1% (2025); ~533 trades/yr | 31.0% WR overall; worst full year 27.7% (2025); ~1,352 trades/yr | 33.3% WR overall; worst full year 17.9% (2025); ~41 trades/yr *(pre-fix; never activated)* |
| Enters monitoring | **already ~18 months into a negative stretch** (corrected: 2025 -$2,869, 2026H1 -$2,569 at 26.2% WR) | **already deteriorating worse than scalp30** (corrected: 2026H1 -$10,546 at 23.7% WR) | pending grandfather decision (below) |
| **Review trigger** | **100 closed trades or 2026-09-15**, whichever first (short clock — deliberately ~2.5 months, not six, because of the standing negative stretch) | **150 closed trades or 2026-08-15**, whichever first *(AMENDED 2026-07-02 from 300 trades / 2026-10-01 — see dated contract amendment below)* | **20 closed trades or 2026-12-01**, whichever first (~3.4 trades/month makes trade-count triggers slow; the calendar governs) |
| **Deterioration threshold** | Rolling-100-trade WR **< 27.1%** (worst full backtest year, corrected 2026-07-02; was 28.5%), OR forward 1%-curve drawdown **> 15%** from forward peak | Rolling-300-trade WR **< 27.7%** (corrected 2026-07-02; was 28.8%), OR forward 1%-curve drawdown **> 20%** from forward peak | Rolling-20-trade WR **< 26.7%** (worst full year excluding outlier-2025), OR forward 1%-curve drawdown **> 10%** |
| **Pre-committed action at review** | Forward net ≤ 0 AND rolling WR below threshold → **SUSPEND** (stop the process; position management via OANDA SL/TP continues). A second consecutive failed review after reinstatement → **RETIRE** | Forward net ≤ 0 → **REDUCE**: cut to the top-2 pairs by forward P&L. Forward net ≤ 0 AND WR below threshold → **SUSPEND** entirely. Second consecutive failure → **RETIRE** | Any threshold breach → **RETIRE** (not suspend — grandfathered status means no re-validation record exists to justify reinstatement) |
| **Early-kill (no waiting for review)** | Forward 1%-curve DD > 15% at any point → immediate SUSPEND | Forward 1%-curve DD > 20% at any point → immediate SUSPEND | Forward 1%-curve DD > 10% at any point → immediate RETIRE |

Statistical honesty note, recorded up front (same convention as pullback30's probation): at n=100, a true-~33% process lands anywhere in ~24–43% (2σ), so a single WR breach is weak evidence alone — which is why every review action requires the conjunction with forward net P&L, and why suspension precedes retirement everywhere a validation record exists.

**Contract amendment (2026-07-02): intraday review trigger shortened to 150 closed trades or 2026-08-15** (from 300 trades / 2026-10-01 — roughly half the original window on both axes). This is a TIMELINE correction only: the deterioration thresholds re-derived earlier the same day (WR floor 27.7%, forward 1%-curve DD > 20%) and the pre-committed actions (REDUCE to top-2 pairs / SUSPEND / RETIRE ladder) apply to the shortened window unchanged. At a 150-trade review the WR check is computed on the full forward sample to date (the rolling-300 window cannot yet exist); the small-n honesty note above applies with proportionally wider bands. Rationale, recorded at amendment time:

1. **The corrected-harness baseline is materially weaker than the one the original contract assumed** — the 2026-07-01 contract was written against +$39,116/6,884 trades; the corrected record is +$28,973.51/7,434 (−26%), with 2023 flipped negative, 3 of 6 periods negative, and USD_JPY concentration at 85%.
2. **Its 2026 H1 backtest already sits below breakeven WR on a large sample** — 23.7% WR on 638 trades (corrected), against a ~28–29% breakeven at the strategy's realized R:R; this is not small-n noise.
3. **Three independent findings this week converge on the same live-regime concern:** the quarterly ER regime map (current quarters trending away from the Donchians' profitable regime), the EUR_JPY edge-to-zero probe (the trend family's documented failure mode, live on one of intraday's own pairs), and the FTMO simulation's trailing-floor analysis (intraday's drawdown-from-peak is the deepest on the board and ongoing).

A weaker historical case plus a deteriorating live regime does not justify waiting the original ~3 months to look.

## Retirement convention

Adopted at swing's retirement (2026-07-01, RESEARCH_LOG entry); applies to all future retirements:

1. **Run-off:** retirement stops new entries immediately (process stopped, scheduled task deleted); existing open positions run to their standing broker-side SL/TP and are never closed early — these bots only ever *open* positions, so a manual early exit would inject a discretionary decision the validated design never had. The retired strategy's final P&L record includes its run-off exits.
2. **Log archiving (added 2026-07-02, applied retroactively to swing):** the retired mode's stdout/stderr logs move from the repo root to `logs/archive/` at retirement — the root holds only live-fleet logs, so a glance at `paper_trade_*.log` files answers "what is running" without cross-referencing the roster. Archived logs are retained, not deleted (they are part of the retirement record).
3. The strategy's passport is preserved in this document as the record it was retired on; strategies.json status updated; dated RESEARCH_LOG entry with the full rationale.

## Swing (USD_CAD) grandfather decision — **DECIDED: RETIRED (option a), 2026-07-01**

Retired the same evening the board was presented; the swing column in the monitoring table above never activated. Record preserved below as presented for the decision.

The retro-fill (below) showed swing/USD_CAD would fail passport boxes 1–3 if proposed today. The decision on its fate was deferred at retro-fill time; the full record for deciding:

| Evidence | Value |
|---|---|
| 6-year net (spread incl.) | **+$292.53** on 225 trades (33.3% WR) |
| Yearly | 2021 +$411, 2022 -$259, 2023 -$224, 2024 +$1,024, 2025 **-$1,522**, 2026 +$863 (n=10) |
| Min-N | **3 failing cells** (2021/2022/2024 short: n=6/4/7) |
| Concentration | 2025: 91% of gross wins in top-5; 2026: 89% — recent years are single-trade artifacts |
| 1%-compounding | -20.3% max DD for a **1.01x** final multiple — six years for +1% |
| Overlap | Structurally zero vs all live strategies (sole USD_CAD strategy) |
| Distinct behavior | No — third copy of Donchian breakout |
| What it costs to keep | One process slot, one 2%-risk position slot, USD_CAD margin when open (~$500–800 at 25:1–20:1), monitoring attention |
| What retiring loses | The portfolio's only USD_CAD exposure and only pair-level diversification away from USD_JPY-dominated P&L — though with a 1.01x six-year multiple, the diversification it provides is diversification into *nothing* |

**Options (decision is the operator's):** (a) **Retire now** — the record would not pass today's gate, and the monitoring table above already pre-commits retirement on its first breach anyway; (b) **Keep on hospice terms** — let the pre-registered monitoring run; first breach retires it with no further decision needed; (c) **Keep indefinitely on grandfather status** — explicitly accept that one live strategy is exempt from the passport (not recommended: it makes the passport aspirational rather than binding).

## Prop-firm compatibility (reference simulation line, added 2026-07-02)

Simulated by `prop_rules.py` over the corrected-harness trade + floating-mark data (`backtests/corrected_f86d9f4_*`), $100k notional, fixed-fractional sizing at 0.25%/0.50%/1.00%. Conventions and documented approximations per the RESEARCH_LOG FTMO entries (UTC day boundary, stop-bounded worst-case marks, daily baseline = closed balance at day start, historical same-instrument stacking). Survival = zero daily-loss breaches AND never below the preset's drawdown floor over the full 2021–2026 window; consistency rules gate passing/payout and are reported separately.

**Cross-preset survival matrix (highest surviving risk level):**

| Strategy | FTMO 2-Step | FTMO 1-Step | 5%ers High Stakes (Classic) | FundedNext Futures Legacy |
|---|---|---|---|---|
| intraday | none | none | none | none |
| scalp30 | **0.50%** | none | **0.50%** | none |
| pullback30 | **0.50%** | **0.25%** | **0.50%** | **0.25%** |
| swing (retired, ref.) | none | none | none | none |

The dividing line is the drawdown mechanic, not the firm: static-floor presets (FTMO 2-Step, High Stakes) admit scalp30 and pullback30 at 0.50%; trailing-floor presets (FTMO 1-Step at 10%-of-peak, FundedNext's 3% MLL lock-at-initial) admit only pullback30 at 0.25%, with thin margins (closest approaches +2.94% and +1.21% respectively).

**Preset sources (verified against each firm's own published rules before encoding; aggregator summaries not relied on):** FTMO — account-comparison-page screenshots, 2026-07-02. The5%ers High Stakes — help.the5ers.com general-rules + drawdown FAQ, fetched 2026-07-02; the CLASSIC variant (8%/5% targets) is encoded, the New variant is 10%/5%; **the 30% single-day consistency cap was verified NOT to apply to High Stakes** (it is a per-position rule in The5%ers Futures programs) — High Stakes' actual mechanism, minimum 3 profitable days ≥0.5% of initial, is encoded instead. FundedNext — fundednext.com/general-rules/futures/trading-objectives, fetched 2026-07-02; the Legacy program encoded ($6k target / $3k EOD-trailing MLL locking at initial / no daily limit / 40% challenge consistency cap); note it is a FUTURES program — the drawdown *mechanic* is what is modeled; this data is FX.

**Account-size equivalence (confirmed 2026-07-02, no rerun needed):** the simulation is exactly percentage-equivalent at any notional — `prop_rules.py` contains no lot arithmetic (risk = f × balance, pnl = R × risk; all thresholds relative), so $50k/$100k/$200k produce identical percentage outcomes by construction. Minimum-increment friction at $50k, checked against the corrected trade records (units at $80 fixed risk: medians 20k–33k, 5th percentiles 5k–12k): at 0.25% risk on $50k ($125/trade, sizes ×1.56), median positions run 0.31–0.52 lots, where 0.01-lot (1,000-unit) rounding — the MT4/MT5 prop-platform granularity — distorts risk-per-trade by ~1–2%, and ≥95% of trades stay under ~6% distortion; only the rare widest-stop tail (≪1% of trades, sizes near 1–3k units) sees material rounding, immaterial in aggregate next to the sim's other documented approximations. At 0.50% the distortion halves. OANDA's own 1-unit granularity makes the friction effectively zero for the paper fleet. **Conclusion: results transfer to $50k–$100k accounts as-is; not to be re-litigated absent a platform with coarser than 0.01-lot increments.**

**Preset policy: this shortlist is deliberately not exhaustive.** New presets are added when a specific firm becomes relevant (e.g., an actual application is being considered), not by encoding the prop-firm market preemptively. Each addition requires firm-published rules, sourced and dated as above.

### Passport tracks (added 2026-07-02)

Two passport tracks exist going forward; a strategy can pass one and not the other, **both verdicts get logged, and neither overwrites the other**:

1. **General validation** — the existing seven passport boxes plus the prop-compatibility row. Gates **paper-fleet deployment**. Unchanged.
2. **Prop-track priority** — the early trailing-floor pre-check (`prop_rules.trailing_precheck()`: worst trailing-style peak-to-trough drawdown at 0.25%/0.50% on the candidate's kill-test / crown-jewel-equivalent stretch, run BEFORE any full window; "prop-deprioritized" iff blown >2× every trailing preset's threshold at both levels). Gates **research-time allocation toward the prop goal** — a prop-deprioritized candidate is deferred on the prop track but may still be pursued for portfolio diversity, logged explicitly as such. A full six-year run must never be the first point a trailing-floor blowout is discovered.

## Portfolio-level note: the one-behavior concern (added 2026-07-01, post-EUR_JPY probe)

Under the persistent-macro-trend reframe (see RESEARCH_LOG's EUR_JPY probe entry), **pullback30 may be the same underlying behavior as the Donchian family** — both profit by capturing persistent trends, differing only in entry mechanics (breakout vs. pullback into structure). If that reading is right, the live roster is effectively **one behavior** exploiting one 2021–2026 macro regime (yen weakness / dollar strength) through four processes. The pullback30 vs scalp30 overlap being "only" 68.1% measured the *entries*; the reframe says the *P&L source* may still be shared.

**Consequence: mean reversion (the Bot E slot) is elevated from open research to the highest-priority diversification need.** A validated mean-reversion behavior would be the first live strategy whose P&L source is structurally distinct from trend capture — the thing this portfolio does not yet have. Constraints already known for that search: candle-scale stops die to spread on this account (the RSI post-mortem and the pair sweep), so a viable mean-reversion candidate likely needs structural stops or a wide-stop pair — and the sweep's candle-scale conclusions do not price structural-stop designs (see sweep-scope nuance in RESEARCH_LOG).

*(Dated note, 2026-07-02 evening: the Bot E mean-reversion line CLOSED after six pre-registered designs failed — see the roster row and RESEARCH_LOG's formal closure. The diversification NEED above remains real and unmet; the conclusion is that it cannot be met by M30/H4 mean reversion on this account. Any future attempt at this need requires a different research direction — timeframe, venue, or mechanism class — and its own pre-registration.)*

## Recurring reconciliation audit (instituted 2026-07-01)

**Cadence:** at every monitoring review trigger (so scalp30's 2026-09-15 review includes one), and **no less than monthly regardless**.

**Scope:** every quantitative claim standing in this document and strategies.json — validation totals, per-year figures, WR baselines, drawdown numbers, overlap percentages, and pair lists / account assignments vs. the live scheduler configs — re-derived from the backtest CSVs / meta.json and live state, **never from prior log prose** (the scalp30 "no negative years" incident is the reason this rule exists).

**Mechanism:** `audit_governance.py` re-derives every mechanically checkable claim and prints PASS/DRIFT per claim (exit code 1 on any drift), plus a short manual checklist for claims that don't reduce to a number (factor-dependence prose, retirement-record reality, probation clock arithmetic, review dates not silently passed). Run:
```
D:/rhyme/venv/Scripts/python.exe D:/rhyme/audit_governance.py
```

**Output convention:** each audit produces a dated reconciliation entry in RESEARCH_LOG.md listing claims checked and PASS/DRIFT counts; any DRIFT is corrected **at source with a dated note** — the same convention as the 2026-07-01 scalp30 fix — never silently rewritten.

**Audit log:** 2026-07-01 (inaugural): 37 claims, 1 DRIFT (intraday pair list, corrected) → re-run clean.

## Retro-fill failure summary (things a current passport would not allow)

*Status notes added 2026-07-01 evening: items 1–4 are now resolved (swing retired; drawdowns computed on both models and in the passports; scalp30 claim corrected with dated note; pair list fixed via the inaugural audit). Item 5 is a standing structural fact, tracked in the one-behavior note above.*

1. **Donchian swing USD_CAD fails boxes 1–3 outright** — +$293/6yr, 3 min-N failures, 91%/89% recent-year win concentration. ~~Live on grandfathered status~~ → **RETIRED 2026-07-01**.
2. **Neither Donchian's max drawdown was ever computed or accepted at validation** — → both models now computed and in the passports; explicit acceptance remains an open operator decision.
3. **Scalp30's "no negative years" claim is false** — → corrected at source with dated note; reconciliation entry in RESEARCH_LOG.
4. **strategies.json / live-process pair-list mismatch for intraday** — → EUR_JPY added with dated note (caught again, and fixed, by the inaugural audit run).
5. **Three of four live strategies are the same market behavior**, two of them at 97–99% measured overlap on the shared pair — the roster is behaviorally thinner than it looks. *(Standing; drives the Bot E priority.)*
