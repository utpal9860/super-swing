"""
Multi-Timeframe Pattern Scanner
Scans patterns across 1W, 1D, 4H, 1H timeframes for top-down analysis
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from utils.data_utils import fetch_stock_data
from pattern_detection.talib_patterns import detect_talib_patterns, extract_pattern_occurrences, filter_high_quality_patterns
from utils.logger import setup_logger

logger = setup_logger("multitimeframe_scanner")

# Timeframe configurations
TIMEFRAMES = {
    '1W': {
        'interval': '1wk',
        'lookback_days': 365,  # 1 year of weekly data
        'min_bars': 50,
        'weight': 0.35,  # Higher timeframe gets more weight
        'label': 'Weekly'
    },
    '1D': {
        'interval': '1d',
        'lookback_days': 200,  # ~8 months of daily data
        'min_bars': 100,
        'weight': 0.30,
        'label': 'Daily'
    },
    '4H': {
        'interval': '1h',  # yfinance doesn't have 4h, we'll resample from 1h
        'lookback_days': 60,  # 2 months
        'min_bars': 120,
        'weight': 0.20,
        'label': '4-Hour'
    },
    '1H': {
        'interval': '1h',
        'lookback_days': 30,  # 1 month
        'min_bars': 100,
        'weight': 0.15,
        'label': 'Hourly'
    }
}


def resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample 1H data to 4H timeframe
    
    Args:
        df: DataFrame with 1H OHLCV data
    
    Returns:
        DataFrame with 4H OHLCV data
    """
    try:
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Resample to 4H
        resampled = df.resample('4H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        # Drop rows with NaN (incomplete 4H bars)
        resampled.dropna(inplace=True)
        
        # Reset index
        resampled.reset_index(inplace=True)
        
        logger.debug(f"Resampled {len(df)} 1H bars to {len(resampled)} 4H bars")
        return resampled
    
    except Exception as e:
        logger.error(f"Error resampling to 4H: {e}")
        return df


def fetch_timeframe_data(ticker: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Fetch data for a specific timeframe
    
    Args:
        ticker: Stock ticker
        timeframe: Timeframe code (1W, 1D, 4H, 1H)
    
    Returns:
        DataFrame with OHLCV data
    """
    try:
        config = TIMEFRAMES[timeframe]
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=config['lookback_days'])
        
        # Fetch data
        df = fetch_stock_data(
            symbol=ticker,
            start_date=start_date,
            end_date=end_date,
            interval=config['interval']
        )
        
        if df is None or len(df) < config['min_bars']:
            logger.warning(f"Insufficient data for {ticker} on {timeframe}: {len(df) if df is not None else 0} bars")
            return None
        
        # If 4H, resample from 1H
        if timeframe == '4H':
            df = resample_to_4h(df)
            if len(df) < config['min_bars']:
                logger.warning(f"Insufficient 4H bars for {ticker}: {len(df)}")
                return None
        
        logger.info(f"Fetched {len(df)} {timeframe} bars for {ticker}")
        return df
    
    except Exception as e:
        logger.error(f"Error fetching {timeframe} data for {ticker}: {e}")
        return None


def scan_timeframe_patterns(ticker: str, timeframe: str, df: pd.DataFrame) -> List[Dict]:
    """
    Scan patterns on a specific timeframe
    
    Args:
        ticker: Stock ticker
        timeframe: Timeframe code
        df: DataFrame with OHLCV data
    
    Returns:
        List of pattern dictionaries
    """
    try:
        # Detect patterns
        df_with_patterns = detect_talib_patterns(df)
        
        # Extract occurrences (last 30 bars only for recent patterns)
        recent_data = df_with_patterns.tail(30)
        patterns = extract_pattern_occurrences(recent_data, ticker, exchange="NSE", min_confidence=0)
        
        if not patterns:
            return []
        
        # Filter high quality
        high_quality = filter_high_quality_patterns(patterns)
        
        # Add timeframe info
        for pattern in high_quality:
            pattern['timeframe'] = timeframe
            pattern['timeframe_label'] = TIMEFRAMES[timeframe]['label']
            pattern['timeframe_weight'] = TIMEFRAMES[timeframe]['weight']
        
        logger.info(f"Found {len(high_quality)} high-quality patterns on {timeframe} for {ticker}")
        return high_quality
    
    except Exception as e:
        logger.error(f"Error scanning {timeframe} for {ticker}: {e}")
        return []


def scan_all_timeframes(ticker: str, timeframes: List[str] = None) -> Dict[str, List[Dict]]:
    """
    Scan patterns across all timeframes
    
    Args:
        ticker: Stock ticker
        timeframes: List of timeframes to scan (default: all)
    
    Returns:
        Dict mapping timeframe to list of patterns
    """
    if timeframes is None:
        timeframes = list(TIMEFRAMES.keys())
    
    results = {}
    
    logger.info(f"Multi-timeframe scan for {ticker} across {len(timeframes)} timeframes")
    
    for tf in timeframes:
        logger.info(f"  Scanning {tf}...")
        
        # Fetch data
        df = fetch_timeframe_data(ticker, tf)
        
        if df is None:
            logger.warning(f"  Skipping {tf} - no data")
            results[tf] = []
            continue
        
        # Scan patterns
        patterns = scan_timeframe_patterns(ticker, tf, df)
        results[tf] = patterns
        
        logger.info(f"  {tf}: {len(patterns)} patterns found")
    
    return results


def combine_multitimeframe_signals(
    ticker: str,
    tf_patterns: Dict[str, List[Dict]],
    min_confidence: float = 0.5
) -> List[Dict]:
    """
    Combine patterns from multiple timeframes into unified signals
    
    Args:
        ticker: Stock ticker
        tf_patterns: Dict mapping timeframe to patterns
        min_confidence: Minimum overall confidence
    
    Returns:
        List of combined multi-timeframe signals
    """
    combined = []
    
    # Get patterns from daily timeframe as base
    daily_patterns = tf_patterns.get('1D', [])
    
    if not daily_patterns:
        # If no daily patterns, use weekly
        daily_patterns = tf_patterns.get('1W', [])
    
    for pattern in daily_patterns:
        signal = {
            'ticker': ticker,
            'pattern_type': pattern['pattern_type'],
            'detection_date': pattern['detection_date'],
            'price_at_detection': pattern['price_at_detection'],
            'primary_timeframe': pattern['timeframe'],
            'confidence_score': pattern['confidence_score'],
            
            # Multi-timeframe context
            'timeframe_alignment': {},
            'timeframe_patterns': {}
        }
        
        # Check for pattern in other timeframes
        pattern_base = pattern['pattern_type'].split('_')[0]  # e.g., CDLHAMMER from CDLHAMMER_BULLISH
        
        total_weight = TIMEFRAMES[pattern['timeframe']]['weight']
        weighted_confidence = pattern['confidence_score'] * total_weight
        
        for tf, patterns_list in tf_patterns.items():
            if tf == pattern['timeframe']:
                continue
            
            # Look for similar patterns on this timeframe
            matching = [p for p in patterns_list if pattern_base in p['pattern_type']]
            
            if matching:
                signal['timeframe_alignment'][tf] = True
                signal['timeframe_patterns'][tf] = matching[0]['pattern_type']
                
                # Add weighted confidence
                weighted_confidence += matching[0]['confidence_score'] * TIMEFRAMES[tf]['weight']
                total_weight += TIMEFRAMES[tf]['weight']
            else:
                signal['timeframe_alignment'][tf] = False
        
        # Calculate overall multi-timeframe confidence
        signal['multitimeframe_confidence'] = weighted_confidence / total_weight if total_weight > 0 else pattern['confidence_score']
        
        # Count aligned timeframes
        aligned_count = sum(1 for aligned in signal['timeframe_alignment'].values() if aligned)
        signal['aligned_timeframes'] = aligned_count
        signal['total_timeframes'] = len(tf_patterns)
        
        # Boost confidence if multiple timeframes align
        if aligned_count >= 2:
            signal['multitimeframe_confidence'] *= 1.1  # 10% boost for alignment
        
        # Only include if meets minimum confidence
        if signal['multitimeframe_confidence'] >= min_confidence:
            combined.append(signal)
    
    # Sort by multitimeframe confidence
    combined.sort(key=lambda x: x['multitimeframe_confidence'], reverse=True)
    
    logger.info(f"Combined {len(combined)} multi-timeframe signals for {ticker}")
    return combined


def batch_scan_multitimeframe(
    tickers: List[str],
    timeframes: List[str] = None,
    min_confidence: float = 0.5
) -> Dict[str, List[Dict]]:
    """
    Batch scan multiple stocks across multiple timeframes
    
    Args:
        tickers: List of stock tickers
        timeframes: List of timeframes to scan
        min_confidence: Minimum confidence for signals
    
    Returns:
        Dict mapping ticker to list of multi-timeframe signals
    """
    all_signals = {}
    
    logger.info(f"Batch multi-timeframe scan: {len(tickers)} stocks")
    
    for i, ticker in enumerate(tickers, 1):
        logger.info(f"[{i}/{len(tickers)}] Scanning {ticker}...")
        
        try:
            # Scan all timeframes
            tf_patterns = scan_all_timeframes(ticker, timeframes)
            
            # Combine into signals
            signals = combine_multitimeframe_signals(ticker, tf_patterns, min_confidence)
            
            all_signals[ticker] = signals
            
            logger.info(f"  {ticker}: {len(signals)} multi-timeframe signals generated")
        
        except Exception as e:
            logger.error(f"Error scanning {ticker}: {e}")
            all_signals[ticker] = []
    
    return all_signals


# Example usage
if __name__ == '__main__':
    print("="*80)
    print("MULTI-TIMEFRAME PATTERN SCANNER")
    print("="*80)
    
    # Test with a single stock
    test_ticker = "RELIANCE"
    
    print(f"\nScanning {test_ticker} across all timeframes...")
    
    # Scan all timeframes
    tf_patterns = scan_all_timeframes(test_ticker)
    
    # Display results
    for tf, patterns in tf_patterns.items():
        print(f"\n{TIMEFRAMES[tf]['label']} ({tf}): {len(patterns)} patterns")
        for pattern in patterns[:3]:  # Show top 3
            print(f"  - {pattern['pattern_type']}: {pattern['confidence_score']:.2f}")
    
    # Combine into multi-timeframe signals
    signals = combine_multitimeframe_signals(test_ticker, tf_patterns)
    
    print(f"\n{'='*80}")
    print(f"MULTI-TIMEFRAME SIGNALS: {len(signals)}")
    print(f"{'='*80}")
    
    for signal in signals:
        print(f"\n{signal['pattern_type']} on {signal['primary_timeframe']}")
        print(f"  Confidence: {signal['multitimeframe_confidence']:.2%}")
        print(f"  Aligned Timeframes: {signal['aligned_timeframes']}/{signal['total_timeframes']}")
        print(f"  Alignment: {signal['timeframe_alignment']}")

