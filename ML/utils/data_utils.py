"""
Data utilities for fetching and processing stock data
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List
import yfinance as yf
from .logger import setup_logger
from .market_utils import is_trading_day

logger = setup_logger("data_utils")

def add_nse_suffix(symbol: str) -> str:
    """Add .NS suffix for NSE stocks in Yahoo Finance"""
    if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
        return f"{symbol}.NS"
    return symbol

def fetch_stock_data(
    symbol: str, 
    start_date: datetime, 
    end_date: datetime,
    interval: str = "1d"
) -> Optional[pd.DataFrame]:
    """
    Fetch stock data from Yahoo Finance
    
    Args:
        symbol: Stock symbol
        start_date: Start date
        end_date: End date
        interval: Data interval (1d, 4h, 1h)
    
    Returns:
        DataFrame with OHLCV data
    """
    try:
        symbol = add_nse_suffix(symbol)
        logger.info(f"Fetching data for {symbol} from {start_date} to {end_date}")
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date, interval=interval)
        
        if df.empty:
            logger.warning(f"No data found for {symbol}")
            return None
        
        # Reset index to have Date as column
        df.reset_index(inplace=True)
        
        # Standardize column names to lowercase
        # Handle both capitalized and lowercase versions
        column_mapping = {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
            'Adj Close': 'adj_close'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        # Also convert any remaining capitalized columns to lowercase
        df.columns = df.columns.str.lower()
        
        # Remove timezone info if present
        if 'date' in df.columns and hasattr(df['date'].dtype, 'tz'):
            df['date'] = df['date'].dt.tz_localize(None)
        
        logger.info(f"Fetched {len(df)} rows for {symbol}")
        return df[['date', 'open', 'high', 'low', 'close', 'volume']]
    
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return None

def fetch_index_data(index_symbol: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
    """
    Fetch index data (Nifty, Bank Nifty, etc.)
    
    Args:
        index_symbol: Index symbol (^NSEI for Nifty 50)
        start_date: Start date
        end_date: End date
    
    Returns:
        DataFrame with OHLCV data
    """
    try:
        logger.info(f"Fetching index data for {index_symbol}")
        ticker = yf.Ticker(index_symbol)
        df = ticker.history(start=start_date, end=end_date, interval="1d")
        
        if df.empty:
            logger.warning(f"No data found for {index_symbol}")
            return None
        
        df.reset_index(inplace=True)
        
        # Standardize column names
        column_mapping = {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
            'Adj Close': 'adj_close'
        }
        df.rename(columns=column_mapping, inplace=True)
        df.columns = df.columns.str.lower()
        
        if 'date' in df.columns and hasattr(df['date'].dtype, 'tz'):
            df['date'] = df['date'].dt.tz_localize(None)
        
        return df[['date', 'open', 'high', 'low', 'close', 'volume']]
    
    except Exception as e:
        logger.error(f"Error fetching index data for {index_symbol}: {e}")
        return None

def get_stock_info(symbol: str) -> dict:
    """
    Get stock information (sector, market cap, etc.)
    
    Args:
        symbol: Stock symbol
    
    Returns:
        Dictionary with stock info
    """
    try:
        symbol = add_nse_suffix(symbol)
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        return {
            'symbol': symbol,
            'sector': info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),
            'market_cap': info.get('marketCap', 0) / 10000000,  # Convert to Crores
            'pe_ratio': info.get('trailingPE', None),
            'pb_ratio': info.get('priceToBook', None),
            '52_week_high': info.get('fiftyTwoWeekHigh', None),
            '52_week_low': info.get('fiftyTwoWeekLow', None),
        }
    
    except Exception as e:
        logger.error(f"Error fetching info for {symbol}: {e}")
        return {}

def validate_data_quality(df: pd.DataFrame) -> bool:
    """
    Validate data quality
    
    Args:
        df: DataFrame with OHLCV data
    
    Returns:
        True if data quality is acceptable
    """
    if df is None or df.empty:
        return False
    
    # Check for required columns
    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
    if not all(col in df.columns for col in required_cols):
        logger.warning("Missing required columns")
        return False
    
    # Check for null values
    null_pct = df[required_cols].isnull().sum().sum() / (len(df) * len(required_cols))
    if null_pct > 0.1:  # More than 10% null values
        logger.warning(f"Too many null values: {null_pct:.2%}")
        return False
    
    # Check for zeros in OHLC
    zero_prices = (df[['open', 'high', 'low', 'close']] == 0).sum().sum()
    if zero_prices > 0:
        logger.warning(f"Found {zero_prices} zero prices")
        return False
    
    # Check high >= low
    invalid_bars = (df['high'] < df['low']).sum()
    if invalid_bars > 0:
        logger.warning(f"Found {invalid_bars} invalid bars (high < low)")
        return False
    
    return True

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and prepare data
    
    Args:
        df: DataFrame with OHLCV data
    
    Returns:
        Cleaned DataFrame
    """
    df = df.copy()
    
    # Ensure column names are lowercase
    df.columns = df.columns.str.lower()
    
    # Remove duplicates
    df.drop_duplicates(subset=['date'], keep='last', inplace=True)
    
    # Sort by date
    df.sort_values('date', inplace=True)
    
    # Forward fill missing values (limited to 2 days)
    df.fillna(method='ffill', limit=2, inplace=True)
    
    # Drop remaining NaN rows
    df.dropna(inplace=True)
    
    # Reset index
    df.reset_index(drop=True, inplace=True)
    
    return df

def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived columns to OHLCV data
    
    Args:
        df: DataFrame with OHLCV data
    
    Returns:
        DataFrame with derived columns
    """
    df = df.copy()
    
    # Price changes
    df['price_change'] = df['close'] - df['close'].shift(1)
    df['price_change_pct'] = df['price_change'] / df['close'].shift(1) * 100
    
    # High-Low range
    df['hl_range'] = df['high'] - df['low']
    df['hl_range_pct'] = df['hl_range'] / df['close'] * 100
    
    # Volume changes
    df['volume_change'] = df['volume'] - df['volume'].shift(1)
    df['volume_change_pct'] = df['volume_change'] / df['volume'].shift(1) * 100
    
    # Day of week (0=Monday, 6=Sunday)
    df['day_of_week'] = pd.to_datetime(df['date']).dt.dayofweek
    df['week_of_month'] = pd.to_datetime(df['date']).dt.day // 7 + 1
    df['month'] = pd.to_datetime(df['date']).dt.month
    df['quarter'] = pd.to_datetime(df['date']).dt.quarter
    
    return df

