# Operations Log

Infrastructure, connectivity, and account-level incidents affecting the live paper-trading processes. Separate from `RESEARCH_LOG.md`, which covers strategy/signal research.

---

## 2026-07-01 — OANDA Auth Outage (401 Insufficient Authorization)

**Status: RESOLVED, self-healed, no code changes required**

### What happened

All three live paper-trading processes (swing, intraday, scalp30) began receiving `401 Insufficient authorization to perform request` errors from OANDA's practice API on account fetches (`AccountSummary` / `TradesList`). Duration varied by process cadence:

- **Intraday** (1h cycle): failed 6 consecutive cycles, 01:00–06:00 UTC (~5 hours continuous), after one successful cycle at restart.
- **Scalp30** (30min cycle): intermittent failures mixed with successes from ~01:00–04:30 UTC, then failed continuously 05:00–06:30 UTC (~2 hours continuous).
- **Swing** (4h cycle): too few cycles in the window to show a clean pattern, but was presumed equally exposed.

All three recovered on their own by their next scheduled cycle (~11:00 UTC) with no restart and no code change.

### Root cause: OANDA-side transient auth failure — confirmed, not assumed

Two alternative explanations were directly ruled out with evidence, not inference:

1. **Not a token/credential problem.** `.env` was last modified 2026-06-29 21:52 — before every process start and before the 401s began, ruling out a token swap mid-flight. A completely fresh, independent auth request (new `API` client, freshly loaded `.env`, run mid-incident while the long-running processes were still failing) **succeeded immediately**, using the identical token value. If the credential itself were expired or revoked, this fresh test would have failed too.

2. **Not a stale client connection.** `oandapyV20.API` caches one `requests.Session()` per process for its full lifetime (confirmed by reading `oandapyV20/oandapyV20.py`). A genuinely dead/stale connection raises `requests.RequestException` *before* a status code is ever received, logged as `"request %s failed [%s]"` (no status code). Every failure observed used the *other* log path — `"failed [401,{...}]"` — which only fires after a complete HTTP round trip: TCP connected, request sent, full response received, server explicitly replied "unauthorized." The connection layer worked correctly on every single failing attempt; OANDA's auth backend was the one returning the negative decision.

Conclusion: a transient OANDA practice-environment auth-service issue, external to this codebase and this account's credentials.

### Position safety during the incident

The open USD_JPY position (22,000 units, entry 162.807) remained protected throughout via its own standing stopLossOrder (162.102) and takeProfitOrder (164.146) resting directly on OANDA's books — these are independent of whether any bot process can currently poll the account, and were confirmed unaffected by direct query (both orders unmodified since the position opened, verified against full transaction history). The 401s affected only this project's ability to *observe* account state; they never affected OANDA's own order management for the position.

### Recovery

All three processes self-healed at their next scheduled cycle once OANDA's auth service stabilized, using the same long-lived connection objects the whole time (confirmed via unchanged PIDs — no process was restarted during the incident). This is direct evidence the existing retry mechanism (simply: try again at the next scheduled candle interval, no explicit backoff needed) was sufficient on its own.

### Follow-up considered and deferred

A persistent-connection reset after N consecutive auth failures was considered as a defensive addition, in case a long outage left a process pinned to a genuinely stale connection. **Not implemented** — it would address a different, unobserved failure class (true TCP-level staleness, which raises a distinct exception type per the code path above) rather than what actually happened here (server-side auth, which a connection reset cannot fix). Flagged as a theoretical risk specifically for swing's 4-hour sleep interval (the longest idle gap between requests, and therefore the most plausible candidate for an actual NAT/load-balancer idle-close) — worth revisiting only if a genuine connection-exception failure (not a 401) is ever observed in practice.

### No code changes required for this incident.
