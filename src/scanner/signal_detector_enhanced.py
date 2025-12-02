"""
Enhanced signal detection with volume and momentum filters.

Only takes SuperTrend buy signals when:
1. Volume is above average (liquidity confirmation)
2. Price has positive momentum
3. Price is above key moving averages
"""

import pandas as pd
import numpy as np
import logging
from datetime import timedelta
from .signal_detector_fixed_exit import find_buy_sell_pairs_fixed_exit

logger = logging.getLogger(__name__)


def add_volume_momentum_filters(df):
    """
    Add volume and momentum indicators to DataFrame.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        DataFrame with additional columns:
        - volume_ma: 20-period volume moving average
        - volume_ratio: current volume / volume_ma
        - sma_20: 20-period price moving average
        - sma_50: 50-period price moving average
        - momentum_4w: 4-week price change %
        - rsi: Relative Strength Index (14-period)
    """
    df = df.copy()
    
    # Volume indicators
    df['volume_ma'] = df['Volume'].rolling(window=20, min_periods=10).mean()
    df['volume_ratio'] = df['Volume'] / df['volume_ma']
    
    # Moving averages
    df['sma_20'] = df['Close'].rolling(window=20, min_periods=10).mean()
    df['sma_50'] = df['Close'].rolling(window=50, min_periods=25).mean()
    
    # Momentum
    df['momentum_4w'] = df['Close'].pct_change(periods=4) * 100  # 4-week momentum
    
    # RSI calculation
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=7).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df


def find_buy_signals_with_filters(df, symbol, 
                                  volume_threshold=1.0,
                                  momentum_threshold=0,
                                  use_ma_filter=True,
                                  use_rsi_filter=True):
    """
    Find SuperTrend buy signals with volume/momentum confirmation.
    
    Args:
        df: DataFrame with SuperTrend indicators and filters
        symbol: Stock symbol
        volume_threshold: Minimum volume_ratio (default: 1.0 = average)
        momentum_threshold: Minimum 4-week momentum % (default: 0 = positive)
        use_ma_filter: Require price > SMA20 (default: True)
        use_rsi_filter: Require RSI > 40 (default: True)
        
    Returns:
        list of dicts with buy signal information
    """
    if df is None or len(df) == 0:
        return []
    
    if 'ST_dir' not in df.columns:
        logger.error(f"DataFrame must have ST_dir column")
        return []
    
    buy_signals = []
    rejected_signals = {
        'volume': 0,
        'momentum': 0,
        'ma': 0,
        'rsi': 0,
        'total_supertrend': 0
    }
    
    df = df.copy()
    df = df.sort_values('Date').reset_index(drop=True)
    
    for i in range(1, len(df)):
        prev_dir = df['ST_dir'].iloc[i-1]
        curr_dir = df['ST_dir'].iloc[i]
        
        # Skip if direction is NaN
        if pd.isna(curr_dir) or pd.isna(prev_dir):
            continue
        
        # SuperTrend buy signal: direction changes from -1 to 1
        if prev_dir == -1 and curr_dir == 1:
            rejected_signals['total_supertrend'] += 1
            
            buy_date = df['Date'].iloc[i]
            buy_price = df['Close'].iloc[i]
            
            # === APPLY FILTERS ===
            
            # 1. Volume filter
            volume_ratio = df['volume_ratio'].iloc[i]
            if pd.isna(volume_ratio) or volume_ratio < volume_threshold:
                rejected_signals['volume'] += 1
                logger.debug(f"{symbol}: Signal rejected - low volume ({volume_ratio:.2f})")
                continue
            
            # 2. Momentum filter
            momentum = df['momentum_4w'].iloc[i]
            if pd.isna(momentum) or momentum < momentum_threshold:
                rejected_signals['momentum'] += 1
                logger.debug(f"{symbol}: Signal rejected - weak momentum ({momentum:.2f}%)")
                continue
            
            # 3. Moving average filter
            if use_ma_filter:
                sma_20 = df['sma_20'].iloc[i]
                if pd.isna(sma_20) or buy_price < sma_20:
                    rejected_signals['ma'] += 1
                    logger.debug(f"{symbol}: Signal rejected - price below SMA20")
                    continue
            
            # 4. RSI filter
            if use_rsi_filter:
                rsi = df['rsi'].iloc[i]
                if pd.isna(rsi) or rsi < 40:
                    rejected_signals['rsi'] += 1
                    logger.debug(f"{symbol}: Signal rejected - RSI too low ({rsi:.1f})")
                    continue
            
            # === SIGNAL PASSED ALL FILTERS ===
            signal = {
                'symbol': symbol,
                'buy_date': buy_date,
                'buy_price': buy_price,
                'buy_idx': i,
                'volume_ratio': volume_ratio,
                'momentum_4w': momentum,
                'rsi': df['rsi'].iloc[i] if 'rsi' in df.columns else None,
                'sma_20': df['sma_20'].iloc[i] if 'sma_20' in df.columns else None
            }
            
            buy_signals.append(signal)
            logger.debug(f"{symbol}: ✓ BUY signal on {buy_date} at {buy_price} "
                        f"(vol: {volume_ratio:.2f}x, mom: {momentum:.1f}%)")
    
    # Log filter statistics
    if rejected_signals['total_supertrend'] > 0:
        logger.info(f"{symbol}: SuperTrend signals: {rejected_signals['total_supertrend']}, "
                   f"Passed filters: {len(buy_signals)}, "
                   f"Rejected (vol: {rejected_signals['volume']}, "
                   f"mom: {rejected_signals['momentum']}, "
                   f"ma: {rejected_signals['ma']}, "
                   f"rsi: {rejected_signals['rsi']})")
    
    return buy_signals


def detect_signals_enhanced(symbol, df, atr_period, multiplier,
                           profit_target=10.0, stop_loss=10.0, max_days=30,
                           volume_threshold=1.0, momentum_threshold=0,
                           use_ma_filter=True, use_rsi_filter=True):
    """
    Complete pipeline: compute SuperTrend, add filters, detect quality signals, apply fixed exits.
    
    Args:
        symbol: Stock symbol
        df: DataFrame with OHLCV data
        atr_period: ATR period for SuperTrend
        multiplier: Multiplier for SuperTrend
        profit_target: Profit target percentage
        stop_loss: Stop loss percentage
        max_days: Maximum holding period in days
        volume_threshold: Minimum volume ratio (1.0 = average volume)
        momentum_threshold: Minimum momentum % (0 = positive momentum)
        use_ma_filter: Require price > SMA20
        use_rsi_filter: Require RSI > 40
        
    Returns:
        tuple: (df_with_indicators, trades_list)
    """
    from .indicators import supertrend
    
    # Compute SuperTrend
    df_st = supertrend(df, atr_period=atr_period, multiplier=multiplier)
    
    # Add volume and momentum filters
    df_enhanced = add_volume_momentum_filters(df_st)
    
    # Find quality buy signals
    buy_signals = find_buy_signals_with_filters(
        df_enhanced, symbol,
        volume_threshold=volume_threshold,
        momentum_threshold=momentum_threshold,
        use_ma_filter=use_ma_filter,
        use_rsi_filter=use_rsi_filter
    )
    
    if not buy_signals:
        logger.info(f"{symbol}: No quality signals found (all filtered out)")
        return df_enhanced, []
    
    # Apply fixed exit strategy to each buy signal
    trades = []
    
    for signal in buy_signals:
        buy_idx = signal['buy_idx']
        buy_date = signal['buy_date']
        buy_price = signal['buy_price']
        
        # Calculate target prices
        target_price = buy_price * (1 + profit_target / 100)
        stop_price = buy_price * (1 - stop_loss / 100)
        max_exit_date = buy_date + timedelta(days=max_days)
        
        # Look forward to find exit point
        sell_date = None
        sell_price = None
        exit_reason = None
        
        for j in range(buy_idx + 1, len(df_enhanced)):
            check_date = df_enhanced['Date'].iloc[j]
            high = df_enhanced['High'].iloc[j]
            low = df_enhanced['Low'].iloc[j]
            close = df_enhanced['Close'].iloc[j]
            
            # Check profit target (highest priority)
            if high >= target_price:
                sell_date = check_date
                sell_price = target_price
                exit_reason = 'profit_target'
                break
            
            # Check stop loss
            if low <= stop_price:
                sell_date = check_date
                sell_price = stop_price
                exit_reason = 'stop_loss'
                break
            
            # Check SuperTrend sell signal (trend reversal)
            curr_st_dir = df_enhanced['ST_dir'].iloc[j]
            prev_st_dir = df_enhanced['ST_dir'].iloc[j-1] if j > 0 else None
            
            if not pd.isna(curr_st_dir) and not pd.isna(prev_st_dir):
                # Sell signal: uptrend (1) to downtrend (-1)
                if prev_st_dir == 1 and curr_st_dir == -1:
                    sell_date = check_date
                    sell_price = close  # Exit at close when trend reverses
                    exit_reason = 'supertrend_sell'
                    logger.debug(f"{symbol}: SuperTrend sell signal at {check_date}, exit at {close}")
                    break
            
            # Check time stop (last resort)
            if check_date >= max_exit_date:
                sell_date = check_date
                sell_price = close
                exit_reason = 'time_stop'
                break
        
        # Record trade if exit found
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
                'exit_reason': exit_reason,
                'volume_ratio': signal['volume_ratio'],
                'momentum_4w': signal['momentum_4w']
            }
            
            trades.append(trade)
    
    logger.info(f"{symbol}: Found {len(trades)} quality trades with enhanced filters")
    
    return df_enhanced, trades

