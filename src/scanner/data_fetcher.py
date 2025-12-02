"""Data fetching module for OHLCV data."""
import pandas as pd
import yfinance as yf
import logging
from pathlib import Path
from datetime import datetime
from .utils import sanitize_symbol

logger = logging.getLogger(__name__)


def fetch_weekly(symbol, start_date, end_date, cache_dir):
    """
    Fetch weekly OHLCV data for a symbol.
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE.NS')
        start_date: Start date (datetime or string)
        end_date: End date (datetime or string)
        cache_dir: Directory to cache data
        
    Returns:
        pandas.DataFrame: Weekly OHLCV data with columns [Date, Open, High, Low, Close, Volume]
    """
    try:
        logger.info(f"Fetching data for {symbol} from {start_date} to {end_date}")
        
        # Fetch data using yfinance
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date, interval="1wk")
        
        if df.empty:
            logger.warning(f"No data found for {symbol}")
            return None
        
        # Reset index to have Date as a column
        df.reset_index(inplace=True)
        
        # Rename columns to standard format
        column_mapping = {
            'Open': 'Open',
            'High': 'High',
            'Low': 'Low',
            'Close': 'Close',
            'Volume': 'Volume'
        }
        
        # Select only needed columns
        needed_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        available_cols = [col for col in needed_cols if col in df.columns]
        df = df[available_cols]
        
        # Drop rows with NaN in critical columns
        df.dropna(subset=['Open', 'High', 'Low', 'Close'], inplace=True)
        
        if len(df) < 20:
            logger.warning(f"Insufficient data for {symbol}: only {len(df)} bars")
            return None
        
        # Save to cache
        cache_path = Path(cache_dir) / f"{sanitize_symbol(symbol)}.csv"
        df.to_csv(cache_path, index=False)
        logger.info(f"Cached {len(df)} bars for {symbol} to {cache_path}")
        
        return df
        
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {str(e)}")
        return None


def fetch_daily(symbol, start_date, end_date, cache_dir):
    """
    Fetch daily OHLCV data for a symbol.
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE.NS')
        start_date: Start date (datetime or string)
        end_date: End date (datetime or string)
        cache_dir: Directory to cache data
        
    Returns:
        pandas.DataFrame: Daily OHLCV data with columns [Date, Open, High, Low, Close, Volume]
    """
    try:
        # Fetch data using yfinance
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date, interval="1d")
        
        if df.empty:
            logger.warning(f"No data found for {symbol}")
            return None
        
        # Reset index to have Date as a column
        df.reset_index(inplace=True)
        
        # Select only needed columns
        needed_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        available_cols = [col for col in needed_cols if col in df.columns]
        df = df[available_cols]
        
        # Drop rows with NaN in critical columns
        df.dropna(subset=['Open', 'High', 'Low', 'Close'], inplace=True)
        
        if len(df) < 10:
            logger.warning(f"Insufficient data for {symbol}: only {len(df)} bars")
            return None
        
        # Save to cache
        cache_path = Path(cache_dir) / f"{sanitize_symbol(symbol)}_daily.csv"
        df.to_csv(cache_path, index=False)
        logger.debug(f"Cached {len(df)} daily bars for {symbol}")
        
        return df
        
    except Exception as e:
        logger.error(f"Error fetching daily data for {symbol}: {str(e)}")
        return None


def load_cached(symbol, cache_dir):
    """
    Load cached data for a symbol.
    
    Args:
        symbol: Stock symbol
        cache_dir: Cache directory
        
    Returns:
        pandas.DataFrame or None
    """
    cache_path = Path(cache_dir) / f"{sanitize_symbol(symbol)}.csv"
    
    if not cache_path.exists():
        logger.debug(f"No cached data for {symbol}")
        return None
    
    try:
        df = pd.read_csv(cache_path, parse_dates=['Date'])
        logger.info(f"Loaded cached data for {symbol}: {len(df)} bars")
        return df
    except Exception as e:
        logger.error(f"Error loading cached data for {symbol}: {str(e)}")
        return None


def fetch_symbols_from_csv(csv_path):
    """
    Load symbols from CSV file.
    
    Expected CSV format:
        symbol,exchange,sector (optional)
    or just:
        symbol
        
    Args:
        csv_path: Path to CSV file
        
    Returns:
        pandas.DataFrame with symbol information
    """
    try:
        df = pd.read_csv(csv_path)
        
        if 'symbol' not in df.columns:
            logger.error(f"CSV file must have 'symbol' column")
            return None
        
        # Add exchange suffix if needed
        if 'exchange' in df.columns:
            df['full_symbol'] = df.apply(
                lambda row: f"{row['symbol']}.{row['exchange']}" if pd.notna(row['exchange']) else row['symbol'],
                axis=1
            )
        else:
            df['full_symbol'] = df['symbol']
        
        logger.info(f"Loaded {len(df)} symbols from {csv_path}")
        return df
        
    except Exception as e:
        logger.error(f"Error loading symbols from CSV: {str(e)}")
        return None

