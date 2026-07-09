"""
Candidate #8 wrapper -- AVWAP fade on XAUUSD (registered 2026-07-09).

Delegates to avwap_fade_plugin UNMODIFIED (every design constant is #7's,
registered e211a17). This wrapper only:
  1. parameterizes the instrument: XAUUSD pip = 0.01, assumed spread =
     25 pips (real Phase B platform median);
  2. enforces the box-9 minimum stop distance (10x spread = 250 pips),
     the spec lesson logged at #7's kill.
"""
from __future__ import annotations
import importlib

import avwap_fade_plugin as core
from strategy import Signal

# Each _load_plugin() of this wrapper gets a fresh module object, but the
# core is cached in sys.modules -- reload it so per-session identity state
# never leaks between runs (same guarantee the harness gives plugins).
core = importlib.reload(core)

_XAU_PIP = 0.01
_XAU_SPREAD_PIPS = 25.0
_MIN_STOP_PIPS = 10.0 * _XAU_SPREAD_PIPS   # box 9: absolute floor, chosen not tuned

# Instrument parameterization of the unmodified core
core._ASSUMED_SPREAD_PIPS["XAUUSD"] = _XAU_SPREAD_PIPS
_orig_pip_size = core._pip_size
core._pip_size = lambda instrument: _XAU_PIP if "XAU" in instrument else _orig_pip_size(instrument)

WARMUP_HTF_CANDLES = core.WARMUP_HTF_CANDLES


def generate_signal(instrument, htf_df, ltf_df, mode) -> Signal | None:
    signal = core.generate_signal(instrument, htf_df, ltf_df, mode)
    if signal is None:
        return None
    stop_pips = abs(signal.entry_price - signal.stop_loss) / _XAU_PIP
    if stop_pips < _MIN_STOP_PIPS:
        return None   # box-9 floor: degenerate near-band entries are not trades
    return signal
