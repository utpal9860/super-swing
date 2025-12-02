"""
Data fetcher for stock universe and historical data
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from utils.data_utils import fetch_stock_data, fetch_index_data, get_stock_info
from utils.logger import setup_logger
from config import RAW_DATA_DIR, STOCK_UNIVERSE

logger = setup_logger("data_fetcher")

# Default NSE F&O stocks list (top liquid stocks)
DEFAULT_FNO_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT", "MARUTI",
    "HCLTECH", "BAJFINANCE", "WIPRO", "ULTRACEMCO", "TITAN", "NESTLEIND",
    "SUNPHARMA", "BAJAJFINSV", "TECHM", "POWERGRID", "TATASTEEL", "NTPC",
    "ONGC", "M&M", "COALINDIA", "ADANIPORTS", "TATAMOTORS", "JSWSTEEL",
    "HINDALCO", "INDUSINDBK", "GRASIM", "CIPLA", "DRREDDY", "EICHERMOT",
    "BAJAJ-AUTO", "DIVISLAB", "BRITANNIA", "SHREECEM", "APOLLOHOSP",
    "HEROMOTOCO", "UPL", "TATACONSUM", "SBILIFE", "VEDL", "ADANIENT",
    "PIDILITIND", "BANDHANBNK", "GODREJCP", "AMBUJACEM", "BERGEPAINT",
    "DABUR", "GAIL", "HAVELLS", "INDIGO", "MARICO", "MUTHOOTFIN", "PNB",
    "SIEMENS", "ACC", "BANKBARODA", "BIOCON", "BOSCHLTD", "CANBK",
    "CHOLAFIN", "COLPAL", "DLF", "HDFCLIFE", "HINDPETRO", "ICICIPRULI",
    "IOC", "IGL", "LICHSGFIN", "LUPIN", "MCDOWELL-N", "MOTHERSON",
    "NMDC", "PETRONET", "PFC", "PEL", "RECLTD", "SRF", "TATAPOWER",
    "TORNTPHARM", "TRENT", "VOLTAS", "ZEEL"
]

def get_stock_universe(universe_type: str = "FNO") -> List[str]:
    """
    Get stock universe to scan
    
    Args:
        universe_type: Type of universe (FNO, NIFTY50, NIFTY100, NIFTY200, ALL)
    
    Returns:
        List of stock tickers
    """
    if universe_type == "FNO":
        return DEFAULT_FNO_STOCKS
    elif universe_type == "NIFTY50":
        return DEFAULT_FNO_STOCKS[:50]  # Top 50
    elif universe_type == "NIFTY100":
        return DEFAULT_FNO_STOCKS
    else:
        return DEFAULT_FNO_STOCKS

def fetch_historical_data(
    ticker: str,
    start_date: datetime,
    end_date: datetime,
    save_csv: bool = True
) -> Optional[pd.DataFrame]:
    """
    Fetch and optionally save historical data
    
    Args:
        ticker: Stock ticker
        start_date: Start date
        end_date: End date
        save_csv: Save to CSV file
    
    Returns:
        DataFrame with OHLCV data
    """
    df = fetch_stock_data(ticker, start_date, end_date)
    
    if df is not None:
        # Ensure lowercase column names
        df.columns = df.columns.str.lower()
        
        if save_csv:
            # Save to CSV
            csv_path = RAW_DATA_DIR / f"{ticker}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
            df.to_csv(csv_path, index=False)
            logger.info(f"Saved data to {csv_path}")
    
    return df

def batch_fetch_data(
    tickers: List[str],
    start_date: datetime,
    end_date: datetime,
    save_csv: bool = True
) -> Dict[str, pd.DataFrame]:
    """
    Fetch data for multiple stocks
    
    Args:
        tickers: List of stock tickers
        start_date: Start date
        end_date: End date
        save_csv: Save to CSV files
    
    Returns:
        Dictionary of {ticker: DataFrame}
    """
    data_dict = {}
    
    logger.info(f"Fetching data for {len(tickers)} stocks from {start_date} to {end_date}")
    
    for i, ticker in enumerate(tickers, 1):
        logger.info(f"[{i}/{len(tickers)}] Fetching {ticker}...")
        
        df = fetch_historical_data(ticker, start_date, end_date, save_csv)
        
        if df is not None and not df.empty:
            data_dict[ticker] = df
        else:
            logger.warning(f"Failed to fetch data for {ticker}")
    
    logger.info(f"Successfully fetched data for {len(data_dict)}/{len(tickers)} stocks")
    return data_dict

def fetch_market_data(start_date: datetime, end_date: datetime) -> Dict[str, pd.DataFrame]:
    """
    Fetch market indices data (Nifty, Bank Nifty, VIX)
    
    Args:
        start_date: Start date
        end_date: End date
    
    Returns:
        Dictionary with index data
    """
    market_data = {}
    
    # Nifty 50
    logger.info("Fetching Nifty 50 data...")
    nifty = fetch_index_data("^NSEI", start_date, end_date)
    if nifty is not None:
        market_data['nifty_50'] = nifty
        # Save
        nifty.to_csv(RAW_DATA_DIR / "NIFTY50.csv", index=False)
    
    # Bank Nifty
    logger.info("Fetching Bank Nifty data...")
    banknifty = fetch_index_data("^NSEBANK", start_date, end_date)
    if banknifty is not None:
        market_data['bank_nifty'] = banknifty
        banknifty.to_csv(RAW_DATA_DIR / "BANKNIFTY.csv", index=False)
    
    # VIX (if available)
    # Note: VIX data might not be available on Yahoo Finance
    
    return market_data

def load_cached_data(ticker: str) -> Optional[pd.DataFrame]:
    """
    Load cached data from CSV
    
    Args:
        ticker: Stock ticker
    
    Returns:
        DataFrame if found, None otherwise
    """
    # Find most recent file for ticker
    files = list(RAW_DATA_DIR.glob(f"{ticker}_*.csv"))
    
    if not files:
        return None
    
    # Get most recent file
    most_recent = max(files, key=lambda p: p.stat().st_mtime)
    
    logger.info(f"Loading cached data for {ticker} from {most_recent}")
    df = pd.read_csv(most_recent)
    
    # Ensure lowercase column names
    df.columns = df.columns.str.lower()
    df['date'] = pd.to_datetime(df['date'])
    
    return df

def get_or_fetch_data(
    ticker: str,
    start_date: datetime,
    end_date: datetime,
    use_cache: bool = True
) -> Optional[pd.DataFrame]:
    """
    Get data from cache or fetch if not available
    
    Args:
        ticker: Stock ticker
        start_date: Start date
        end_date: End date
        use_cache: Use cached data if available
    
    Returns:
        DataFrame with OHLCV data
    """
    if use_cache:
        cached_df = load_cached_data(ticker)
        
        if cached_df is not None:
            # Check if cached data covers requested period
            cached_start = cached_df['date'].min()
            cached_end = cached_df['date'].max()
            
            if cached_start <= start_date and cached_end >= end_date:
                logger.info(f"Using cached data for {ticker}")
                # Filter to requested period
                mask = (cached_df['date'] >= start_date) & (cached_df['date'] <= end_date)
                return cached_df[mask].reset_index(drop=True)
    
    # Fetch fresh data
    logger.info(f"Fetching fresh data for {ticker}")
    return fetch_historical_data(ticker, start_date, end_date, save_csv=True)

if __name__ == "__main__":
    # Test data fetching
    print("Testing data fetcher...")
    
    # Get stock universe
    universe = get_stock_universe("FNO")
    print(f"Stock universe size: {len(universe)}")
    print(f"Sample stocks: {universe[:10]}")
    
    # Test single stock fetch
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2)  # 2 years
    
    print(f"\nFetching test data for RELIANCE...")
    df = fetch_historical_data("RELIANCE", start_date, end_date)
    if df is not None:
        print(f"Fetched {len(df)} rows")
        print(df.head())

