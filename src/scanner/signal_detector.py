"""Signal detection and buy/sell pairing."""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def find_buy_sell_pairs(df, symbol, include_open=False):
    """
    Find buy→sell signal pairs from SuperTrend data.
    
    A buy signal occurs when ST_dir changes from -1 to 1 (downtrend to uptrend).
    A sell signal occurs when ST_dir changes from 1 to -1 (uptrend to downtrend).
    
    Args:
        df: DataFrame with SuperTrend indicators (must have ST_dir and Date columns)
        symbol: Stock symbol for labeling
        include_open: Whether to include open trades (no sell yet)
        
    Returns:
        list of dict: Each dict contains trade information
            {symbol, buy_date, buy_price, sell_date, sell_price, pct_change, weeks_held}
    """
    if df is None or len(df) == 0:
        return []
    
    if 'ST_dir' not in df.columns:
        logger.error(f"DataFrame must have ST_dir column")
        return []
    
    trades = []
    last_buy_date = None
    last_buy_price = None
    last_buy_idx = None
    
    # Iterate through data chronologically
    for i in range(1, len(df)):
        prev_dir = df['ST_dir'].iloc[i-1]
        curr_dir = df['ST_dir'].iloc[i]
        
        # Skip if either direction is NaN
        if pd.isna(prev_dir) or pd.isna(curr_dir):
            continue
        
        # Buy signal: direction changes from -1 to 1
        if prev_dir == -1 and curr_dir == 1:
            # If there was an open buy, close it first (shouldn't happen with proper logic)
            if last_buy_date is not None:
                logger.warning(f"{symbol}: New buy signal before sell, closing previous trade")
                
            last_buy_date = df['Date'].iloc[i]
            last_buy_price = df['Close'].iloc[i]
            last_buy_idx = i
            logger.debug(f"{symbol}: BUY signal on {last_buy_date} at {last_buy_price}")
        
        # Sell signal: direction changes from 1 to -1
        elif prev_dir == 1 and curr_dir == -1:
            if last_buy_date is not None:
                sell_date = df['Date'].iloc[i]
                sell_price = df['Close'].iloc[i]
                
                # Calculate metrics
                pct_change = ((sell_price - last_buy_price) / last_buy_price) * 100
                weeks_held = (sell_date - last_buy_date).days / 7
                
                trade = {
                    'symbol': symbol,
                    'buy_date': last_buy_date,
                    'buy_price': last_buy_price,
                    'sell_date': sell_date,
                    'sell_price': sell_price,
                    'pct_change': pct_change,
                    'weeks_held': weeks_held
                }
                
                trades.append(trade)
                logger.debug(f"{symbol}: SELL signal on {sell_date} at {sell_price}, "
                           f"return: {pct_change:.2f}%, held: {weeks_held:.1f} weeks")
                
                # Reset for next trade
                last_buy_date = None
                last_buy_price = None
                last_buy_idx = None
    
    # Handle open trade at end of data
    if last_buy_date is not None and include_open:
        trade = {
            'symbol': symbol,
            'buy_date': last_buy_date,
            'buy_price': last_buy_price,
            'sell_date': None,
            'sell_price': None,
            'pct_change': None,
            'weeks_held': None
        }
        trades.append(trade)
        logger.debug(f"{symbol}: Open trade from {last_buy_date}")
    
    logger.info(f"{symbol}: Found {len(trades)} trade pairs")
    return trades


def detect_signals_for_symbol(symbol, df, atr_period, multiplier, include_open=False):
    """
    Complete pipeline: compute SuperTrend and detect signals for a symbol.
    
    Args:
        symbol: Stock symbol
        df: DataFrame with OHLCV data
        atr_period: ATR period for SuperTrend
        multiplier: Multiplier for SuperTrend
        include_open: Include open trades
        
    Returns:
        tuple: (df_with_indicators, trades_list)
    """
    from .indicators import supertrend
    
    # Compute SuperTrend
    df_st = supertrend(df, atr_period=atr_period, multiplier=multiplier)
    
    # Find buy/sell pairs
    trades = find_buy_sell_pairs(df_st, symbol, include_open=include_open)
    
    return df_st, trades

