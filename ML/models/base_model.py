"""
Base model class for pattern prediction
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import pickle
from pathlib import Path
from datetime import datetime
import sys
sys.path.append(str(Path(__file__).parent.parent))

from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, 
    roc_auc_score, mean_absolute_error, mean_squared_error, r2_score
)
from utils.logger import setup_logger
from config import MODELS_DIR

logger = setup_logger("base_model")

class BasePatternModel:
    """Base class for pattern prediction models"""
    
    def __init__(self, model_name: str, model_type: str = "classifier"):
        """
        Initialize base model
        
        Args:
            model_name: Name of the model
            model_type: Type of model (classifier or regressor)
        """
        self.model_name = model_name
        self.model_type = model_type
        self.model = None
        self.feature_names = []
        self.feature_importance = {}
        self.metrics = {}
        self.trained_at = None
        self.version = "1.0"
    
    def time_series_split(
        self, 
        X: pd.DataFrame, 
        y: pd.Series, 
        n_splits: int = 5
    ) -> Tuple:
        """
        Time series train-test split
        
        Args:
            X: Features DataFrame
            y: Target Series
            n_splits: Number of splits for CV
        
        Returns:
            Tuple of (X_train, X_test, y_train, y_test)
        """
        # Sort by index (assuming index is chronological)
        X = X.sort_index()
        y = y.sort_index()
        
        # Split: 70% train, 15% val, 15% test
        n_samples = len(X)
        train_end = int(n_samples * 0.70)
        val_end = int(n_samples * 0.85)
        
        X_train = X.iloc[:train_end]
        X_val = X.iloc[train_end:val_end]
        X_test = X.iloc[val_end:]
        
        y_train = y.iloc[:train_end]
        y_val = y.iloc[train_end:val_end]
        y_test = y.iloc[val_end:]
        
        logger.info(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
        
        return X_train, X_val, X_test, y_train, y_val, y_test
    
    def train(
        self, 
        X_train: pd.DataFrame, 
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None
    ):
        """
        Train the model
        
        Args:
            X_train: Training features
            y_train: Training target
            X_val: Validation features (optional)
            y_val: Validation target (optional)
        """
        raise NotImplementedError("Subclass must implement train method")
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make predictions
        
        Args:
            X: Features DataFrame
        
        Returns:
            Predictions array
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        return self.model.predict(X)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict probabilities (for classifiers)
        
        Args:
            X: Features DataFrame
        
        Returns:
            Probability predictions array
        """
        if self.model_type != "classifier":
            raise ValueError("predict_proba only available for classifiers")
        
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        return self.model.predict_proba(X)
    
    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict:
        """
        Evaluate model performance
        
        Args:
            X_test: Test features
            y_test: Test target
        
        Returns:
            Dictionary with metrics
        """
        predictions = self.predict(X_test)
        
        if self.model_type == "classifier":
            metrics = {
                'accuracy': accuracy_score(y_test, predictions),
                'precision': precision_score(y_test, predictions, average='binary', zero_division=0),
                'recall': recall_score(y_test, predictions, average='binary', zero_division=0),
                'f1_score': f1_score(y_test, predictions, average='binary', zero_division=0),
            }
            
            # ROC-AUC (if predict_proba available)
            try:
                proba = self.predict_proba(X_test)[:, 1]
                metrics['roc_auc'] = roc_auc_score(y_test, proba)
            except:
                metrics['roc_auc'] = 0.0
        
        else:  # Regressor
            metrics = {
                'mae': mean_absolute_error(y_test, predictions),
                'rmse': np.sqrt(mean_squared_error(y_test, predictions)),
                'r2_score': r2_score(y_test, predictions),
            }
        
        self.metrics = metrics
        logger.info(f"{self.model_name} Metrics: {metrics}")
        
        return metrics
    
    def get_feature_importance(self) -> Dict:
        """
        Get feature importance
        
        Returns:
            Dictionary with feature importance
        """
        if self.model is None:
            return {}
        
        if hasattr(self.model, 'feature_importances_'):
            importance = self.model.feature_importances_
            
            # Create sorted dictionary
            importance_dict = {
                name: float(imp) 
                for name, imp in zip(self.feature_names, importance)
            }
            
            # Sort by importance
            self.feature_importance = dict(
                sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
            )
        
        return self.feature_importance
    
    def save(self, filepath: Optional[Path] = None):
        """
        Save model to disk
        
        Args:
            filepath: Path to save model
        """
        if self.model is None:
            raise ValueError("No model to save")
        
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = MODELS_DIR / f"{self.model_name}_{timestamp}.pkl"
        
        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Save model and metadata
        save_data = {
            'model': self.model,
            'model_name': self.model_name,
            'model_type': self.model_type,
            'feature_names': self.feature_names,
            'feature_importance': self.feature_importance,
            'metrics': self.metrics,
            'trained_at': self.trained_at,
            'version': self.version,
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(save_data, f)
        
        logger.info(f"Model saved to {filepath}")
        return filepath
    
    def load(self, filepath: Path):
        """
        Load model from disk
        
        Args:
            filepath: Path to load model from
        """
        with open(filepath, 'rb') as f:
            save_data = pickle.load(f)
        
        self.model = save_data['model']
        self.model_name = save_data['model_name']
        self.model_type = save_data['model_type']
        self.feature_names = save_data['feature_names']
        self.feature_importance = save_data.get('feature_importance', {})
        self.metrics = save_data.get('metrics', {})
        self.trained_at = save_data.get('trained_at')
        self.version = save_data.get('version', '1.0')
        
        logger.info(f"Model loaded from {filepath}")
    
    def cross_validate(
        self, 
        X: pd.DataFrame, 
        y: pd.Series, 
        cv: int = 5
    ) -> Dict:
        """
        Perform time series cross-validation
        
        Args:
            X: Features DataFrame
            y: Target Series
            cv: Number of CV folds
        
        Returns:
            Dictionary with CV scores
        """
        tscv = TimeSeriesSplit(n_splits=cv)
        
        if self.model_type == "classifier":
            scoring = ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']
        else:
            scoring = ['neg_mean_absolute_error', 'neg_root_mean_squared_error', 'r2']
        
        cv_results = {}
        
        for score_name in scoring:
            scores = cross_val_score(
                self.model, X, y, 
                cv=tscv, 
                scoring=score_name,
                n_jobs=-1
            )
            cv_results[score_name] = {
                'mean': scores.mean(),
                'std': scores.std(),
                'scores': scores.tolist()
            }
        
        logger.info(f"Cross-validation results: {cv_results}")
        return cv_results

