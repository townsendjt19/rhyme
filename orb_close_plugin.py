"""Line B wrapper: ORB close-confirmed entry variant (registered A/B arm 1)."""
import importlib

import orb_plugin_core as core
core = importlib.reload(core)   # fresh single-use state per _load_plugin

WARMUP_HTF_CANDLES = core.WARMUP_HTF_CANDLES


def generate_signal(instrument, htf_df, ltf_df, mode):
    return core.generate_signal(instrument, htf_df, ltf_df, mode, entry_style="close")
