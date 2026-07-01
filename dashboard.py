"""
Forex Bot Terminal Dashboard
------------------------------
Reads all backtest_*.csv trade logs and pulls live account data from OANDA
to display a complete portfolio view in the terminal.

Usage:
    python dashboard.py                           # active strategies only (default)
    python dashboard.py --all                     # include archived strategies
    python dashboard.py --strategy rsi_plugin_25r # specific strategy only
    python dashboard.py --live                    # auto-refresh every 60 s
    python dashboard.py --live --interval 30      # custom refresh interval
    python dashboard.py --dir /path/to/logs       # custom CSV directory

Strategy config: D:/forex_bot/strategies.json
    Set "status": "active" to include in default view.
    Set "status": "archived" to hide unless --all or --strategy is passed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

load_dotenv(Path(__file__).parent / ".env")

# ── Constants ─────────────────────────────────────────────────────────────────

BOT_DIR = Path(__file__).parent
ALERT_WIN_RATE_THRESHOLD = 0.35   # flag if last-20 win rate drops below 35%
ALERT_DRAWDOWN_THRESHOLD = 0.10   # flag if drawdown from peak exceeds 10%

# GLOBAL_RISK_CAP_PCT / RISK_PCT_PER_TRADE are the canonical risk constants,
# defined once in risk.py and enforced for real in main.py's order-placement
# path. Imported here (not redefined) so the dashboard's display can never
# silently drift out of sync with what's actually enforced.
from risk import GLOBAL_RISK_CAP_PCT, RISK_PCT as RISK_PCT_PER_TRADE

# get_portfolio_state() is the single source of truth for live open-position
# state across every running bot process (reads OANDA directly, not any one
# process's in-memory view). The risk panel and the new exposure panel both
# read from the SAME PortfolioState snapshot per refresh, rather than each
# independently recomputing its own partial view of open positions.
from portfolio_state import get_portfolio_state, PortfolioState

STRATEGIES_CONFIG = BOT_DIR / "strategies.json"

# Width is auto-detected in a real terminal. Override with --width if needed.
console = Console()


# ── Strategy config ───────────────────────────────────────────────────────────

def _load_strategy_config() -> dict:
    """Load strategies.json. Returns empty dict if file is missing."""
    if not STRATEGIES_CONFIG.exists():
        return {}
    try:
        return json.loads(STRATEGIES_CONFIG.read_text())
    except Exception:
        return {}


def _active_strategies(config: dict) -> set[str]:
    """Return strategy names whose status is 'active'."""
    strats = config.get("strategies", {})
    return {name for name, meta in strats.items() if meta.get("status") == "active"}


def _archived_strategies(config: dict) -> set[str]:
    strats = config.get("strategies", {})
    return {name for name, meta in strats.items() if meta.get("status") == "archived"}


def _apply_strategy_filter(
    df: pd.DataFrame,
    config: dict,
    show_all: bool,
    only: list[str] | None,
) -> tuple[pd.DataFrame, int]:
    """
    Filter df to the requested strategies.
    Returns (filtered_df, n_hidden) where n_hidden is how many archived
    rows were dropped so the footer can report it.
    """
    if df.empty:
        return df, 0

    if only:
        # Explicit --strategy list overrides everything
        mask = df["strategy"].isin(only)
        return df[mask], 0

    if show_all:
        return df, 0

    # Default: active strategies only
    active = _active_strategies(config)
    if not active:
        # Config missing or empty — show everything rather than a blank screen
        return df, 0

    mask    = df["strategy"].isin(active)
    n_hidden = int((~mask).sum())
    return df[mask], n_hidden


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_csvs(directory: Path, source: str = "paper") -> pd.DataFrame:
    """
    Load trade CSVs from directory.

    source='paper'    — paper_trades.csv only
    source='backtest' — all backtest_*.csv files only
    source='all'      — both
    """
    frames: list[pd.DataFrame] = []

    # ── paper_trades.csv ──────────────────────────────────────────────────────
    if source in ("paper", "all"):
        paper_path = directory / "paper_trades.csv"
        if paper_path.exists():
            try:
                df = pd.read_csv(paper_path, parse_dates=["time"])
                if not df.empty:
                    if df["time"].dt.tz is None:
                        df["time"] = df["time"].dt.tz_localize("UTC")
                    else:
                        df["time"] = df["time"].dt.tz_convert("UTC")
                    if "instrument" not in df.columns and "pair" in df.columns:
                        df = df.rename(columns={"pair": "instrument"})
                    df["_source"] = "paper"
                    frames.append(df)
            except Exception:
                pass

    # ── backtest_*.csv files ──────────────────────────────────────────────────
    if source in ("backtest", "all"):
        pattern = re.compile(r"backtest_([A-Z]+_[A-Z]+)_(\w+)\.csv$")
        for csv_path in sorted(directory.glob("backtest_*.csv")):
            try:
                df = pd.read_csv(csv_path, parse_dates=["time"])
            except Exception:
                continue
            if df.empty:
                continue
            if df["time"].dt.tz is None:
                df["time"] = df["time"].dt.tz_localize("UTC")
            else:
                df["time"] = df["time"].dt.tz_convert("UTC")
            m = pattern.match(csv_path.name)
            if "instrument" not in df.columns:
                df["instrument"] = m.group(1) if m else "UNKNOWN"
            if "strategy" not in df.columns:
                df["strategy"] = m.group(2) if m else "unknown"
            df["_source"] = "backtest"
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined.sort_values("time", inplace=True)
    combined.reset_index(drop=True, inplace=True)
    return combined


def _enrich_missing_pnl(df: pd.DataFrame, state: "PortfolioState") -> pd.DataFrame:
    """
    paper_trades.csv (written by main.py's _log_trade_csv) has no
    pnl/balance/exit_reason columns -- OANDA's own SL/TP orders manage trade
    exits, so the log only records entries, never a synchronous
    close-and-log step the way backtest_*.csv's _simulate_trade() does.
    Loading a paper CSV (or 'all', which concatenates paper with backtest
    frames) therefore leaves "pnl" missing entirely, or NaN on paper rows
    once concatenated against backtest rows that DO have it.

    Fills in the best HONESTLY available P&L per row using OANDA directly,
    rather than assuming a backtest-style column exists:
      - trade still open (its trade_id is in the live OANDA open trades,
        from the SAME PortfolioState snapshot used by the rest of this
        dashboard render) -> unrealized P&L, exit_reason="open"
      - trade closed (trade_id found in OANDA's recent closed trades) ->
        realized P&L straight from OANDA, exit_reason="closed"
      - trade_id blank (e.g. a rejected fill was still logged) or older
        than OANDA's returned closed-trade window -> pnl=0.0,
        exit_reason="unknown" -- explicitly unknown, not fabricated
    Does NOT synthesize a "balance" column: there's no historical running
    balance to reconstruct honestly from what's available, so
    _max_drawdown_pct's existing "'balance' not in columns" guard is left
    to apply -- drawdown just isn't computed for paper-only data, rather
    than showing a plausible-looking but potentially wrong number.
    """
    if df.empty:
        return df

    if "pnl" not in df.columns:
        df = df.copy()
        df["pnl"] = float("nan")
    if "exit_reason" not in df.columns:
        df["exit_reason"] = None

    missing_mask = df["pnl"].isna()
    if not missing_mask.any():
        return df

    open_pnl = {p.trade_id: p.unrealized_pnl for p in state.open_positions if p.trade_id}

    try:
        from broker import get_closed_trades
        closed = get_closed_trades()
    except Exception:
        closed = []
    closed_pnl = {c["id"]: float(c.get("realizedPL", 0.0)) for c in closed if c.get("id")}

    df = df.copy()
    for idx in df.index[missing_mask]:
        raw_tid = df.at[idx, "trade_id"] if "trade_id" in df.columns else None
        # A blank trade_id cell anywhere in the CSV (e.g. a rejected fill
        # that still got logged) makes pandas read the whole column as
        # float64 -- "37" becomes 37.0, which str()'d as "37.0" would never
        # match OANDA's own string id "37". Normalize through int() first.
        if pd.isna(raw_tid):
            tid = ""
        else:
            try:
                tid = str(int(float(raw_tid)))
            except (ValueError, TypeError):
                tid = str(raw_tid).strip()
        if tid in open_pnl:
            df.at[idx, "pnl"] = open_pnl[tid]
            df.at[idx, "exit_reason"] = "open"
        elif tid in closed_pnl:
            df.at[idx, "pnl"] = closed_pnl[tid]
            df.at[idx, "exit_reason"] = "closed"
        else:
            df.at[idx, "pnl"] = 0.0
            df.at[idx, "exit_reason"] = "unknown"

    return df


def _get_live_account() -> dict:
    """
    Fetch live account balance and open trades from OANDA.
    Returns a dict with keys: balance, open_trades, nav, unrealised_pnl.
    Returns sensible defaults on error (so dashboard still renders).
    """
    try:
        from broker import get_account_balance, get_open_trades
        balance = get_account_balance()
        open_trades = get_open_trades()
        unrealised = sum(float(t.get("unrealizedPL", 0)) for t in open_trades)
        return {
            "balance": balance,
            "open_trades": open_trades,
            "unrealised_pnl": unrealised,
        }
    except Exception as e:
        return {
            "balance": 0.0,
            "open_trades": [],
            "unrealised_pnl": 0.0,
            "_error": str(e),
        }


# ── Metric helpers ────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _pnl_since(df: pd.DataFrame, since: datetime) -> float:
    return float(df[df["time"] >= since]["pnl"].sum()) if not df.empty else 0.0


def _win_rate(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    return float((df["pnl"] > 0).sum() / len(df))


def _avg(df: pd.DataFrame, positive: bool) -> float:
    sub = df[df["pnl"] > 0] if positive else df[df["pnl"] <= 0]
    return float(sub["pnl"].mean()) if not sub.empty else 0.0


def _rr(df: pd.DataFrame) -> float:
    avg_w = _avg(df, True)
    avg_l = abs(_avg(df, False))
    return round(avg_w / avg_l, 2) if avg_l else 0.0


def _max_drawdown_pct(df: pd.DataFrame) -> float:
    """Max drawdown as fraction of peak balance in the series."""
    if df.empty or "balance" not in df.columns:
        return 0.0
    balances = df["balance"].values
    peak = balances[0]
    max_dd = 0.0
    for b in balances:
        if b > peak:
            peak = b
        dd = (peak - b) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _pnl_color(val: float) -> str:
    return "green" if val > 0 else ("red" if val < 0 else "white")


def _fmt_pnl(val: float) -> Text:
    color = _pnl_color(val)
    sign = "+" if val > 0 else ""
    return Text(f"{sign}${val:,.2f}", style=color)


def _strategy_status(df: pd.DataFrame, alerts: set[str], key: str) -> Text:
    if key in alerts:
        return Text("ALERT", style="bold red")
    return Text("active", style="green")


# ── Alert detection ───────────────────────────────────────────────────────────

def _build_alerts(df: pd.DataFrame) -> tuple[list[str], set[str]]:
    """
    Returns (alert_messages, alert_keys).
    alert_keys is a set of '{strategy}:{instrument}' strings used to colour
    the strategy table rows.
    """
    messages: list[str] = []
    keys: set[str] = set()

    if df.empty:
        return messages, keys

    for (strat, inst), grp in df.groupby(["strategy", "instrument"]):
        key = f"{strat}:{inst}"
        grp = grp.sort_values("time")

        # Recent win-rate alert (last 20 trades)
        recent = grp.tail(20)
        if len(recent) >= 10:
            wr = _win_rate(recent)
            if wr < ALERT_WIN_RATE_THRESHOLD:
                msg = (
                    f"[bold red]LOW WIN RATE[/] {strat} / {inst}: "
                    f"{wr:.0%} over last {len(recent)} trades "
                    f"(threshold {ALERT_WIN_RATE_THRESHOLD:.0%})"
                )
                messages.append(msg)
                keys.add(key)

        # Drawdown alert
        dd = _max_drawdown_pct(grp)
        if dd > ALERT_DRAWDOWN_THRESHOLD:
            msg = (
                f"[bold red]DRAWDOWN[/] {strat} / {inst}: "
                f"{dd:.1%} from peak "
                f"(threshold {ALERT_DRAWDOWN_THRESHOLD:.0%})"
            )
            messages.append(msg)
            keys.add(key)

    return messages, keys


# ── Panel builders ────────────────────────────────────────────────────────────

def _panel_portfolio(df: pd.DataFrame, account: dict) -> Panel:
    now   = _now_utc()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week  = today - timedelta(days=today.weekday())   # Monday
    month = today.replace(day=1)

    total_pnl = float(df["pnl"].sum()) if not df.empty else 0.0
    today_pnl = _pnl_since(df, today)
    week_pnl  = _pnl_since(df, week)
    month_pnl = _pnl_since(df, month)
    balance   = account["balance"]
    unreal    = account["unrealised_pnl"]
    err       = account.get("_error")

    t = Table.grid(padding=(0, 2))
    t.add_column(style="bold cyan", no_wrap=True)
    t.add_column(justify="right", no_wrap=True)

    bal_text = Text(f"${balance:,.2f}", style="bold white") if balance is not None else Text("N/A", style="dim")
    t.add_row("Live Balance",   bal_text)
    t.add_row("Unrealised P&L", _fmt_pnl(unreal))
    t.add_row("Today P&L",      _fmt_pnl(today_pnl))
    t.add_row("Week P&L",       _fmt_pnl(week_pnl))
    t.add_row("Month P&L",      _fmt_pnl(month_pnl))
    t.add_row("Total Backtest PnL", _fmt_pnl(total_pnl))
    if err:
        t.add_row("[dim]OANDA status[/]", Text(f"offline ({err[:40]})", style="dim red"))

    return Panel(t, title="[bold]Portfolio Summary[/]", border_style="cyan")


def _panel_strategy(df: pd.DataFrame, alert_keys: set[str]) -> Panel:
    t = Table(
        show_header=True, header_style="bold magenta",
        border_style="magenta", expand=True,
    )
    t.add_column("Strategy",     style="bold", no_wrap=True)
    t.add_column("Pair",         no_wrap=True)
    t.add_column("Dir",          no_wrap=True)
    t.add_column("Trades",       justify="right")
    t.add_column("Win%",         justify="right")
    t.add_column("Avg W",        justify="right")
    t.add_column("Avg L",        justify="right")
    t.add_column("R:R",          justify="right")
    t.add_column("Net PnL",      justify="right")
    t.add_column("Status",       justify="center")

    if df.empty:
        t.add_row("[dim]No trade data found[/]", *["—"] * 8)
        return Panel(t, title="[bold]Strategy Breakdown[/]", border_style="magenta")

    for (strat, inst), grp in df.groupby(["strategy", "instrument"]):
        key = f"{strat}:{inst}"
        wr  = _win_rate(grp)
        net = float(grp["pnl"].sum())
        row_style = "red" if key in alert_keys else ""
        t.add_row(
            strat, inst, "ALL",
            str(len(grp)),
            f"{wr:.0%}",
            f"${_avg(grp, True):,.2f}",
            f"${_avg(grp, False):,.2f}",
            str(_rr(grp)),
            _fmt_pnl(net),
            _strategy_status(grp, alert_keys, key),
            style=row_style,
        )

        if "direction" in grp.columns:
            for direction in ("long", "short"):
                dgrp = grp[grp["direction"] == direction]
                if dgrp.empty:
                    continue
                dwr  = _win_rate(dgrp)
                dnet = float(dgrp["pnl"].sum())
                dir_text = Text(
                    "  ^ long" if direction == "long" else "  v short",
                    style="dim green" if direction == "long" else "dim red",
                )
                t.add_row(
                    "", "", dir_text,
                    str(len(dgrp)),
                    f"{dwr:.0%}",
                    f"${_avg(dgrp, True):,.2f}",
                    f"${_avg(dgrp, False):,.2f}",
                    str(_rr(dgrp)),
                    _fmt_pnl(dnet),
                    "",
                    style="dim",
                )

    return Panel(t, title="[bold]Strategy Breakdown[/]", border_style="magenta")


def _panel_pairs(df: pd.DataFrame, state: PortfolioState) -> Panel:
    t = Table(
        show_header=True, header_style="bold yellow",
        border_style="yellow", expand=True,
    )
    t.add_column("Pair",        no_wrap=True)
    t.add_column("Strategies",  no_wrap=True)
    t.add_column("Open Pos.",   justify="center")
    t.add_column("Today Trades",justify="right")
    t.add_column("Today PnL",   justify="right")
    t.add_column("Total PnL",   justify="right")

    # Open-position counts come from the same PortfolioState snapshot as the
    # Risk Monitor and Currency Exposure panels -- one fetch of OANDA's live
    # open trades per refresh, not a separate independent read here.
    open_by_pair: dict[str, int] = {}
    for pos in state.open_positions:
        open_by_pair[pos.instrument] = open_by_pair.get(pos.instrument, 0) + 1

    today = _now_utc().replace(hour=0, minute=0, second=0, microsecond=0)

    if df.empty:
        t.add_row("[dim]No data[/]", "—", "—", "—", "—", "—")
        return Panel(t, title="[bold]Per-Pair Breakdown[/]", border_style="yellow")

    for inst, grp in df.groupby("instrument"):
        strats = ", ".join(sorted(grp["strategy"].unique()))
        open_n = open_by_pair.get(inst, 0)
        open_str = f"[green]{open_n}[/]" if open_n else "—"
        today_grp = grp[grp["time"] >= today]
        t.add_row(
            inst, strats,
            open_str,
            str(len(today_grp)),
            _fmt_pnl(float(today_grp["pnl"].sum())) if not today_grp.empty else Text("—"),
            _fmt_pnl(float(grp["pnl"].sum())),
        )

    return Panel(t, title="[bold]Per-Pair Breakdown[/]", border_style="yellow")


def _panel_risk(state: PortfolioState) -> Panel:
    """Risk-cap headroom, read entirely from the shared PortfolioState
    snapshot (get_portfolio_state()) rather than recomputing exposure from
    a locally-fetched open-trades list -- this is the single source of
    truth every bot process and panel should agree with."""
    balance      = state.balance or 1.0
    n_open       = len(state.open_positions)

    exposure_pct = state.risk_deployed_pct
    remaining_trades = state.remaining_trade_capacity

    exp_color = "red" if exposure_pct >= state.risk_cap_pct else (
        "yellow" if exposure_pct >= state.risk_cap_pct * 0.75 else "green"
    )

    t = Table.grid(padding=(0, 2))
    t.add_column(style="bold cyan", no_wrap=True)
    t.add_column(justify="right", no_wrap=True)

    t.add_row("Open trades",        Text(str(n_open), style="white"))
    t.add_row("Current exposure",   Text(f"{exposure_pct:.0%}", style=exp_color))
    t.add_row("Risk cap",           Text(f"{state.risk_cap_pct:.0%}", style="dim"))
    t.add_row("Remaining capacity", Text(f"{remaining_trades} trade(s)", style=exp_color))
    t.add_row("Risk per trade",     Text(f"{RISK_PCT_PER_TRADE:.0%} (~${balance * RISK_PCT_PER_TRADE:,.0f})", style="dim"))

    if state.error:
        t.add_row("[dim]Portfolio state[/]", Text(f"offline ({state.error[:40]})", style="dim red"))

    if state.open_positions:
        t.add_row("Open positions", Text(""))
        for pos in state.open_positions:
            color = "green" if pos.unrealized_pnl >= 0 else "red"
            side = pos.direction.upper()
            r = f"  [bold]{pos.instrument}[/] {side} [{color}]{pos.unrealized_pnl:+.2f}[/] [dim]({pos.strategy})[/]"
            t.add_row("", Text.from_markup(r))

    return Panel(t, title="[bold]Risk Monitor[/]", border_style="cyan")


def _panel_exposure(state: PortfolioState) -> Panel:
    """Net exposure per currency and correlation clusters, from the shared
    PortfolioState snapshot -- the same single-source-of-truth used by the
    risk panel, so the two can never disagree about what's actually open."""
    t = Table.grid(padding=(0, 2))
    t.add_column(style="bold cyan", no_wrap=True)
    t.add_column(justify="right", no_wrap=True)

    if state.error:
        t.add_row("[dim]Status[/]", Text(f"offline ({state.error[:40]})", style="dim red"))
        return Panel(t, title="[bold]Currency Exposure[/]", border_style="cyan")

    if not state.net_exposure_by_currency:
        t.add_row("[dim]No open positions[/]", Text(""))
        return Panel(t, title="[bold]Currency Exposure[/]", border_style="cyan")

    for ccy, units in sorted(
        state.net_exposure_by_currency.items(), key=lambda kv: -abs(kv[1])
    ):
        color = "green" if units > 0 else ("red" if units < 0 else "white")
        sign  = "+" if units > 0 else ""
        t.add_row(ccy, Text(f"{sign}{units:,}", style=color))

    t.add_row("", Text(""))
    t.add_row("[bold]Clusters[/]", Text(""))
    for cluster in state.clusters:
        if len(cluster) < 2:
            continue
        label = " + ".join(sorted(p.instrument for p in cluster))
        t.add_row("", Text(label, style="yellow"))

    if all(len(c) < 2 for c in state.clusters):
        t.add_row("", Text("(no correlated pairs open)", style="dim"))

    return Panel(t, title="[bold]Currency Exposure[/]", border_style="cyan")


def _panel_recent_trades(df: pd.DataFrame) -> Panel:
    t = Table(
        show_header=True, header_style="bold blue",
        border_style="blue", expand=True,
    )
    t.add_column("Time (UTC)",  no_wrap=True, style="dim")
    t.add_column("Pair",        no_wrap=True)
    t.add_column("Strategy",    no_wrap=True)
    t.add_column("Dir",         justify="center")
    t.add_column("Entry",       justify="right", style="dim")
    t.add_column("Exit",        justify="center", style="dim")
    t.add_column("PnL",         justify="right")

    if df.empty:
        t.add_row("[dim]No trades[/]", *["—"] * 6)
        return Panel(t, title="[bold]Recent Trades (last 10)[/]", border_style="blue")

    recent = df.sort_values("time").tail(10).iloc[::-1]
    for _, row in recent.iterrows():
        pnl    = float(row["pnl"])
        dir_t  = Text("^ LONG" if row["direction"] == "long" else "v SHORT",
                      style="green" if row["direction"] == "long" else "red")
        t.add_row(
            row["time"].strftime("%Y-%m-%d %H:%M"),
            str(row.get("instrument", "?")),
            str(row.get("strategy", "?")),
            dir_t,
            f"{row.get('entry', 0):.5f}",
            str(row.get("exit_reason", "?")),
            _fmt_pnl(pnl),
        )

    return Panel(t, title="[bold]Recent Trades (last 10)[/]", border_style="blue")


def _panel_alerts(alert_messages: list[str]) -> Panel:
    if not alert_messages:
        content = Text("  No alerts - all strategies within normal parameters.", style="green")
    else:
        lines = []
        for msg in alert_messages:
            lines.append(Text.from_markup(f"  [!]  {msg}"))
        content = Text("\n").join(lines)  # type: ignore[arg-type]

    border = "red" if alert_messages else "green"
    title  = f"[bold {'red' if alert_messages else 'green'}]Alerts ({len(alert_messages)})[/]"
    return Panel(content, title=title, border_style=border)


# ── Render ────────────────────────────────────────────────────────────────────

def _render(df: pd.DataFrame, account: dict, state: PortfolioState) -> Layout:
    alert_messages, alert_keys = _build_alerts(df)

    layout = Layout()
    layout.split_column(
        Layout(name="top",     ratio=2),
        Layout(name="mid",     ratio=3),
        Layout(name="bottom",  ratio=3),
        Layout(name="alerts",  ratio=1),
    )
    layout["top"].split_row(
        Layout(_panel_portfolio(df, account), name="portfolio"),
        Layout(_panel_risk(state),             name="risk"),
        Layout(_panel_exposure(state),         name="exposure"),
    )
    layout["mid"].split_row(
        Layout(_panel_strategy(df, alert_keys), name="strategy", ratio=3),
        Layout(_panel_pairs(df, state),         name="pairs",    ratio=2),
    )
    layout["bottom"].update(_panel_recent_trades(df))
    layout["alerts"].update(_panel_alerts(alert_messages))

    return layout


def _snapshot(
    directory: Path,
    console: Console,
    config: dict,
    show_all: bool,
    only: list[str] | None,
    source: str = "paper",
) -> None:
    account = _get_live_account()
    state   = get_portfolio_state()
    df_raw  = _enrich_missing_pnl(_load_csvs(directory, source=source), state)
    df, n_hidden = _apply_strategy_filter(df_raw, config, show_all, only)
    layout  = _render(df, account, state)
    console.print(layout)

    now    = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    n      = len(df) if not df.empty else 0
    hidden = f"  |  {n_hidden} archived rows hidden (--all to show)" if n_hidden else ""
    filter_label = ""
    if only:
        filter_label = f"  |  filter: {', '.join(only)}"
    elif show_all:
        filter_label = "  |  showing all strategies"
    console.print(
        f"[dim]  {now}  |  source={source}  |  {n} trades{filter_label}{hidden}[/]"
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Forex Bot Terminal Dashboard")
    parser.add_argument(
        "--live", action="store_true",
        help="Auto-refresh every --interval seconds",
    )
    parser.add_argument(
        "--interval", type=int, default=60,
        help="Refresh interval in seconds (default 60, requires --live)",
    )
    parser.add_argument(
        "--dir", default=str(BOT_DIR),
        help="Directory containing backtest_*.csv files (default: bot directory)",
    )
    parser.add_argument(
        "--width", type=int, default=None,
        help="Force console render width in characters (default: auto-detect from terminal)",
    )
    parser.add_argument(
        "--strategy", default=None, metavar="NAME[,NAME...]",
        help="Show only the named strategy/strategies (comma-separated). "
             "Overrides active/archived status from strategies.json.",
    )
    parser.add_argument(
        "--all", action="store_true", dest="show_all",
        help="Show all strategies including archived ones (ignores strategies.json status).",
    )
    parser.add_argument(
        "--source", default="paper", choices=["paper", "backtest", "all"],
        help="Which trade logs to load: 'paper' (paper_trades.csv only, default), "
             "'backtest' (backtest_*.csv only), or 'all' (both).",
    )
    args = parser.parse_args()
    directory = Path(args.dir)

    # Resolve filter params once
    config   = _load_strategy_config()
    only     = [s.strip() for s in args.strategy.split(",")] if args.strategy else None
    show_all = args.show_all
    source   = args.source

    global console
    if args.width:
        console = Console(width=args.width)

    if not args.live:
        _snapshot(directory, console, config, show_all, only, source=source)
        return

    # Live refresh loop
    console.print("[dim]Starting live dashboard — press Ctrl+C to exit[/]")
    try:
        with Live(console=console, screen=True, refresh_per_second=1) as live:
            while True:
                account = _get_live_account()
                state   = get_portfolio_state()
                df_raw, n_hidden = _apply_strategy_filter(
                    _enrich_missing_pnl(_load_csvs(directory, source=source), state),
                    config, show_all, only,
                )
                layout  = _render(df_raw, account, state)

                now    = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                n      = len(df_raw) if not df_raw.empty else 0
                hidden = f"  |  {n_hidden} archived hidden (--all)" if n_hidden else ""
                filter_label = ""
                if only:
                    filter_label = f"  |  filter: {', '.join(only)}"
                elif show_all:
                    filter_label = "  |  showing all strategies"
                footer = (
                    f"\n[dim]  {now}  |  source={source}  |  {n} trades{filter_label}{hidden}"
                    f"  |  refresh every {args.interval}s  |  Ctrl+C to exit[/]"
                )

                from rich.console import Group
                live.update(Group(layout, Text.from_markup(footer)))

                time.sleep(args.interval)

    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard closed.[/]")


if __name__ == "__main__":
    main()
