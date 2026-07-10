"""
Read-only web dashboard for the FTMO trial bot (Obsidian Gold).

Serves index.html plus six JSON endpoints on 127.0.0.1 only. Never touches
MT5 and never writes anything the bot reads: inputs are the bot's own
state.json / state_history.ndjson heartbeats, its log file, and the root
research artifacts (failure_db.json, book_prop_sim_results.json). Safe to
kill or restart at any time.

Event regexes below mirror the exact log.info format strings in
ftmo_trial/ftmo_gold_bot.py (scan_slot / cycle / main). If those messages
are ever reworded, update both sides -- unmatched lines are dropped from
the timeline and capture counts.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/dashboard_web/server.py [--port 8787]
      ... --selftest   (parse hardcoded sample lines, no server)
"""
from __future__ import annotations
import argparse
import json
import re
import threading
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
TRIAL_DIR = ROOT / "ftmo_trial"
STATE_FILE = TRIAL_DIR / "state.json"
STATE_HISTORY = TRIAL_DIR / "state_history.ndjson"
LOG_FILE = TRIAL_DIR / "ftmo_gold_bot.log"
FAILURE_DB = ROOT / "failure_db.json"
PROP_SIM = ROOT / "book_prop_sim_results.json"

# Trial display constants (dashboard-only; the bot's guards are its own)
TRIAL_START_BALANCE = 100_000.0
TRIAL_TARGET_EQUITY = 105_000.0
TRIAL_FLOOR_EQUITY = 93_000.0
TRIAL_END = "2026-07-22"

# Log timestamps are local wall clock with a spelled-out Windows zone name
# (strptime cannot consume %Z, so the name is captured and mapped here)
TZ_OFFSET_H = {"Eastern Daylight Time": -4, "Eastern Standard Time": -5}
_LOCAL_OFF_H = datetime.now().astimezone().utcoffset().total_seconds() / 3600

LINE_RE = re.compile(
    r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [AP]M) (?P<tzname>[^,]*?),"
    r"(?P<ms>\d{3}) (?P<level>\w+) (?P<msg>.*)$")

# Ordered: SHADOW before SIGNAL (substring overlap), first match wins
EVENT_RES = [
    ("shadow", re.compile(
        r"\[(?P<slot>\w+)\] >> SHADOW SIGNAL \(slot occupied, NOT traded\)\s+"
        r"(?P<direction>LONG|SHORT) (?P<symbol>\S+)\s+entry~(?P<entry>[\d.]+) sl=(?P<sl>[\d.]+)")),
    ("signal", re.compile(
        r"\[(?P<slot>\w+)\] >> SIGNAL\s+(?P<direction>LONG|SHORT) (?P<symbol>\S+)\s+"
        r"entry~(?P<entry>[\d.]+) sl=(?P<sl>[\d.]+) tp=(?P<tp>[\d.]+) lots=(?P<lots>[\d.]+)")),
    ("filled", re.compile(
        r"\[(?P<slot>\w+)\] >> FILLED\s+order=(?P<order>\d+) vol=(?P<lots>[\d.]+) @ (?P<entry>[\d.]+)")),
    ("dry_run", re.compile(r"\[(?P<slot>\w+)\] >> DRY-RUN")),
    ("timed_exit", re.compile(r"\[(?P<slot>\w+)\] >> TIMED EXIT closed (?P<lots>[\d.]+) lots")),
    ("halt", re.compile(r"-- HALT\s+(?P<guard>daily circuit breaker|floor guard): .*?\$(?P<value>-?[\d,.]+)")),
    ("rejected", re.compile(r"\[(?P<slot>\w+)\] (?:order rejected|timed-exit close REJECTED)")),
    ("startup", re.compile(r"FTMO TRIAL FORWARD TEST")),
]

_NUM_FIELDS = {"entry", "sl", "tp", "lots", "value"}


def parse_line(line: str) -> dict | None:
    m = LINE_RE.match(line)
    if not m:
        return None
    try:
        dt = datetime.strptime(m["dt"], "%Y-%m-%d %I:%M:%S %p")
    except ValueError:
        return None
    off = TZ_OFFSET_H.get(m["tzname"].strip(), _LOCAL_OFF_H)
    ts_utc = dt - timedelta(hours=off)
    msg = m["msg"].strip()
    for kind, rx in EVENT_RES:
        em = rx.search(msg)
        if em:
            ev = {"ts_utc": ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "level": m["level"], "kind": kind, "raw": msg}
            for k, v in em.groupdict().items():
                ev[k] = float(v.replace(",", "")) if k in _NUM_FIELDS else v
            return ev
    return None


_cache_lock = threading.Lock()
_log_cache: dict = {"key": None, "events": []}


def parse_log() -> list[dict]:
    """All structured events from the log, cached on (mtime, size)."""
    if not LOG_FILE.exists():
        return []
    st = LOG_FILE.stat()
    key = (st.st_mtime, st.st_size)
    with _cache_lock:
        if _log_cache["key"] == key:
            return _log_cache["events"]
    events = []
    for line in LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        ev = parse_line(line)
        if ev:
            events.append(ev)
    with _cache_lock:
        _log_cache["key"], _log_cache["events"] = key, events
    return events


def _since(events: list[dict], hours: float) -> list[dict]:
    cut = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
           ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [e for e in events if e["ts_utc"] >= cut]


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------- endpoint handlers ----------------

def api_state(params) -> dict:
    if not STATE_FILE.exists():
        return {"state": None, "staleness_s": None, "state_file_exists": False}
    for attempt in range(2):
        try:
            state = _read_json(STATE_FILE)
            break
        except (json.JSONDecodeError, OSError):
            if attempt:                       # mid-replace race: retry once
                return {"state": None, "staleness_s": None,
                        "state_file_exists": True, "note": "state.json unreadable"}
            time.sleep(0.1)
    ts = datetime.strptime(state["ts_utc"], "%Y-%m-%dT%H:%M:%SZ")
    stale = (datetime.now(timezone.utc).replace(tzinfo=None) - ts).total_seconds()
    return {"state": state, "staleness_s": round(stale, 1), "state_file_exists": True,
            "trial": {"start_balance": TRIAL_START_BALANCE, "target": TRIAL_TARGET_EQUITY,
                      "floor": TRIAL_FLOOR_EQUITY, "end": TRIAL_END}}


def api_log_events(params) -> list[dict]:
    hours = float(params.get("hours", ["24"])[0])
    return _since(parse_log(), hours)


def api_capture(params) -> dict:
    out: dict = {}
    for e in parse_log():
        slot = e.get("slot")
        if not slot:
            continue
        c = out.setdefault(slot, {"taken": 0, "filled": 0, "shadow": 0})
        if e["kind"] == "signal":
            c["taken"] += 1
        elif e["kind"] == "filled":
            c["filled"] += 1
        elif e["kind"] == "shadow":
            c["shadow"] += 1
    for c in out.values():
        seen = c["taken"] + c["shadow"]
        c["capture_rate"] = round(c["taken"] / seen, 3) if seen else None
    return out


def api_research(params) -> dict:
    out = {"failure_db": None, "prop_sim": None}
    if FAILURE_DB.exists():
        out["failure_db"] = _read_json(FAILURE_DB)
    if PROP_SIM.exists():
        out["prop_sim"] = _read_json(PROP_SIM)
    return out


def api_equity(params) -> list[dict]:
    if not STATE_HISTORY.exists():
        return []
    rows = []
    for line in STATE_HISTORY.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            s = json.loads(line)
            rows.append({"ts_utc": s["ts_utc"], "equity": s["equity"],
                         "balance": s["balance"], "day_pnl": s["day_pnl"]})
        except (json.JSONDecodeError, KeyError):
            continue                          # torn tail line is expected
    if "hours" in params:
        cut = (datetime.now(timezone.utc).replace(tzinfo=None)
               - timedelta(hours=float(params["hours"][0]))).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = [r for r in rows if r["ts_utc"] >= cut]
    return rows


ROUTES = {
    "/api/state": api_state,
    "/api/log-events": api_log_events,
    "/api/capture": api_capture,
    "/api/research": api_research,
    "/api/equity": api_equity,
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path in ("/", "/index.html"):
            body = (HERE / "index.html").read_bytes()
            self._send(200, body, "text/html; charset=utf-8")
            return
        fn = ROUTES.get(url.path)
        if fn is None:
            self._send(404, b'{"error": "not found"}')
            return
        try:
            payload = fn(urllib.parse.parse_qs(url.query))
            self._send(200, json.dumps(payload).encode())
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}).encode())

    def _send(self, code: int, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):      # quiet: no per-request console spam
        pass


# ---------------- selftest ----------------

_SAMPLES = [
    ("2026-07-09 04:17:43 AM Eastern Daylight Time,309 INFO   [jpy] >> SIGNAL  LONG USDJPY.sim  "
     "entry~162.349 sl=161.597 tp=164.229 lots=1.07  risk $500",
     {"kind": "signal", "slot": "jpy", "direction": "LONG", "entry": 162.349,
      "lots": 1.07, "ts_utc": "2026-07-09T08:17:43Z"}),
    ("2026-07-09 04:18:54 AM Eastern Daylight Time,194 INFO   [jpy] >> FILLED  order=39294746 "
     "vol=1.07 @ 0.000 (requested 162.327, slippage -162.327, spread at entry 0.003)",
     {"kind": "filled", "slot": "jpy", "order": "39294746"}),
    ("2026-07-10 08:15:05 AM Eastern Daylight Time,008 WARNING   -- HALT  daily circuit breaker: "
     "day P&L $-2007.61 <= $-2000.00",
     {"kind": "halt", "guard": "daily circuit breaker", "value": -2007.61}),
    ("2026-01-15 04:18:54 AM Eastern Standard Time,194 INFO   [xau] >> SHADOW SIGNAL "
     "(slot occupied, NOT traded)  SHORT XAUUSD.sim  entry~4100.500 sl=4110.250",
     {"kind": "shadow", "slot": "xau", "direction": "SHORT", "entry": 4100.5,
      "ts_utc": "2026-01-15T09:18:54Z"}),          # EST = UTC-5
    ("2026-07-09 03:11:25 AM Eastern Daylight Time,709 INFO   FTMO TRIAL FORWARD TEST  "
     "(isolated; not a Rhyme fleet bot)",
     {"kind": "startup"}),
    ("2026-07-10 05:30:05 PM Eastern Daylight Time,161 INFO Next candle at ... -- sleeping 899s",
     None),                                        # non-event line -> dropped
]


def selftest() -> None:
    for line, want in _SAMPLES:
        got = parse_line(line)
        if want is None:
            assert got is None, f"expected drop, got {got}\n  {line}"
            continue
        assert got is not None, f"failed to parse:\n  {line}"
        for k, v in want.items():
            assert got.get(k) == v, f"{k}: want {v!r}, got {got.get(k)!r}\n  {line}"
    print(f"PASS: selftest ({len(_SAMPLES)} sample lines)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"rhyme dashboard  ->  http://127.0.0.1:{args.port}/   (read-only; Ctrl+C to stop)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
