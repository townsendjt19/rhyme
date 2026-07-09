"""Line B wrapper: ORB touch (stop-entry) variant (registered A/B arm 2).

Fill convention (registered): entry booked AT the OR level on the crossing
bar; harness resolution starts next bar -- same-bar post-touch SL hits are
unmodeled (bias direction mixed, stated in the registration).
"""
import importlib

import orb_plugin_core as core
core = importlib.reload(core)   # fresh single-use state per _load_plugin

WARMUP_HTF_CANDLES = core.WARMUP_HTF_CANDLES


def generate_signal(instrument, htf_df, ltf_df, mode):
    return core.generate_signal(instrument, htf_df, ltf_df, mode, entry_style="touch")
