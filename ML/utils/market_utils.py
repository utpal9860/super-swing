"""
Market utilities for Indian stock markets (NSE/BSE)
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict
from config import NSE_HOLIDAYS

def is_trading_day(date: datetime) -> bool:
    """
    Check if a given date is a trading day
    
    Args:
        date: Date to check
    
    Returns:
        True if trading day, False otherwise
    """
    # Check if weekend
    if date.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    
    # Check if holiday
    date_str = date.strftime("%Y-%m-%d")
    if date_str in NSE_HOLIDAYS:
        return False
    
    return True

def get_trading_days(start_date: datetime, end_date: datetime) -> List[datetime]:
    """
    Get list of trading days between two dates
    
    Args:
        start_date: Start date
        end_date: End date
    
    Returns:
        List of trading days
    """
    trading_days = []
    current_date = start_date
    
    while current_date <= end_date:
        if is_trading_day(current_date):
            trading_days.append(current_date)
        current_date += timedelta(days=1)
    
    return trading_days

def get_next_trading_day(date: datetime) -> datetime:
    """
    Get next trading day after given date
    
    Args:
        date: Current date
    
    Returns:
        Next trading day
    """
    next_day = date + timedelta(days=1)
    while not is_trading_day(next_day):
        next_day += timedelta(days=1)
    return next_day

def get_previous_trading_day(date: datetime) -> datetime:
    """
    Get previous trading day before given date
    
    Args:
        date: Current date
    
    Returns:
        Previous trading day
    """
    prev_day = date - timedelta(days=1)
    while not is_trading_day(prev_day):
        prev_day -= timedelta(days=1)
    return prev_day

def check_circuit_breaker(current_price: float, previous_close: float, limit: float = 0.20) -> bool:
    """
    Check if circuit breaker would be hit
    
    Args:
        current_price: Current price
        previous_close: Previous day close
        limit: Circuit breaker limit (default 20%)
    
    Returns:
        True if circuit breaker hit
    """
    price_change_pct = abs((current_price - previous_close) / previous_close)
    return price_change_pct >= limit

def get_market_trend(index_data: pd.DataFrame, period: int = 20) -> str:
    """
    Determine market trend based on index data
    
    Args:
        index_data: DataFrame with OHLCV data
        period: Period for trend calculation
    
    Returns:
        'BULLISH', 'BEARISH', or 'SIDEWAYS'
    """
    if len(index_data) < period:
        return 'UNKNOWN'
    
    # Calculate moving averages
    sma_20 = index_data['Close'].rolling(window=period).mean().iloc[-1]
    sma_50 = index_data['Close'].rolling(window=50).mean().iloc[-1] if len(index_data) >= 50 else sma_20
    current_price = index_data['Close'].iloc[-1]
    
    # Simple trend logic
    if current_price > sma_20 and sma_20 > sma_50:
        return 'BULLISH'
    elif current_price < sma_20 and sma_20 < sma_50:
        return 'BEARISH'
    else:
        return 'SIDEWAYS'

def categorize_market_cap(market_cap: float) -> str:
    """
    Categorize stock by market cap (Indian context)
    
    Args:
        market_cap: Market capitalization in crores
    
    Returns:
        'LARGE', 'MID', or 'SMALL'
    """
    if market_cap >= 20000:  # ₹20,000 Cr
        return 'LARGE'
    elif market_cap >= 5000:  # ₹5,000 Cr
        return 'MID'
    else:
        return 'SMALL'

def calculate_transaction_costs(trade_value: float, is_intraday: bool = False) -> Dict[str, float]:
    """
    Calculate total transaction costs for Indian markets
    
    Args:
        trade_value: Trade value in INR
        is_intraday: Whether it's an intraday trade
    
    Returns:
        Dictionary with cost breakdown
    """
    costs = {}
    
    # Brokerage
    brokerage_pct = 0.0003 if is_intraday else 0.0005
    costs['brokerage'] = min(trade_value * brokerage_pct, 20)
    
    # STT (Securities Transaction Tax)
    costs['stt'] = trade_value * 0.001  # 0.1% on sell side
    
    # Exchange charges
    costs['exchange'] = trade_value * 0.0000325  # NSE: 0.00325%
    
    # GST (18% on brokerage + exchange)
    costs['gst'] = (costs['brokerage'] + costs['exchange']) * 0.18
    
    # SEBI charges
    costs['sebi'] = trade_value * 0.0000001  # Negligible
    
    # Stamp duty
    costs['stamp_duty'] = trade_value * 0.00015  # 0.015% on buy side
    
    # Total (round-trip: buy + sell)
    costs['total_one_way'] = sum(costs.values())
    costs['total_round_trip'] = costs['total_one_way'] * 2
    
    return costs

