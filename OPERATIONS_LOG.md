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

---

## 2026-07-02 — Power loss / unplanned reboot; fleet self-recovered via scheduler

**Outage window:** last pre-crash log activity 14:30:07 EDT (scalp30/pullback30's 14:30 cycles completed normally; intraday's last cycle 14:00:08); system boot 14:51:15 EDT; all three bots re-launched by their logon-triggered scheduled tasks with the staggered delays, first banners 14:52:49-14:53:38 EDT. **Trading gap: ~23 minutes** (14:30 to 14:53), spanning at most one M30 candle boundary.

**Recovery was fully automatic — no manual intervention:** the S4U processes died with the power; at logon the tasks fired and main.py's stale-pidfile guard handled the leftover pidfiles exactly as designed, logging "Stale pidfile (PID <old>, mode=<mode>) no longer alive — removing" for all three modes before starting cleanly with fresh PIDs (intraday 5184, scalp30 24364, pullback30 27484 — all matching pidfiles, all Session 0, commit ab52347).

**Positions:** both open -002 positions (trade 46 GBP_USD long, trade 50 AUD_JPY short) were protected by standing broker-side SL/TP throughout and are intact and correctly tracked in the first post-crash cycles. -001 was flat.

**Collateral:** the two range_fade v2 full-window background backtests (USD_CAD, USD_JPY) died with the machine — relaunched from scratch (see RESEARCH_LOG; backtests are deterministic, no data loss beyond compute time).

**This validates the crash-recovery design end-to-end** (logon triggers + staggered delays + stale-pidfile guard + broker-side position management): the first real power-loss event cost ~23 minutes of scanning and zero manual steps.

---

## 2026-07-03 — Token regeneration requires a coordinated fleet restart, not just an .env edit

Regenerating the OANDA v20 token (done to grant access to the new -003 sub-account) instantly revoked the old token — which the three running bots still held IN MEMORY, having read .env once at startup. Editing .env fixes nothing for running processes: every bot keeps failing with 401s until restarted. Sequence that works: update .env FIRST, then restart the whole fleet in one pass (schtasks /end does NOT kill the python descendants under S4U — an elevated Stop-Process is required — then schtasks /run, staggered, verify banners). Positions were never at risk (broker-side SL/TP are independent of API auth), but scanning stops fleet-wide the moment the old token dies. **The trap generalizes: ANY token regeneration, for any reason, is a fleet-restart event — plan it as one.**

---

## 2026-07-03 — OANDA practice 401 flakiness, THIRD occurrence: addendum per the standing pre-commitment

Overnight (top-of-hour cycles ~05:00-08:00 EDT), all three main.py bots logged intermittent 401 "Insufficient authorization" on account summaries and occasional candle fetches, self-recovering by the 08:30/09:00 cycles with no restart and no token change (the same token succeeded in adjacent requests and works on demand). Prior occurrences: 2026-07-01 ~17:00 and ~23:00 EDT — also top-of-hour. Pattern across all three: transient, clustered at :00 cycles when three bots fire ~18 near-simultaneous requests on one token, never persistent, never affecting spread2b's off-hour (:16) cycles. Working read: OANDA practice-host flakiness under concurrent request bursts, NOT a credential problem — distinguish it from a real token event by (a) adjacent successes on the same token and (b) recovery without restart; a REAL revocation fails every request until the fleet restarts (see 2026-07-03 token entry above). All gates failed open as designed; no trades were affected; positions are broker-side protected regardless. No code change: the fail-open convention is the correct handling. If bursts worsen, the cheap mitigation is offsetting the bots'' cycle alignment by a few seconds (already partially true via startup stagger).

---

## 2026-07-04 — Double power-loss reboot (suspected USB-induced overdraw); fleet self-recovered via scheduler, second and third real crash events

**Outage window:** two back-to-back unexpected shutdowns early morning (System event log IDs 41/6008): first crash at 04:11:34 EDT, reboot ~04:16:09; second crash shortly after, final boot 04:27:06. The event log's 6008 estimate places the second shutdown at 04:16:23, but spread2b's log shows a fully completed cycle at 04:19:28 during the inter-crash uptime — the 6008 timestamp is a last-dirty-flush estimate and undershoots; the second crash actually occurred between 04:19:28 and the 04:27 boot. Operator's suspected cause: power overdraw after plugging in a USB device (hardware concern, outside software scope — this makes 4 unexpected shutdowns in 3 days: 2 on 07-02, 2 today).

**Last pre-crash bot activity:** intraday/scalp30/pullback30 completed their 04:00 cycles normally; spread2b completed an hourly cycle at 04:19:28 (between the two crashes). First post-crash banners 04:29:29–04:30:20 EDT.

**Recovery was fully automatic — no manual intervention, and zero missed evaluations:** at logon the four scheduled tasks fired with their staggered delays; main.py's stale-pidfile guard logged "Stale pidfile (PID <old>, mode=<mode>) no longer alive — removing" for all four modes (old→new PIDs: intraday 5060→5772, pullback30 8520→16664, scalp30 19740→21304, spread2b 9124→8880), all starting clean on commit 2883ea7. Because the fleet was back up by 04:29–04:30, scalp30 and pullback30 ran their 04:30:05 M30 cycle *on time* — no candle boundary was missed at all (intraday's next H1 cycle was 05:00; spread2b resumed its hourly cadence at 04:30). Verified post-restart: all four pidfiles match live python.exe PIDs (tasklist), all four `\Rhyme\*` scheduler tasks report Running, startup banners show correct plugin/pairs/commit.

**Positions:** scalp30's open GBP_USD long (trade on -002, +$61.60 unrealized at restart) was protected by its standing broker-side SL/TP throughout and is intact and correctly tracked in the first post-crash cycle. Other accounts flat.

**Reading:** the crash-recovery design (logon triggers + staggered delays + stale-pidfile guard + broker-side position management) has now survived three real power-loss events (07-02 ×1 recovery cycle, 07-04 ×1 covering a double crash) — this one at literally zero trading cost. The recurring hardware instability itself is the open item, and it is an operator/hardware matter (PSU load / USB device), not a software one.
