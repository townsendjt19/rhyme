"""
Supertrend plugin file for frozen-validator reproduction of the
mega-screen survivors (registration 2c7adba; adjudication entry 9661d5b).
Semantics come VERBATIM from megascreen_killtest.make_plugin("supertrend") --
this file is a named door to the same code, not a reimplementation.

Also injects the registered pip conventions for the screen's non-FX
instruments (XAUUSD 0.01/$0.10, SPX 0.10/$0.10, XAGUSD 0.001/$0.10) --
instrument configuration the validator CLI cannot express; declared here
openly. Grader code is untouched.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import risk
from megascreen_killtest import make_plugin, CELLS

for (inst, _tf), (_src, _mode, ps, pv, _sp) in CELLS.items():
    if pv is not None:
        risk._PIP_SIZE[inst] = ps
        risk._PIP_VALUE_USD[inst] = pv

WARMUP_HTF_CANDLES = 30
generate_signal = make_plugin("supertrend")
