# Rhyme — Portfolio

> **Guiding principle: Rhyme is a portfolio of independently validated market behaviors, unified by a single risk engine.**
>
> The unit of account is the *behavior* (a repeatable market phenomenon with a measured edge), not the bot. Processes, modes, and accounts are plumbing; the roster below is organized by what each strategy actually exploits.

---

## Strategy roster by market behavior

| Market behavior | Strategy / config | Pairs | Status |
|---|---|---|---|
| **Channel breakout (trend initiation)** | Donchian, intraday (H1/H4) | GBP_USD, EUR_USD, USD_JPY, AUD_JPY, EUR_JPY | **Validated, live** (account -002) |
| **Channel breakout (trend initiation)** | Donchian, scalp30 (M30/H4) | USD_JPY | **Validated, live** (account -002) |
| **Channel breakout (trend initiation)** | Donchian, swing (H4/D) | USD_CAD | **Live** (account -002) — see passport: fails several current boxes |
| **Trend pullback (continuation)** | trend-origin pullback, long-only, pullback30 (M30/H4) | USD_JPY | **Probation** (isolated account -001; 60 trades / 6 months from 2026-07-01) |
| **Mean reversion** | — | — | **Open research** — RSI crossover tested and rejected (spread-eaten); no viable candidate found yet |
| **Retracement-level confluence** | — | — | **Closed** — Fibonacci 61.8% bounce rejected as-designed and with volume-profile gating (see RESEARCH_LOG) |
| **Supply/demand zone retest** | — | — | **Blocked on architecture** — order blocks rejected due to single-pending-block starvation; requires multi-pending rebuild to revisit |
| **Session/time-of-day** | — | — | **Closed** — London breakout rejected (WR 7–22%) |
| **Volatility regime / carry / news** | — | — | **Future** — unexplored |

Note the honest concentration: three of four live strategies exploit the *same* behavior (Donchian channel breakout) at different timeframes, and their measured pairwise overlaps are extreme (see passports). The portfolio today is closer to **two** behaviors than four strategies.

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

| Box | Status | Evidence |
|---|---|---|
| 6yr spread-included | ✅ | 6,884 trades, 32.0% WR, **+$39,116.41** (per-pair per-year CSVs, 2021–2026 YTD) |
| Min-N | ✅ | Zero failures across all pair × year × direction cells |
| No single-year dependency | ⚠️ | Not year-concentrated, but **pair-concentrated: USD_JPY is +$26,406 of the +$39,116 (67%)**; the other 4 pairs average ~+$3,178 each |
| Drawdown | ❌ | Fixed-$80 curve: **-$18,057**. 1%-compounding: **-90.7% of equity** (final multiple 57.1x — enormous growth through near-total intermediate wipeout). Never computed at validation; the 1% number assumes every signal taken concurrently at 1% each, which live 1-position-per-instrument throttling prevents — but neither number was ever explicitly accepted |
| Overlap vs live | ❌→✅ | vs scalp30 on USD_JPY: **99.7% trading-day overlap, 97.3% same-direction, 0.5h median gap** — measured only after validation; the redundancy is now documented and deliberately accepted (scalp30 outperforms on the shared days; see RESEARCH_LOG "inverted conclusion") |
| Factor dependence | ⚠️ | Shared caveat: validated entirely within the 2021–2026 macro window; USD_JPY (its dominant P&L source) is long-USD-direction-carried, tying it to the long-USD hypothesis logged 2026-07-01 |
| Distinct behavior | ❌ | Same behavior as scalp30 (Donchian breakout); on USD_JPY specifically, largely the same *trades* |
| **Doc discrepancy** | ❌ | **strategies.json lists 4 pairs; the live process trades 5 (EUR_JPY included, +$3,444/6yr backtested).** Needs reconciliation |

### 2. Donchian scalp30 (M30/H4) — USD_JPY

| Box | Status | Evidence |
|---|---|---|
| 6yr spread-included | ✅ | 2,719 trades, 33.5% WR, **+$28,000.34** |
| Min-N | ✅ | Zero failures |
| No single-year dependency | ✅ | Top-5 concentration 3–9% per year; 2022 is the best year (+$15,413) but every 2021–2024 year is positive without it |
| Drawdown | ❌ | Fixed-$80 curve: **-$8,979**. 1%-compounding: **-68.9% of equity** (final multiple 23.3x). Never computed at validation; same acceptance gap as intraday. Note the -68.9% is dominated by the ongoing 2025–2026 stretch |
| Overlap vs live | ✅ (post-hoc) | vs intraday: 99.7%/97.3% (accepted — this is the stronger side of the pair); vs pullback30: 68.1% same-direction / 28.4% opposite (and now cross-account) |
| Factor dependence | ⚠️→❌ | **The "no negative years" claim in RESEARCH_LOG/strategies.json is false per the CSVs: 2025 is -$943 and 2026 YTD is -$3,324 — the two most recent periods are both negative and deteriorating.** Long-USD-direction exposure per the 2026-07-01 hypothesis. This is the portfolio's flagship and its recent trajectory is its biggest open risk |
| Distinct behavior | ❌ | Same behavior as intraday (see above); kept because it's the *better* expression of it |

### 3. Donchian swing (H4/D) — USD_CAD

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
| Overlap vs live | ✅ | vs Donchian scalp30: **68.1% same-direction / 28.4% opposite / 6.0h median gap / 62.8% long-day overlap** — measured before deployment; materially more independent than the 88.9–97.3% overlaps that killed prior candidates. (Not separately measured vs intraday's USD_JPY; intraday≈scalp30 at 97.3% makes scalp30 a fair proxy) |
| Factor dependence | ✅ | **Persistent-macro-trend dependence (supersedes the long-USD framing after the EUR_JPY probe, 2026-07-01): the profitable direction is the pair's dominant secular trend — short-yen for USD_JPY.** Falsifier restated: a sustained **yen-strengthening** stretch is the true stress test. **EUR_JPY 2025–2026 is the live preview of the failure mode: edge-to-zero, not losses** (long P&L -$9 and -$32 after four strongly positive years — HH/HL structure stops forming, so signals and P&L flatline). Note: the $1,200 drawdown early-kill will NOT catch this mode; the 6-month calendar trigger is the backstop |
| Distinct behavior | ✅ | Trend *pullback/continuation* — entry on retracement into structure with origin-anchored stop — vs the Donchians' breakout entries. The one genuinely distinct behavior added since Donchian |

---

## Pre-registered forward monitoring — Donchian modes (defined 2026-07-01, before forward data)

Forward windows start 2026-07-01. All thresholds are against each mode's own backtest baseline, computed from the validation CSVs (commit bf9d732 lineage). Deterioration is measured on the forward record only; the pre-committed actions below were decided now, not at review time. WR thresholds use each mode's worst FULL backtest year (partial 2026 noted separately). The forward "1%-sizing curve" = equity from compounding 1% risk per closed forward trade (R = pnl/$80-equivalent).

| | scalp30 (USD_JPY) | intraday (5 pairs) | swing (USD_CAD) |
|---|---|---|---|
| Backtest baseline | 33.5% WR overall; worst full year 28.5% (2025); ~494 trades/yr | 32.0% WR overall; worst full year 28.8% (2025); ~1,252 trades/yr | 33.3% WR overall; worst full year 17.9% (2025); ~41 trades/yr |
| Enters monitoring | **already ~18 months into a negative stretch** (2025 -$943, 2026H1 -$3,324 at 24.9% WR) | **already deteriorating worse than scalp30** (2026H1 -$10,866 at 22.6% WR) | pending grandfather decision (below) |
| **Review trigger** | **100 closed trades or 2026-09-15**, whichever first (short clock — deliberately ~2.5 months, not six, because of the standing negative stretch) | **300 closed trades or 2026-10-01**, whichever first (~3 months at backtest frequency) | **20 closed trades or 2026-12-01**, whichever first (~3.4 trades/month makes trade-count triggers slow; the calendar governs) |
| **Deterioration threshold** | Rolling-100-trade WR **< 28.5%** (worst full backtest year), OR forward 1%-curve drawdown **> 15%** from forward peak | Rolling-300-trade WR **< 28.8%**, OR forward 1%-curve drawdown **> 20%** from forward peak | Rolling-20-trade WR **< 26.7%** (worst full year excluding outlier-2025), OR forward 1%-curve drawdown **> 10%** |
| **Pre-committed action at review** | Forward net ≤ 0 AND rolling WR below threshold → **SUSPEND** (stop the process; position management via OANDA SL/TP continues). A second consecutive failed review after reinstatement → **RETIRE** | Forward net ≤ 0 → **REDUCE**: cut to the top-2 pairs by forward P&L. Forward net ≤ 0 AND WR below threshold → **SUSPEND** entirely. Second consecutive failure → **RETIRE** | Any threshold breach → **RETIRE** (not suspend — grandfathered status means no re-validation record exists to justify reinstatement) |
| **Early-kill (no waiting for review)** | Forward 1%-curve DD > 15% at any point → immediate SUSPEND | Forward 1%-curve DD > 20% at any point → immediate SUSPEND | Forward 1%-curve DD > 10% at any point → immediate RETIRE |

Statistical honesty note, recorded up front (same convention as pullback30's probation): at n=100, a true-33.5% process lands anywhere in ~24–43% (2σ), so a single WR breach is weak evidence alone — which is why every review action requires the conjunction with forward net P&L, and why suspension precedes retirement everywhere a validation record exists.

## Swing (USD_CAD) grandfather decision — PENDING, full record on the table

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

## Portfolio-level note: the one-behavior concern (added 2026-07-01, post-EUR_JPY probe)

Under the persistent-macro-trend reframe (see RESEARCH_LOG's EUR_JPY probe entry), **pullback30 may be the same underlying behavior as the Donchian family** — both profit by capturing persistent trends, differing only in entry mechanics (breakout vs. pullback into structure). If that reading is right, the live roster is effectively **one behavior** exploiting one 2021–2026 macro regime (yen weakness / dollar strength) through four processes. The pullback30 vs scalp30 overlap being "only" 68.1% measured the *entries*; the reframe says the *P&L source* may still be shared.

**Consequence: mean reversion (the Bot E slot) is elevated from open research to the highest-priority diversification need.** A validated mean-reversion behavior would be the first live strategy whose P&L source is structurally distinct from trend capture — the thing this portfolio does not yet have. Constraints already known for that search: candle-scale stops die to spread on this account (the RSI post-mortem and the pair sweep), so a viable mean-reversion candidate likely needs structural stops or a wide-stop pair — and the sweep's candle-scale conclusions do not price structural-stop designs (see sweep-scope nuance in RESEARCH_LOG).

## Retro-fill failure summary (things a current passport would not allow)

1. **Donchian swing USD_CAD fails boxes 1–3 outright** — +$293/6yr, 3 min-N failures, 91%/89% recent-year win concentration. It is live on grandfathered status, not current standards.
2. **Neither Donchian's max drawdown was ever computed or accepted at validation** — both exceed the live account size on the fixed-risk curve (-$18,057 intraday, -$8,979 scalp30).
3. **Scalp30's "no negative years" claim is false**: 2025 and 2026 YTD are both negative, and they are the two most recent periods.
4. **strategies.json / live-process pair-list mismatch for intraday** (4 listed vs 5 traded, EUR_JPY missing from the doc).
5. **Three of four live strategies are the same market behavior**, two of them at 97–99% measured overlap on the shared pair — the roster is behaviorally thinner than it looks.
