"""
NSE Option utilities: fetch LTP from NSE option-chain.
"""
from __future__ import annotations

from typing import Optional, Tuple, Dict
import requests
import json
from pathlib import Path
from datetime import datetime, timedelta
import calendar
import logging

logger = logging.getLogger(__name__)

NSE_OC_URL_EQUITIES = "https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
NSE_OC_URL_INDICES = "https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
NSE_REFERER = "https://www.nseindia.com/option-chain"

# List of index symbols (not equities)
INDEX_SYMBOLS = {'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX', 'BANKEX', 'SENSEX50', 'NIFTYNXT50'}

# NSE/BSE Trading Holidays 2024-2025 (update annually)
# Format: "YYYY-MM-DD"
NSE_BSE_HOLIDAYS = [
    "2024-01-26", "2024-03-08", "2024-03-25", "2024-03-29", "2024-04-11", "2024-04-17",
    "2024-04-21", "2024-05-01", "2024-05-23", "2024-06-17", "2024-07-17", "2024-08-15",
    "2024-08-26", "2024-10-02", "2024-10-12", "2024-11-01", "2024-11-02", "2024-11-15",
    "2024-12-25",
    "2025-01-26", "2025-03-14", "2025-03-31", "2025-04-10", "2025-04-14", "2025-04-18",
    "2025-05-01", "2025-08-15", "2025-08-27", "2025-10-02", "2025-10-21", "2025-11-01",
    "2025-11-05", "2025-12-25",
]

# Index expiry schedules (as per NSE/BSE rules)
# Format: {symbol: (expiry_day_of_week, expiry_type)}
# expiry_day_of_week: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday
# expiry_type: 'weekly' or 'monthly' (last day of month)
INDEX_EXPIRY_SCHEDULE = {
    'NIFTY': (1, 'weekly'),  # Tuesday - weekly contracts
    'BANKNIFTY': (1, 'monthly'),  # Last Tuesday - monthly contracts
    'FINNIFTY': (1, 'monthly'),  # Last Tuesday - monthly contracts
    'MIDCPNIFTY': (1, 'monthly'),  # Last Tuesday - monthly contracts
    'NIFTYNXT50': (1, 'monthly'),  # Last Tuesday - monthly contracts (assumed, update if different)
    'SENSEX': (3, 'weekly'),  # Thursday - weekly contracts (BSE). If Thursday is holiday, advanced to previous trading day
    'BANKEX': (1, 'monthly'),  # Last Tuesday - monthly contracts (BSE)
    'SENSEX50': (1, 'monthly'),  # Last Tuesday - monthly contracts (BSE)
}
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
    session.get(NSE_REFERER, timeout=10)
    return session


def _get_last_thursday_of_month(year: int, month: int) -> datetime:
    """
    Calculate the last Thursday of a given month.
    NSE stock options expire on the last Thursday of the month.
    """
    # Get the last day of the month
    last_day = calendar.monthrange(year, month)[1]
    last_date = datetime(year, month, last_day)
    
    # Find the last Thursday
    # Thursday is weekday 3 (Monday=0, Tuesday=1, Wednesday=2, Thursday=3, etc.)
    weekday = last_date.weekday()
    if weekday == 3:  # Last day is Thursday
        return last_date
    elif weekday < 3:  # Last day is Mon, Tue, Wed - go back to previous Thursday
        days_back = weekday + 4  # Go back to previous week's Thursday
    else:  # Last day is Fri, Sat, Sun - go back to current week's Thursday
        days_back = weekday - 3
    
    last_thursday = last_date - timedelta(days=days_back)
    return last_thursday


def _get_next_weekday(from_date: datetime, target_weekday: int) -> datetime:
    """
    Calculate the next occurrence of a specific weekday from a given date.
    
    Args:
        from_date: Starting date
        target_weekday: Target weekday (0=Monday, 1=Tuesday, ..., 6=Sunday)
    
    Returns:
        Next occurrence of the target weekday
    """
    if from_date is None:
        from_date = datetime.now()
    
    days_ahead = (target_weekday - from_date.weekday()) % 7
    if days_ahead == 0:
        # If today is the target weekday, get next week's occurrence
        days_ahead = 7
    
    return from_date + timedelta(days=days_ahead)


def _is_trading_holiday(date: datetime) -> bool:
    """
    Check if a date is a trading holiday (weekend or market holiday).
    
    Args:
        date: Date to check
    
    Returns:
        True if it's a holiday, False if it's a trading day
    """
    # Check if weekend (Saturday=5, Sunday=6)
    if date.weekday() >= 5:
        return True
    
    # Check if it's a market holiday
    date_str = date.strftime('%Y-%m-%d')
    if date_str in NSE_BSE_HOLIDAYS:
        return True
    
    return False


def _adjust_for_trading_holiday(date: datetime) -> datetime:
    """
    Adjust expiry date if it falls on a non-trading day.
    For SENSEX: If Thursday is a holiday, expiry moves to previous trading day.
    
    Args:
        date: Date to check
    
    Returns:
        Adjusted date (or original if it's a trading day)
    """
    # Check if weekend (Saturday=5, Sunday=6)
    if date.weekday() >= 5:
        # Move back to Friday (weekday 4)
        days_back = date.weekday() - 4
        return date - timedelta(days=days_back)
    
    # For market holidays, we'd need a holiday calendar
    # For now, if it's a weekday, assume it's a trading day
    # The exchange will handle holiday adjustments
    return date


def _get_previous_trading_day(date: datetime) -> datetime:
    """
    Get the previous trading day (skip weekends and holidays).
    
    Args:
        date: Starting date
    
    Returns:
        Previous trading day
    """
    prev_day = date - timedelta(days=1)
    while _is_trading_holiday(prev_day):
        prev_day = prev_day - timedelta(days=1)
    return prev_day


def _get_last_weekday_of_month(year: int, month: int, target_weekday: int) -> datetime:
    """
    Calculate the last occurrence of a specific weekday in a given month.
    
    Args:
        year: Year
        month: Month (1-12)
        target_weekday: Target weekday (0=Monday, 1=Tuesday, ..., 6=Sunday)
    
    Returns:
        Last occurrence of the target weekday in the month
    """
    # Get the last day of the month
    last_day = calendar.monthrange(year, month)[1]
    last_date = datetime(year, month, last_day)
    
    # Find the last occurrence of target weekday
    weekday = last_date.weekday()
    if weekday == target_weekday:
        return last_date
    elif weekday < target_weekday:
        # Last day is before target weekday, go back to previous week
        days_back = weekday + (7 - target_weekday) + 1
    else:
        # Last day is after target weekday, go back to current week
        days_back = weekday - target_weekday
    
    return last_date - timedelta(days=days_back)


def calculate_option_expiry(symbol: str, expiry_month: Optional[str] = None, reference_date: datetime = None, force_recalculate: bool = False) -> Optional[str]:
    """
    Calculate option expiry date based on NSE rules:
    - Stock options: Last Thursday of the month
    - Index options: Weekly/Bi-weekly Tuesdays
    
    Args:
        symbol: Underlying symbol (e.g., "PRESTIGE", "BANKNIFTY")
        expiry_month: Optional month name hint (e.g., "DECEMBER") or date format (e.g., "30-Dec-2025")
        reference_date: Reference date for calculation (defaults to today)
        force_recalculate: If True, recalculate even if expiry_month is in date format (useful for weekly contracts)
    
    Returns:
        Expiry date in format "30-Dec-2025" or None if calculation fails
    """
    if reference_date is None:
        reference_date = datetime.now()
    
    symbol = symbol.upper().replace(".NS", "")
    is_index = symbol in INDEX_SYMBOLS
    
    # If expiry_month is already in date format, return it (unless force_recalculate is True)
    # For weekly contracts, we should force recalculation to ensure correctness
    if expiry_month and '-' in expiry_month and not force_recalculate:
        try:
            # Validate the date format
            datetime.strptime(expiry_month, '%d-%b-%Y')
            return expiry_month
        except ValueError:
            pass  # Not a valid date format, continue with calculation
    
    try:
        if is_index:
            # Get index-specific expiry schedule
            expiry_day, expiry_type = INDEX_EXPIRY_SCHEDULE.get(symbol, (0, 'weekly'))
            
            if expiry_type == 'weekly':
                # Weekly expiry: Get next occurrence of the target weekday
                # CRITICAL: For weekly contracts, we ALWAYS want the next weekly expiry from reference_date
                # Never use monthly expiry logic for weekly contracts
                
                if expiry_month:
                    # Month hint provided - find next weekly expiry in that month
                    month_names = {
                        'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4,
                        'MAY': 5, 'JUNE': 6, 'JULY': 7, 'AUGUST': 8,
                        'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12
                    }
                    month_num = month_names.get(expiry_month.upper())
                    if month_num:
                        year = reference_date.year
                        if month_num < reference_date.month:
                            year += 1
                        
                        # Start from reference_date and find next weekly expiry in target month
                        # Keep iterating until we find one in the target month
                        candidate = _get_next_weekday(reference_date, expiry_day)
                        max_iterations = 10  # Safety limit (shouldn't need more than 4-5 weeks)
                        iterations = 0
                        
                        while (candidate.month != month_num or candidate.year != year) and iterations < max_iterations:
                            # If candidate is before target month, jump to target month
                            if candidate.year < year or (candidate.year == year and candidate.month < month_num):
                                # Jump to first day of target month and find next weekday
                                first_day = datetime(year, month_num, 1)
                                candidate = _get_next_weekday(first_day - timedelta(days=1), expiry_day)
                            elif candidate.month > month_num or candidate.year > year:
                                # We've passed the target month - this shouldn't happen if we're in the month
                                # But if it does, we've gone too far
                                logger.warning(f"[EXPIRY] {symbol} weekly: Candidate {candidate.date()} passed target month {month_num}/{year}")
                                break
                            else:
                                # Get next weekly expiry
                                candidate = _get_next_weekday(candidate, expiry_day)
                            iterations += 1
                        
                        if candidate.month == month_num and candidate.year == year:
                            expiry_date = candidate
                            logger.info(f"[EXPIRY] {symbol} weekly: Found expiry in target month {month_num}/{year}: {expiry_date.date()}")
                        else:
                            logger.warning(f"[EXPIRY] {symbol} weekly: Could not find expiry in target month {month_num}/{year}, using: {candidate.date()}")
                            expiry_date = candidate
                    else:
                        # Month name not recognized, just get next weekly expiry
                        expiry_date = _get_next_weekday(reference_date, expiry_day)
                        logger.warning(f"[EXPIRY] {symbol} weekly: Month hint '{expiry_month}' not recognized, using next weekly: {expiry_date.date()}")
                else:
                    # No month hint - just get next weekly expiry
                    expiry_date = _get_next_weekday(reference_date, expiry_day)
                    logger.debug(f"[EXPIRY] {symbol} weekly: No month hint, next {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][expiry_day]} from {reference_date.date()} = {expiry_date.date()}")
                
                # Ensure expiry_date is not in the past (safety check)
                if expiry_date < reference_date:
                    logger.warning(f"[EXPIRY] {symbol} weekly: Calculated expiry {expiry_date.date()} is in past, recalculating from {reference_date.date()}")
                    expiry_date = _get_next_weekday(reference_date, expiry_day)
                
                # For SENSEX (weekly Thursday), adjust if Thursday falls on a holiday
                # Move to previous trading day (at minimum, handle weekends)
                if symbol == 'SENSEX':
                    original_expiry = expiry_date
                    expiry_date = _adjust_for_trading_holiday(expiry_date)
                    if expiry_date != original_expiry:
                        logger.info(f"[EXPIRY] SENSEX: Adjusted expiry from {original_expiry.date()} to {expiry_date.date()} (holiday adjustment)")
            else:
                # Monthly expiry: Last occurrence of target weekday in the month
                if expiry_month:
                    month_names = {
                        'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4,
                        'MAY': 5, 'JUNE': 6, 'JULY': 7, 'AUGUST': 8,
                        'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12
                    }
                    month_num = month_names.get(expiry_month.upper())
                    if month_num:
                        year = reference_date.year
                        if month_num < reference_date.month:
                            year += 1
                        expiry_date = _get_last_weekday_of_month(year, month_num, expiry_day)
                    else:
                        # Month name not recognized, use current/next month
                        if reference_date.month == 12:
                            expiry_date = _get_last_weekday_of_month(reference_date.year + 1, 1, expiry_day)
                        else:
                            expiry_date = _get_last_weekday_of_month(reference_date.year, reference_date.month + 1, expiry_day)
                else:
                    # No month hint, use current/next month
                    if reference_date.month == 12:
                        expiry_date = _get_last_weekday_of_month(reference_date.year + 1, 1, expiry_day)
                    else:
                        expiry_date = _get_last_weekday_of_month(reference_date.year, reference_date.month + 1, expiry_day)
        else:
            # Stock options: Last Thursday of the month
            if expiry_month:
                # Parse month name to get year and month
                month_names = {
                    'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4,
                    'MAY': 5, 'JUNE': 6, 'JULY': 7, 'AUGUST': 8,
                    'SEPTEMBER': 9, 'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12
                }
                month_num = month_names.get(expiry_month.upper())
                if month_num:
                    # Use current year, or next year if month has passed
                    year = reference_date.year
                    if month_num < reference_date.month:
                        year += 1
                    expiry_date = _get_last_thursday_of_month(year, month_num)
                else:
                    # Month name not recognized, use current/next month
                    if reference_date.month == 12:
                        expiry_date = _get_last_thursday_of_month(reference_date.year + 1, 1)
                    else:
                        expiry_date = _get_last_thursday_of_month(reference_date.year, reference_date.month + 1)
            else:
                # No month hint, use current/next month
                if reference_date.month == 12:
                    expiry_date = _get_last_thursday_of_month(reference_date.year + 1, 1)
                else:
                    expiry_date = _get_last_thursday_of_month(reference_date.year, reference_date.month + 1)
        
        # Format as "30-Dec-2025"
        formatted_expiry = expiry_date.strftime('%d-%b-%Y')
        # Log expiry type (only available for indices)
        expiry_type_str = expiry_type if is_index else 'monthly (stock)'
        logger.info(f"[EXPIRY] {symbol}: Calculated expiry: {formatted_expiry} (type: {expiry_type_str}, reference: {reference_date.date()})")
        return formatted_expiry
    except Exception as e:
        logger.warning(f"Failed to calculate expiry for {symbol}: {e}")
        import traceback
        logger.error(f"Expiry calculation error traceback: {traceback.format_exc()}")
        return None


def validate_expiry_for_order(symbol: str, expiry_date_str: str, strike: float, option_type: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validate expiry date before placing order on Zerodha/Groww.
    
    This is CRITICAL for live trading - wrong expiry = wrong contract = wrong trade!
    
    Args:
        symbol: Underlying symbol (e.g., "SENSEX", "NIFTY")
        expiry_date_str: Expiry date in format "30-Dec-2025"
        strike: Strike price
        option_type: "CE" or "PE"
    
    Returns:
        Tuple of (is_valid, error_message, suggested_correct_expiry)
        - is_valid: True if expiry seems correct
        - error_message: Error description if invalid
        - suggested_correct_expiry: Suggested correct expiry if invalid (None if valid)
    
    Note:
        Zerodha/Groww APIs require the exact trading symbol which includes expiry.
        Format: SYMBOL + YY + MON + STRIKE + TYPE (e.g., "NIFTY25DEC59600CE")
        The expiry date must match an actual available contract on the exchange.
    """
    try:
        symbol = symbol.upper().replace(".NS", "")
        is_index = symbol in INDEX_SYMBOLS
        
        if not is_index:
            # For stocks, expiry should be last Thursday of month
            return True, "", None
        
        # Parse expiry date
        expiry_date = datetime.strptime(expiry_date_str, '%d-%b-%Y')
        today = datetime.now()
        
        # Check if expiry is in the past
        if expiry_date.date() < today.date():
            return False, f"Expiry date {expiry_date_str} is in the past", None
        
        # Get expected expiry schedule
        expiry_day, expiry_type = INDEX_EXPIRY_SCHEDULE.get(symbol, (0, 'weekly'))
        
        # Validate weekday matches expected schedule
        # For weekly contracts: Allow the date to be either the expected weekday OR the previous trading day
        # (in case the expected weekday was a holiday)
        expected_weekday = expiry_date.weekday()
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        expected_name = weekday_names[expiry_day]
        actual_name = weekday_names[expected_weekday]
        
        if expiry_type == 'weekly':
            # For weekly contracts, the date should be:
            # 1. The expected weekday (e.g., Thursday for SENSEX), OR
            # 2. The previous trading day (if expected weekday was a holiday)
            if expected_weekday == expiry_day:
                # Perfect match - it's the expected weekday
                pass
            elif expected_weekday == (expiry_day - 1) % 7:
                # It's the day before - might be holiday adjustment
                # Check if the expected weekday would have been a holiday
                expected_date = expiry_date + timedelta(days=1)
                if _is_trading_holiday(expected_date):
                    # Expected weekday was a holiday, so this is correct
                    logger.info(f"[VALIDATE] {symbol} expiry {expiry_date_str} is {actual_name} (day before {expected_name} which was a holiday) - valid")
                    pass
                else:
                    # Expected weekday was not a holiday, so this date is wrong
                    return False, f"Expiry date {expiry_date_str} is {actual_name}, but {symbol} weekly contracts expire on {expected_name} (and {expected_name} is not a holiday)", None
            else:
                # Wrong weekday entirely
                return False, f"Expiry date {expiry_date_str} is {actual_name}, but {symbol} weekly contracts expire on {expected_name} (or previous trading day if {expected_name} is a holiday)", None
        else:
            # For monthly contracts, must be exact weekday
            if expected_weekday != expiry_day:
                return False, f"Expiry date {expiry_date_str} is {actual_name}, but {symbol} {expiry_type} contracts expire on {expected_name}", None
        
        # For weekly contracts, check if it's a reasonable date (not too far in future)
        if expiry_type == 'weekly':
            days_ahead = (expiry_date.date() - today.date()).days
            if days_ahead > 35:  # More than 5 weeks ahead seems wrong
                # Calculate what the next weekly expiry should be
                correct_expiry = calculate_option_expiry(symbol, None, today)
                return False, f"Expiry date {expiry_date_str} is {days_ahead} days ahead, seems incorrect for weekly contract", correct_expiry
        
        # For monthly contracts, check if it's the last weekday of the month
        if expiry_type == 'monthly':
            last_weekday = _get_last_weekday_of_month(expiry_date.year, expiry_date.month, expiry_day)
            if expiry_date.date() != last_weekday.date():
                return False, f"Expiry date {expiry_date_str} is not the last {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][expiry_day]} of {expiry_date.strftime('%B %Y')}", last_weekday.strftime('%d-%b-%Y')
        
        return True, "", None
        
    except ValueError as e:
        return False, f"Invalid expiry date format: {expiry_date_str}", None
    except Exception as e:
        logger.error(f"Error validating expiry: {e}")
        return False, f"Validation error: {str(e)}", None


def _match_expiry(expiry_list, desired_month_upper: Optional[str]) -> Optional[str]:
    """Helper function for matching expiry from NSE API list (kept for backward compatibility)"""
    if not expiry_list:
        return None
    if desired_month_upper:
        for exp in expiry_list:
            if desired_month_upper[:3].upper() in exp.upper():
                return exp
    return expiry_list[0]


def get_option_ltp(symbol: str, strike: float, option_type: str, expiry_month: Optional[str]) -> Tuple[Optional[float], Optional[str], Optional[float], Optional[float]]:
    """
    Get LTP for given option contract from NSE option-chain.
    Returns (ltp, resolved_expiry, today_high, today_low).
    
    Automatically detects if symbol is an index (BANKNIFTY, NIFTY, etc.) or equity
    and uses the correct API endpoint.
    """
    symbol = symbol.upper().replace(".NS", "")
    opt_type = option_type.upper()
    if opt_type not in {"CE", "PE"}:
        raise ValueError("option_type must be 'CE' or 'PE'")

    # Determine if symbol is an index or equity
    is_index = symbol in INDEX_SYMBOLS
    url = NSE_OC_URL_INDICES.format(symbol=symbol) if is_index else NSE_OC_URL_EQUITIES.format(symbol=symbol)
    
    session = _create_session()
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # For index options, prefer fetching actual expiry dates from NSE API
    # (indices have complex weekly schedules that are best obtained from API)
    # For stock options, calculate based on last Thursday (more reliable)
    expiry_list = data.get("records", {}).get("expiryDates", [])
    
    # Check if expiry_month is already in date format (e.g., "16-Dec-2025")
    expiry_is_date_format = expiry_month and '-' in expiry_month
    
    if is_index:
        # For indices: Get actual expiry dates from API first
        if expiry_is_date_format:
            # If expiry_month is already a date, try to match it exactly in the expiry list
            # NSE API returns dates in format like "16-Dec-2025" or "16DEC2025"
            resolved_expiry = None
            for exp in expiry_list:
                # Normalize both dates for comparison
                try:
                    # Try to parse expiry_month as date
                    expiry_date = datetime.strptime(expiry_month, '%d-%b-%Y')
                    # Try to parse API expiry date (could be various formats)
                    api_expiry_str = str(exp).strip()
                    # Try common formats
                    for fmt in ['%d-%b-%Y', '%d%b%Y', '%Y-%m-%d', '%d/%m/%Y']:
                        try:
                            api_expiry_date = datetime.strptime(api_expiry_str, fmt)
                            if expiry_date.date() == api_expiry_date.date():
                                resolved_expiry = exp
                                break
                        except:
                            continue
                    if resolved_expiry:
                        break
                except:
                    # If parsing fails, try string matching
                    if expiry_month.upper() in str(exp).upper():
                        resolved_expiry = exp
                        break
            
            # If exact match not found, use the stored date format
            if not resolved_expiry:
                resolved_expiry = expiry_month
        else:
            # Month name format - use existing matching logic
            resolved_expiry = _match_expiry(expiry_list, expiry_month.upper() if expiry_month else None)
            if not resolved_expiry and expiry_list:
                # If month hint doesn't match, use nearest expiry
                resolved_expiry = expiry_list[0]
        
        if not resolved_expiry:
            # Fallback to calculation if API doesn't have expiry dates
            resolved_expiry = calculate_option_expiry(symbol, expiry_month)
            if not resolved_expiry:
                return None, None, None, None
    else:
        # For stocks: Calculate based on last Thursday (more reliable)
        resolved_expiry = calculate_option_expiry(symbol, expiry_month)
        if not resolved_expiry:
            # Fallback to API if calculation fails
            resolved_expiry = _match_expiry(expiry_list, expiry_month.upper() if expiry_month else None)
            if not resolved_expiry:
                return None, None, None, None

    entries = data.get("records", {}).get("data", [])
    ltp = None
    today_high = None
    today_low = None
    strike_int = int(round(float(strike)))
    for row in entries:
        if row.get("expiryDate") != resolved_expiry:
            continue
        sp = row.get("strikePrice")
        if sp is None:
            continue
        if int(round(float(sp))) != strike_int:
            continue
        leg = row.get(opt_type)
        if leg and isinstance(leg, dict):
            ltp = leg.get("lastPrice")
            # Try multiple possible field names for high/low
            today_high = leg.get("highPrice") or leg.get("high") or leg.get("dayHigh") or leg.get("intradayHigh")
            today_low = leg.get("lowPrice") or leg.get("low") or leg.get("dayLow") or leg.get("intradayLow")
            if ltp is not None:
                break

    return (
        float(ltp) if ltp is not None else None,
        resolved_expiry,
        float(today_high) if today_high is not None else None,
        float(today_low) if today_low is not None else None
    )


def get_option_lot_size(symbol: str) -> int:
    """
    Return lot size for the given underlying symbol from static JSON file.
    
    Args:
        symbol: Underlying symbol (e.g., "PRESTIGE", "BANKNIFTY")
    
    Returns:
        Lot size (defaults to 1 if not found)
    """
    underlying = symbol.upper().replace(".NS", "")
    
    # Load from static JSON file
    try:
        project_root = Path(__file__).resolve().parents[2]
        lot_file = project_root / "webapp" / "data" / "lot_sizes.json"
        if lot_file.exists():
            with lot_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return int(data.get(underlying, 1))
    except Exception as e:
        logger.warning(f"Failed to load lot size for {symbol} from static file: {e}")
    
    # Default fallback
    return 1


