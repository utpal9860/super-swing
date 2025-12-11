"""
Parses textual trade signals from Telegram messages.
Target format example:

BUY ASHOKLEY 163 CE ABOVE 3.75
TARGET :- 4.25 / 5
SL :- PAID
DECEMBER EXPIRY
"""
from __future__ import annotations

import re
from typing import Dict, Optional, List


MONTHS = [
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
]


def _to_upper(text: str) -> str:
    return text.upper() if text else ""


def parse_signal(message_text: str) -> Optional[Dict]:
    """
    Parse a trade signal from free-form message text.
    Returns a dict with parsed fields or None if not matched.
    """
    if not message_text:
        return None

    text = _to_upper(message_text)

    # Primary line: BUY ASHOKLEY 163 CE ABOVE 3.75
    header_re = re.compile(
        r"\b(?P<action>BUY|SELL)\s+"
        r"(?P<symbol>[A-Z\-]+)\s+"
        r"(?P<strike>\d+(?:\.\d+)?)\s+"
        r"(?P<option_type>CE|PE)\s+"
        r"(?P<trigger_type>ABOVE|BELOW)\s+"
        r"(?P<trigger_price>\d+(?:\.\d+)?)\b",
        re.IGNORECASE | re.MULTILINE,
    )
    header_match = header_re.search(text)
    if not header_match:
        return None

    action = header_match.group("action")
    symbol = header_match.group("symbol")
    strike = float(header_match.group("strike"))
    option_type = header_match.group("option_type")
    trigger_type = header_match.group("trigger_type")
    trigger_price = float(header_match.group("trigger_price"))

    # Targets line: TARGET :- 4.25 / 5
    targets_re = re.compile(
        r"\bTARGET\s*[:\-]*\s*(?P<t1>\d+(?:\.\d+)?)"
        r"(?:\s*/\s*(?P<t2>\d+(?:\.\d+)?))?",
        re.IGNORECASE,
    )
    targets_match = targets_re.search(text)
    targets: List[float] = []
    if targets_match:
        t1 = targets_match.group("t1")
        t2 = targets_match.group("t2")
        if t1:
            targets.append(float(t1))
        if t2:
            targets.append(float(t2))

    # Stop-loss line: SL :- PAID or SL :- 3.2
    sl_re = re.compile(
        r"\bSL\s*[:\-]*\s*(?P<sl>(PAID|\d+(?:\.\d+)?))\b",
        re.IGNORECASE,
    )
    sl_match = sl_re.search(text)
    stop_loss: Optional[str] = None
    if sl_match:
        stop_loss = sl_match.group("sl")

    # Expiry parsing: Handle both explicit dates and month names
    # Priority 1: Explicit date formats like "11 December", "11-Dec", "11/12", "11-12-2025"
    # Priority 2: Month name like "DECEMBER EXPIRY"
    
    from datetime import datetime
    
    expiry_date_str: Optional[str] = None
    expiry_month: Optional[str] = None
    
    # Try to match explicit date formats first
    # Pattern 1: "11 December" or "11 DECEMBER" (day + month name)
    date_month_re = re.compile(
        r"\b(?P<day>\d{1,2})\s+(?P<month>(" + "|".join(MONTHS) + r"))\b",
        re.IGNORECASE,
    )
    date_month_match = date_month_re.search(text)
    if date_month_match:
        day = int(date_month_match.group("day"))
        month_name = date_month_match.group("month").upper()
        month_names = {
            'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4,
            'MAY': 5, 'JUNE': 6, 'JULY': 7, 'AUGUST': 8,
            'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12
        }
        month_num = month_names.get(month_name)
        if month_num:
            # Use current year, or next year if month has passed
            current_year = datetime.now().year
            current_date = datetime.now()
            if month_num < current_date.month or (month_num == current_date.month and day < current_date.day):
                year = current_year + 1
            else:
                year = current_year
            
            try:
                # Validate the date (e.g., Feb 30 doesn't exist)
                expiry_date = datetime(year, month_num, day)
                # Format as "11-Dec-2025"
                expiry_date_str = expiry_date.strftime('%d-%b-%Y')
            except ValueError:
                # Invalid date (e.g., Feb 30), fall back to month name
                expiry_month = month_name
    
    # Pattern 2: "11-Dec" or "11/12" or "11-12-2025" (numeric date formats)
    if not expiry_date_str:
        numeric_date_re = re.compile(
            r"\b(?P<day>\d{1,2})[-\/](?P<month>\d{1,2})(?:[-\/](?P<year>\d{2,4}))?\b",
            re.IGNORECASE,
        )
        numeric_date_match = numeric_date_re.search(text)
        if numeric_date_match:
            day = int(numeric_date_match.group("day"))
            month = int(numeric_date_match.group("month"))
            year_str = numeric_date_match.group("year")
            
            if year_str:
                if len(year_str) == 2:
                    year = 2000 + int(year_str)
                else:
                    year = int(year_str)
            else:
                # No year specified, use current or next year
                current_year = datetime.now().year
                current_date = datetime.now()
                if month < current_date.month or (month == current_date.month and day < current_date.day):
                    year = current_year + 1
                else:
                    year = current_year
            
            try:
                expiry_date = datetime(year, month, day)
                expiry_date_str = expiry_date.strftime('%d-%b-%Y')
            except ValueError:
                pass  # Invalid date, continue to month name fallback
    
    # Pattern 3: Month name only like "DECEMBER EXPIRY"
    if not expiry_date_str:
        expiry_re = re.compile(
            r"\b(?P<month>(" + "|".join(MONTHS) + r"))\s+EXPIRY\b",
            re.IGNORECASE,
        )
        expiry_match = expiry_re.search(text)
        if expiry_match:
            expiry_month = expiry_match.group("month").upper()

    parsed = {
        "action": action,
        "symbol": symbol,
        "strike": strike,
        "option_type": option_type,  # CE or PE
        "trigger_type": trigger_type,  # ABOVE or BELOW
        "trigger_price": trigger_price,
        "targets": targets,
        "stop_loss": stop_loss,
        "expiry_month": expiry_date_str if expiry_date_str else expiry_month,  # Date format (e.g., "11-Dec-2025") or month name (e.g., "DECEMBER")
    }
    return parsed


