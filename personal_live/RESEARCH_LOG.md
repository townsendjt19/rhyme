# Personal Live Experiment — Observation Log

**PERSONAL-EXPERIMENT OBSERVATION ONLY.** This log belongs to the personal
live-account experiment (`personal_live_scalp.py`, live account
001-001-21728068-001). It is NOT a Rhyme research document: never referenced
by the fleet's RESEARCH_LOG.md, GOVERNANCE.md, or audit_governance.py, and
nothing in it feeds any validation pipeline.

---

## 2026-07-03 — PHASE BOUNDARY, pre-registered BEFORE any live trade results exist

At the time of writing, the experiment has placed **zero live orders** (first
armed launch was tonight; the first cycle found a pre-existing manual position
and correctly skipped). This boundary is therefore decided on zero live P&L —
logged explicitly so it can never be mistaken for a rule written after seeing
results.

**Phase 1 (current, ~$99 NAV): infrastructure and execution-mechanics
validation ONLY.** What gets observed: fills vs signal prices, slippage,
spread paid, SL/TP placement behavior, process mechanics (pidfile, cycle
timing, error handling), the one-position cap and $50 floor in practice.
**What does NOT get concluded: anything about strategy performance.** Live
P&L in this phase is explicitly meaningless for strategy inference, for two
pre-stated reasons: (a) sizing distortion — at ~$99, whole-unit sizing is
mechanically sound but the dollar amounts are microscopic and the effective
per-trade risk profile differs from every validated record; (b) sample size —
a handful of trades carries no evidential weight (the fleet's own thin-sample
standards would laugh at n<10, and Phase 1 will likely see fewer).

**Phase 2 begins when the account is funded to a threshold determined by the
feasibility checker's output** (`account_feasibility.py`, main repo — pure
analysis, no orders). At that point live strategies run at undistorted sizing
and live-vs-paper comparison becomes meaningful. The threshold is picked from
the checker's table by the operator, as an informed number — not improvised.

## 2026-07-03 — Deployment facts (Phase 1, day zero)

- Built at fleet commit `3a21bc7`; 7/7 unit tests, order placement fully
  mocked; dry-run default with `--armed` gate.
- Live-host auth verified before anything else: account 001-001-21728068-001,
  NAV $99.20 at verification, USD, api-fxtrade.oanda.com, own
  `PERSONAL_LIVE_*` credentials (fleet's practice credentials untouched).
- First armed launch ~00:42 EDT 2026-07-03 (PID 35012, console session,
  manual launch). First cycle: NAV $99.21, found a PRE-EXISTING manual
  position on the account → one-position cap correctly skipped scanning.
  That position was not placed by this experiment; the experiment's own
  record starts from the first order IT places.
- Isolation state at deployment: no scheduler task; not in
  RESEARCH_ACCOUNTS; invisible to portfolio_state, the fleet floor, and the
  audit (verified by grep across all enumeration points; see fleet commit
  3a21bc7's report).

## 2026-07-03 morning — two Phase 1 findings (exactly what this phase exists to catch)

1. **Enrichment bug — the experiment could never actually signal.** Once the
   pre-existing manual position closed overnight, every scanning cycle died
   with `cycle error: 'ema_20'`: `donchian_plugin` reads `ema_20/ema_50` off
   the HTF frame, which the fleet's pipeline adds via `add_emas` before any
   plugin call — `fetch_frame` here passed raw OHLC. Zero orders were ever at
   risk (the error fired before sizing), but the experiment was signal-blind
   from first launch until this fix. Fixed: `fetch_frame` now applies the
   fleet's exact enrichment (`add_emas(detect_fractals(df))` — pure-function
   import-surface addition, noted in the file header). New seam test mocks at
   the API boundary and runs the REAL signal function on `fetch_frame`
   output. The original suite missed this by mocking `generate_signal`
   itself — a lesson worth keeping: mock at the boundary you own, not the
   function you're integrating.
2. **Observation-log integrity: the 08:54:33 block in `personal_live.log` is
   TEST OUTPUT, not live activity.** A test run wrote its mock events
   (including a `>> FILLED ... trade_id=mock` line) into the live log because
   importing the module attaches its file handler. Disregard that block
   entirely. Fixed: the test suite strips file handlers at import; verified a
   test run no longer touches the log.

Status after fixes: manual position closed cleanly overnight (cycles moved
past the one-position cap); ZERO real orders placed to date; the running
process (PID 35012, pre-restyle, pre-fix) still errors each cycle — the
operator's planned manual restart picks up both the restyle and the
enrichment fix.
