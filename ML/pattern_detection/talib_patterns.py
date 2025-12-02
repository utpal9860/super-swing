"""
TA-Lib based candlestick pattern detection
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
import uuid
from datetime import datetime
from config import TALIB_PATTERNS
from utils.logger import setup_logger

logger = setup_logger("talib_patterns")

# Try to import talib, provide fallback if not available
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    logger.warning("TA-Lib not installed. Pattern detection will be limited.")
    TALIB_AVAILABLE = False

def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate technical indicators for pattern context
    
    Args:
        df: DataFrame with OHLCV data
    
    Returns:
        DataFrame with added indicators
    """
    df = df.copy()
    
    if not TALIB_AVAILABLE:
        logger.warning("TA-Lib not available, using basic indicators")
        # Basic fallback indicators
        df['rsi_14'] = 50.0
        df['atr_14'] = df['high'] - df['low']
        df['volume_ratio'] = 1.0
        return df
    
    # RSI
    df['rsi_14'] = talib.RSI(df['close'], timeperiod=14)
    
    # ATR
    df['atr_14'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
    
    # Volume ratio (current volume vs 20-day average)
    df['volume_ma_20'] = talib.SMA(df['volume'], timeperiod=20)
    df['volume_ratio'] = df['volume'] / df['volume_ma_20']
    
    # Moving averages
    df['sma_20'] = talib.SMA(df['close'], timeperiod=20)
    df['sma_50'] = talib.SMA(df['close'], timeperiod=50)
    df['sma_200'] = talib.SMA(df['close'], timeperiod=200)
    
    # Bollinger Bands
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
        df['close'], timeperiod=20, nbdevup=2, nbdevdn=2
    )
    
    # Distance from moving averages
    df['distance_from_sma20'] = (df['close'] - df['sma_20']) / df['sma_20'] * 100
    df['distance_from_sma200'] = (df['close'] - df['sma_200']) / df['sma_200'] * 100
    
    return df

def detect_talib_patterns(df: pd.DataFrame, min_confidence: float = 0) -> pd.DataFrame:
    """
    Detect all TA-Lib candlestick patterns
    
    Args:
        df: DataFrame with OHLCV data
        min_confidence: Minimum confidence threshold
    
    Returns:
        DataFrame with pattern columns
    """
    if not TALIB_AVAILABLE:
        logger.error("TA-Lib not available. Cannot detect patterns.")
        return df
    
    df = df.copy()
    
    # Add technical indicators
    df = calculate_technical_indicators(df)
    
    # Detect each pattern
    for pattern_name in TALIB_PATTERNS:
        try:
            pattern_func = getattr(talib, pattern_name)
            df[pattern_name] = pattern_func(
                df['open'], df['high'], df['low'], df['close']
            )
        except Exception as e:
            logger.warning(f"Error detecting {pattern_name}: {e}")
            df[pattern_name] = 0
    
    return df

def extract_pattern_occurrences(
    df: pd.DataFrame, 
    ticker: str,
    exchange: str = "NSE",
    min_confidence: int = 0
) -> List[Dict]:
    """
    Extract pattern occurrences from detected patterns
    
    Args:
        df: DataFrame with detected patterns
        ticker: Stock ticker
        exchange: Exchange (NSE/BSE)
        min_confidence: Minimum pattern confidence
    
    Returns:
        List of pattern occurrence dictionaries
    """
    occurrences = []
    
    for pattern_name in TALIB_PATTERNS:
        if pattern_name not in df.columns:
            continue
        
        # Find where pattern is non-zero
        pattern_dates = df[df[pattern_name] != 0].copy()
        
        for idx, row in pattern_dates.iterrows():
            pattern_value = row[pattern_name]
            
            # Skip if confidence too low
            if abs(pattern_value) < min_confidence:
                continue
            
            # Determine pattern direction
            direction = "BULLISH" if pattern_value > 0 else "BEARISH"
            
            # Create pattern record
            pattern = {
                'pattern_id': f"{ticker}_{pattern_name}_{row['date'].strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}",
                'ticker': ticker,
                'exchange': exchange,
                'pattern_type': f"{pattern_name}_{direction}",
                'detection_date': row['date'].strftime('%Y-%m-%d'),
                'timeframe': '1d',
                'confidence_score': abs(pattern_value) / 100.0,  # Normalize to 0-1
                'price_at_detection': row['close'],
                'volume_at_detection': int(row['volume']),
                'pattern_start_date': row['date'].strftime('%Y-%m-%d'),
                'pattern_end_date': row['date'].strftime('%Y-%m-%d'),
                
                # Technical context
                'rsi_14': row.get('rsi_14', None),
                'volume_ratio': row.get('volume_ratio', None),
                'atr_14': row.get('atr_14', None),
                'distance_from_52w_high': None,  # To be calculated
                'distance_from_52w_low': None,   # To be calculated
                
                # Validation status
                'validation_status': 'PENDING',
                'human_label': None,
                'pattern_quality': None,
                'outcome': None,
            }
            
            occurrences.append(pattern)
    
    logger.info(f"Found {len(occurrences)} pattern occurrences for {ticker}")
    return occurrences

def calculate_52_week_metrics(df: pd.DataFrame, current_price: float) -> dict:
    """
    Calculate 52-week high/low metrics
    
    Args:
        df: DataFrame with historical data
        current_price: Current price
    
    Returns:
        Dictionary with 52-week metrics
    """
    # Get last 252 trading days (approx 1 year)
    recent_data = df.tail(252)
    
    high_52w = recent_data['high'].max()
    low_52w = recent_data['low'].min()
    
    distance_from_high = ((current_price - high_52w) / high_52w * 100) if high_52w > 0 else 0
    distance_from_low = ((current_price - low_52w) / low_52w * 100) if low_52w > 0 else 0
    
    return {
        '52w_high': high_52w,
        '52w_low': low_52w,
        'distance_from_52w_high': distance_from_high,
        'distance_from_52w_low': distance_from_low
    }

def scan_stock_for_patterns(
    ticker: str,
    df: pd.DataFrame,
    exchange: str = "NSE",
    lookback_days: int = 30
) -> List[Dict]:
    """
    Scan a single stock for patterns
    
    Args:
        ticker: Stock ticker
        df: DataFrame with OHLCV data
        exchange: Exchange
        lookback_days: Days to look back for patterns
    
    Returns:
        List of detected patterns
    """
    if df is None or df.empty:
        logger.warning(f"No data for {ticker}")
        return []
    
    # Detect patterns
    df_with_patterns = detect_talib_patterns(df)
    
    # Get recent patterns only (last N days)
    recent_data = df_with_patterns.tail(lookback_days)
    
    # Extract occurrences
    patterns = extract_pattern_occurrences(
        recent_data, 
        ticker, 
        exchange,
        min_confidence=0  # Detect all, filter later
    )
    
    # Add 52-week metrics
    for pattern in patterns:
        metrics_52w = calculate_52_week_metrics(df, pattern['price_at_detection'])
        pattern['distance_from_52w_high'] = metrics_52w['distance_from_52w_high']
        pattern['distance_from_52w_low'] = metrics_52w['distance_from_52w_low']
    
    return patterns

def batch_scan_patterns(
    tickers: List[str],
    data_dict: Dict[str, pd.DataFrame],
    exchange: str = "NSE",
    lookback_days: int = 30
) -> List[Dict]:
    """
    Scan multiple stocks for patterns
    
    Args:
        tickers: List of stock tickers
        data_dict: Dictionary of {ticker: DataFrame}
        exchange: Exchange
        lookback_days: Days to look back
    
    Returns:
        List of all detected patterns
    """
    all_patterns = []
    
    logger.info(f"Scanning {len(tickers)} stocks for patterns...")
    
    for ticker in tickers:
        if ticker not in data_dict:
            logger.warning(f"No data for {ticker}")
            continue
        
        df = data_dict[ticker]
        patterns = scan_stock_for_patterns(ticker, df, exchange, lookback_days)
        all_patterns.extend(patterns)
    
    logger.info(f"Total patterns detected: {len(all_patterns)}")
    return all_patterns

def filter_high_quality_patterns(patterns: List[Dict], min_quality: float = 0.6) -> List[Dict]:
    """
    Filter patterns by quality criteria
    
    Args:
        patterns: List of pattern dictionaries
        min_quality: Minimum quality score
    
    Returns:
        Filtered list of patterns
    """
    filtered = []
    
    for pattern in patterns:
        # Quality criteria
        has_volume = pattern.get('volume_ratio', 0) > 1.2  # 20% above average
        not_extreme_rsi = 30 < pattern.get('rsi_14', 50) < 70  # Not overbought/oversold
        has_confidence = pattern.get('confidence_score', 0) >= min_quality
        
        # Simple quality score
        quality_score = 0
        if has_volume:
            quality_score += 0.4
        if not_extreme_rsi:
            quality_score += 0.3
        if has_confidence:
            quality_score += 0.3
        
        if quality_score >= min_quality:
            filtered.append(pattern)
    
    logger.info(f"Filtered {len(filtered)} high-quality patterns from {len(patterns)}")
    return filtered

if __name__ == "__main__":
    # Test pattern detection
    print("Testing TA-Lib pattern detection...")
    print(f"TA-Lib available: {TALIB_AVAILABLE}")
    print(f"Number of patterns to detect: {len(TALIB_PATTERNS)}")

