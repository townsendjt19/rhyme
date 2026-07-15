"""
Indicator mega-screen (registered 2026-07-15, commit 2c7adba, BEFORE results).
12 momentum/trend/breakout families x 5 cost-floor-surviving cells = 60
quick-check cells; grid kill criteria verbatim. Textbook-default constants.

Run:  D:/workspace/rhyme/venv/Scripts/python.exe D:/workspace/rhyme/megascreen_killtest.py [full FAMILY:INSTRUMENT:TF ...]
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import backtest
import risk
from strategy import Signal
from gate2_killtest import mt5_fetch_candles

HERE = Path(__file__).parent
QUICK = (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc))
FULL = (datetime(2021, 12, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc))
FIXED_RISK = 80.0
TAIL = 260          # bars needed by the slowest family (aroon 25, trix 15-EMA x3)

# (source, mode, pip_size, pip_value, spread_pips) -- standing conventions
CELLS = {
    ("USD_JPY", "M30"): ("oanda", "scalp30", 0.01, None, 0.9),
    ("XAUUSD", "M30"): ("mt5", "scalp30", 0.01, 0.10, 30.0),
    ("XAUUSD", "M15"): ("mt5", "scalp", 0.01, 0.10, 30.0),
    ("SPX", "M30"): ("mt5", "scalp30", 0.10, 0.10, 5.0),
    ("XAGUSD", "M30"): ("mt5", "scalp30", 0.001, 0.10, 10.5),
}


def _atr(df, n=14):
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - df["close"].shift()).abs(),
                    (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def _wma(s, n):
    w = np.arange(1, n + 1)
    return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def _hma(s, n):
    return _wma(2 * _wma(s, n // 2) - _wma(s, n), int(np.sqrt(n)))


def _tema(s, n):
    e1 = _ema(s, n); e2 = _ema(e1, n); e3 = _ema(e2, n)
    return 3 * e1 - 3 * e2 + e3


def _kama(s, n=10, fast=2, slow=30):
    change = (s - s.shift(n)).abs()
    vol = s.diff().abs().rolling(n).sum()
    er = (change / vol).fillna(0.0)
    sc = (er * (2 / (fast + 1) - 2 / (slow + 1)) + 2 / (slow + 1)) ** 2
    out = s.copy().astype(float)
    vals, scv = s.values.astype(float), sc.values
    for i in range(1, len(vals)):
        out.iloc[i] = out.iloc[i - 1] + scv[i] * (vals[i] - out.iloc[i - 1])
    return out


def _supertrend(df, n=10, mult=3.0):
    atr = _atr(df, n)
    mid = (df["high"] + df["low"]) / 2
    ub, lb = mid + mult * atr, mid - mult * atr
    st = pd.Series(index=df.index, dtype=float)
    dirn = pd.Series(index=df.index, dtype=float)
    fu, fl, d = ub.iloc[0], lb.iloc[0], 1
    for i in range(len(df)):
        u, l, c = ub.iloc[i], lb.iloc[i], df["close"].iloc[i]
        fu = min(u, fu) if i and df["close"].iloc[i - 1] <= fu else u
        fl = max(l, fl) if i and df["close"].iloc[i - 1] >= fl else l
        if c > fu:
            d = 1
        elif c < fl:
            d = -1
        st.iloc[i], dirn.iloc[i] = (fl if d == 1 else fu), d
    return st, dirn


def _psar(df, af0=0.02, afmax=0.2):
    h, l = df["high"].values, df["low"].values
    sar = np.zeros(len(df)); dirn = np.zeros(len(df))
    up, af, ep, s = True, af0, h[0], l[0]
    for i in range(1, len(df)):
        s = s + af * (ep - s)
        if up:
            if l[i] < s:
                up, s, ep, af = False, ep, l[i], af0
            elif h[i] > ep:
                ep, af = h[i], min(af + af0, afmax)
        else:
            if h[i] > s:
                up, s, ep, af = True, ep, h[i], af0
            elif l[i] < ep:
                ep, af = l[i], min(af + af0, afmax)
        sar[i], dirn[i] = s, 1 if up else -1
    return pd.Series(sar, df.index), pd.Series(dirn, df.index)


def _state(df, family):
    """Per-bar state series in {+1,-1,0} and optional native stop series."""
    c = df["close"]
    if family == "supertrend":
        st, d = _supertrend(df); return d, st
    if family == "psar":
        s, d = _psar(df); return d, s
    if family == "keltner":
        mid = _ema(c, 20); band = 2 * _atr(df, 10)
        d = pd.Series(0, index=df.index)
        d[c > mid + band] = 1; d[c < mid - band] = -1
        return d.replace(0, np.nan).ffill().fillna(0), pd.concat(
            [mid - band, mid + band], axis=1)
    if family == "bollinger":
        mid = c.rolling(20).mean(); sd = 2 * c.rolling(20).std()
        d = pd.Series(0, index=df.index)
        d[c > mid + sd] = 1; d[c < mid - sd] = -1
        return d.replace(0, np.nan).ffill().fillna(0), pd.concat(
            [mid - sd, mid + sd], axis=1)
    if family == "aroon":
        n = 25
        up = df["high"].rolling(n + 1).apply(np.argmax, raw=True) / n * 100
        dn = df["low"].rolling(n + 1).apply(np.argmin, raw=True) / n * 100
        return pd.Series(np.where(up > dn, 1, -1), df.index), None
    if family == "vortex":
        n = 14
        tr = _atr(df, 1) * 1.0
        vp = (df["high"] - df["low"].shift()).abs().rolling(n).sum()
        vm = (df["low"] - df["high"].shift()).abs().rolling(n).sum()
        trs = pd.concat([df["high"] - df["low"],
                         (df["high"] - df["close"].shift()).abs(),
                         (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1).rolling(n).sum()
        return pd.Series(np.where(vp / trs > vm / trs, 1, -1), df.index), None
    if family == "cci":
        tp = (df["high"] + df["low"] + df["close"]) / 3
        ma = tp.rolling(20).mean()
        md = (tp - ma).abs().rolling(20).mean()
        cci = (tp - ma) / (0.015 * md)
        d = pd.Series(0, index=df.index); d[cci > 100] = 1; d[cci < -100] = -1
        return d.replace(0, np.nan).ffill().fillna(0), None
    if family == "trix":
        t = _ema(_ema(_ema(c, 15), 15), 15).pct_change()
        return pd.Series(np.where(t > 0, 1, -1), df.index), None
    if family == "hma":
        return pd.Series(np.where(_hma(c, 9) > _hma(c, 21), 1, -1), df.index), None
    if family == "tema":
        return pd.Series(np.where(_tema(c, 9) > _tema(c, 21), 1, -1), df.index), None
    if family == "kama":
        return pd.Series(np.where(c > _kama(c), 1, -1), df.index), None
    if family == "cmo":
        n = 14
        d1 = c.diff()
        su = d1.clip(lower=0).rolling(n).sum(); sd = (-d1.clip(upper=0)).rolling(n).sum()
        cmo = 100 * (su - sd) / (su + sd)
        d = pd.Series(0, index=df.index); d[cmo > 40] = 1; d[cmo < -40] = -1
        return d.replace(0, np.nan).ffill().fillna(0), None
    raise ValueError(family)


FAMILIES = ["supertrend", "psar", "keltner", "bollinger", "aroon", "vortex",
            "cci", "trix", "hma", "tema", "kama", "cmo"]


def make_plugin(family):
    def generate_signal(instrument, htf_df, ltf_df, mode):
        df = ltf_df.iloc[-TAIL:]
        if len(df) < TAIL:
            return None
        state, native = _state(df, family)
        if len(state) < 2 or state.iloc[-1] == 0 or state.iloc[-1] == state.iloc[-2]:
            return None                      # signal only on the flip bar
        dirn = int(state.iloc[-1])
        entry = float(df["close"].iloc[-1])
        if native is not None:
            lvl = native.iloc[-1]
            sl = float(lvl if np.isscalar(lvl) or isinstance(lvl, (int, float))
                       else (lvl.iloc[0] if dirn == 1 else lvl.iloc[1]))
        else:
            sl = entry - dirn * 1.5 * float(_atr(df, 14).iloc[-1])
        if (dirn == 1 and sl >= entry) or (dirn == -1 and sl <= entry):
            return None
        tp = entry + dirn * 2.5 * abs(entry - sl)
        return Signal(direction="long" if dirn == 1 else "short",
                      entry_price=entry, stop_loss=sl, take_profits=[tp] * 3,
                      instrument=instrument, timeframe="X",
                      reason=f"megascreen_{family}")
    generate_signal.WARMUP_HTF_CANDLES = 30
    return generate_signal


def main():
    args = sys.argv[1:]
    full = args and args[0] == "full"
    only = set(args[1:]) if full else set(args)
    backtest.TF_MAP.setdefault("scalp30", ("H4", "M30"))
    for (inst, tf), (src, mode, ps, pv, _sp) in CELLS.items():
        if pv is not None:
            risk._PIP_SIZE[inst] = ps
            risk._PIP_VALUE_USD[inst] = pv

    from data import fetch_candles as oanda_fetch
    results = []
    for family in FAMILIES:
        for (inst, tf), (src, mode, ps, pv, spread) in CELLS.items():
            key = f"{family}:{inst}:{tf}"
            if only and key not in only:
                continue
            backtest.fetch_candles = mt5_fetch_candles if src == "mt5" else oanda_fetch
            start, end = FULL if full else QUICK
            name = f"megascreen_{family}_{inst}_{tf}_{'full' if full else '2023'}"
            print(f"\n########## {name} ##########", flush=True)
            try:
                tr = backtest.run_backtest(
                    instrument=inst, mode=mode, start=start, end=end,
                    signal_plugin=make_plugin(family), fixed_risk=FIXED_RISK,
                    spread_pips=spread, strategy_name=name)
            except Exception as e:
                print(f"  CELL ERROR: {e}", flush=True)
                continue
            tr.to_csv(HERE / f"{name}.csv", index=False)
            n = len(tr)
            net = tr["pnl"].sum() if n else 0.0
            exp = net / n if n else float("nan")
            med = (tr["entry"] - tr["sl"]).abs().median() / ps if n else float("nan")
            verdict = "KILL" if (n < 20 or exp <= 0 or med < 10 * spread) else "CLEAR"
            print(f"  RESULT {key}: n={n} net=${net:.2f} exp=${exp:.2f}/tr "
                  f"med_stop={med:.0f}p (floor {10*spread:.0f}p) -> {verdict}", flush=True)
            results.append((key, n, net, exp, verdict))

    print("\n===== SCOREBOARD =====")
    for key, n, net, exp, verdict in sorted(results, key=lambda r: -r[3] if r[3] == r[3] else 0):
        print(f"  {key:28s} n={n:5d} exp={exp:+7.2f} -> {verdict}")


if __name__ == "__main__":
    main()
