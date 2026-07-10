"""
HMM regime-transition trades (registration 9fb48de, committed before results).
2-state Gaussian HMM on daily log-returns, walk-forward (monthly refit,
trailing 500 completed days, day-t label from a Viterbi pass over the prefix
ending at t -- no lookahead). Transition day -> enter next open in the
flip-day's return sign; exit on opposite transition or 5 trading days;
stop 1x ATR(20d). XAUUSD + SPX, Phase A D1; costs = registered .sim spreads
(gold commission-inclusive).

Run:  venv/Scripts/python.exe hmm_transition_killtest.py
"""
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

import mt5_client

warnings.filterwarnings("ignore")
HERE = Path(__file__).parent
SYMBOLS = {"XAUUSD": 0.30, "SPX": 0.5}     # cost in price units, RT (XAU incl. ~$5 comm)
FIT_WIN, N_STATES, SEED = 500, 2, 20260710
HOLD_MAX, RISK_USD = 5, 80.0
START, END = datetime(2020, 6, 1), datetime(2026, 7, 1)
QUICK = (pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"))


def daily_states(logret: pd.Series) -> pd.Series:
    """Walk-forward filtered state labels (variance-sorted), monthly refits."""
    labels = pd.Series(index=logret.index, dtype=float)
    months = pd.PeriodIndex(logret.index, freq="M")
    model, fit_start, order = None, None, None
    for i in range(FIT_WIN, len(logret)):
        if model is None or (i > FIT_WIN and months[i] != months[i - 1]):
            fit_start = i - FIT_WIN
            X = logret.iloc[fit_start:i].values.reshape(-1, 1)
            model = GaussianHMM(n_components=N_STATES, covariance_type="full",
                                random_state=SEED, n_iter=100)
            model.fit(X)
            order = np.argsort(model.covars_.ravel())     # 0 = quiet, 1 = turbulent
        prefix = logret.iloc[fit_start:i + 1].values.reshape(-1, 1)
        raw = model.predict(prefix)[-1]
        labels.iloc[i] = int(np.where(order == raw)[0][0])
    return labels.dropna()


def simulate(symbol: str, cost: float) -> pd.DataFrame:
    d1 = mt5_client.get_history(symbol, "D", START, END)
    logret = np.log(d1["close"]).diff().dropna()
    atr = (d1["high"] - d1["low"]).rolling(20).mean()
    states = daily_states(logret)
    days = list(states.index)
    trades, i = [], 1
    while i < len(days) - 1:
        t = days[i]
        if states[t] == states[days[i - 1]]:
            i += 1
            continue
        dirn = 1 if logret[t] > 0 else -1
        a = atr.get(t)
        if a is None or a != a or a <= 0:
            i += 1
            continue
        entry_day_idx = i + 1
        entry = d1.loc[days[entry_day_idx], "open"]
        sl = entry - dirn * a
        exit_px, reason, j = None, "time", entry_day_idx
        for j in range(entry_day_idx, min(entry_day_idx + HOLD_MAX, len(days))):
            bar = d1.loc[days[j]]
            if (dirn == 1 and bar["low"] <= sl) or (dirn == -1 and bar["high"] >= sl):
                exit_px, reason = sl, "sl"
                break
            if j > entry_day_idx and states[days[j]] != states[t]:
                exit_px, reason = bar["close"], "flip"
                break
        if exit_px is None:
            exit_px = d1.loc[days[min(j, len(days) - 1)], "close"]
        r = (dirn * (exit_px - entry) - cost) / a
        trades.append({"time": days[entry_day_idx], "instrument": symbol,
                       "strategy": "hmm_transition",
                       "direction": "long" if dirn == 1 else "short",
                       "entry": entry, "sl": sl, "tp1": 0.0, "tp2": 0.0, "tp3": 0.0,
                       "units": 0, "pnl": RISK_USD * r, "balance": 0.0,
                       "exit_reason": reason, "exit_time": days[min(j, len(days) - 1)],
                       "risk_px": a})
        i = j + 1                                          # one position at a time
    return pd.DataFrame(trades)


def main() -> None:
    print("=== HMM regime-transition killtest (registration 9fb48de) ===")
    all_tr = []
    for sym, cost in SYMBOLS.items():
        tr = simulate(sym, cost)
        all_tr.append(tr)
        for label, g in [("2023", tr[(tr["time"] >= QUICK[0]) & (tr["time"] < QUICK[1])]),
                         ("full", tr)]:
            n, net = len(g), g["pnl"].sum()
            exp = net / n if n else 0.0
            kill = exp <= 0 or n < 20
            print(f"  {sym:7s} {label:5s} n={n:4d} net={net:+9.2f} exp={exp:+7.2f}/tr "
                  f"WR={100 * (g['pnl'] > 0).mean():.1f}% -> {'KILL' if kill else 'clear'}")
        yearly = tr.set_index("time")["pnl"].resample("YE").sum()
        print("    yearly: " + " ".join(f"{t.year}:{v:+.0f}" for t, v in yearly.items()) +
              f"  ex-best-year: {tr['pnl'].sum() - yearly.max():+.2f}")
    pd.concat(all_tr).to_csv(HERE / "hmm_transition_full.csv", index=False)


if __name__ == "__main__":
    main()
