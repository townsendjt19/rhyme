"""
OANDA order management — place, modify, close orders.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from oandapyV20 import API
from oandapyV20.endpoints import orders, trades, accounts
from oandapyV20.exceptions import V20Error

from risk import price_precision

load_dotenv(Path(__file__).parent / ".env", override=True)

logger = logging.getLogger(__name__)

ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
ACCESS_TOKEN = os.getenv("OANDA_ACCESS_TOKEN", "")
ENVIRONMENT = os.getenv("OANDA_ENV", "practice")

_client: API | None = None


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
