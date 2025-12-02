"""Technical indicators implementation."""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def atr(df, period=10):
    """
    Calculate Average True Range (ATR).
    
    Args:
        df: DataFrame with 'High', 'Low', 'Close' columns
        period: ATR period (default: 10)
        
    Returns:
        pandas.Series: ATR values
    """
    high_low = df['High'] - df['Low']
    high_prev_close = (df['High'] - df['Close'].shift()).abs()
    low_prev_close = (df['Low'] - df['Close'].shift()).abs()
    
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def supertrend(df, atr_period=10, multiplier=3.0):
    """
    Calculate SuperTrend indicator.
    
    Args:
        df: DataFrame with OHLC data
        atr_period: Period for ATR calculation (default: 10)
        multiplier: Multiplier for ATR (default: 3.0)
        
    Returns:
        DataFrame with additional columns:
            - ATR: Average True Range
            - ST: SuperTrend value
            - ST_dir: Direction (1 for uptrend, -1 for downtrend)
            - basic_ub: Basic upper band
            - basic_lb: Basic lower band
            - final_ub: Final upper band
            - final_lb: Final lower band
    """
    df = df.copy()
    
    # Calculate ATR
    df['ATR'] = atr(df, atr_period)
    
    # Calculate basic bands
    hl2 = (df['High'] + df['Low']) / 2
    df['basic_ub'] = hl2 + multiplier * df['ATR']
    df['basic_lb'] = hl2 - multiplier * df['ATR']
    
    # Initialize final bands
    df['final_ub'] = df['basic_ub']
    df['final_lb'] = df['basic_lb']
    
    # Calculate final upper band
    for i in range(atr_period, len(df)):
        if df['basic_ub'].iloc[i] < df['final_ub'].iloc[i-1] or df['Close'].iloc[i-1] > df['final_ub'].iloc[i-1]:
            df.loc[df.index[i], 'final_ub'] = df['basic_ub'].iloc[i]
        else:
            df.loc[df.index[i], 'final_ub'] = df['final_ub'].iloc[i-1]
            
        # Calculate final lower band
        if df['basic_lb'].iloc[i] > df['final_lb'].iloc[i-1] or df['Close'].iloc[i-1] < df['final_lb'].iloc[i-1]:
            df.loc[df.index[i], 'final_lb'] = df['basic_lb'].iloc[i]
        else:
            df.loc[df.index[i], 'final_lb'] = df['final_lb'].iloc[i-1]
    
    # Determine SuperTrend direction and value
    df['ST'] = np.nan
    df['ST_dir'] = 1  # Start with uptrend
    
    for i in range(atr_period, len(df)):
        if i == atr_period:
            # Initial direction
            if df['Close'].iloc[i] <= df['final_ub'].iloc[i]:
                df.loc[df.index[i], 'ST_dir'] = -1
                df.loc[df.index[i], 'ST'] = df['final_ub'].iloc[i]
            else:
                df.loc[df.index[i], 'ST_dir'] = 1
                df.loc[df.index[i], 'ST'] = df['final_lb'].iloc[i]
        else:
            # Previous direction
            prev_dir = df['ST_dir'].iloc[i-1]
            
            if prev_dir == 1:
                # Was in uptrend
                if df['Close'].iloc[i] <= df['final_lb'].iloc[i]:
                    # Switch to downtrend
                    df.loc[df.index[i], 'ST_dir'] = -1
                    df.loc[df.index[i], 'ST'] = df['final_ub'].iloc[i]
                else:
                    # Continue uptrend
                    df.loc[df.index[i], 'ST_dir'] = 1
                    df.loc[df.index[i], 'ST'] = df['final_lb'].iloc[i]
            else:
                # Was in downtrend
                if df['Close'].iloc[i] >= df['final_ub'].iloc[i]:
                    # Switch to uptrend
                    df.loc[df.index[i], 'ST_dir'] = 1
                    df.loc[df.index[i], 'ST'] = df['final_lb'].iloc[i]
                else:
                    # Continue downtrend
                    df.loc[df.index[i], 'ST_dir'] = -1
                    df.loc[df.index[i], 'ST'] = df['final_ub'].iloc[i]
    
    logger.debug(f"SuperTrend calculated: {len(df)} bars, {df['ST'].notna().sum()} valid ST values")
    
    return df


def calculate_sma(df, window=20):
    """
    Calculate Simple Moving Average.
    
    Args:
        df: DataFrame with 'Close' column
        window: Period for SMA (default: 20)
        
    Returns:
        pandas.Series: SMA values
    """
    return df['Close'].rolling(window=window).mean()


def calculate_rsi(df, window=14):
    """
    Calculate Relative Strength Index (RSI).
    
    Args:
        df: DataFrame with 'Close' column
        window: Period for RSI (default: 14)
        
    Returns:
        pandas.Series: RSI values (0-100)
    """
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_momentum(df, window=4):
    """
    Calculate momentum as percentage change over a window.
    
    Args:
        df: DataFrame with 'Close' column
        window: Number of periods to look back (default: 4)
        
    Returns:
        pandas.Series: Momentum as percentage change
    """
    return ((df['Close'] - df['Close'].shift(window)) / df['Close'].shift(window)) * 100
