"""Signal detection with fixed profit/loss targets and time-based exit."""
import pandas as pd
import numpy as np
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


def find_buy_sell_pairs_fixed_exit(df, symbol, profit_target=10.0, stop_loss=10.0, max_days=30):
    """
    Find buy→sell signal pairs with fixed exit rules.
    
    Exit conditions (whichever comes first):
    1. Price reaches profit_target% above buy price
    2. Price reaches stop_loss% below buy price
    3. max_days elapsed from buy date
    
    Args:
        df: DataFrame with SuperTrend indicators (must have ST_dir and Date columns)
        symbol: Stock symbol for labeling
        profit_target: Profit target percentage (default: 10%)
        stop_loss: Stop loss percentage (default: 10%)
        max_days: Maximum holding period in days (default: 30)
        
    Returns:
        list of dict: Each dict contains trade information
    """
    if df is None or len(df) == 0:
        return []
    
    if 'ST_dir' not in df.columns:
        logger.error(f"DataFrame must have ST_dir column")
        return []
    
    trades = []
    
    # Convert to daily data for more precise exit detection
    # If data is weekly, we'll check each week
    df = df.copy()
    df = df.sort_values('Date').reset_index(drop=True)
    
    i = 1  # Start from index 1 (need previous bar to detect change)
    while i < len(df):
        prev_dir = df['ST_dir'].iloc[i-1]
        curr_dir = df['ST_dir'].iloc[i]
        
        # Skip if direction is NaN
        if pd.isna(curr_dir) or pd.isna(prev_dir):
            i += 1
            continue
        
        # Buy signal: direction changes from -1 to 1 (downtrend to uptrend)
        if prev_dir == -1 and curr_dir == 1:
            buy_date = df['Date'].iloc[i]
            buy_price = df['Close'].iloc[i]
            buy_idx = i
            
            logger.debug(f"{symbol}: BUY signal on {buy_date} at {buy_price}")
            
            # Calculate target prices
            target_price = buy_price * (1 + profit_target / 100)
            stop_price = buy_price * (1 - stop_loss / 100)
            max_exit_date = buy_date + timedelta(days=max_days)
            
            # Look forward to find exit point
            sell_date = None
            sell_price = None
            exit_reason = None
            
            for j in range(i + 1, len(df)):
                check_date = df['Date'].iloc[j]
                high = df['High'].iloc[j]
                low = df['Low'].iloc[j]
                close = df['Close'].iloc[j]
                
                # Check if profit target hit (using high of the candle)
                if high >= target_price:
                    sell_date = check_date
                    sell_price = target_price  # Assume we got out at target
                    exit_reason = 'profit_target'
                    logger.debug(f"{symbol}: Profit target hit on {sell_date}")
                    break
                
                # Check if stop loss hit (using low of the candle)
                if low <= stop_price:
                    sell_date = check_date
                    sell_price = stop_price  # Assume we got stopped out
                    exit_reason = 'stop_loss'
                    logger.debug(f"{symbol}: Stop loss hit on {sell_date}")
                    break
                
                # Check if max holding period reached
                if check_date >= max_exit_date:
                    sell_date = check_date
                    sell_price = close  # Exit at close price
                    exit_reason = 'time_stop'
                    logger.debug(f"{symbol}: Time stop at {sell_date}, price: {sell_price}")
                    break
            
            # If we found an exit point, record the trade
            if sell_date is not None:
                pct_change = ((sell_price - buy_price) / buy_price) * 100
                days_held = (sell_date - buy_date).days
                weeks_held = days_held / 7
                
                trade = {
                    'symbol': symbol,
                    'buy_date': buy_date,
                    'buy_price': buy_price,
                    'sell_date': sell_date,
                    'sell_price': sell_price,
                    'pct_change': pct_change,
                    'days_held': days_held,
                    'weeks_held': weeks_held,
                    'exit_reason': exit_reason
                }
                
                trades.append(trade)
                logger.debug(f"{symbol}: Trade completed - {exit_reason}, "
                           f"return: {pct_change:.2f}%, held: {days_held} days")
                
                # Move to the sell index to look for next buy signal
                # Find the index corresponding to sell_date
                next_idx = df[df['Date'] >= sell_date].index[0] if len(df[df['Date'] >= sell_date]) > 0 else len(df)
                i = next_idx
            else:
                # No exit found (data ends before any exit condition)
                # Could optionally record as open trade
                i += 1
        else:
            i += 1
    
    logger.info(f"{symbol}: Found {len(trades)} trade pairs with fixed exits")
    return trades


def detect_signals_fixed_exit(symbol, df, atr_period, multiplier, 
                              profit_target=10.0, stop_loss=10.0, max_days=30):
    """
    Complete pipeline: compute SuperTrend and detect signals with fixed exits.
    
    Args:
        symbol: Stock symbol
        df: DataFrame with OHLCV data
        atr_period: ATR period for SuperTrend
        multiplier: Multiplier for SuperTrend
        profit_target: Profit target percentage (default: 10%)
        stop_loss: Stop loss percentage (default: 10%)
        max_days: Maximum holding period in days (default: 30)
        
    Returns:
        tuple: (df_with_indicators, trades_list)
    """
    from .indicators import supertrend
    
    # Compute SuperTrend
    df_st = supertrend(df, atr_period=atr_period, multiplier=multiplier)
    
    # Find buy/sell pairs with fixed exits
    trades = find_buy_sell_pairs_fixed_exit(
        df_st, symbol, 
        profit_target=profit_target,
        stop_loss=stop_loss,
        max_days=max_days
    )
    
    return df_st, trades

