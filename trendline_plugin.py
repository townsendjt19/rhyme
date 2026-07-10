"""
Trendline-break plugin (registration 16e41f8, committed before results).
UP-trendline: the line through the two most recent confirmed fractal swing
lows (second higher); DOWN-trendline mirrors. Break = M30 close beyond the
projected line -> enter in the break's direction; SL at the most recent
opposing fractal; TP 2.5R; one trade per line identity (anchor pair).
Bounce arm deliberately absent (MR bar). Uses the harness's fractal
enrichment columns (fractal_high / fractal_low).
"""
from types import SimpleNamespace

RR = 2.5
_used: set = set()


def generate_signal(instrument, htf_df, ltf_df, mode="scalp30"):
    df = ltf_df
    if df is None or len(df) < 30 or "fractal_low" not in df.columns:
        return None
    bar = df.iloc[-1]
    n = len(df)

    # Code-review fix 2026-07-10: CONFIRMED fractals only (a center-of-5 mark
    # at position >= n-2 needs future bars -- look-ahead in the harness, and
    # unknowable live). Mirrors the fleet pullback plugin's confirmed_cutoff.
    conf = df.iloc[: n - 2]
    lows = conf[conf["fractal_low"].notna()]
    highs = conf[conf["fractal_high"].notna()]
    if len(lows) < 2 or len(highs) < 2:
        return None

    out = None
    # UP-trendline: two most recent swing lows, rising -> short on close below
    (t1, p1), (t2, p2) = [(df.index.get_loc(t), float(v["fractal_low"]))
                          for t, v in lows.iloc[-2:].iterrows()]
    if p2 > p1 and t2 > t1:
        key = ("up", lows.index[-2], lows.index[-1])
        slope = (p2 - p1) / (t2 - t1)
        line = p2 + slope * (n - 1 - t2)
        # First-break only (code-review fix): if an EARLIER bar since the
        # second anchor already closed below its projected line value, the
        # line is spent -- never chase (also kills restart double-entries).
        prior_break = any(float(df["close"].iloc[p]) < p2 + slope * (p - t2)
                          for p in range(t2 + 1, n - 1))
        if prior_break:
            _used.add(key)
        if key not in _used and bar["close"] < line:
            sl = float(highs["fractal_high"].iloc[-1])
            entry = float(bar["close"])
            risk = sl - entry
            if risk > 0:
                _used.add(key)
                out = SimpleNamespace(direction="short", entry_price=entry, stop_loss=sl,
                                      take_profits=[entry - RR * risk] * 3)
    if out is not None:
        return out

    # DOWN-trendline: two most recent swing highs, falling -> long on close above
    (t1, p1), (t2, p2) = [(df.index.get_loc(t), float(v["fractal_high"]))
                          for t, v in highs.iloc[-2:].iterrows()]
    if p2 < p1 and t2 > t1:
        key = ("down", highs.index[-2], highs.index[-1])
        slope = (p2 - p1) / (t2 - t1)
        line = p2 + slope * (n - 1 - t2)
        prior_break = any(float(df["close"].iloc[p]) > p2 + slope * (p - t2)
                          for p in range(t2 + 1, n - 1))
        if prior_break:
            _used.add(key)
        if key not in _used and bar["close"] > line:
            sl = float(lows["fractal_low"].iloc[-1])
            entry = float(bar["close"])
            risk = entry - sl
            if risk > 0:
                _used.add(key)
                return SimpleNamespace(direction="long", entry_price=entry, stop_loss=sl,
                                       take_profits=[entry + RR * risk] * 3)
    return None
