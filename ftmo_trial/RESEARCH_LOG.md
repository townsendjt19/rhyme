# FTMO Trial Forward Test — Observation Log

**FTMO-TRIAL EXPERIMENT OBSERVATION ONLY.** This log belongs to the FTMO
free-trial forward test (`ftmo_gold_bot.py`, demo account 1600158217 on
OANDA-Demo-1). It is NOT a fleet research document: never referenced by the
fleet's RESEARCH_LOG.md validation pipelines, GOVERNANCE.md roster, or
audit_governance.py. The governing registration (purpose, mechanics, guards,
what does NOT get concluded) lives in the main RESEARCH_LOG.md, dated
2026-07-09 — this file records only what is observed.

---

## 2026-07-09 — Deployment facts (day zero)

- Built at fleet commit `eed1d54`; 9/9 boundary-mocked unit tests passed,
  including the real-plugin enrichment seam test (mock at the MT5 boundary,
  run the actual `generate_signal` on `fetch_frame` output).
- Isolation verified by grep: not in `RESEARCH_ACCOUNTS`, invisible to
  `portfolio_state.py` and `audit_governance.py`; no scheduler task by design
  (manual WMI launch — a host outage is a test outage, accepted cost, same
  as the personal-live experiment).
- Dry-run launch 03:11 EDT (PID 21588): connected to 1600158217 @
  OANDA-Demo-1 (demo assert passed), equity $100,000.00, one clean scan
  cycle ("no signal"), correct M30 alignment. Stopped, stale pidfile
  removed.
- **Armed launch 03:12:36 EDT via WMI `Win32_Process Create`** (the
  detached-launch method verified 2026-07-09 on the personal-live bot):
  PID 26608 matching fresh pidfile, ARMED banner, equity $100,000.00,
  first cycle clean.
- **Survival past the first M30 boundary verified natively:** the 03:30:05
  cycle ran on schedule (scan clean, no signal), process alive at 03:31:30,
  next wake 04:00:05. Zero orders placed to date.
- Connection dependency noted: the OANDA MT5 terminal (GUI session the
  operator opened at ~02:44 EDT) holds the platform session. The bot's
  attach targets the same terminal path; if the terminal is closed, the
  next cycle's API calls will error visibly in this log (`cycle error`) —
  watch for that signature rather than silence.

## 2026-07-09 ~04:15 — Multi-slot deployment (campaign Track 2) + THREE mechanics findings in the first 4 minutes

Bot refactored to 2 slots (xau both-directions, jpy long-only = pullback30's
probation variant), fleet commit 877ba18, 11/11 tests. The first armed
cycles immediately produced exactly the class of findings this phase exists
for:

1. **Sizing bug (fails-safe): contract-size formula wrong for non-USD-quoted
   symbols.** First jpy scan found a LONG signal and sized it to ZERO —
   1 lot × 1.0 USDJPY move is 100,000 JPY (~$680), not $100,000; the formula
   undersized ~146×. Fixed to tick economics (`trade_tick_value /
   trade_tick_size`, account currency, universal); test added with
   JPY-shaped fake symbol economics. Gold was never affected (USD-quoted).
2. **Order filling mode: this server accepts FOK only.** First armed jpy
   order rejected retcode 10030 (Unsupported filling mode) on hardcoded IOC.
   Fixed: filling mode chosen from `symbol_info.filling_mode` flags
   (both .sim symbols report FOK-only).
3. **Order-result price field is 0.0 on this server** — real fill price
   lives on the opened position; logging falls back accordingly.

**First live fill (04:18:54 EDT): jpy slot, order 39294746 — LONG 1.07 lots
USDJPY.sim @ 162.327, SL 161.597 / TP 164.229 resting broker-side, spread at
entry 0.003 (0.3 pips), realized risk ~$515 ≈ 0.5%.** Position verified
directly on the account (`positions_get`), tagged `ftmo_trial_jpy`. Current
process PID 4124 (restart sequence 26936 → 28048 → 7292 → 4124 as the fixes
landed; each restart re-verified; zero positions were held during restarts
except the final one, which holds the jpy position — restarts never touch
open positions by design).

## 2026-07-09 ~04:44 — THIRD SLOT (spx) deployed; second live fill on its first cycle

Campaign Tracks 1+3 complete (fleet commit 6a9d564): US500 × trend-origin
pullback validated same-night (Gate 2 pass, cleanest factor-overlap profile
on the map, trailing pre-check `proceed`) and added as the `spx` slot. Bot
restarted as a 3-slot process, PID 29452.

**Second live fill (04:44:03 EDT): spx slot, order 39295348 — SHORT 12.90
lots US500.sim @ 7508.9, SL 7553.7 / TP 7419.0, slippage 0.000, spread at
entry 0.5 index points (exactly the cost-gate median).** Mechanics note:
price moved 6.3 points between the M30-close signal (~7515.2) and the
market fill (7508.9), so realized risk from fill is ~$578 vs the $500 sized
at signal — signal-to-fill drift on market orders is now a measured
quantity, worth tracking across fills.

Account state after both fills: 2 open positions (jpy +$21.75, spx −$12.90
floating), equity $100,006.17. Three slots live: xau (flat, scanning), jpy
(long, position), spx (short, position) — worst-case concurrent exposure
1.5% of initial; all pairwise weekly co-loss lifts at/below chance per the
extended factor-overlap map.

## 2026-07-09 ~15:20 — SLOTS 5–6 (ospx, oxau: ORB close-variant, M15) deployed at 0.5%; six-slot book live

Fleet commit 428d28e. Bot gains per-slot timeframes (main loop now wakes
every M15 boundary; M30 slots scan every other wake) and magic-filtered
per-slot caps (orb-xau and pullback-xau share XAUUSD.sim without blocking
each other). Aggregate cap 4. Dry-run verified (2/6 slots due on a :15
wake, both scanned clean); armed relaunch PID 23284; **native verification
at the 15:30 M30 boundary: 6/6 slots due, all scanned or correctly
self-capped (jpy and btc hold positions), next M15 wake scheduled.**
Prop-sim (6-slot book): trial P(+5%) 47.9%, challenge P(+10%) 78.9%.
ORB slots trade the close-confirmed variant; touch variants benched
pending live stop-entry slippage data.

## 2026-07-09 ~11:43 — FOURTH SLOT (btc) deployed at 0.25% risk

BTCUSD.sim × donchian (fleet commit 727ecfc) — the first non-pullback slot
and the first at reduced risk: the trailing pre-check measured −35.8% worst
trailing DD at 0.5% (twice the book's profile) vs −19.4% at 0.25%, so the
slot deploys at the pre-check's registered lower level. Bot restarted as a
4-slot process (PID 12004), all four slots scanning cleanly (jpy and spx
still holding their positions through the restart, untouched by design).
Worst-case concurrent exposure now 1.75% of initial. 11/11 tests green
(per-slot plugin files; both plugin modules covered by the isolation test).

## 2026-07-09 ~19:11 ET — SIXTH SLOT (vxau) deployed at 0.5% risk

XAUUSD.sim x volatility-compression breakout (Campaign 2 Track B survivor,
fleet commit e681712) — the first genuinely new mechanism class deployed
since ORB, and the third slot on gold (xau/oxau/vxau; magic-filtered caps
are the isolation). Operator rationale: forward information — at ~2.7
trades/month the trial-window sample will be small; the record accrues for
the paid-challenge decision. Marks-bound pre-check −6.19% at 0.5% (proceed).
Bot restarted as a 6-slot process (banner PID 14812), all six slots scanning
cleanly on the first ARMED cycle (jpy and spx holding positions through the
restart, untouched by design). Aggregate cap stays 4 (worst-case concurrent
exposure 2.0% of initial). 16/16 tests green (volcomp seam covered:
breaking-close levels, re-entry guard, missed-break flat). Prop-sim 6-slot
book: challenge 79.0% / breach 12.3%; trial-13d 44.4%. Watch item: first
gold fill (any gold slot) confirms the assumed ~$2.50/side commission.

## 2026-07-10 ~10:01 ET — SEVENTH SLOT (gap) deployed at 0.5% + first TIMED-EXIT capability

EURUSD.sim x weekend-gap continuation (Campaign 6, fleet commit 512a0be) —
the first FX addition since jpy, the cleanest overlap profile on the map
(lifts 0.59-1.11x vs the entire roster), and the bot's first timed-exit
slot: entries only Monday 03:00-03:30 ET, position force-closed at 16:00 ET
Monday (every-wake pre-guard pass; downtime recovery closes at first wake).
Bot restarted as a 7-slot process (PID 31280). Deployment context, recorded
honestly: the daily circuit breaker is TRIPPED at relaunch (server-day P&L
~-$2,100 after the overnight stop-outs) — the bot armed correctly into the
halt state; entries resume at the 00:00 EET reset (~17:00 ET). Equity
$97,214 (-2.8% from initial; floor guard 4.5% away). 19/19 tests. Prop-sim
7-slot book: challenge 79.4% / breach 11.9%; trial-13d 44.8%. First gap
trade expected Monday 2026-07-13 ~03:00 ET.

## 2026-07-10 ~12:41 ET — EIGHTH SLOT (tl) deployed at 0.5%

USDJPY.sim x trendline-break (fleet commit 5b87b0c) — the first slot
adjudicated entirely under the capture-rate framework: record/greedy/queued
= +$51.1k/+$11.1k/+$44.0k, deployed because the book improves at BOTH
decision bounds (lower 49.4->59.5%, upper 81.1->96.5%). Expected to become
the book's most active slot (~1-1.5 trades/day live) and the richest
shadow-scan r data source. Bot restarted as an 8-slot process (PID 22740),
8/8 due on first cycle, breaker still correctly halting entries until the
EET reset. 20/20 tests.

## 2026-07-10 ~13:16 ET — MIXED-K capture engineering live (fleet commit fa0cb6a)

spx now runs up to 3 concurrent positions at 0.167% each, tl up to 2 at
0.25% each (slot totals unchanged at 0.5%); aggregate backstop 4 -> 11
(exposure control moved to per-slot caps). Derived from the k-cap study's
pre-stated per-record rule; pessimistic-bound book odds 59.7% -> 68.8%,
breach 10.3% -> 3.3%. Bot restarted (PID 25712), 21/21 tests, breaker still
correctly holding entries until the EET reset.

## 2026-07-13 — WATCH ITEM CLOSED: metals commission measured off real gold fills

Seven XAUUSD.sim deals (2026-07-10 → 07-13, both oxau round-trips, the xau entry+SL close, the vxau entry): commission **$2.76–$2.87/side/lot, mean ≈ $2.83** vs the assumed $2.50/side — 13% higher, same order. Impact: ~5.7 pips-equivalent RT on gold (inside every XAU pass margin; original cost gate priced 37p total) and ~1.13 pips-equivalent on silver at its $5/pip/lot real value (the XAG validation registered 1.0p; the 0.13p delta is ~0.05% of the median stop — no verdict moves). Deal history also confirms the ledger: oxau #1 −$482.54 (SL, +0.5p favorable slippage), xau long −$464.40 + −$3.83 swap (SL 4049.94), oxau #2 **+$781.32** (TP filled 3990.50, better than the 3991.18 target). No fill anomalies; broker-side SL/TP execution is behaving as modeled.

## 2026-07-13 ~20:21 ET — MARGIN GUARD deployed (challenge-prep registration; commit a358af8); armed relaunch verified

Pre-trade margin guard live: entries capped at 50% total margin utilization of current equity (downsize to step / skip below volume_min; entries-only; fail-closed; venue-rate-agnostic via order_calc_margin — rehearses at OANDA demo rates now, enforces FTMO Swing rates on the challenge account unchanged). Tests 28/28 before relaunch. Old process (PID 22512) stopped by operator authorization; armed WMI relaunch → PID 4768 matching fresh pidfile, ARMED banner, equity $97,269.13, clean first scan 20:21, **native verification past the 20:30 M30 boundary: 6/6 slots scanned, next M15 wake scheduled.** Open positions (spx 39388826, vxau 39382769) unaffected (broker-side SL/TP).
