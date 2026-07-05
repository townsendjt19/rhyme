"""
Gate 0 instrument inventory for prop-firm multi-asset expansion.

Pulls the tradeable instrument list from the OANDA practice account,
classifies each by asset class, measures M5 history depth, and
cross-references a static prop-firm eligibility table.

Output: instrument_inventory.csv + printed summary by asset class.

Run from D:/rhyme with the venv interpreter:
    D:/rhyme/venv/Scripts/python.exe D:/rhyme/inventory_instruments.py
"""
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from oandapyV20.endpoints.accounts import AccountInstruments
from oandapyV20.endpoints.instruments import InstrumentsCandles

# Reuse the project's client/credential wiring (loads .env itself)
from data import get_client, ACCOUNT_ID, ENVIRONMENT

# ---------------------------------------------------------------------------
# Asset-class classification.
# Pattern-matched on known OANDA v20 naming conventions — anything that does
# not match a known pattern is tagged 'cfd_other' for manual review, never
# silently dropped.
# ---------------------------------------------------------------------------
METAL_CODES = {"XAU", "XAG", "XPT", "XPD", "XCU"}
ENERGY_NAMES = {"WTICO", "BCO", "NATGAS"}
AGRI_NAMES = {"CORN", "WHEAT", "SOYBN", "SUGAR"}
INDEX_NAMES = {
    "SPX500", "NAS100", "US30", "US2000", "UK100", "DE30", "DE40", "JP225",
    "JP225Y", "AU200", "EU50", "FR40", "HK33", "SG30", "CN50", "TWIX",
    "NL25", "CH20", "ESPIX", "IN50", "USDX",
}
BOND_NAMES = {"DE10YB", "UK10YB", "USB02Y", "USB05Y", "USB10Y", "USB30Y"}


def classify(name: str, oanda_type: str) -> str:
    parts = name.split("_")
    base = parts[0]
    if base in ENERGY_NAMES:
        return "energy"
    if base in AGRI_NAMES:
        return "agriculture"
    if base in INDEX_NAMES:
        return "indices"
    if base in BOND_NAMES:
        return "bonds"
    if base in METAL_CODES or (len(parts) == 2 and parts[1] in METAL_CODES):
        return "metals"
    if (
        oanda_type == "CURRENCY"
        and len(parts) == 2
        and all(len(p) == 3 and p.isalpha() for p in parts)
    ):
        return "forex"
    return "cfd_other"


# ---------------------------------------------------------------------------
# Static prop-firm eligibility by asset class.
# Built from public FTMO / The5%ers / FundedNext docs as of mid-2026.
# *** REFERENCE ONLY — VERIFY AGAINST EACH FIRM'S CURRENT SYMBOL LIST FOR
# THE SPECIFIC CHALLENGE TYPE BEFORE USING TO FILTER ANYTHING. ***
# ---------------------------------------------------------------------------
PROP_FIRM_CATEGORY_SUPPORT = {
    #                 (ftmo, five_percenters, fundednext)
    "forex":       (True,  True,  True),
    "metals":      (True,  True,  True),
    "energy":      (True,  True,  True),
    "agriculture": (False, False, False),
    "indices":     (True,  True,  True),
    "bonds":       (False, False, False),
    "cfd_other":   (False, False, False),
}

M5_PROBE_FROM = "2005-01-01T00:00:00Z"  # probe start for earliest M5 candle


def earliest_m5(client, name: str) -> str:
    """Return ISO date of the earliest available M5 candle (probe from 2005)."""
    params = {"granularity": "M5", "price": "M", "from": M5_PROBE_FROM, "count": 1}
    req = InstrumentsCandles(instrument=name, params=params)
    client.request(req)
    candles = req.response.get("candles", [])
    if not candles:
        return ""
    return candles[0]["time"][:10]


def main() -> None:
    client = get_client()
    print(f"Environment: {ENVIRONMENT}  Account: ...{ACCOUNT_ID[-4:]}")
    if ENVIRONMENT != "practice":
        print("WARNING: not the practice environment — aborting.")
        sys.exit(1)

    req = AccountInstruments(accountID=ACCOUNT_ID)
    client.request(req)
    instruments = req.response["instruments"]
    print(f"{len(instruments)} tradeable instruments returned by AccountInstruments\n")

    rows = []
    for i, inst in enumerate(sorted(instruments, key=lambda x: x["name"])):
        name = inst["name"]
        asset_class = classify(name, inst.get("type", ""))
        try:
            first_m5 = earliest_m5(client, name)
        except Exception as e:  # keep the row; flag the probe failure
            first_m5 = ""
            print(f"  M5 probe failed for {name}: {e}")
        ftmo, fivepct, fnext = PROP_FIRM_CATEGORY_SUPPORT[asset_class]
        rows.append({
            "instrument": name,
            "display_name": inst.get("displayName", ""),
            "oanda_type": inst.get("type", ""),
            "asset_class": asset_class,
            "pip_location": inst.get("pipLocation", ""),
            "margin_rate": inst.get("marginRate", ""),
            "earliest_m5": first_m5,
            "m5_history_years": (
                round((datetime.now(timezone.utc)
                       - datetime.fromisoformat(first_m5 + "T00:00:00+00:00")).days / 365.25, 1)
                if first_m5 else ""
            ),
            "ftmo": ftmo,
            "five_percenters": fivepct,
            "fundednext": fnext,
        })
        time.sleep(0.05)
        if (i + 1) % 25 == 0:
            print(f"  probed {i + 1}/{len(instruments)}")

    out = Path(__file__).parent / "instrument_inventory.csv"
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {out} ({len(rows)} rows)\n")

    # Summary table by asset class
    classes = sorted({r["asset_class"] for r in rows})
    print(f"{'asset_class':<14}{'count':>6}{'ftmo':>7}{'5%ers':>7}{'fnext':>7}   earliest_m5 range")
    for c in classes:
        sub = [r for r in rows if r["asset_class"] == c]
        dates = sorted(r["earliest_m5"] for r in sub if r["earliest_m5"])
        rng = f"{dates[0]} .. {dates[-1]}" if dates else "(no data)"
        ftmo, fivepct, fnext = PROP_FIRM_CATEGORY_SUPPORT[c]
        print(f"{c:<14}{len(sub):>6}{str(ftmo):>7}{str(fivepct):>7}{str(fnext):>7}   {rng}")

    other = [r["instrument"] for r in rows if r["asset_class"] == "cfd_other"]
    if other:
        print(f"\ncfd_other (manual review needed): {', '.join(other)}")
    print("\nKnown gap: crypto is not available via OANDA v20 — needs a separate data source.")


if __name__ == "__main__":
    main()
