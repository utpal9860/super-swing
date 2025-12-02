"""
Complete ML training pipeline
Trains all three models on validated pattern data
"""
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from database.schema import get_validated_patterns
from feature_engineering.features import create_feature_dataframe, prepare_ml_dataset
from models.validity_classifier import PatternValidityClassifier
from models.success_predictor import PatternSuccessPredictor
from models.risk_reward_estimator import RiskRewardEstimator
from pattern_detection.data_fetcher import get_or_fetch_data, fetch_market_data
from utils.logger import setup_logger
from config import MODELS_DIR

logger = setup_logger("training_pipeline")

def load_pattern_data():
    """Load validated patterns from database"""
    logger.info("Loading validated patterns from database...")
    patterns = get_validated_patterns()
    
    if not patterns:
        logger.error("No validated patterns found! Please review patterns first.")
        return None
    
    logger.info(f"Loaded {len(patterns)} validated patterns")
    return pd.DataFrame(patterns)

def fetch_required_data(patterns_df):
    """Fetch stock and market data for patterns"""
    logger.info("Fetching stock data for patterns...")
    
    # Get unique tickers
    tickers = patterns_df['ticker'].unique()
    logger.info(f"Need data for {len(tickers)} stocks")
    
    # Get date range
    patterns_df['detection_date'] = pd.to_datetime(patterns_df['detection_date'])
    start_date = patterns_df['detection_date'].min() - pd.Timedelta(days=730)  # 2 years before
    end_date = patterns_df['detection_date'].max() + pd.Timedelta(days=60)  # 2 months after
    
    # Fetch stock data
    data_dict = {}
    for ticker in tickers:
        df = get_or_fetch_data(ticker, start_date, end_date, use_cache=True)
        if df is not None:
            data_dict[ticker] = df
    
    logger.info(f"Fetched data for {len(data_dict)} stocks")
    
    # Fetch market data
    logger.info("Fetching market data...")
    market_data = fetch_market_data(start_date, end_date)
    nifty_data = market_data.get('nifty_50')
    
    return data_dict, nifty_data

def calculate_pattern_outcomes(patterns_df, data_dict):
    """Calculate outcomes for patterns"""
    logger.info("Calculating pattern outcomes...")
    
    patterns_with_outcomes = []
    
    for idx, pattern in patterns_df.iterrows():
        ticker = pattern['ticker']
        
        if ticker not in data_dict:
            continue
        
        df = data_dict[ticker]
        df['date'] = pd.to_datetime(df['date'])
        
        # Find pattern date
        pattern_date = pd.to_datetime(pattern['detection_date'])
        pattern_idx = (df['date'] - pattern_date).abs().argmin()
        
        if pattern_idx >= len(df) - 1:
            continue
        
        # Entry at next day open
        entry_idx = pattern_idx + 1
        entry_price = df.iloc[entry_idx]['open']
        
        # Calculate target and stop
        pattern_height = abs(df.iloc[max(0, pattern_idx-10):pattern_idx+1]['high'].max() - 
                             df.iloc[max(0, pattern_idx-10):pattern_idx+1]['low'].min())
        
        target = entry_price + pattern_height
        stop_loss = df.iloc[max(0, pattern_idx-10):pattern_idx+1]['low'].min() * 0.98
        
        # Track outcome over next 20 days
        max_gain = 0
        max_loss = 0
        target_hit = False
        stop_hit = False
        days_to_target = None
        days_to_stop = None
        
        for i in range(entry_idx, min(entry_idx + 20, len(df))):
            bar = df.iloc[i]
            
            # Check target
            if bar['high'] >= target and not target_hit:
                target_hit = True
                days_to_target = i - entry_idx
            
            # Check stop
            if bar['low'] <= stop_loss and not stop_hit:
                stop_hit = True
                days_to_stop = i - entry_idx
            
            # Track max gain/loss
            gain = (bar['high'] - entry_price) / entry_price * 100
            loss = (bar['low'] - entry_price) / entry_price * 100
            
            max_gain = max(max_gain, gain)
            max_loss = min(max_loss, loss)
        
        # Determine success
        is_successful = target_hit and not stop_hit
        
        # Final price after 10 days (or last available)
        final_idx = min(entry_idx + 10, len(df) - 1)
        final_price = df.iloc[final_idx]['close']
        final_gain = (final_price - entry_price) / entry_price * 100
        
        # Add outcome data
        pattern_with_outcome = pattern.to_dict()
        pattern_with_outcome.update({
            'is_successful': is_successful,
            'entry_price': entry_price,
            'target_price': target,
            'stop_loss': stop_loss,
            'target_hit': target_hit,
            'stop_hit': stop_hit,
            'max_gain_pct': max_gain,
            'max_loss_pct': max_loss,
            'final_gain_pct': final_gain,
            'days_to_target': days_to_target,
            'days_to_stop': days_to_stop,
            'actual_holding_days': min(days_to_target or 20, days_to_stop or 20, 20),
        })
        
        patterns_with_outcomes.append(pattern_with_outcome)
    
    logger.info(f"Calculated outcomes for {len(patterns_with_outcomes)} patterns")
    
    df_outcomes = pd.DataFrame(patterns_with_outcomes)
    logger.info(f"Success rate: {df_outcomes['is_successful'].mean():.2%}")
    
    return df_outcomes

def train_all_models(features_df):
    """Train all three ML models"""
    
    # Prepare dataset
    logger.info("Preparing ML dataset...")
    
    # Add target variables
    X, y_success, feature_names = prepare_ml_dataset(features_df, target_column='is_successful')
    
    logger.info(f"Dataset: {len(X)} samples, {len(feature_names)} features")
    
    # Model 1: Validity Classifier
    logger.info("\n" + "="*60)
    logger.info("Training Model 1: Pattern Validity Classifier")
    logger.info("="*60)
    
    model1 = PatternValidityClassifier()
    
    # Create validation labels (using human_label from database)
    if 'human_label' in features_df.columns:
        y_validity = (features_df['human_label'] == 'VALID').astype(int)
        
        # Train-val-test split
        from sklearn.model_selection import train_test_split
        X_train, X_temp, y_train, y_temp = train_test_split(
            X, y_validity, test_size=0.3, random_state=42, stratify=y_validity
        )
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
        )
        
        # Train
        model1.train(X_train, y_train, X_val, y_val)
        
        # Evaluate
        metrics1 = model1.evaluate(X_test, y_test)
        
        # Save
        model1_path = MODELS_DIR / f"validity_classifier_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        model1.save(model1_path)
        logger.info(f"Model 1 saved to {model1_path}")
    
    # Model 2: Success Predictor
    logger.info("\n" + "="*60)
    logger.info("Training Model 2: Pattern Success Predictor")
    logger.info("="*60)
    
    model2 = PatternSuccessPredictor(use_xgboost=True)
    
    # Train-val-test split
    from sklearn.model_selection import train_test_split
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y_success, test_size=0.3, random_state=42
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42
    )
    
    # Train
    model2.train(X_train, y_train, X_val, y_val)
    
    # Evaluate
    metrics2 = model2.evaluate(X_test, y_test)
    
    # Save
    model2_path = MODELS_DIR / f"success_predictor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
    model2.save(model2_path)
    logger.info(f"Model 2 saved to {model2_path}")
    
    # Model 3: Risk-Reward Estimator
    logger.info("\n" + "="*60)
    logger.info("Training Model 3: Risk-Reward Estimator")
    logger.info("="*60)
    
    model3 = RiskRewardEstimator()
    
    # Prepare regression targets
    y_gain = features_df['final_gain_pct']
    y_time = features_df['actual_holding_days']
    
    # Train-val-test split
    X_train, X_temp, y_gain_train, y_gain_temp, y_time_train, y_time_temp = train_test_split(
        X, y_gain, y_time, test_size=0.3, random_state=42
    )
    X_val, X_test, y_gain_val, y_gain_test, y_time_val, y_time_test = train_test_split(
        X_temp, y_gain_temp, y_time_temp, test_size=0.5, random_state=42
    )
    
    # Train
    model3.train(X_train, y_gain_train, y_time_train, X_val, y_gain_val, y_time_val)
    
    # Evaluate
    metrics3 = model3.evaluate(X_test, y_gain_test, y_time_test)
    
    # Save
    model3_path = MODELS_DIR / f"risk_reward_estimator_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
    model3.save(model3_path)
    logger.info(f"Model 3 saved to {model3_path}")
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("Training Complete!")
    logger.info("="*60)
    logger.info(f"Model 1 (Validity): Accuracy = {metrics1.get('accuracy', 0):.2%}")
    logger.info(f"Model 2 (Success): ROC-AUC = {metrics2.get('roc_auc', 0):.3f}")
    logger.info(f"Model 3 (Risk-Reward): Gain MAE = {metrics3.get('gain_mae', 0):.2f}%")
    logger.info("="*60)
    
    return model1, model2, model3

def run_training_pipeline():
    """Run complete training pipeline"""
    
    logger.info("="*60)
    logger.info("ML PATTERN TRADING SYSTEM - TRAINING PIPELINE")
    logger.info("="*60)
    
    # Step 1: Load patterns
    patterns_df = load_pattern_data()
    if patterns_df is None:
        return
    
    # Step 2: Fetch data
    data_dict, market_data = fetch_required_data(patterns_df)
    
    # Step 3: Calculate outcomes
    patterns_df = calculate_pattern_outcomes(patterns_df, data_dict)
    
    # Step 4: Engineer features
    logger.info("Engineering features...")
    features_df = create_feature_dataframe(
        patterns_df.to_dict('records'),
        data_dict,
        market_data
    )
    
    # Step 5: Train models
    models = train_all_models(features_df)
    
    logger.info("\nTraining pipeline completed successfully!")
    
    return models

if __name__ == "__main__":
    run_training_pipeline()

