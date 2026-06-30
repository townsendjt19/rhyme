# Archived: RSI Crossover Plugins

The files in this folder (`rsi_plugin.py`, `rsi_plugin_25r.py`, `rsi_plugin_2r.py`, `rsi_plugin_atr.py`) implement an RSI(14) crossover entry signal at various TP/exit variants (2R, 2.5R, ATR-based). They were tested across all 7 major pairs and three timeframe modes (scalp, intraday, swing) over 2021-2026.

**Result: rejected.** The strategy looked profitable under a zero-spread backtest assumption, but lost money once realistic OANDA spreads were applied retroactively. Tight stop-losses combined with fixed-dollar-risk position sizing made spread cost per trade comparable to or larger than the pre-spread edge per trade, across every pair and timeframe tested.

Kept for reference rather than deleted, in case a future revision (e.g. wider stops, volatility-scaled risk, or a spread-aware filter) revisits the underlying RSI signal.

See [../RESEARCH_LOG.md](../RESEARCH_LOG.md) for full findings, numbers, and root-cause analysis.
