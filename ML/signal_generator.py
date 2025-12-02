"""
ML-Powered Signal Generator
Scans stocks, detects patterns, applies ML models, generates trading signals
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from pattern_detection.data_fetcher import get_stock_universe, batch_fetch_data, fetch_market_data
from pattern_detection.talib_patterns import batch_scan_patterns, filter_high_quality_patterns
from feature_engineering.features import create_feature_dataframe, prepare_ml_dataset
from models.validity_classifier import PatternValidityClassifier
from models.success_predictor import PatternSuccessPredictor
from models.risk_reward_estimator import RiskRewardEstimator
from database.schema import create_database, insert_pattern
from utils.logger import setup_logger
from config import MODELS_DIR, SIGNAL_CONFIG

logger = setup_logger("signal_generator")

class MLSignalGenerator:
    """
    ML-powered signal generator
    Combines pattern detection with ML prediction models
    """
    
    def __init__(self):
        """Initialize signal generator with trained models"""
        self.model1 = None  # Validity classifier
        self.model2 = None  # Success predictor
        self.model3 = None  # Risk-reward estimator
        
        logger.info("ML Signal Generator initialized")
    
    def load_models(self, model1_path=None, model2_path=None, model3_path=None):
        """
        Load trained ML models
        
        Args:
            model1_path: Path to validity classifier
            model2_path: Path to success predictor
            model3_path: Path to risk-reward estimator
        """
        # Auto-find latest models if paths not provided
        if model1_path is None:
            model1_files = list(MODELS_DIR.glob("validity_classifier_*.pkl"))
            if model1_files:
                model1_path = max(model1_files, key=lambda p: p.stat().st_mtime)
        
        if model2_path is None:
            model2_files = list(MODELS_DIR.glob("success_predictor_*.pkl"))
            if model2_files:
                model2_path = max(model2_files, key=lambda p: p.stat().st_mtime)
        
        if model3_path is None:
            model3_files = list(MODELS_DIR.glob("risk_reward_estimator_*.pkl"))
            if model3_files:
                model3_path = max(model3_files, key=lambda p: p.stat().st_mtime)
        
        # Load models
        if model1_path and model1_path.exists():
            self.model1 = PatternValidityClassifier()
            self.model1.load(model1_path)
            logger.info(f"Loaded validity classifier from {model1_path}")
        
        if model2_path and model2_path.exists():
            self.model2 = PatternSuccessPredictor(use_xgboost=False)
            self.model2.load(model2_path)
            logger.info(f"Loaded success predictor from {model2_path}")
        
        if model3_path and model3_path.exists():
            self.model3 = RiskRewardEstimator()
            self.model3.load(model3_path)
            logger.info(f"Loaded risk-reward estimator from {model3_path}")
    
    def scan_for_patterns(
        self,
        universe_type: str = "FNO",
        lookback_days: int = 730,
        recent_patterns_days: int = 5
    ) -> tuple:
        """
        Scan stocks for patterns
        
        Returns:
            (patterns, data_dict, market_data)
        """
        logger.info("="*60)
        logger.info("Step 1: Scanning for Patterns")
        logger.info("="*60)
        
        # Get stock universe
        tickers = get_stock_universe(universe_type)
        logger.info(f"Scanning {len(tickers)} stocks")
        
        # Fetch data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        logger.info("Fetching stock data...")
        data_dict = batch_fetch_data(tickers, start_date, end_date)
        
        logger.info("Fetching market data...")
        market_data = fetch_market_data(start_date, end_date)
        
        # Scan for patterns
        logger.info("Detecting patterns...")
        all_patterns = batch_scan_patterns(
            list(data_dict.keys()),
            data_dict,
            exchange="NSE",
            lookback_days=recent_patterns_days
        )
        
        # Filter quality patterns
        quality_patterns = filter_high_quality_patterns(all_patterns, min_quality=0.5)
        
        logger.info(f"Found {len(quality_patterns)} quality patterns")
        
        return quality_patterns, data_dict, market_data
    
    def apply_ml_models(
        self,
        patterns: List[Dict],
        data_dict: Dict,
        market_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Apply ML models to filter and rank patterns
        
        Returns:
            DataFrame with predictions
        """
        logger.info("="*60)
        logger.info("Step 2: Applying ML Models")
        logger.info("="*60)
        
        # Engineer features
        logger.info("Engineering features...")
        features_df = create_feature_dataframe(
            patterns,
            data_dict,
            market_data.get('nifty_50')
        )
        
        logger.info(f"Features DataFrame: {features_df.shape[0]} rows, {features_df.shape[1] if not features_df.empty else 0} columns")
        
        if features_df.empty:
            logger.warning("No features engineered, returning empty DataFrame")
            return pd.DataFrame()
        
        # Prepare for ML
        try:
            X, _, feature_names = prepare_ml_dataset(features_df)
            logger.info(f"ML Dataset prepared: {X.shape[0]} samples, {X.shape[1]} features")
        except Exception as e:
            logger.error(f"Error preparing ML dataset: {e}")
            return pd.DataFrame()
        
        if X.empty or len(X) == 0:
            logger.warning("ML dataset is empty after preparation")
            return pd.DataFrame()
        
        # Apply Model 1: Validity Filter
        if self.model1 is not None:
            try:
                logger.info("Applying validity filter...")
                valid_mask = self.model1.filter_valid_patterns(X)
                logger.info(f"Validity filter: {valid_mask.sum()}/{len(X)} patterns passed")
                
                X = X[valid_mask]
                features_df = features_df[valid_mask].reset_index(drop=True)
            except Exception as e:
                logger.warning(f"Error applying validity filter: {e}, continuing without it")
        
        if len(X) == 0:
            logger.warning("No patterns passed validity filter")
            return pd.DataFrame()
        
        # Apply Model 2: Success Probability
        if self.model2 is not None:
            logger.info("Predicting success probability...")
            success_prob = self.model2.get_success_probability(X)
            features_df['success_probability'] = success_prob
        else:
            features_df['success_probability'] = 0.5
        
        # Apply Model 3: Risk-Reward Estimation
        if self.model3 is not None:
            logger.info("Estimating risk-reward...")
            expected_gain, expected_days = self.model3.predict_both(X)
            features_df['expected_gain'] = expected_gain
            features_df['expected_holding_days'] = expected_days
        else:
            features_df['expected_gain'] = 3.0
            features_df['expected_holding_days'] = 10
        
        logger.info(f"ML models applied to {len(features_df)} patterns")
        
        return features_df
    
    def generate_signals(
        self,
        predictions_df: pd.DataFrame,
        min_success_prob: float = None,
        min_expected_gain: float = None,
        max_signals: int = None
    ) -> pd.DataFrame:
        """
        Generate trading signals from predictions
        
        Returns:
            DataFrame with trading signals
        """
        logger.info("="*60)
        logger.info("Step 3: Generating Trading Signals")
        logger.info("="*60)
        
        if predictions_df.empty:
            logger.warning("No predictions available")
            return pd.DataFrame()
        
        # Apply filters
        min_success_prob = min_success_prob or SIGNAL_CONFIG['min_success_probability']
        min_expected_gain = min_expected_gain or SIGNAL_CONFIG['min_expected_gain']
        max_signals = max_signals or SIGNAL_CONFIG['max_signals_per_day']
        
        logger.info(f"Filters: Success >= {min_success_prob:.0%}, Gain >= {min_expected_gain}%")
        
        # Filter signals
        signals = predictions_df[
            (predictions_df['success_probability'] >= min_success_prob) &
            (predictions_df['expected_gain'] >= min_expected_gain)
        ].copy()
        
        logger.info(f"Filtered to {len(signals)} signals")
        
        if signals.empty:
            logger.warning("No signals meet criteria")
            return pd.DataFrame()
        
        # Rank signals
        signals['rank_score'] = (
            signals['success_probability'] * 0.5 +
            (signals['expected_gain'] / 10) * 0.3 +
            (1 / (signals['expected_holding_days'] + 1)) * 0.2
        )
        
        signals = signals.sort_values('rank_score', ascending=False)
        
        # Limit number of signals
        signals = signals.head(max_signals)
        
        # Add recommendation
        signals['recommendation'] = 'BUY'
        signals['signal_date'] = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"Generated {len(signals)} trading signals")
        
        return signals
    
    def run(
        self,
        universe_type: str = "FNO",
        save_signals: bool = True
    ) -> pd.DataFrame:
        """
        Run complete signal generation pipeline
        
        Returns:
            DataFrame with trading signals
        """
        logger.info("="*60)
        logger.info("ML SIGNAL GENERATOR - STARTING")
        logger.info("="*60)
        
        # Step 1: Scan for patterns
        patterns, data_dict, market_data = self.scan_for_patterns(
            universe_type=universe_type
        )
        
        if not patterns:
            logger.warning("No patterns found")
            return pd.DataFrame()
        
        # Step 2: Apply ML models
        predictions = self.apply_ml_models(patterns, data_dict, market_data)
        
        if predictions.empty:
            logger.warning("No predictions generated")
            return pd.DataFrame()
        
        # Step 3: Generate signals
        signals = self.generate_signals(predictions)
        
        # Save signals
        if save_signals and not signals.empty:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = Path(f"ML/data/signals_{timestamp}.csv")
            signals.to_csv(output_file, index=False)
            logger.info(f"Signals saved to {output_file}")
        
        # Summary
        logger.info("="*60)
        logger.info("SIGNAL GENERATION COMPLETE")
        logger.info("="*60)
        if not signals.empty:
            logger.info(f"Total Signals: {len(signals)}")
            logger.info(f"Avg Success Probability: {signals['success_probability'].mean():.2%}")
            logger.info(f"Avg Expected Gain: {signals['expected_gain'].mean():.2f}%")
            logger.info("\nTop 5 Signals:")
            for idx, row in signals.head(5).iterrows():
                logger.info(f"  {row['ticker']}: {row['pattern_type']} | "
                           f"Success: {row['success_probability']:.0%} | "
                           f"Gain: {row['expected_gain']:.1f}%")
        logger.info("="*60)
        
        return signals

def main():
    """Main function to run signal generator"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ML-Powered Signal Generator")
    parser.add_argument(
        "--universe",
        type=str,
        default="FNO",
        choices=["FNO", "NIFTY50", "NIFTY100"],
        help="Stock universe to scan"
    )
    parser.add_argument(
        "--load-models",
        action="store_true",
        help="Load trained models"
    )
    
    args = parser.parse_args()
    
    # Create signal generator
    generator = MLSignalGenerator()
    
    # Load models if requested
    if args.load_models:
        generator.load_models()
    
    # Run signal generation
    signals = generator.run(universe_type=args.universe)
    
    # Print results
    if not signals.empty:
        print("\n" + "="*60)
        print("TRADING SIGNALS")
        print("="*60)
        print(signals[['ticker', 'pattern_type', 'success_probability', 
                      'expected_gain', 'recommendation']].to_string(index=False))
        print("="*60)
    else:
        print("\nNo signals generated today.")

if __name__ == "__main__":
    main()

