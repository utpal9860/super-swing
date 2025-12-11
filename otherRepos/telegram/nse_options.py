"""
Fetch current option prices from NSE option-chain API.
"""
from __future__ import annotations

import time
from typing import Optional, Tuple
import requests

NSE_OC_URL = "https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
NSE_REFERER = "https://www.nseindia.com/option-chain"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": NSE_REFERER,
            "Connection": "keep-alive",
        }
    )
    # Warm-up hit to set cookies
    session.get(NSE_REFERER, timeout=10)
    return session


def _match_expiry(expiry_list, desired_month_upper: Optional[str]) -> Optional[str]:
    """
    Pick an expiry string. If desired_month_upper is provided (e.g., 'DECEMBER'),
    pick the first expiry whose month name matches; else pick the nearest expiry (first in list).
    """
    if not expiry_list:
        return None
    if desired_month_upper:
        for exp in expiry_list:
            # Expect formats like '26-Dec-2025'
            if any(month[:3].upper() in exp.upper() for month in [desired_month_upper]):
                return exp
    return expiry_list[0]


def get_option_ltp(symbol: str, strike: float, option_type: str, expiry_month: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """
    Get LTP for given option contract from NSE option-chain.
    Returns (ltp, resolved_expiry) where ltp can be None if not found.
    """
    symbol = symbol.upper().replace(".NS", "")
    opt_type = option_type.upper()
    if opt_type not in {"CE", "PE"}:
        raise ValueError("option_type must be 'CE' or 'PE'")

    session = _create_session()
    url = NSE_OC_URL.format(symbol=symbol)
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # Find expiry to use
    expiry_list = data.get("records", {}).get("expiryDates", []) or data.get("records", {}).get("expiryDates", [])
    resolved_expiry = _match_expiry(expiry_list, expiry_month.upper() if expiry_month else None)
    if not resolved_expiry:
        return None, None

    # Search the data array for the matching strike and expiry
    entries = data.get("records", {}).get("data", [])
    ltp = None
    # NSE strikes are often rounded; use int for comparison when exact match isn't present
    strike_int = int(round(float(strike)))
    for row in entries:
        if row.get("expiryDate") != resolved_expiry:
            continue
        # Compare strike
        sp = row.get("strikePrice")
        if sp is None:
            continue
        if int(round(float(sp))) != strike_int:
            continue
        leg = row.get(opt_type)
        if leg and isinstance(leg, dict):
            ltp = leg.get("lastPrice")
            if ltp is not None:
                break

    return (float(ltp) if ltp is not None else None), resolved_expiry


