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

## 2026-07-09 ~11:43 — FOURTH SLOT (btc) deployed at 0.25% risk

BTCUSD.sim × donchian (fleet commit 727ecfc) — the first non-pullback slot
and the first at reduced risk: the trailing pre-check measured −35.8% worst
trailing DD at 0.5% (twice the book's profile) vs −19.4% at 0.25%, so the
slot deploys at the pre-check's registered lower level. Bot restarted as a
4-slot process (PID 12004), all four slots scanning cleanly (jpy and spx
still holding their positions through the restart, untouched by design).
Worst-case concurrent exposure now 1.75% of initial. 11/11 tests green
(per-slot plugin files; both plugin modules covered by the isolation test).
