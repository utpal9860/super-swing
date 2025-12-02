"""
Model 1: Pattern Validity Classifier
Filters out false positives from ML pattern detection
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

logger = setup_logger("validity_classifier")

class PatternValidityClassifier(BasePatternModel):
    """
    Model to classify patterns as valid or invalid
    Filters out false positives from automated detection
    """
    
    def __init__(self):
        super().__init__(
            model_name="pattern_validity_classifier",
            model_type="classifier"
        )
        
        # Initialize Random Forest
        config = MODEL_CONFIG['model_1_validity']
        self.model = RandomForestClassifier(**config['params'])
        self.scaler = StandardScaler()
        self.threshold = config['threshold']
    
    def train(self, X_train, y_train, X_val=None, y_val=None):
        """
        Train pattern validity classifier
        
        Args:
            X_train: Training features
            y_train: Training labels (1=valid, 0=invalid)
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
        """
        logger.info(f"Training {self.model_name}...")
        logger.info(f"Training samples: {len(X_train)}")
        logger.info(f"Class distribution: {y_train.value_counts().to_dict()}")
        
        # Store feature names
        self.feature_names = X_train.columns.tolist()
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        # Train model
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
        top_features = list(self.feature_importance.items())[:10]
        logger.info("Top 10 important features:")
        for feat, imp in top_features:
            logger.info(f"  {feat}: {imp:.4f}")
    
    def predict(self, X):
        """
        Predict pattern validity
        
        Args:
            X: Features DataFrame
        
        Returns:
            Binary predictions (1=valid, 0=invalid)
        """
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def predict_proba(self, X):
        """
        Predict validity probability
        
        Args:
            X: Features DataFrame
        
        Returns:
            Probability array
        """
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)
    
    def filter_valid_patterns(self, X, threshold=None):
        """
        Filter patterns by validity threshold
        
        Args:
            X: Features DataFrame
            threshold: Probability threshold (default from config)
        
        Returns:
            Boolean mask of valid patterns
        """
        threshold = threshold or self.threshold
        proba = self.predict_proba(X)[:, 1]
        return proba >= threshold
    
    def evaluate(self, X_test, y_test):
        """
        Evaluate model with additional metrics
        
        Args:
            X_test: Test features
            y_test: Test labels
        
        Returns:
            Dictionary with metrics
        """
        X_test_scaled = self.scaler.transform(X_test)
        
        # Base metrics
        metrics = super().evaluate(pd.DataFrame(X_test_scaled, columns=self.feature_names), y_test)
        
        # Additional analysis
        proba = self.predict_proba(X_test)[:, 1]
        
        # Precision at different thresholds
        for thresh in [0.5, 0.6, 0.7, 0.8]:
            predictions_at_thresh = (proba >= thresh).astype(int)
            from sklearn.metrics import precision_score
            precision_at_thresh = precision_score(y_test, predictions_at_thresh, zero_division=0)
            metrics[f'precision_at_{thresh}'] = precision_at_thresh
        
        logger.info(f"Validity Classifier Metrics: {metrics}")
        return metrics

if __name__ == "__main__":
    print("Pattern Validity Classifier")
    print("============================")
    print("Purpose: Filter false positives from automated pattern detection")
    print("Model: Random Forest Classifier")
    print(f"Configuration: {MODEL_CONFIG['model_1_validity']}")

