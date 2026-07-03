"""
Atomic two-leg spread execution — spec §1/§1a (RESEARCH_LOG 2026-07-02,
commits a8df3ed + e201c6f). Sequenced fill-or-kill with unwind-on-partner-
failure. The only acceptable end states are FULLY-HEDGED or FULLY-FLAT;
a naked leg is an incident with a bounded lifetime, never a design state.

Broker operations are injected (`ops`) so the failure-mode paths are unit-
testable without an API. The default ops hit OANDA: FOK market orders with
stopLossOnFill (the emergency hard SL) and clientExtensions tag
"spread:<idea_id>"; unwind via TradeClose.
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

UNWIND_RETRIES = 3
UNWIND_BACKOFF_S = 2.0
LEG2_TIMEOUT_S = 5.0   # documented in spec; FOK rejects are immediate, the
                       # timeout bounds transport-level hangs


@dataclass
class SpreadLeg:
    instrument: str
    units: int            # signed: positive = long, negative = short
    emergency_sl: float   # catastrophe hard SL price (spec item 6)


class OandaSpreadOps:
    """Real broker operations. Import-light so tests never touch it."""

    def place_fok(self, instrument: str, units: int, sl_price: float, tag: str):
        """Place a FOK market order with emergency SL and idea tag.
        Returns trade_id (str) on fill, None on no-fill/reject."""
        import broker
        from oandapyV20.endpoints import orders
        data = {"order": {
            "type": "MARKET", "instrument": instrument, "units": str(units),
            "timeInForce": "FOK",
            "stopLossOnFill": {"price": f"{sl_price:.5f}"},
            "clientExtensions": {"tag": tag},
            "tradeClientExtensions": {"tag": tag},
        }}
        req = orders.OrderCreate(broker.ACCOUNT_ID, data=data)
        try:
            broker.get_client().request(req)
        except Exception as e:
            logger.error("FOK %s %+d failed: %s", instrument, units, e)
            return None
        fill = req.response.get("orderFillTransaction")
        if not fill:
            cancel = req.response.get("orderCancelTransaction", {})
            logger.warning("FOK %s %+d not filled: %s", instrument, units,
                           cancel.get("reason", "no fill transaction"))
            return None
        return fill.get("tradeOpened", {}).get("tradeID")

    def close_trade(self, trade_id: str) -> bool:
        import broker
        from oandapyV20.endpoints import trades as tr_ep
        req = tr_ep.TradeClose(broker.ACCOUNT_ID, tradeID=trade_id)
        try:
            broker.get_client().request(req)
            return True
        except Exception as e:
            logger.error("TradeClose %s failed: %s", trade_id, e)
            return False

    def list_open_spread_trades(self) -> list[dict]:
        """Open trades carrying a spread tag: [{trade_id, instrument, tag}]."""
        import broker
        out = []
        for t in broker.get_open_trades():
            tag = (t.get("clientExtensions") or {}).get("tag", "")
            if tag.startswith("spread:"):
                out.append({"trade_id": t.get("id"), "instrument": t.get("instrument"), "tag": tag})
        return out


def execute_spread_idea(idea_id: str, leg1: SpreadLeg, leg2: SpreadLeg, ops) -> dict:
    """Run the §1 sequence. Caller has ALREADY passed the joint gates and the
    §1a staleness check. leg1 must be the LESS LIQUID leg (the harder fill
    decides). Returns a dict with status: "open" | "aborted_leg1" |
    "aborted_unwound" | "NAKED_LEG"."""
    tag = f"spread:{idea_id}"
    incidents: list[str] = []

    t1 = ops.place_fok(leg1.instrument, leg1.units, leg1.emergency_sl, tag)
    if t1 is None:
        return {"status": "aborted_leg1", "incidents": incidents, "legs": {}}

    t2 = ops.place_fok(leg2.instrument, leg2.units, leg2.emergency_sl, tag)
    if t2 is not None:
        return {"status": "open", "incidents": incidents,
                "legs": {leg1.instrument: t1, leg2.instrument: t2}}

    # Leg 2 failed -> unwind leg 1 (spec item 4). No signal re-check (spec 1a).
    incidents.append(f"leg2 {leg2.instrument} failed; unwinding leg1 {leg1.instrument} trade {t1}")
    logger.warning(incidents[-1])
    for attempt in range(1, UNWIND_RETRIES + 1):
        if ops.close_trade(t1):
            incidents.append(f"leg1 unwound on attempt {attempt}")
            return {"status": "aborted_unwound", "incidents": incidents, "legs": {}}
        time.sleep(UNWIND_BACKOFF_S * attempt)

    incidents.append(f"UNWIND FAILED x{UNWIND_RETRIES}: NAKED LEG {leg1.instrument} trade {t1} "
                     f"(bounded by emergency SL {leg1.emergency_sl}); strategy must suspend")
    logger.critical(incidents[-1])
    return {"status": "NAKED_LEG", "incidents": incidents,
            "legs": {leg1.instrument: t1}, "naked_trade_id": t1}


def reconcile_orphans(ops) -> list[str]:
    """Startup reconciliation (spec item 7): any spread-tagged trade whose
    idea has only ONE open leg is an orphan -> unwind immediately. Returns
    the incident strings (empty = clean)."""
    incidents: list[str] = []
    open_spread = ops.list_open_spread_trades()
    by_idea: dict[str, list[dict]] = {}
    for t in open_spread:
        by_idea.setdefault(t["tag"], []).append(t)
    for tag, legs in by_idea.items():
        if len(legs) == 1:
            orphan = legs[0]
            msg = f"orphaned spread leg at startup: {tag} {orphan['instrument']} trade {orphan['trade_id']}"
            logger.critical(msg)
            incidents.append(msg)
            if ops.close_trade(orphan["trade_id"]):
                incidents.append(f"orphan {orphan['trade_id']} unwound")
            else:
                incidents.append(f"ORPHAN UNWIND FAILED for {orphan['trade_id']} -- manual intervention; "
                                 f"emergency SL remains the bound")
    return incidents
