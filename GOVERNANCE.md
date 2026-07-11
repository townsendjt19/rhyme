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
| **Cross-instrument spread reversion (stat-arb)** | adaptive-beta z-spread, daily | NZD_USD+USD_CAD (2B) | **LIVE ON PROBATION since 2026-07-03** (isolated account -003, $4,000; 24-month clock started; terms below; first fleet-uncorrelated behavior, r≈0.01; engineering review due 2026-10-03, first quarterly cointegration battery due 2026-10-01) |
| **Cross-instrument spread reversion (stat-arb)** | same mechanics | USD_CHF+USD_SGD (2C); EUR_USD+GBP_USD (2A) | **Validated-but-benched 2026-07-02** — available for a future slot decision, not discarded (2A additionally FIFO-conflicted with intraday's legs) |
| **Volatility regime / carry / news** | — | — | **Future** — unexplored |
| *(not a behavior slot)* | `personal_live/personal_live_scalp.py` | USD_JPY, live acct 001-001-21728068-001 ($99) | **Personal live-account experiment, not a Rhyme strategy** — no passport, not covered by fleet monitoring, audit, or the $800 floor; excluded by design (own live-host client/credentials, manual console launch only, dry-run unless `--armed`) |

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
| 8 | **Sortino ratio stated** (added 2026-07-03, methodology below, fixed BEFORE first computation) | Annualized Sortino on the 1%-compounding curve, computed exactly per the convention below; reported alongside the roster's ranked table for comparability |
| 9 | **Absolute minimum stop distance stated alongside any R:R floor** (added 2026-07-03) | Any design using an R:R or reward-to-risk ratio check — structural-stop designs especially — must ALSO state and enforce an absolute minimum stop distance (in pips or price units, per pair). A ratio check alone can pass with degenerate absolute sizing when the stop distance (the denominator) is near zero; the floor must be checked at DESIGN time, not discovered post-mortem. The spec must state the number and where in the code it is enforced |

### Box-8 Sortino convention (registered 2026-07-03, before any Sortino was computed)

Chosen — not tuned — and fixed for all strategies, current and future:

- **Curve:** the 1%-compounding equity curve (box 4's percent-of-equity model), NOT the fixed-$80 dollar curve. Per-trade return = 1% × R where R = pnl/$80; trades applied in `exit_time` order; equity(t) = ∏(1 + 0.01·R).
- **Aggregation:** the trade-level curve is resampled to **calendar-week (ISO week, Friday-anchored) returns** over the strategy's own record span (first exit week → last exit week). Weeks with no closed trades are **included as 0% returns** — the calendar-uniform basis is what makes a 24-trade spread comparable to a 7,434-trade Donchian; the flat-week convention is stated here precisely because it flatters sparse strategies, and any reading of the ranked table must carry that caveat.
- **MAR = 0:** downside deviation is the root-mean-square of negative weekly returns with the mean taken **over ALL weeks in the span** (full-sample denominator, not losing-weeks-only).
- **Annualization:** Sortino = mean(weekly return) / downside_dev × √52.
- **Why Sortino and not Sharpe (logged with the registration):** the book's payoff shape is trend-following — many small losses, rare large wins. Sharpe's symmetric volatility penalty counts exactly those rare large wins AGAINST the strategy; upside dispersion is the edge here, not risk. Sortino penalizes only downside dispersion, which is the thing the risk tolerance actually constrains.

**Box-8 values, roster (computed 2026-07-03 via `sortino.py`, corrected f86d9f4 records):**

| rank | strategy | Sortino (ann.) | mean wk (bps) | downside dev wk (bps) | weeks (losing) |
|---|---|---|---|---|---|
| 1 | pullback30 | **3.38** | +83.0 | 177.2 | 286 (141) |
| 2 | scalp30 | **2.31** | +139.4 | 434.6 | 287 (151) |
| 3 | intraday | **2.04** | +249.5 | 882.9 | 287 (164) |
| 4 | spread 2C (CHF/SGD, benched) | 1.03 | +3.0 | 20.9 | 235 (5) |
| 5 | spread 2B (NZD/CAD, probation) | 0.97 | +4.1 | 30.7 | 246 (6) |
| 6 | trend-origin D/H4 (benched) | 0.94 | +12.6 | 97.2 | 285 (76) |
| 7 | spread 2A (EUR/GBP, benched) | 0.89 | +2.5 | 20.2 | 235 (6) |

Flat-week caveat applies to rows 4/5/7 (5–6 losing weeks in ~240 — the spreads trade ~2×/month, so most weeks are structurally flat).

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

### 5–7. Stat-arb spread candidates (validated 2026-07-02; passports shared-format, thin-sample reservation explicit)

**Standing evidence statement, stated once for all three:** these candidates' evidence base — 19–24 trades over 5.5 years (~4/year) — is **structurally thinner than any other live or benched strategy on this board, and will remain so for years regardless of probation design.** Every year-cell fails min-N 10 by construction; 2B's 75% backtest WR carries a 95% CI of 53–89%. The passports' box-2 ❌ below is honest, not remediable by waiting a quarter.

| Box | 2B NZD_USD/USD_CAD (deployment priority) | 2C USD_CHF/USD_SGD (benched) | 2A EUR_USD/GBP_USD (benched) |
|---|---|---|---|
| 6yr spread-included | ✅ 24 trades, 75.0% WR, **+$813.89**; per-trade cost 3.4%/7.0% of risk | ✅ 21 / 71.4% / **+$559.36** | ✅ 19 / 68.4% / **+$471.22** |
| Min-N | ❌ every year-cell < 10 (structural at ~4 trades/yr) | ❌ same | ❌ same (thinnest, n=19) |
| Single-year dependency | ✅ ex-best +$562.26; top-5 share 42.6% | ✅ ex-best +$423.92 | ⚠️ ex-best +$258.00; top-5 56.5% at n=19 |
| Drawdown | ✅ worst daily −2.31% at 0.50% sizing; trailing floors never touched ≤0.50% (close-based marks caveat) | ✅ −1.15% | ✅ −1.75% |
| Overlap vs live | ✅ **monthly P&L corr vs fleet +0.013**; legs unfleeted | ✅ r −0.030; legs unfleeted | ⚠️ r −0.049 but **legs collide with intraday's EUR_USD/GBP_USD (FIFO)** |
| Factor dependence | ✅ documented: the Phase-1 cointegration regime; falsifier = relationship decorrelates — made mechanical via the quarterly stability re-run in the probation terms | ✅ same | ✅ same |
| Distinct behavior | ✅✅ spread reversion — the first P&L source structurally uncorrelated with trend capture | ✅ (same family as 2B — cross-correlation check pre-required if ever co-deployed) | ✅ (same family) |
| Prop-compatible (2026-07-02) | ✅ best matrix on the board: 2-Step/High-Stakes/FundedNext at 1.00%, 1-Step at 0.50% | ✅ three at 1.00%, FundedNext 0.50% | ✅ three at 1.00%, 1-Step 0.50% |

**2B probation terms (pre-registered 2026-07-02, activate at deployment; designed for this evidence profile, NOT the pullback30 template):**
- **Horizon: minimum 24 months calendar** (expected forward n ≈ 9 at the backtest rate). Stated honestly: this narrows the WR CI only marginally — the probation validates the EXECUTION MACHINERY and absence-of-collapse, not statistical significance of the edge, which no near-term horizon can deliver at 4 trades/year.
- **Engineering review at 3 months** (machinery, not edge): realized slippage vs assumed spreads, unwind incidents, fill asymmetry, per-trade realized risk vs the $80 design.
- **Quarterly cointegration re-run, pre-committed:** the Phase-1 rolling-90 stability battery on refreshed data — the strategy's factor-dependence falsifier made mechanical. Battery failure = the relationship decorrelated = **early-kill regardless of P&L**.
- **Early-kill (any time):** forward net ≤ −$400 (≈5R); OR any single trade's realized loss > 1.5× design risk (an ENGINEERING kill — sizing/unwind failure is distinct from edge failure); OR any naked-leg incident unresolved > 1 hour; OR quarterly battery failure (above).
- **24-month review pass:** forward net > 0 AND forward WR ≥ 45% (deliberately below the CI floor — a tight WR threshold at n≈9 would be noise theater) AND zero unresolved execution incidents. Fail → retire per convention; benched candidates do not auto-promote.

**Standing collision rule (generalizing the 2026-07-01 FIFO discovery): any future strategy — trend or stat-arb — that would trade an instrument which is also a LEG of a live spread trade (or vice versa) must be checked for account-level collision BEFORE deployment**, via `portfolio_state.check_spread_position_cap` semantics, not discovered per-incident. Spread legs occupy their instruments' single positions like any other trade; the roster above names each spread's legs for exactly this check.

## Portfolio Risk Tolerance (decided 2026-07-01)

- **Total research budget: $3,279.** **Floor: $800 PER ACCOUNT** — each research account's marked-to-market NAV (-001 and -002, including open positions) is checked independently against $800. Decided 2026-07-01. *(Dated note, per the correct-at-source convention: the initial implementation earlier the same evening checked COMBINED equity against $800; corrected same-day to per-account to match the decided intent — a research vehicle hitting the floor is a portfolio-level event demanding full review regardless of where it happens, and a combined check would have let one account be wiped while the other's balance masked it.)*
- **If EITHER account touches the floor, the ENTIRE fleet suspends new entries pending full review** — not just that account's processes. Enforced in code, not just prose: every bot runs `check_equity_floor()` (main.py) once per cycle before any scanning — per-account NAV via `broker.get_nav_for()`; a breach on any account skips the cycle's entries entirely, logs at CRITICAL naming the breached account(s), and prints the breach in the cycle output. Since every process runs the same check, a breach suspends the whole fleet within one candle interval of each mode. Existing positions remain managed by their standing SL/TP (run-off convention). ~~Fails open on transient API errors, matching the per-trade gates' convention.~~ *(Dated note, 2026-07-10: the fail-open convention is REVERSED — the floor and every API-backed per-trade gate now fail CLOSED for entries (an unverifiable gate is an unverified risk; a transient outage previously disabled every risk control at exactly the moment orders could still be placed). Exits/run-off are never blocked. Entry starvation during API flakiness is the accepted cost, made visible by an operator alert after `GATE_ALERT_AFTER = 3` consecutive failures of the same gate (risk.py). See the RESEARCH_LOG 2026-07-10 fleet-hardening entry and the OPERATIONS_LOG 2026-07-03 addendum.)*
- **Fleet trailing drawdown halt (added 2026-07-10): −25% from the fleet NAV peak** (`FLEET_DD_HALT_PCT`, risk.py; combined NAV across all research accounts vs its recorded peak, state persisted in `fleet_halt.json`). Sits BETWEEN the per-strategy monitoring triggers (research-efficiency thresholds, below) and the per-account $800 floor above — before this, the corridor from current NAV down to the floors (~80% at current funding) had no intermediate capital brake. On trigger: entire fleet suspends new entries, operator alerted; the halt is STICKY (NAV recovery does not clear it) and cleared only by the operator editing `fleet_halt.json` after review, **with a dated RESEARCH_LOG entry at each clear** (same convention as the spread naked-leg suspension). Open positions run off on standing SL/TP. Checked once per cycle by every process, reusing the floor check's NAV fetches (zero extra API calls); the peak update is monotonic-max, so concurrent processes cannot lower it.
- **Sizing basis (changed 2026-07-10): live position sizing uses marked-to-market NAV, not balance** — open floating losses shrink new positions. The backtest risk models (fixed-$80 and 1%-compounding) are unchanged; this is a live-execution convention, logged in RESEARCH_LOG so forward-vs-backtest comparisons account for it.
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

**Context note for scalp30's 2026-09-15 review (added 2026-07-03):** the July 2026 timeframe grid measured the Donchian family's edge gradient across timeframes on the same pair and year — **M5 −$4.75/trade → M15 −$0.47 → M30 +$4.25** (cells 2–3 vs scalp30's own 2023). The family's expectancy crosses zero between M15 and M30: **scalp30's edge sits just above the family's viability floor, not comfortably over it**, which reduces its cushion against the regime deterioration already flagged in this table (2025–2026 negative, corrected baselines). This is INPUT to the 2026-09-15 review, not a new trigger — thresholds and pre-committed actions unchanged.

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

## Pre-registered timeframe grid — July 2026

*(Registered 2026-07-03, before any cell run. Fixed: no cells added or modified after results start coming in.)*

**Scope:** open research lines only. Closed lines (mean reversion, RSI-family, London breakout, order blocks, MA pullback, swing structure, Fibonacci) are NOT re-tested at new timeframes; doing so constitutes a reopening and must meet each line's stated reopening bar first.

**Common rules for all cells:** $80 fixed risk, spread included from entry, 2023 quick check before any full 6-year run, standard passport (boxes 1–7, n≥10 per cell, per-year per-direction, concentration check) for quick-check survivors, prop_rules.py overlay for passport survivors. No parameter tuning after first run in any cell.

**Multiplicity note:** 9 cells registered. At this count, one spurious quick-check pass is expected by chance; therefore a quick-check pass grants only a full-window test, never deployment, and any cell whose full-window result depends on a single year fails the concentration check as usual.

| # | Mechanism | Cell | Pairs | Quick-check kill criteria (2023) |
|---|---|---|---|---|
| 1 | fvg_nested | M5 entry / 4H anchor | GBP_USD, USD_JPY | <15 trades combined; median stop <15 pips; expectancy negative on both |
| 2 | Donchian midpoint-stop | M5 | USD_JPY | median stop <15 pips; expectancy negative; <20 trades |
| 3 | Donchian midpoint-stop | M15 | USD_JPY | same as cell 2 |
| 4 | Trend-origin pullback | H1 | USD_JPY | expectancy negative; <15 trades |
| 5 | Trend-origin pullback | H4 | USD_JPY | expectancy negative; <8 trades (H4 frequency allowance) |
| 6 | Stat-arb (rolling-90 OLS — the validated Phase-2 chassis) | H4 estimation | EUR_USD/GBP_USD | spread half-life unstable (>3x M-cell baseline); expectancy negative |
| 7 | Stat-arb (rolling-90 OLS — the validated Phase-2 chassis) | H4 estimation | NZD_USD/USD_CAD | same as cell 6 |
| 8 | Stat-arb (rolling-90 OLS — the validated Phase-2 chassis) | Daily estimation | EUR_USD/GBP_USD | <10 round-trip trades in 2023 → skip to 2021–2023 window before judging; expectancy negative |
| 9 | Stat-arb (rolling-90 OLS — the validated Phase-2 chassis) | Daily estimation | NZD_USD/USD_CAD | same as cell 8 |

**Closure rule:** a cell that fails its quick-check closes permanently for that mechanism × timeframe × pair combination. Reopening bar: structurally different stop or estimation mechanism only.

**Prop overlay:** passport survivors run prop_rules.py against all four encoded presets; results go to the passport's prop-compatibility row. No new presets encoded unless a specific firm becomes relevant (existing policy).

**Registration notes (pre-run, part of the registration):** (a) Cells 4–5 use the pullback mechanism currently on probation at M30; the grid tests whether the mechanism has life at higher timeframes. If the M30 probation ends in retirement, that is evidence AGAINST the H1/H4 cells, not grounds to skip them — run them anyway and let the numbers speak. (b) Cells 8–9 will be sample-starved in a single year; their kill criteria pre-authorize extending to 2021–2023 — that extension is part of this registration, not a post-hoc adjustment.

**Amendment 2026-07-03 (pre-run — correction, not tampering):** cells 6–9's mechanism amended from "rolling-90 Kalman" to "rolling-90 OLS — the validated Phase-2 chassis." Reason: the grid's purpose is timeframe-testing the VALIDATED design, and "Kalman" was drafting shorthand that named the wrong estimator (Kalman was Phase 1's non-discriminating test estimator, not the Phase-2 trading chassis). Caught and corrected before any cell ran, per the correction-vs-tampering line. The registration is FINAL as of this amendment; zero cells have run.

**Lesson note (2026-07-03, post-adjudication observation — not a registration change):** quick-check passes are maximally uninformative for mechanisms whose edge concentrates in the check year itself — cell 1, July 2026, is the reference case (2023 quick-check passed on +$15/trade expectancy; the full window showed the single 2023-short cell exceeding the entire six-year net, ex-cell −$299; see RESEARCH_LOG 7913943).

**Pre-run interpretation note for cells 6–7 (2026-07-03, committed BEFORE either cell ran):** the registered kill criterion "spread half-life unstable (>3x M-cell baseline)" is operationalized as follows. **(a) Baselines** — deterministic recompute of the Phase-2 daily rolling-90 OLS spread (the validated chassis code path: `spread_signal.rolling_beta_spread` on daily log closes, 2021-01-01→2026-07-01), AR(1) half-life on the demeaned spread: **EUR_USD/GBP_USD = 12.1 trading days (292h); NZD_USD/USD_CAD = 16.2 trading days (389h).** **(b) H4 computation** — identical rolling-90 OLS estimator on H4 log closes (90 H4-bar window, the registered chassis at H4 granularity); AR(1) half-life on the demeaned 2023 spread (90-bar warm-up excluded), expressed in H4 bars and converted ×4 to HOURS, so the comparison is in calendar time across granularities. **(c) Numeric thresholds** — unstable iff HL(H4) exceeds 3× the pair's baseline: **cell 6 kill above 875 hours (≈219 H4 bars); cell 7 kill above 1,167 hours (≈292 H4 bars).** Expectancy criterion unchanged (2023 trades under the Phase-2 z-rules at H4: entry 2.0 / exit 0.5 / stop 3.5, $80 trade-idea risk, two-leg costs included).

## Frozen validator (instituted 2026-07-11)

**Passport and adjudication numbers only count when produced by the frozen validator** — `validate.py` run from the clean, tagged clone at `D:\workspace\rhyme_validator` (`validator-v1` at institution). The script self-verifies (clean tree + exact `validator-*` tag) and refuses otherwise; no override exists. Dev-tree runs are exploration ("pitch, not evidence"); kill-test KILLS from the dev tree still count. Validator upgrades require: regression suite pass, a new `validator-vN` tag, a dated note stating what changed and why, and fast-forwarding the clone — a mid-adjudication validator change voids that adjudication's in-flight runs. Rationale and honesty notes: RESEARCH_LOG 2026-07-11 adoption entry.

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
