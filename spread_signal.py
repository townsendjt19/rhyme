"""
Spread signal computation for the stat-arb 2B strategy (NZD_USD / USD_CAD).

Ported verbatim from the Phase 2 kill-test mechanics (pre-registration
1149237): rolling-90 OLS adaptive beta on daily log closes, z-score of the
spread vs its own rolling-90 mean/std. Constants CHOSEN NOT TUNED; any change
is a new pre-registration.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from data import fetch_candles

ROLL_W = 90
Z_ENTRY = 2.0
Z_EXIT = 0.5
Z_STOP = 3.5
HISTORY_DAYS = 420   # calendar fetch window: comfortably > 2x ROLL_W trading days


def daily_log_closes(pair: str, now: datetime | None = None) -> pd.Series:
    now = now or datetime.now(timezone.utc)
    df = fetch_candles(pair, "D", from_time=now - timedelta(days=HISTORY_DAYS), to_time=now)
    s = np.log(df["close"])
    s.index = s.index.normalize()
    return s


def rolling_beta_spread(y: pd.Series, x: pd.Series, w: int = ROLL_W):
    """Rolling-window OLS beta/alpha spread — identical to the Phase 1/2 code."""
    beta = pd.Series(index=y.index, dtype=float)
    alpha = pd.Series(index=y.index, dtype=float)
    for i in range(w - 1, len(y)):
        ys, xs = y.iloc[i - w + 1: i + 1], x.iloc[i - w + 1: i + 1]
        b = np.cov(ys, xs)[0, 1] / np.var(xs)
        a = ys.mean() - b * xs.mean()
        beta.iloc[i] = b
        alpha.iloc[i] = a
    spread = (y - alpha - beta * x).dropna()
    return spread, beta.dropna()


def current_signal(pair_y: str, pair_x: str, now: datetime | None = None) -> dict:
    """Signal state from the latest COMPLETED daily closes."""
    y, x = daily_log_closes(pair_y, now), daily_log_closes(pair_x, now)
    panel = pd.concat([y, x], axis=1, keys=["y", "x"]).dropna()
    y, x = panel["y"], panel["x"]
    spread, beta = rolling_beta_spread(y, x)
    mu = spread.rolling(ROLL_W).mean()
    sd = spread.rolling(ROLL_W).std()
    z = ((spread - mu) / sd).dropna()
    t = z.index[-1]
    return {
        "asof": t, "z": float(z.iloc[-1]), "beta": float(beta.iloc[-1]),
        "sigma": float(sd.iloc[-1]), "mu": float(mu.iloc[-1]),
        "alpha_spread_last": float(spread.iloc[-1]),
        "y_close": float(np.exp(y.iloc[-1])), "x_close": float(np.exp(x.iloc[-1])),
    }


def live_z(sig: dict, y_mid: float, x_mid: float) -> float:
    """Spec 1a pre-flight staleness check: z recomputed with live mids as the
    current observation, against the close-based mu/sd/beta. Same 2.0
    threshold applies at the moment of commitment — no new constant."""
    live_spread = sig["alpha_spread_last"] + (np.log(y_mid) - np.log(sig["y_close"])) \
        - sig["beta"] * (np.log(x_mid) - np.log(sig["x_close"]))
    return float((live_spread - sig["mu"]) / sig["sigma"])
