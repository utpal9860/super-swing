"""
Feature engineering for pattern prediction
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from utils.logger import setup_logger
from utils.market_utils import get_market_trend, categorize_market_cap
from config import FEATURE_CONFIG, NSE_HOLIDAYS

logger = setup_logger("features")

def calculate_stock_features(df: pd.DataFrame, current_idx: int) -> Dict:
    """
    Calculate stock-level features
    
    Args:
        df: DataFrame with OHLCV and technical indicators
        current_idx: Index of current pattern occurrence
    
    Returns:
        Dictionary with stock features
    """
    if current_idx < 20:  # Need at least 20 days for some calculations
        logger.warning(f"Insufficient data at index {current_idx}")
        return {}
    
    # Calculate technical indicators if not present
    if 'atr_14' not in df.columns:
        try:
            import talib
            df['atr_14'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            df['rsi_14'] = talib.RSI(df['close'], timeperiod=14)
            df['sma_20'] = talib.SMA(df['close'], timeperiod=20)
            df['sma_200'] = talib.SMA(df['close'], timeperiod=200)
        except Exception as e:
            logger.warning(f"Could not calculate technical indicators: {e}")
            # Use simple calculations as fallback
            df['atr_14'] = df['high'] - df['low']
            df['rsi_14'] = 50.0  # Neutral
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_200'] = df['close'].rolling(window=200).mean()
    
    # Get current row and recent data
    current = df.iloc[current_idx]
    recent_20 = df.iloc[max(0, current_idx-20):current_idx+1]
    recent_50 = df.iloc[max(0, current_idx-50):current_idx+1] if current_idx >= 50 else recent_20
    
    features = {}
    
    # Liquidity & Volume
    features['avg_volume_20d'] = recent_20['volume'].mean()
    features['volume_ratio'] = current['volume'] / features['avg_volume_20d'] if features['avg_volume_20d'] > 0 else 1.0
    
    # Volatility
    atr_value = current.get('atr_14')
    if pd.isna(atr_value) or atr_value == 0:
        # Calculate simple ATR if missing
        atr_value = (current['high'] - current['low'])
    features['atr_14'] = float(atr_value)
    
    if len(recent_50) >= 50:
        atr_mean = recent_50['atr_14'].mean()
        features['atr_ratio'] = features['atr_14'] / atr_mean if atr_mean > 0 else 1.0
    else:
        features['atr_ratio'] = 1.0
    
    features['historical_volatility_30d'] = recent_20['close'].pct_change().std() * np.sqrt(252) * 100  # Annualized
    
    # Price Position
    sma_20 = current.get('sma_20')
    if pd.isna(sma_20) or sma_20 == 0:
        sma_20 = df.iloc[max(0, current_idx-20):current_idx+1]['close'].mean()
    features['distance_from_sma20'] = ((current['close'] - sma_20) / sma_20 * 100) if sma_20 > 0 else 0
    
    sma_200 = current.get('sma_200')
    if pd.isna(sma_200) or sma_200 == 0:
        if len(df) >= 200:
            sma_200 = df.iloc[max(0, current_idx-200):current_idx+1]['close'].mean()
        else:
            sma_200 = current['close']
    features['distance_from_sma200'] = ((current['close'] - sma_200) / sma_200 * 100) if sma_200 > 0 else 0
    
    rsi_value = current.get('rsi_14')
    features['rsi_14'] = float(rsi_value) if not pd.isna(rsi_value) else 50.0
    
    # Recent Performance
    if current_idx >= 5:
        features['return_5d'] = (current['close'] - df.iloc[current_idx-5]['close']) / df.iloc[current_idx-5]['close'] * 100
    else:
        features['return_5d'] = 0
    
    if current_idx >= 20:
        features['return_20d'] = (current['close'] - df.iloc[current_idx-20]['close']) / df.iloc[current_idx-20]['close'] * 100
    else:
        features['return_20d'] = 0
    
    return features

def calculate_market_features(market_data: pd.DataFrame, current_date: datetime) -> Dict:
    """
    Calculate market-level features
    
    Args:
        market_data: DataFrame with market index data
        current_date: Current date
    
    Returns:
        Dictionary with market features
    """
    features = {}
    
    # Find closest date in market data
    market_data['date'] = pd.to_datetime(market_data['date'])
    closest_idx = (market_data['date'] - current_date).abs().argmin()
    
    if closest_idx < 20:
        logger.warning("Insufficient market data")
        return {
            'nifty_trend': 'UNKNOWN',
            'nifty_rsi': 50,
            'india_vix': 15,
        }
    
    # Market trend
    features['nifty_trend'] = get_market_trend(market_data.iloc[:closest_idx+1], period=20)
    
    # Nifty RSI
    features['nifty_rsi'] = market_data.iloc[closest_idx].get('rsi_14', 50)
    
    # Distance from 200 SMA
    current_close = market_data.iloc[closest_idx]['close']
    sma_200 = market_data.iloc[closest_idx].get('sma_200', current_close)
    features['nifty_distance_from_sma200'] = ((current_close - sma_200) / sma_200 * 100) if sma_200 > 0 else 0
    
    # VIX (placeholder - would need actual VIX data)
    features['india_vix'] = 15.0  # Default value
    
    # Market breadth (placeholder - would need breadth data)
    features['advance_decline_ratio'] = 1.0
    
    return features

def calculate_pattern_features(pattern_data: Dict, df: pd.DataFrame) -> Dict:
    """
    Calculate pattern-specific features
    
    Args:
        pattern_data: Pattern information
        df: DataFrame with OHLCV data
    
    Returns:
        Dictionary with pattern features
    """
    features = {}
    
    # Pattern characteristics
    features['pattern_type'] = pattern_data.get('pattern_type', 'UNKNOWN')
    features['confidence_score'] = pattern_data.get('confidence_score', 0)
    
    # Volume behavior
    features['volume_at_formation'] = pattern_data.get('volume_at_detection', 0)
    features['volume_ratio_at_formation'] = pattern_data.get('volume_ratio', 1.0)
    
    # Pattern quality (from human labeling)
    features['human_quality_rating'] = pattern_data.get('pattern_quality', 3)  # Default to 3/5
    
    return features

def calculate_temporal_features(current_date: datetime) -> Dict:
    """
    Calculate temporal features
    
    Args:
        current_date: Current date
    
    Returns:
        Dictionary with temporal features
    """
    features = {}
    
    # Calendar
    features['day_of_week'] = current_date.strftime('%A').upper()
    features['week_of_month'] = (current_date.day - 1) // 7 + 1
    features['month'] = current_date.strftime('%B').upper()
    features['quarter'] = f"Q{(current_date.month - 1) // 3 + 1}"
    
    # Seasonality
    features['is_budget_season'] = current_date.month in [1, 2]
    features['is_earnings_season'] = current_date.month in [1, 4, 7, 10]  # Quarterly earnings months
    
    # Market events
    # Check if it's derivatives expiry week (last Thursday of month)
    last_day = (current_date.replace(day=28) + pd.Timedelta(days=4)).replace(day=1) - pd.Timedelta(days=1)
    last_thursday = last_day - pd.Timedelta(days=(last_day.weekday() - 3) % 7)
    features['is_derivatives_expiry_week'] = abs((current_date - last_thursday).days) <= 3
    
    # Days to month end
    features['days_to_month_end'] = (last_day - current_date).days
    
    # Check if recent holiday
    date_str = current_date.strftime('%Y-%m-%d')
    features['is_holiday'] = date_str in NSE_HOLIDAYS
    
    return features

def engineer_features_for_pattern(
    pattern_data: Dict,
    stock_data: pd.DataFrame,
    market_data: Optional[pd.DataFrame] = None
) -> Dict:
    """
    Engineer all features for a single pattern
    
    Args:
        pattern_data: Pattern information
        stock_data: Stock OHLCV data
        market_data: Market index data (optional)
    
    Returns:
        Dictionary with all engineered features
    """
    all_features = {}
    
    try:
        # Get pattern date and find index in stock data
        pattern_date = pd.to_datetime(pattern_data['detection_date'])
        stock_data = stock_data.copy()
        stock_data['date'] = pd.to_datetime(stock_data['date'])
        
        # Find closest index
        idx = (stock_data['date'] - pattern_date).abs().argmin()
        
        # Ensure we have enough data
        if idx < 20:
            logger.warning(f"Insufficient data for pattern {pattern_data.get('pattern_id', 'unknown')}")
            return {}
        
        # Stock features
        stock_features = calculate_stock_features(stock_data, idx)
        if not stock_features:
            return {}
        all_features.update(stock_features)
    
        # Market features
        if market_data is not None:
            market_features = calculate_market_features(market_data, pattern_date)
            all_features.update(market_features)
        
        # Pattern features
        pattern_features = calculate_pattern_features(pattern_data, stock_data)
        all_features.update(pattern_features)
        
        # Temporal features
        temporal_features = calculate_temporal_features(pattern_date)
        all_features.update(temporal_features)
        
        # Add pattern ID and ticker
        all_features['pattern_id'] = pattern_data['pattern_id']
        all_features['ticker'] = pattern_data['ticker']
        
        return all_features
        
    except Exception as e:
        logger.error(f"Error engineering features for pattern {pattern_data.get('pattern_id', 'unknown')}: {e}")
        return {}

def create_feature_dataframe(patterns: List[Dict], data_dict: Dict[str, pd.DataFrame], 
                              market_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Create feature DataFrame for all patterns
    
    Args:
        patterns: List of pattern dictionaries
        data_dict: Dictionary of stock DataFrames
        market_data: Market index data
    
    Returns:
        DataFrame with all features
    """
    logger.info(f"Engineering features for {len(patterns)} patterns...")
    
    all_features = []
    
    for i, pattern in enumerate(patterns):
        if i % 100 == 0:
            logger.info(f"Processing {i}/{len(patterns)}...")
        
        ticker = pattern['ticker']
        
        if ticker not in data_dict:
            logger.warning(f"No data for {ticker}, skipping pattern {pattern.get('pattern_id', 'unknown')}")
            continue
        
        stock_data = data_dict[ticker].copy()
        
        # Ensure lowercase column names
        stock_data.columns = stock_data.columns.str.lower()
        
        try:
            features = engineer_features_for_pattern(pattern, stock_data, market_data)
            if features:  # Only add if features were successfully generated
                all_features.append(features)
        except Exception as e:
            logger.error(f"Error engineering features for pattern {pattern.get('pattern_id', 'unknown')}: {e}")
    
    logger.info(f"Engineered features for {len(all_features)} patterns")
    
    # Create DataFrame
    if not all_features:
        logger.warning("No features were successfully generated")
        return pd.DataFrame()
    
    df_features = pd.DataFrame(all_features)
    
    # Remove any rows with all NaN values
    df_features.dropna(how='all', inplace=True)
    
    logger.info(f"Final feature DataFrame shape: {df_features.shape}")
    
    return df_features

def prepare_ml_dataset(df_features: pd.DataFrame, target_column: str = 'is_successful') -> tuple:
    """
    Prepare dataset for ML training
    
    Args:
        df_features: DataFrame with features
        target_column: Name of target column
    
    Returns:
        Tuple of (X, y, feature_names)
    """
    # Separate features and target
    feature_cols = [col for col in df_features.columns 
                    if col not in ['pattern_id', 'ticker', target_column, 
                                   'outcome', 'gain_loss_pct', 'exit_reason']]
    
    # One-hot encode categorical variables
    categorical_cols = df_features[feature_cols].select_dtypes(include=['object']).columns
    df_encoded = pd.get_dummies(df_features[feature_cols], columns=categorical_cols)
    
    X = df_encoded
    y = df_features[target_column] if target_column in df_features.columns else None
    
    logger.info(f"Prepared ML dataset: {X.shape[0]} samples, {X.shape[1]} features")
    
    return X, y, X.columns.tolist()

if __name__ == "__main__":
    print("Feature engineering module loaded successfully")
    print(f"Available feature calculations:")
    print("- Stock features: volume, volatility, price position, momentum")
    print("- Market features: trend, breadth, VIX")
    print("- Pattern features: type, confidence, quality")
    print("- Temporal features: calendar, seasonality, events")

