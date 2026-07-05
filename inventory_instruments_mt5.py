"""
Gate 0 instrument inventory — MT5 (Phase A generic demo) edition.

Same shape as inventory_instruments.py (the OANDA pass), run against the
MT5 demo account via mt5_client. Classifies every symbol by asset class,
probes earliest available M5 bar, and cross-references the static
prop-firm category table (REFERENCE ONLY — verify symbol-level before use).

Output: mt5_instrument_inventory.csv (kept separate from the OANDA
instrument_inventory.csv — never merged).

Run:  D:/rhyme/venv/Scripts/python.exe D:/rhyme/inventory_instruments_mt5.py
"""
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5

from mt5_client import connect, list_symbols, SOURCE_TAG

# ---------------------------------------------------------------------------
# Classification: broker's own category path (first segment) is primary;
# name patterns are the fallback. Anything unmatched → cfd_other, flagged
# for manual review, never dropped.
# ---------------------------------------------------------------------------
ENERGY_HINTS = {"WTI", "BRENT", "XBR", "XTI", "XNG", "NATGAS", "NGAS", "UKOIL", "USOIL", "OIL"}
AGRI_HINTS = {"CORN", "WHEAT", "SOYBEAN", "SOYBN", "SUGAR", "COFFEE", "COCOA", "COTTON"}
METAL_HINTS = {"XAU", "XAG", "XPT", "XPD", "GOLD", "SILVER", "COPPER", "XCU"}
INDEX_HINTS = {"SPX", "SP500", "US500", "NAS", "US100", "USTEC", "US30", "DJ30", "DOW",
               "DAX", "DE30", "DE40", "GER", "UK100", "FTSE", "JP225", "NIK", "AUS200",
               "AU200", "STOXX", "EU50", "FR40", "CAC", "HK50", "HSI", "ES35", "IT40"}
BOND_HINTS = {"BUND", "GILT", "TNOTE", "USTB", "USB", "BOBL", "SCHATZ"}
CRYPTO_HINTS = {"BTC", "ETH", "LTC", "XRP", "ADA", "DOT", "DOGE", "SOL", "BNB", "AVAX",
                "LINK", "MATIC", "TRX", "BCH", "XLM", "EOS", "ETC", "UNI", "AAVE", "TON"}

PATH_CLASS = {
    "forex": "forex", "fx": "forex", "currencies": "forex", "majors": "forex",
    "minors": "forex", "exotics": "forex",
    "metals": "metals", "spot metals": "metals",
    "energies": "energy", "energy": "energy", "oil": "energy",
    "agricultures": "agriculture", "agriculture": "agriculture", "softs": "agriculture",
    "indices": "indices", "indexes": "indices", "index": "indices", "cash indices": "indices",
    "bonds": "bonds",
    "crypto": "crypto", "cryptos": "crypto", "cryptocurrencies": "crypto",
    "stocks": "stocks", "shares": "stocks", "equities": "stocks",
}


def _name_fallback(sym: str) -> str:
    up = sym.upper()
    for hints, cls in ((CRYPTO_HINTS, "crypto"), (ENERGY_HINTS, "energy"),
                       (AGRI_HINTS, "agriculture"), (METAL_HINTS, "metals"),
                       (BOND_HINTS, "bonds"), (INDEX_HINTS, "indices")):
        if any(h in up for h in hints):
            return cls
    if len(up) in (6, 7) and up[:3].isalpha() and up[3:6].isalpha():
        return "forex"
    return "cfd_other"


def classify(symbol: str, path: str) -> str:
    top = path.split("\\")[0].strip().lower() if path else ""
    if top in PATH_CLASS:
        return PATH_CLASS[top]
    return _name_fallback(symbol)


# ---------------------------------------------------------------------------
# Static prop-firm eligibility by asset class (ftmo, five_percenters,
# fundednext). Category-level, built from public docs as of 2026-07 —
# *** REFERENCE ONLY, verify per-symbol per-challenge before filtering. ***
# Stocks: only FTMO advertises them. Crypto: all three advertise it.
# ---------------------------------------------------------------------------
PROP_FIRM_CATEGORY_SUPPORT = {
    "forex":       (True,  True,  True),
    "metals":      (True,  True,  True),
    "energy":      (True,  True,  True),
    "agriculture": (False, False, False),  # FTMO likely True — see Gate 0 report
    "indices":     (True,  True,  True),
    "bonds":       (False, False, False),
    "crypto":      (True,  True,  True),
    "stocks":      (True,  False, False),
    "cfd_other":   (False, False, False),
}

PROBE_FLOOR = datetime(2005, 1, 1)
WINDOW = timedelta(days=7)


def _has_bars(symbol: str, when: datetime) -> bool:
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M5, when, when + WINDOW)
    return rates is not None and len(rates) > 0


def earliest_m5(symbol: str) -> str:
    """Binary-search the earliest date with M5 bars (7-day probe window),
    then return the ISO date of the first bar found there."""
    now = datetime.now()
    if not _has_bars(symbol, now - timedelta(days=10)):
        return ""  # no recent M5 data at all
    lo, hi = PROBE_FLOOR, now - timedelta(days=10)
    if _has_bars(symbol, lo):
        hi = lo
    while lo < hi - timedelta(days=3):
        mid = lo + (hi - lo) / 2
        if _has_bars(symbol, mid):
            hi = mid
        else:
            lo = mid
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M5, hi, hi + WINDOW)
    if rates is None or len(rates) == 0:
        return ""
    return datetime.fromtimestamp(int(rates[0][0]), tz=timezone.utc).strftime("%Y-%m-%d")


def main() -> None:
    connect()
    account = mt5.account_info()
    print(f"Source: {SOURCE_TAG} | login {account.login} @ {account.server} "
          f"({'DEMO' if account.trade_mode == 0 else 'NOT DEMO'})")
    syms = list_symbols()
    print(f"{len(syms)} symbols returned\n")

    rows = []
    for i, s in enumerate(syms.itertuples()):
        asset_class = classify(s.symbol, s.path)
        mt5.symbol_select(s.symbol, True)
        try:
            first = earliest_m5(s.symbol)
        except Exception as e:
            first = ""
            print(f"  M5 probe failed for {s.symbol}: {e}")
        ftmo, fivepct, fnext = PROP_FIRM_CATEGORY_SUPPORT[asset_class]
        rows.append({
            "symbol": s.symbol,
            "description": s.description,
            "broker_path": s.path,
            "asset_class": asset_class,
            "digits": s.digits,
            "earliest_m5": first,
            "m5_history_years": (
                round((datetime.now(timezone.utc)
                       - datetime.fromisoformat(first + "T00:00:00+00:00")).days / 365.25, 1)
                if first else ""
            ),
            "ftmo": ftmo,
            "five_percenters": fivepct,
            "fundednext": fnext,
            "source": SOURCE_TAG,
        })
        if (i + 1) % 25 == 0:
            print(f"  probed {i + 1}/{len(syms)}")

    out = Path(__file__).parent / "mt5_instrument_inventory.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {out} ({len(rows)} rows)\n")

    classes = sorted({r["asset_class"] for r in rows})
    print(f"{'asset_class':<14}{'count':>6}{'ftmo':>7}{'5%ers':>7}{'fnext':>7}   earliest_m5 range")
    for c in classes:
        sub = [r for r in rows if r["asset_class"] == c]
        dates = sorted(r["earliest_m5"] for r in sub if r["earliest_m5"])
        rng = f"{dates[0]} .. {dates[-1]}" if dates else "(no M5 data)"
        ftmo, fivepct, fnext = PROP_FIRM_CATEGORY_SUPPORT[c]
        print(f"{c:<14}{len(sub):>6}{str(ftmo):>7}{str(fivepct):>7}{str(fnext):>7}   {rng}")

    other = [r["symbol"] for r in rows if r["asset_class"] == "cfd_other"]
    if other:
        print(f"\ncfd_other (manual review needed): {', '.join(other)}")
    no_m5 = [r["symbol"] for r in rows if not r["earliest_m5"]]
    if no_m5:
        print(f"\nno M5 history returned ({len(no_m5)}): {', '.join(no_m5)}")


if __name__ == "__main__":
    main()
