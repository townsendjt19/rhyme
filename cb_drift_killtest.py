"""
CB-decision drift extension (registered 2026-07-13 BEFORE this script):
the validated FOMC drift design transplanted verbatim to ECB (EUR_USD)
and BoE (GBP_USD). BoJ excluded at registration (no fixed release time).

Preconditions run first, per registration:
  1. calendar-verification: event-day spread spike >= 2x at the statement
     minute vs same-clock non-event control (bank fails -> cells VOID);
  2. entry-minute cost measurement (2024+ events); > 10x session norm ->
     bank closes on execution.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/cb_drift_killtest.py
"""
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import data
from campaign6_killtest import et_frame, atr20, leg, pip, RISK_USD, START, END

HERE = Path(__file__).parent

# Registered event calendars (scheduled decisions only; see registration for
# the sourcing/verification statement).
ECB = [
 "2021-01-21","2021-03-11","2021-04-22","2021-06-10","2021-07-22","2021-09-09","2021-10-28","2021-12-16",
 "2022-02-03","2022-03-10","2022-04-14","2022-06-09","2022-07-21","2022-09-08","2022-10-27","2022-12-15",
 "2023-02-02","2023-03-16","2023-05-04","2023-06-15","2023-07-27","2023-09-14","2023-10-26","2023-12-14",
 "2024-01-25","2024-03-07","2024-04-11","2024-06-06","2024-07-18","2024-09-12","2024-10-17","2024-12-12",
 "2025-01-30","2025-03-06","2025-04-17","2025-06-05","2025-07-24","2025-09-11","2025-10-30","2025-12-18",
 "2026-02-05","2026-03-19","2026-04-30","2026-06-11"]
BOE = [
 "2021-02-04","2021-03-18","2021-05-06","2021-06-24","2021-08-05","2021-09-23","2021-11-04","2021-12-16",
 "2022-02-03","2022-03-17","2022-05-05","2022-06-16","2022-08-04","2022-09-22","2022-11-03","2022-12-15",
 "2023-02-02","2023-03-23","2023-05-11","2023-06-22","2023-08-03","2023-09-21","2023-11-02","2023-12-14",
 "2024-02-01","2024-03-21","2024-05-09","2024-06-20","2024-08-01","2024-09-19","2024-11-07","2024-12-19",
 "2025-02-06","2025-03-20","2025-05-08","2025-06-19","2025-08-07","2025-09-18","2025-11-06","2025-12-18",
 "2026-02-05","2026-03-19","2026-05-07","2026-06-18"]

BANKS = {
    "ECB": {"pair": "EUR_USD", "dates": ECB, "session_norm": 0.2},
    "BOE": {"pair": "GBP_USD", "dates": BOE, "session_norm": 0.3},
}
QUICK = (pd.Timestamp("2022-01-01", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC"))
COMMISSION_P = 0.5


def statement_utc(bank: str, d: str) -> pd.Timestamp:
    """Per-event statement time in UTC via the home IANA zone."""
    if bank == "ECB":
        hh, mm = (13, 45) if d <= "2022-06-09" else (14, 15)
        local = pd.Timestamp(f"{d} {hh:02d}:{mm:02d}").tz_localize(ZoneInfo("Europe/Berlin"))
    else:
        local = pd.Timestamp(f"{d} 12:00").tz_localize(ZoneInfo("Europe/London"))
    return local.tz_convert("UTC")


def fetch_spread_window(pair: str, t0: pd.Timestamp, t1: pd.Timestamp) -> pd.DataFrame:
    from oandapyV20.endpoints.instruments import InstrumentsCandles
    from data import get_client, _dt_to_rfc3339
    req = InstrumentsCandles(instrument=pair, params={
        "granularity": "M5", "price": "MBA",
        "from": _dt_to_rfc3339(t0.to_pydatetime()), "to": _dt_to_rfc3339(t1.to_pydatetime())})
    get_client().request(req)
    rows = [(pd.Timestamp(c["time"]), float(c["ask"]["c"]) - float(c["bid"]["c"]))
            for c in req.response.get("candles", []) if c.get("complete")]
    return pd.DataFrame(rows, columns=["t", "spr"]).set_index("t")


def preconditions(bank: str, cfg: dict) -> tuple[bool, float]:
    """Returns (calendar_ok, entry_cost_pips). Measured on 2024+ events."""
    pair, ppip = cfg["pair"], pip(cfg["pair"])
    ev, ctrl, entry = [], [], []
    for d in cfg["dates"]:
        if d < "2024-01-01":
            continue
        t = statement_utc(bank, d)
        try:
            e = fetch_spread_window(pair, t - pd.Timedelta("30min"), t + pd.Timedelta("90min"))
            c = fetch_spread_window(pair, t - pd.Timedelta("7d 30min"), t - pd.Timedelta("7d") + pd.Timedelta("90min"))
        except Exception as ex:
            print(f"  {bank} {d}: spread fetch failed ({ex}) -- skipped")
            continue
        ev += list(e[(e.index >= t) & (e.index < t + pd.Timedelta("10min"))]["spr"])
        tc = t - pd.Timedelta("7d")
        ctrl += list(c[(c.index >= tc) & (c.index < tc + pd.Timedelta("10min"))]["spr"])
        entry += list(e[(e.index >= t + pd.Timedelta("60min")) & (e.index < t + pd.Timedelta("70min"))]["spr"])
    ev_p = np.median(ev) / ppip if ev else float("nan")
    ctrl_p = np.median(ctrl) / ppip if ctrl else float("nan")
    entry_p = np.median(entry) / ppip if entry else float("nan")
    spike = ev_p / ctrl_p if ctrl_p and ctrl_p == ctrl_p else float("nan")
    cal_ok = spike >= 2.0
    toxic = entry_p > 10 * cfg["session_norm"]
    print(f"  {bank}: statement-minute spread {ev_p:.2f}p vs control {ctrl_p:.2f}p -> spike {spike:.1f}x "
          f"({'CALENDAR OK' if cal_ok else 'CALENDAR VOID'}); entry-minute {entry_p:.2f}p "
          f"({'TOXIC -> execution close' if toxic else 'usable'})")
    return cal_ok and not toxic, entry_p + COMMISSION_P


def main():
    print("=== Preconditions (calendar verification + entry-cost measurement) ===")
    live = {}
    for bank, cfg in BANKS.items():
        ok, cost = preconditions(bank, cfg)
        if ok:
            live[bank] = cost
    if not live:
        print("No bank cleared preconditions -- line closes here per registration.")
        return

    print("\n=== Trade simulation ===")
    all_tr = []
    for bank, cost in live.items():
        cfg = BANKS[bank]
        pair = cfg["pair"]
        m30 = et_frame(data.fetch_candles(pair, "M30", from_time=START, to_time=END))
        m5 = et_frame(data.fetch_candles(pair, "M5", from_time=START, to_time=END))
        a = atr20(m30)
        trades, skipped = [], 0
        for d in cfg["dates"]:
            t = statement_utc(bank, d)
            imp = m5[(m5.index >= t) & (m5.index < t + pd.Timedelta("55min"))]
            if len(imp) < 5:
                skipped += 1
                continue
            move = imp["close"].iloc[-1] - imp["open"].iloc[0]
            et_d = imp["et_date"].iloc[0]
            av = a.get(et_d)
            if move == 0 or av is None or av != av:
                skipped += 1
                continue
            nxt = m5[m5.index >= t + pd.Timedelta("60min")]
            if nxt.empty:
                skipped += 1
                continue
            entry_t = nxt.index[0]
            exit_mask = nxt.index >= entry_t + pd.Timedelta("20h")
            end_i = int(np.argmax(exit_mask)) if exit_mask.any() else len(nxt) - 1
            bars = nxt.iloc[:end_i + 1]
            trades.append(leg(bars, 1 if move > 0 else -1, av, cost * pip(pair),
                              {"instrument": pair, "strategy": f"cbdrift_{bank.lower()}", "bank": bank}))
        df = pd.DataFrame(trades)
        df.to_csv(HERE / f"cbdrift_{bank}.csv", index=False)
        print(f"  {bank}: {len(df)} trades ({skipped} events skipped on data), cost {cost:.2f}p")
        all_tr.append(df)

    pooled = pd.concat(all_tr, ignore_index=True)
    print("\n=== Adjudication (pooled; per-bank rows are diagnostics) ===")
    for label, g in [("quick 22-23", pooled[(pooled["time"] >= QUICK[0]) & (pooled["time"] < QUICK[1])]),
                     ("full", pooled)] + [(b, pooled[pooled["bank"] == b]) for b in live]:
        n = len(g)
        net = g["pnl"].sum() if n else 0.0
        exp = net / n if n else 0.0
        wr = 100 * (g["pnl"] > 0).mean() if n else float("nan")
        print(f"  {label:12s} n={n:3d}  net={net:+9.2f}  exp={exp:+6.2f}/tr  WR={wr:.1f}%")
    q = pooled[(pooled["time"] >= QUICK[0]) & (pooled["time"] < QUICK[1])]
    kill = len(q) < 20 or q["pnl"].sum() <= 0
    print(f"\n  QUICK-CHECK VERDICT: {'KILL' if kill else 'CLEAR'} "
          f"(n={len(q)}, exp={q['pnl'].sum()/max(len(q),1):+.2f}/tr)")
    if not kill:
        yearly = pooled.set_index("time")["pnl"].resample("YE").sum()
        print("  full yearly: " + " ".join(f"{t.year}:{v:+.0f}" for t, v in yearly.items()))
        print(f"  ex-best-year: {pooled['pnl'].sum() - yearly.max():+.2f}")


if __name__ == "__main__":
    main()
