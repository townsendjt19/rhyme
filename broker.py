"""
OANDA order management — place, modify, close orders.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from oandapyV20 import API
from oandapyV20.endpoints import orders, trades, accounts, pricing
from oandapyV20.exceptions import V20Error

from risk import price_precision

load_dotenv(Path(__file__).parent / ".env", override=True)

logger = logging.getLogger(__name__)

ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
ACCESS_TOKEN = os.getenv("OANDA_ACCESS_TOKEN", "")
ENVIRONMENT = os.getenv("OANDA_ENV", "practice")

_client: API | None = None


def set_account(account_id: str) -> None:
    """Per-process account override (token and environment stay shared).

    Every broker function reads the module-level ACCOUNT_ID at call time,
    so setting it once at process startup (before any API call) redirects
    the entire process -- orders, trades, margin, NAV -- to the given
    sub-account. Motivated by OANDA's NFA FIFO safeguard: a second
    same-instrument position is broker-cancelled within one account, so
    running Bot D against a separate practice sub-account is the only way
    for it to trade USD_JPY concurrently with the Donchian modes. Note the
    cross-account blind spots this creates: get_open_trades()/margin/NAV
    are all per-account, so cross-mode gates (position cap, margin
    utilization, currency exposure) see only THIS process's account.
    """
    global ACCOUNT_ID
    ACCOUNT_ID = account_id
    logger.info("Broker account set to %s for this process", account_id)


def get_client() -> API:
    global _client
    if _client is None:
        _client = API(access_token=ACCESS_TOKEN, environment=ENVIRONMENT)
    return _client


# ── Account ───────────────────────────────────────────────────────────────────

def get_account_balance() -> float:
    req = accounts.AccountSummary(ACCOUNT_ID)
    get_client().request(req)
    return float(req.response["account"]["balance"])


def get_open_trades() -> list[dict]:
    req = trades.TradesList(ACCOUNT_ID)
    get_client().request(req)
    return req.response.get("trades", [])


def get_closed_trades(count: int = 500) -> list[dict]:
    """Most recently closed trades, each including OANDA's own realizedPL --
    the authoritative source for realized P&L on paper trades, since
    paper_trades.csv only logs entries (OANDA's own SL/TP orders manage the
    exit, so there's no synchronous close-and-log step the way backtests
    have one). Used by dashboard.py to fill in real P&L for paper trades
    instead of assuming a backtest-style "pnl" column exists."""
    req = trades.TradesList(ACCOUNT_ID, params={"state": "CLOSED", "count": count})
    get_client().request(req)
    return req.response.get("trades", [])


# ── Margin ────────────────────────────────────────────────────────────────────
# GLOBAL_RISK_CAP_PCT (see risk.py / main.py) bounds potential LOSS across open
# positions. Margin bounds the CAPITAL REQUIRED to hold a position at all --
# a different constraint that can fail independently (a low-risk-% trade on a
# low-margin-rate account can still exceed available margin if the position
# is large enough, as happened live with an 89,000-unit USD_JPY order: 0.09%
# risk, well under any risk cap, but $4,450 required margin against $4,075.63
# available). Checked separately, right before order placement.

_margin_rate_cache: dict[str, float] = {}

DEFAULT_MARGIN_RATE = 0.05   # conservative fallback (20:1) if the per-instrument query fails


def get_margin_rate(instrument: str) -> float:
    """Instrument-specific margin rate (fraction of notional required as margin).

    NOT the same as AccountSummary's account-level marginRate -- each
    instrument can require a higher rate (USD_JPY is 0.05 / 20:1 on this
    account, not the account-level default 0.02 / 50:1). Cached per
    instrument for the life of the process since this rarely changes.
    """
    if instrument in _margin_rate_cache:
        return _margin_rate_cache[instrument]
    try:
        req = accounts.AccountInstruments(accountID=ACCOUNT_ID, params={"instruments": instrument})
        get_client().request(req)
        rate = float(req.response["instruments"][0]["marginRate"])
    except Exception as e:
        logger.warning("Could not fetch margin rate for %s (%s) — using default %.2f",
                        instrument, e, DEFAULT_MARGIN_RATE)
        rate = DEFAULT_MARGIN_RATE
    _margin_rate_cache[instrument] = rate
    return rate


def get_account_margin() -> tuple[float, float]:
    """Return (marginAvailable, marginUsed), fresh from the account."""
    req = accounts.AccountSummary(ACCOUNT_ID)
    get_client().request(req)
    acct = req.response["account"]
    return float(acct["marginAvailable"]), float(acct["marginUsed"])


def get_account_nav() -> float:
    """Net Asset Value (balance + unrealized P&L), fresh from the account.
    The margin-utilization cap is expressed against NAV rather than balance
    because OANDA's own margin closeout math works off NAV -- a large
    unrealized loss shrinks real margin capacity even while balance is
    unchanged."""
    req = accounts.AccountSummary(ACCOUNT_ID)
    get_client().request(req)
    return float(req.response["account"]["NAV"])


def _current_price(instrument: str) -> float:
    req = pricing.PricingInfo(accountID=ACCOUNT_ID, params={"instruments": instrument})
    get_client().request(req)
    p = req.response["prices"][0]
    bid = float(p["bids"][0]["price"])
    ask = float(p["asks"][0]["price"])
    return (bid + ask) / 2


def convert_to_usd(amount: float, currency: str) -> float:
    """Convert `amount` of `currency` to USD using live pricing.

    Tries USD_<currency> first (currency is the quote leg, e.g. USD_JPY --
    divide), then <currency>_USD (currency is the base leg, e.g. EUR_USD --
    multiply). Works for any currency that's quotable against USD on this
    account, which covers every currency traded by this project.

    Public (not underscore-prefixed): used both internally by
    required_margin_usd() and externally by portfolio_state.py's currency
    exposure cap, which needs to compare net exposure across different
    currencies on a common USD basis.
    """
    if currency == "USD":
        return amount
    try:
        rate = _current_price(f"USD_{currency}")
        return amount / rate
    except Exception:
        pass
    rate = _current_price(f"{currency}_USD")
    return amount * rate


def required_margin_usd(instrument: str, units: int) -> float:
    """Margin (in USD) required to open this position, using the
    instrument's own margin rate and converting the BASE currency notional
    to USD (the base currency, not the quote currency -- OANDA margins a
    position by the value of the base-currency notional held)."""
    base = instrument.split("_")[0]
    notional_usd = convert_to_usd(abs(units), base)
    return notional_usd * get_margin_rate(instrument)


# ── Place orders ──────────────────────────────────────────────────────────────

def place_market_order(
    instrument: str,
    units: int,                # positive = long, negative = short
    stop_loss: float,
    take_profit: float,
    client_extensions: dict | None = None,
) -> dict:
    """
    Place a market order with attached SL and primary TP.
    Returns the OANDA response dict.
    """
    prec = price_precision(instrument)
    order_data: dict = {
        "order": {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(units),
            "stopLossOnFill": {"price": f"{stop_loss:.{prec}f}"},
            "takeProfitOnFill": {"price": f"{take_profit:.{prec}f}"},
            "timeInForce": "FOK",
        }
    }
    if client_extensions:
        order_data["order"]["clientExtensions"] = client_extensions

    req = orders.OrderCreate(ACCOUNT_ID, data=order_data)
    try:
        get_client().request(req)
        logger.info("Order placed: %s", req.response)
        return req.response
    except V20Error as e:
        logger.error("OrderCreate failed: %s", e)
        raise


# ── Modify existing trade ──────────────────────────────────────────────────────

def modify_trade_sl_tp(
    trade_id: str,
    instrument: str,
    new_stop: float | None = None,
    new_tp: float | None = None,
) -> dict:
    """Modify SL and/or TP on an open trade."""
    prec = price_precision(instrument)
    data: dict = {}
    if new_stop is not None:
        data["stopLoss"] = {"price": f"{new_stop:.{prec}f}", "timeInForce": "GTC"}
    if new_tp is not None:
        data["takeProfit"] = {"price": f"{new_tp:.{prec}f}", "timeInForce": "GTC"}

    req = trades.TradeCRCDO(ACCOUNT_ID, tradeID=trade_id, data=data)
    try:
        get_client().request(req)
        logger.info("Trade %s modified: %s", trade_id, data)
        return req.response
    except V20Error as e:
        logger.error("TradeCRCDO failed: %s", e)
        raise


def close_trade(trade_id: str, units: int | None = None) -> dict:
    """
    Close a trade fully or partially.
    units = None means full close; otherwise partial close of `units` units.
    """
    data: dict = {}
    if units is not None:
        data["units"] = str(abs(units))

    req = trades.TradeClose(ACCOUNT_ID, tradeID=trade_id, data=data if data else None)
    try:
        get_client().request(req)
        logger.info("Trade %s closed (units=%s)", trade_id, units)
        return req.response
    except V20Error as e:
        logger.error("TradeClose failed: %s", e)
        raise


# ── Trailing stop management ──────────────────────────────────────────────────

def advance_trailing_stop(
    trade_id: str,
    instrument: str,
    direction: str,
    current_price: float,
    ema_20: float,
    current_tp_idx: int,
    next_tp: float | None,
) -> None:
    """
    After each TP hit:
      - Advance SL to the 20 EMA.
      - Update TP to next extension level if available.
    """
    new_sl = ema_20
    modify_kwargs: dict = {"new_stop": new_sl}
    if next_tp is not None:
        modify_kwargs["new_tp"] = next_tp
    modify_trade_sl_tp(trade_id, instrument, **modify_kwargs)
    logger.info(
        "Trailing stop advanced: trade=%s sl=%.5f next_tp=%s",
        trade_id, new_sl, next_tp,
    )
