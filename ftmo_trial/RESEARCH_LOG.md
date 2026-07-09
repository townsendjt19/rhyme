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
