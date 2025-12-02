"""
Model 3: Risk-Reward Estimator
Predicts expected gain/loss and holding period
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.base_model import BasePatternModel
from utils.logger import setup_logger
from config import MODEL_CONFIG
from datetime import datetime

logger = setup_logger("risk_reward_estimator")

class RiskRewardEstimator(BasePatternModel):
    """
    Model to estimate expected gain and holding period
    Helps with position sizing and trade selection
    """
    
    def __init__(self):
        super().__init__(
            model_name="risk_reward_estimator",
            model_type="regressor"
        )
        
        config = MODEL_CONFIG['model_3_risk_reward']
        
        # Separate models for different targets
        self.gain_model = RandomForestRegressor(**config['params'])
        self.time_model = RandomForestRegressor(**config['params'])
        
        self.scaler = StandardScaler()
        self.trained_at = None
    
    def train(self, X_train, y_gain_train, y_time_train, X_val=None, y_gain_val=None, y_time_val=None):
        """
        Train risk-reward estimator
        
        Args:
            X_train: Training features
            y_gain_train: Expected gain/loss percentage
            y_time_train: Expected holding days
            X_val: Validation features (optional)
            y_gain_val: Validation gain targets (optional)
            y_time_val: Validation time targets (optional)
        """
        logger.info(f"Training {self.model_name}...")
        logger.info(f"Training samples: {len(X_train)}")
        logger.info(f"Avg expected gain: {y_gain_train.mean():.2f}%")
        logger.info(f"Avg holding days: {y_time_train.mean():.1f}")
        
        # Store feature names
        self.feature_names = X_train.columns.tolist()
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        # Train gain model
        logger.info("Training gain predictor...")
        self.gain_model.fit(X_train_scaled, y_gain_train)
        
        # Train time model
        logger.info("Training holding period predictor...")
        self.time_model.fit(X_train_scaled, y_time_train)
        
        self.trained_at = datetime.now()
        
        # Evaluate on training set
        gain_train_score = self.gain_model.score(X_train_scaled, y_gain_train)
        time_train_score = self.time_model.score(X_train_scaled, y_time_train)
        logger.info(f"Gain model R²: {gain_train_score:.4f}")
        logger.info(f"Time model R²: {time_train_score:.4f}")
        
        # Evaluate on validation set if provided
        if X_val is not None and y_gain_val is not None:
            X_val_scaled = self.scaler.transform(X_val)
            gain_val_score = self.gain_model.score(X_val_scaled, y_gain_val)
            time_val_score = self.time_model.score(X_val_scaled, y_time_val)
            logger.info(f"Validation - Gain R²: {gain_val_score:.4f}, Time R²: {time_val_score:.4f}")
        
        # Get feature importance
        self.get_feature_importance_gain()
        self.get_feature_importance_time()
    
    def predict_gain(self, X):
        """
        Predict expected gain/loss
        
        Args:
            X: Features DataFrame
        
        Returns:
            Expected gain percentage
        """
        X_scaled = self.scaler.transform(X)
        return self.gain_model.predict(X_scaled)
    
    def predict_holding_days(self, X):
        """
        Predict expected holding period
        
        Args:
            X: Features DataFrame
        
        Returns:
            Expected holding days
        """
        X_scaled = self.scaler.transform(X)
        return self.time_model.predict(X_scaled)
    
    def predict_both(self, X):
        """
        Predict both gain and holding period
        
        Args:
            X: Features DataFrame
        
        Returns:
            Tuple of (gain, holding_days)
        """
        return self.predict_gain(X), self.predict_holding_days(X)
    
    def calculate_risk_reward_ratio(self, expected_gain, stop_loss_pct=2.0):
        """
        Calculate risk-reward ratio
        
        Args:
            expected_gain: Expected gain percentage
            stop_loss_pct: Stop loss percentage (default 2%)
        
        Returns:
            Risk-reward ratio
        """
        return expected_gain / stop_loss_pct if stop_loss_pct > 0 else 0
    
    def get_feature_importance_gain(self):
        """Get feature importance for gain model"""
        if hasattr(self.gain_model, 'feature_importances_'):
            importance = self.gain_model.feature_importances_
            importance_dict = {
                name: float(imp) 
                for name, imp in zip(self.feature_names, importance)
            }
            self.gain_feature_importance = dict(
                sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
            )
            
            # Log top features
            top_features = list(self.gain_feature_importance.items())[:10]
            logger.info("Top 10 features for gain prediction:")
            for feat, imp in top_features:
                logger.info(f"  {feat}: {imp:.4f}")
        
        return getattr(self, 'gain_feature_importance', {})
    
    def get_feature_importance_time(self):
        """Get feature importance for time model"""
        if hasattr(self.time_model, 'feature_importances_'):
            importance = self.time_model.feature_importances_
            importance_dict = {
                name: float(imp) 
                for name, imp in zip(self.feature_names, importance)
            }
            self.time_feature_importance = dict(
                sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
            )
            
            # Log top features
            top_features = list(self.time_feature_importance.items())[:10]
            logger.info("Top 10 features for holding period prediction:")
            for feat, imp in top_features:
                logger.info(f"  {feat}: {imp:.4f}")
        
        return getattr(self, 'time_feature_importance', {})
    
    def evaluate(self, X_test, y_gain_test, y_time_test):
        """
        Evaluate both models
        
        Args:
            X_test: Test features
            y_gain_test: Test gain targets
            y_time_test: Test time targets
        
        Returns:
            Dictionary with metrics
        """
        X_test_scaled = self.scaler.transform(X_test)
        
        # Gain model metrics
        gain_pred = self.gain_model.predict(X_test_scaled)
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        
        gain_metrics = {
            'gain_mae': mean_absolute_error(y_gain_test, gain_pred),
            'gain_rmse': np.sqrt(mean_squared_error(y_gain_test, gain_pred)),
            'gain_r2': r2_score(y_gain_test, gain_pred),
        }
        
        # Time model metrics
        time_pred = self.time_model.predict(X_test_scaled)
        time_metrics = {
            'time_mae': mean_absolute_error(y_time_test, time_pred),
            'time_rmse': np.sqrt(mean_squared_error(y_time_test, time_pred)),
            'time_r2': r2_score(y_time_test, time_pred),
        }
        
        metrics = {**gain_metrics, **time_metrics}
        self.metrics = metrics
        
        logger.info(f"Risk-Reward Estimator Metrics:")
        logger.info(f"  Gain MAE: {gain_metrics['gain_mae']:.2f}%")
        logger.info(f"  Time MAE: {time_metrics['time_mae']:.1f} days")
        
        return metrics
    
    def save(self, filepath=None):
        """Save both models"""
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = Path(f"models/risk_reward_estimator_{timestamp}.pkl")
        
        import pickle
        save_data = {
            'gain_model': self.gain_model,
            'time_model': self.time_model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'trained_at': self.trained_at,
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(save_data, f)
        
        logger.info(f"Models saved to {filepath}")
        return filepath
    
    def load(self, filepath):
        """Load both models"""
        import pickle
        with open(filepath, 'rb') as f:
            save_data = pickle.load(f)
        
        self.gain_model = save_data['gain_model']
        self.time_model = save_data['time_model']
        self.scaler = save_data['scaler']
        self.feature_names = save_data['feature_names']
        self.trained_at = save_data['trained_at']
        
        logger.info(f"Models loaded from {filepath}")

if __name__ == "__main__":
    print("Risk-Reward Estimator")
    print("=====================")
    print("Purpose: Estimate expected gain and holding period")
    print("Models: Dual Random Forest Regressors")
    print(f"Configuration: {MODEL_CONFIG['model_3_risk_reward']}")

