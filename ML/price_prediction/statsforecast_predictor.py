"""
FREE Price Prediction using StatsForecast
Alternative to TimeGPT - by the same company (Nixtla), but open source!
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from utils.logger import setup_logger

logger = setup_logger("statsforecast_predictor")

# Try to import StatsForecast
try:
    from statsforecast import StatsForecast
    from statsforecast.models import (
        AutoARIMA,    # Classic time series
        AutoETS,      # Exponential smoothing
        AutoTheta,    # Theta method (good for stocks!)
    )
    STATSFORECAST_AVAILABLE = True
except ImportError:
    logger.warning("StatsForecast not installed. Run: pip install statsforecast")
    STATSFORECAST_AVAILABLE = False


class StatsForecastPredictor:
    """
    FREE price prediction using StatsForecast
    
    Replaces TimeGPT with open-source models from Nixtla (same company!)
    """
    
    def __init__(self, models=None):
        """
        Initialize predictor with ensemble of models
        
        Args:
            models: List of models to use (default: AutoARIMA, AutoETS, AutoTheta)
        """
        if not STATSFORECAST_AVAILABLE:
            raise ImportError(
                "StatsForecast is not installed. "
                "Install it with: pip install statsforecast"
            )
        
        if models is None:
            # Default ensemble - these work best for stock prices
            self.models = [
                AutoARIMA(season_length=5),  # 5-day trading week
                AutoETS(season_length=5),
                AutoTheta(season_length=5),
            ]
        else:
            self.models = models
        
        logger.info(f"StatsForecast initialized with {len(self.models)} models")
    
    def prepare_data(self, prices: pd.Series) -> pd.DataFrame:
        """
        Prepare price data for StatsForecast
        
        Args:
            prices: Series with DatetimeIndex and close prices
        
        Returns:
            DataFrame with columns: unique_id, ds, y
        """
        df = pd.DataFrame({
            'unique_id': 'stock',  # Required by StatsForecast
            'ds': prices.index,
            'y': prices.values
        })
        
        return df
    
    def forecast_stock_price(self, historical_prices: pd.Series, 
                            horizon: int = 10) -> Dict:
        """
        Forecast next N days of stock prices
        
        Args:
            historical_prices: Series with DatetimeIndex and close prices
            horizon: Number of days to forecast (default: 10)
        
        Returns:
            {
                'predictions': [3595, 3620, 3655, ...],
                'confidence_low': [3550, 3570, ...],
                'confidence_high': [3640, 3670, ...],
                'expected_return': 0.042,
                'probability_gain': 0.72,
                'model_used': 'ensemble',
                'forecast_dates': [...],
                'current_price': 3565.0,
                'predicted_price': 3650.0
            }
        """
        try:
            # Prepare data
            df = self.prepare_data(historical_prices)
            
            # Initialize StatsForecast
            sf = StatsForecast(
                models=self.models,
                freq='D',  # Daily frequency
                n_jobs=-1  # Use all CPU cores
            )
            
            # Generate forecast
            logger.info(f"Generating {horizon}-day forecast...")
            forecast = sf.forecast(df=df, h=horizon, level=[80, 95])
            
            # Extract predictions (average across models)
            model_cols = [col for col in forecast.columns 
                         if col not in ['unique_id', 'ds'] 
                         and not '-lo-' in col 
                         and not '-hi-' in col]
            
            # Average predictions from all models (ensemble)
            predictions = forecast[model_cols].mean(axis=1).values
            
            # Get confidence intervals (use 80% by default)
            lo_cols = [col for col in forecast.columns if '-lo-80' in col]
            hi_cols = [col for col in forecast.columns if '-hi-80' in col]
            
            if lo_cols and hi_cols:
                confidence_low = forecast[lo_cols].mean(axis=1).values
                confidence_high = forecast[hi_cols].mean(axis=1).values
            else:
                # Fallback: use simple percentage bands
                confidence_low = predictions * 0.97
                confidence_high = predictions * 1.03
            
            # Calculate metrics
            current_price = float(historical_prices.iloc[-1])
            predicted_price = float(predictions[-1])
            expected_return = (predicted_price - current_price) / current_price
            
            # Calculate probability of gain based on confidence intervals
            probability_gain = self._calculate_gain_probability(
                current_price, predictions, confidence_low
            )
            
            # Generate forecast dates
            last_date = historical_prices.index[-1]
            forecast_dates = pd.date_range(
                start=last_date + timedelta(days=1),
                periods=horizon,
                freq='D'
            )
            
            result = {
                'predictions': [float(p) for p in predictions],
                'confidence_low': [float(p) for p in confidence_low],
                'confidence_high': [float(p) for p in confidence_high],
                'expected_return': float(expected_return),
                'probability_gain': float(probability_gain),
                'model_used': 'ensemble',
                'forecast_dates': [d.strftime('%Y-%m-%d') for d in forecast_dates],
                'current_price': current_price,
                'predicted_price': predicted_price,
                'confidence_range': float(confidence_high[-1] - confidence_low[-1])
            }
            
            logger.info(f"Forecast complete: Rs.{current_price:.2f} -> Rs.{predicted_price:.2f} "
                       f"({expected_return*100:+.2f}%)")
            
            return result
        
        except Exception as e:
            logger.error(f"Forecast error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'error': str(e),
                'predictions': None
            }
    
    def _calculate_gain_probability(self, current_price: float, 
                                    predictions: np.ndarray,
                                    confidence_low: np.ndarray) -> float:
        """
        Calculate probability of gain based on predictions and confidence intervals
        
        Simple heuristic: If lower bound of confidence interval is above current price,
        high probability of gain
        """
        final_prediction = predictions[-1]
        final_low = confidence_low[-1]
        
        # If even the lower bound is above current price, high probability
        if final_low > current_price:
            return 0.85
        # If prediction is above but lower bound is below, moderate probability
        elif final_prediction > current_price:
            # Linear interpolation based on how far prediction is above current
            distance_above = final_prediction - current_price
            distance_to_low = final_prediction - final_low
            if distance_to_low > 0:
                ratio = distance_above / distance_to_low
                return 0.50 + (0.30 * min(ratio, 1.0))
            else:
                return 0.60
        else:
            # Prediction is below current price
            return 0.30
    
    def get_prediction_score(self, forecast_result: Dict) -> float:
        """
        Convert forecast to 0-1 score for fusion layer
        
        Args:
            forecast_result: Output from forecast_stock_price
        
        Returns:
            Score from 0 (bearish) to 1 (bullish)
            0.5 = neutral (0% expected return)
        """
        if 'error' in forecast_result or forecast_result.get('predictions') is None:
            return 0.5  # Neutral if forecast failed
        
        expected_return = forecast_result['expected_return']
        
        # Map: 0% return = 0.5, 5%+ return = 1.0, -5% return = 0.0
        # Linear scaling
        if expected_return >= 0:
            score = 0.5 + (min(expected_return / 0.05, 1.0) * 0.5)
        else:
            score = 0.5 + (max(expected_return / 0.05, -1.0) * 0.5)
        
        return float(score)


# Test code
if __name__ == '__main__':
    import yfinance as yf
    
    print("="*80)
    print("STATSFORECAST PREDICTOR TEST")
    print("="*80)
    
    # Test with L&T
    print("\nFetching L&T stock data...")
    ticker = yf.Ticker("LT.NS")
    data = ticker.history(period="6mo")
    
    if data.empty:
        print("ERROR: Could not fetch data")
        exit(1)
    
    prices = data['Close']
    print(f"Fetched {len(prices)} days of data")
    print(f"Current Price: Rs.{prices.iloc[-1]:.2f}")
    
    # Initialize predictor
    print("\nInitializing StatsForecast predictor...")
    predictor = StatsForecastPredictor()
    
    # Generate forecast
    print("\nGenerating 10-day forecast...")
    forecast = predictor.forecast_stock_price(prices, horizon=10)
    
    if 'error' in forecast:
        print(f"\nERROR: {forecast['error']}")
    else:
        print("\n" + "="*80)
        print("FORECAST RESULT")
        print("="*80)
        print(f"\nCurrent Price: Rs.{forecast['current_price']:.2f}")
        print(f"Predicted Price (10d): Rs.{forecast['predicted_price']:.2f}")
        print(f"Expected Return: {forecast['expected_return']*100:+.2f}%")
        print(f"Probability of Gain: {forecast['probability_gain']*100:.0f}%")
        print(f"Confidence Range: Rs.{forecast['confidence_range']:.2f}")
        
        print(f"\nDaily Predictions:")
        for i, (date, pred, low, high) in enumerate(zip(
            forecast['forecast_dates'],
            forecast['predictions'],
            forecast['confidence_low'],
            forecast['confidence_high']
        )):
            print(f"  Day {i+1} ({date}): Rs.{pred:.2f} (Range: {low:.2f} - {high:.2f})")
        
        # Test fusion score
        score = predictor.get_prediction_score(forecast)
        print(f"\nFusion Score: {score:.3f} (0=bearish, 0.5=neutral, 1=bullish)")

