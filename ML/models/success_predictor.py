"""
Model 2: Pattern Success Predictor
Predicts probability of pattern reaching target
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.base_model import BasePatternModel
from utils.logger import setup_logger
from config import MODEL_CONFIG
from datetime import datetime

logger = setup_logger("success_predictor")

# Try to import XGBoost, fallback to RandomForest
try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    logger.warning("XGBoost not available, using RandomForest instead")
    XGBOOST_AVAILABLE = False

class PatternSuccessPredictor(BasePatternModel):
    """
    Model to predict pattern success probability
    Learns which patterns work for which stocks/sectors/market conditions
    """
    
    def __init__(self, use_xgboost: bool = True):
        super().__init__(
            model_name="pattern_success_predictor",
            model_type="classifier"
        )
        
        config = MODEL_CONFIG['model_2_success']
        
        # Use XGBoost if available and requested
        if use_xgboost and XGBOOST_AVAILABLE:
            self.model = XGBClassifier(**config['params'])
            logger.info("Using XGBoost for success prediction")
        else:
            # Fallback to RandomForest
            from sklearn.ensemble import RandomForestClassifier
            rf_params = {
                'n_estimators': 100,
                'max_depth': 6,
                'min_samples_split': 20,
                'min_samples_leaf': 10,
                'class_weight': 'balanced',
                'random_state': 42,
            }
            self.model = RandomForestClassifier(**rf_params)
            logger.info("Using Random Forest for success prediction")
        
        self.scaler = StandardScaler()
        self.threshold = config['threshold']
    
    def train(self, X_train, y_train, X_val=None, y_val=None):
        """
        Train pattern success predictor
        
        Args:
            X_train: Training features
            y_train: Training labels (1=success, 0=failure)
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
        """
        logger.info(f"Training {self.model_name}...")
        logger.info(f"Training samples: {len(X_train)}")
        logger.info(f"Success rate: {y_train.mean():.2%}")
        
        # Store feature names
        self.feature_names = X_train.columns.tolist()
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        # Train model
        if isinstance(self.model, XGBClassifier):
            # XGBoost with early stopping
            if X_val is not None and y_val is not None:
                X_val_scaled = self.scaler.transform(X_val)
                eval_set = [(X_train_scaled, y_train), (X_val_scaled, y_val)]
                self.model.fit(
                    X_train_scaled, y_train,
                    eval_set=eval_set,
                    verbose=False
                )
            else:
                self.model.fit(X_train_scaled, y_train)
        else:
            self.model.fit(X_train_scaled, y_train)
        
        self.trained_at = datetime.now()
        
        # Evaluate on training set
        train_score = self.model.score(X_train_scaled, y_train)
        logger.info(f"Training accuracy: {train_score:.4f}")
        
        # Evaluate on validation set if provided
        if X_val is not None and y_val is not None:
            X_val_scaled = self.scaler.transform(X_val)
            val_score = self.model.score(X_val_scaled, y_val)
            logger.info(f"Validation accuracy: {val_score:.4f}")
        
        # Get feature importance
        self.get_feature_importance()
        
        # Log top features
        top_features = list(self.feature_importance.items())[:15]
        logger.info("Top 15 important features for pattern success:")
        for feat, imp in top_features:
            logger.info(f"  {feat}: {imp:.4f}")
    
    def predict(self, X):
        """
        Predict pattern success
        
        Args:
            X: Features DataFrame
        
        Returns:
            Binary predictions (1=success, 0=failure)
        """
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def predict_proba(self, X):
        """
        Predict success probability
        
        Args:
            X: Features DataFrame
        
        Returns:
            Probability array
        """
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)
    
    def get_success_probability(self, X):
        """
        Get probability of success for each pattern
        
        Args:
            X: Features DataFrame
        
        Returns:
            Array of success probabilities
        """
        return self.predict_proba(X)[:, 1]
    
    def rank_patterns(self, X, patterns_df=None):
        """
        Rank patterns by success probability
        
        Args:
            X: Features DataFrame
            patterns_df: Optional DataFrame with pattern info
        
        Returns:
            DataFrame with ranked patterns
        """
        proba = self.get_success_probability(X)
        
        if patterns_df is not None:
            patterns_df = patterns_df.copy()
            patterns_df['success_probability'] = proba
            patterns_df = patterns_df.sort_values('success_probability', ascending=False)
        else:
            patterns_df = pd.DataFrame({
                'index': range(len(proba)),
                'success_probability': proba
            }).sort_values('success_probability', ascending=False)
        
        return patterns_df
    
    def evaluate(self, X_test, y_test):
        """
        Comprehensive evaluation
        
        Args:
            X_test: Test features
            y_test: Test labels
        
        Returns:
            Dictionary with metrics
        """
        X_test_scaled = self.scaler.transform(X_test)
        
        # Base metrics
        metrics = super().evaluate(pd.DataFrame(X_test_scaled, columns=self.feature_names), y_test)
        
        # Additional metrics
        proba = self.predict_proba(X_test)[:, 1]
        
        # Top decile precision (precision of top 10% predictions)
        top_decile_idx = np.argsort(proba)[-int(len(proba)*0.1):]
        top_decile_precision = y_test.iloc[top_decile_idx].mean()
        metrics['top_decile_success_rate'] = top_decile_precision
        
        logger.info(f"Success Predictor Metrics: {metrics}")
        logger.info(f"Top 10% patterns have {top_decile_precision:.2%} success rate")
        
        return metrics

if __name__ == "__main__":
    print("Pattern Success Predictor")
    print("==========================")
    print("Purpose: Predict which patterns will reach target")
    print("Model: XGBoost or Random Forest Classifier")
    print(f"XGBoost available: {XGBOOST_AVAILABLE}")
    print(f"Configuration: {MODEL_CONFIG['model_2_success']}")

