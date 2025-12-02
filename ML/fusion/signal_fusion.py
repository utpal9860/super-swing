"""
Signal Fusion - Combine Pattern Detection + Sentiment + Price Prediction
Implements the multi-modal decision logic from the master plan
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional
from utils.logger import setup_logger

logger = setup_logger("signal_fusion")


@dataclass
class MultiModalSignal:
    """Container for all three signals combined"""
    ticker: str
    company_name: str
    date: str
    
    # Pattern Detection
    pattern_type: str
    pattern_quality: float  # 0-1
    pattern_win_rate: float
    pattern_score: float  # Normalized 0-1
    
    # Sentiment Analysis
    sentiment_raw: float  # -1 to +1
    sentiment_label: str
    sentiment_confidence: float
    sentiment_score: float  # Normalized 0-1
    num_articles: int
    
    # Price Prediction
    predicted_return: float
    prediction_confidence: float
    probability_gain: float
    prediction_score: float  # Normalized 0-1
    
    # Fusion Results
    final_confidence: float
    recommendation: str  # STRONG_BUY, BUY, WEAK_BUY, HOLD
    position_size_pct: float  # Recommended position size (%)
    
    # Trade Parameters
    entry_price: float
    stop_loss: float
    target_price: float
    risk_reward_ratio: float


class SignalFusion:
    """
    Combine all three signals into final trading decision
    """
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize fusion layer with weights
        
        Args:
            weights: Dict with 'pattern', 'sentiment', 'prediction' keys
                    Default: pattern=0.35, sentiment=0.25, prediction=0.40
        """
        # Default weights from master plan
        self.weights = weights or {
            'pattern': 0.35,
            'sentiment': 0.25,
            'prediction': 0.40
        }
        
        # Validate weights sum to 1.0
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Weights sum to {total:.3f}, normalizing...")
            for key in self.weights:
                self.weights[key] /= total
        
        logger.info(f"Signal Fusion initialized with weights: {self.weights}")
    
    def normalize_pattern_score(self, pattern_quality: float, win_rate: float) -> float:
        """
        Convert pattern metrics to 0-1 score
        
        Args:
            pattern_quality: Quality score from pattern detector (0-1)
            win_rate: Historical win rate (0-1)
        
        Returns:
            Normalized score combining quality and historical performance
        """
        # Combine quality (60%) and historical win rate (40%)
        score = (pattern_quality * 0.6) + (win_rate * 0.4)
        return float(np.clip(score, 0, 1))
    
    def normalize_sentiment_score(self, sentiment: float) -> float:
        """
        Convert sentiment (-1 to +1) to (0 to 1)
        
        Args:
            sentiment: Raw sentiment score (-1 to +1)
        
        Returns:
            Normalized score (0 to 1)
        """
        normalized = (sentiment + 1) / 2
        return float(np.clip(normalized, 0, 1))
    
    def normalize_prediction_score(self, predicted_return: float) -> float:
        """
        Convert predicted return to 0-1 score
        
        Args:
            predicted_return: Expected return as decimal (e.g., 0.045 for 4.5%)
        
        Returns:
            Normalized score where 0% = 0.5, 5%+ = 1.0, -5% = 0.0
        """
        # Map: 0% return = 0.5, ±5% return = 1.0 or 0.0
        if predicted_return >= 0:
            score = 0.5 + (min(predicted_return / 0.05, 1.0) * 0.5)
        else:
            score = 0.5 + (max(predicted_return / 0.05, -1.0) * 0.5)
        
        return float(np.clip(score, 0, 1))
    
    def calculate_confidence(self, pattern_score: float, sentiment_score: float, 
                           prediction_score: float) -> float:
        """
        Calculate final confidence using weighted average
        
        Example from master plan:
        - Pattern: 0.78
        - Sentiment: 0.84
        - Prediction: 0.72
        - Final = (0.78 × 0.35) + (0.84 × 0.25) + (0.72 × 0.40) = 0.771 = 77.1%
        
        Args:
            pattern_score: Normalized pattern score (0-1)
            sentiment_score: Normalized sentiment score (0-1)
            prediction_score: Normalized prediction score (0-1)
        
        Returns:
            Final confidence score (0-1)
        """
        confidence = (
            pattern_score * self.weights['pattern'] +
            sentiment_score * self.weights['sentiment'] +
            prediction_score * self.weights['prediction']
        )
        return float(confidence)
    
    def generate_recommendation(self, confidence: float, risk_reward_ratio: float, 
                               market_condition: Dict) -> str:
        """
        Apply decision rules from master plan
        
        Args:
            confidence: Final confidence score (0-1)
            risk_reward_ratio: Risk-reward ratio (e.g., 2.5 = 2.5:1)
            market_condition: Dict with market context
        
        Returns:
            'STRONG_BUY', 'BUY', 'WEAK_BUY', or 'HOLD'
        """
        # Gate checks first
        if not self._pass_gate_checks(market_condition):
            logger.info("Failed gate checks")
            return 'HOLD'
        
        # Decision logic from master plan
        if confidence >= 0.70 and risk_reward_ratio >= 2.0:
            return 'STRONG_BUY'
        elif confidence >= 0.60 and risk_reward_ratio >= 1.5:
            return 'BUY'
        elif confidence >= 0.55 and risk_reward_ratio >= 2.0:
            return 'WEAK_BUY'
        else:
            return 'HOLD'
    
    def calculate_position_size(self, recommendation: str, confidence: float) -> float:
        """
        Calculate recommended position size based on recommendation and confidence
        
        Args:
            recommendation: STRONG_BUY, BUY, WEAK_BUY, HOLD
            confidence: Final confidence score
        
        Returns:
            Position size as percentage (e.g., 2.5 for 2.5% of capital)
        """
        if recommendation == 'STRONG_BUY':
            # Full position: 2.5% risk per trade (from master plan)
            return 2.5
        elif recommendation == 'BUY':
            # 60-70% of normal: 1.5-1.75%
            return 1.5 + (confidence - 0.60) * 2.5
        elif recommendation == 'WEAK_BUY':
            # 40-50% of normal: 1.0-1.25%
            return 1.0 + (confidence - 0.55) * 5.0
        else:
            return 0.0
    
    def _pass_gate_checks(self, market_condition: Dict) -> bool:
        """
        Check all gate conditions from master plan
        
        Gate Checks:
        - Market not in strong downtrend (>5% down in 5 days)
        - VIX not too high (>25)
        - No major event risk
        
        Args:
            market_condition: Dict with market data
        
        Returns:
            True if all checks pass
        """
        # Market condition filter
        nifty_change = market_condition.get('nifty_change_5d', 0)
        if nifty_change < -0.05:  # >5% down
            logger.info(f"Gate check failed: Nifty down {nifty_change*100:.1f}% in 5 days")
            return False
        
        vix = market_condition.get('vix', 0)
        if vix > 25:  # High volatility
            logger.info(f"Gate check failed: VIX too high ({vix})")
            return False
        
        # Event risk check
        if market_condition.get('major_event_risk', False):
            logger.info("Gate check failed: Major event risk")
            return False
        
        return True
    
    def calculate_trade_levels(self, pattern_data: Dict, prediction_data: Dict, 
                              sentiment_data: Dict) -> Dict:
        """
        Calculate entry, stop loss, and target prices
        Handles both BULLISH and BEARISH patterns correctly
        
        Args:
            pattern_data: Pattern detection output
            prediction_data: Price prediction output
            sentiment_data: Sentiment analysis output
        
        Returns:
            Dict with entry, stop_loss, target, risk_reward_ratio
        """
        # Determine pattern direction from pattern_type (e.g., "CDLHAMMER_BULLISH")
        pattern_type = pattern_data.get('pattern_type', '')
        is_bullish = 'BULLISH' in pattern_type.upper()
        
        current_price = pattern_data.get('current_price', 0)
        support = pattern_data.get('support', current_price * 0.95)
        resistance = pattern_data.get('resistance', current_price * 1.05)
        
        # Get predicted price
        predicted_price = prediction_data.get('predicted_price', None)
        predicted_return = prediction_data.get('expected_return', 0)
        
        if is_bullish:
            # BULLISH PATTERN: Buy at resistance breakout
            entry = resistance * 1.002  # 0.2% above resistance
            stop_loss = support * 0.98  # 2% below support
            
            # Target: Use prediction if available, else pattern height projection
            if predicted_price and predicted_price > entry:
                target = predicted_price
            else:
                # Project pattern height above entry
                pattern_height = resistance - support
                target = entry + pattern_height * 1.0  # 1x pattern height
            
            # If sentiment very bullish, extend target
            sentiment_raw = sentiment_data.get('overall_sentiment', 0)
            if sentiment_raw > 0.8:
                target = target * 1.10  # +10% extension
            
            # Ensure minimum target (at least 3% gain)
            min_target = entry * 1.03
            target = max(target, min_target)
        
        else:
            # BEARISH PATTERN: Short at support breakdown
            entry = support * 0.998  # 0.2% below support
            stop_loss = resistance * 1.02  # 2% above resistance
            
            # Target: Use prediction if available, else pattern height projection
            if predicted_price and predicted_price < entry:
                target = predicted_price
            else:
                # Project pattern height below entry
                pattern_height = resistance - support
                target = entry - pattern_height * 1.0  # 1x pattern height
            
            # If sentiment very bearish, extend target
            sentiment_raw = sentiment_data.get('overall_sentiment', 0)
            if sentiment_raw < -0.8:
                target = target * 0.90  # -10% extension (more downside)
            
            # Ensure minimum target (at least 3% drop)
            max_target = entry * 0.97
            target = min(target, max_target)
        
        # Calculate risk-reward ratio
        risk = abs(entry - stop_loss)
        reward = abs(target - entry)
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        # Log the trade setup
        logger.info(f"Trade setup ({pattern_type}):")
        logger.info(f"  Direction: {'BULLISH (LONG)' if is_bullish else 'BEARISH (SHORT)'}")
        logger.info(f"  Entry: {entry:.2f}, SL: {stop_loss:.2f}, Target: {target:.2f}")
        logger.info(f"  R:R = {risk_reward_ratio:.2f}:1")
        
        return {
            'entry': float(entry),
            'stop_loss': float(stop_loss),
            'target': float(target),
            'risk_reward_ratio': float(risk_reward_ratio)
        }
    
    def fuse_signals(self, pattern_data: Dict, sentiment_data: Dict, 
                    prediction_data: Dict, market_data: Dict) -> MultiModalSignal:
        """
        Main fusion function - combines everything!
        
        This is where the magic happens!
        
        Args:
            pattern_data: Output from pattern detection
            sentiment_data: Output from sentiment analysis
            prediction_data: Output from price prediction
            market_data: Market context (Nifty, VIX, etc.)
        
        Returns:
            MultiModalSignal with complete analysis and recommendation
        """
        # Step 1: Normalize all scores to 0-1
        pattern_score = self.normalize_pattern_score(
            pattern_data.get('quality', 0.5),
            pattern_data.get('win_rate', 0.5)
        )
        
        sentiment_score = self.normalize_sentiment_score(
            sentiment_data.get('overall_sentiment', 0)
        )
        
        prediction_score = self.normalize_prediction_score(
            prediction_data.get('expected_return', 0)
        )
        
        logger.info(f"Normalized scores - Pattern: {pattern_score:.3f}, "
                   f"Sentiment: {sentiment_score:.3f}, Prediction: {prediction_score:.3f}")
        
        # Step 2: Calculate final confidence
        final_confidence = self.calculate_confidence(
            pattern_score,
            sentiment_score,
            prediction_score
        )
        
        logger.info(f"Final confidence: {final_confidence:.3f} ({final_confidence*100:.1f}%)")
        
        # Step 3: Calculate trade levels
        trade_levels = self.calculate_trade_levels(pattern_data, prediction_data, sentiment_data)
        
        # Step 4: Generate recommendation
        recommendation = self.generate_recommendation(
            final_confidence,
            trade_levels['risk_reward_ratio'],
            market_data
        )
        
        # Step 5: Calculate position size
        position_size = self.calculate_position_size(recommendation, final_confidence)
        
        logger.info(f"Recommendation: {recommendation} (Position size: {position_size:.2f}%)")
        
        # Step 6: Create signal object
        signal = MultiModalSignal(
            ticker=pattern_data['ticker'],
            company_name=pattern_data.get('company_name', pattern_data['ticker']),
            date=pattern_data.get('date', ''),
            
            # Pattern
            pattern_type=pattern_data['pattern_type'],
            pattern_quality=pattern_data.get('quality', 0.5),
            pattern_win_rate=pattern_data.get('win_rate', 0.5),
            pattern_score=pattern_score,
            
            # Sentiment
            sentiment_raw=sentiment_data.get('overall_sentiment', 0),
            sentiment_label=sentiment_data.get('sentiment_label', 'NEUTRAL'),
            sentiment_confidence=sentiment_data.get('confidence', 0.5),
            sentiment_score=sentiment_score,
            num_articles=sentiment_data.get('num_articles', 0),
            
            # Prediction
            predicted_return=prediction_data.get('expected_return', 0),
            prediction_confidence=prediction_data.get('probability_gain', 0.5),
            probability_gain=prediction_data.get('probability_gain', 0.5),
            prediction_score=prediction_score,
            
            # Fusion
            final_confidence=final_confidence,
            recommendation=recommendation,
            position_size_pct=position_size,
            
            # Trade levels
            entry_price=trade_levels['entry'],
            stop_loss=trade_levels['stop_loss'],
            target_price=trade_levels['target'],
            risk_reward_ratio=trade_levels['risk_reward_ratio']
        )
        
        return signal


# Test code
if __name__ == '__main__':
    # Test the fusion logic
    print("="*80)
    print("SIGNAL FUSION TEST")
    print("="*80)
    
    # Mock data for testing
    pattern_data = {
        'ticker': 'LT',
        'company_name': 'Larsen & Toubro',
        'date': '2025-10-31',
        'pattern_type': 'DOUBLE_BOTTOM',
        'quality': 0.78,
        'win_rate': 0.65,
        'current_price': 3565,
        'support': 3420,
        'resistance': 3580,
        'target': 3740
    }
    
    sentiment_data = {
        'overall_sentiment': 0.68,  # Bullish
        'sentiment_label': 'BULLISH',
        'confidence': 0.82,
        'num_articles': 12
    }
    
    prediction_data = {
        'expected_return': 0.042,  # 4.2%
        'predicted_price': 3730,
        'probability_gain': 0.72
    }
    
    market_data = {
        'nifty_change_5d': 0.012,  # +1.2%
        'vix': 15.5,
        'major_event_risk': False
    }
    
    # Create fusion instance
    fusion = SignalFusion()
    
    # Fuse signals
    signal = fusion.fuse_signals(
        pattern_data=pattern_data,
        sentiment_data=sentiment_data,
        prediction_data=prediction_data,
        market_data=market_data
    )
    
    # Display results
    print(f"\n{'='*80}")
    print("MULTI-MODAL SIGNAL")
    print(f"{'='*80}")
    print(f"\nStock: {signal.ticker} ({signal.company_name})")
    print(f"Pattern: {signal.pattern_type}")
    
    print(f"\n--- Individual Scores ---")
    print(f"Pattern Score:    {signal.pattern_score:.3f} (Quality: {signal.pattern_quality:.2f}, Win Rate: {signal.pattern_win_rate:.0f}%)")
    print(f"Sentiment Score:  {signal.sentiment_score:.3f} ({signal.sentiment_label}, {signal.num_articles} articles)")
    print(f"Prediction Score: {signal.prediction_score:.3f} (Expected: {signal.predicted_return*100:+.1f}%)")
    
    print(f"\n--- Fusion Result ---")
    print(f"Final Confidence: {signal.final_confidence:.3f} ({signal.final_confidence*100:.1f}%)")
    print(f"Recommendation:   {signal.recommendation}")
    print(f"Position Size:    {signal.position_size_pct:.2f}% of capital")
    
    print(f"\n--- Trade Levels ---")
    print(f"Entry:     Rs.{signal.entry_price:.2f}")
    print(f"Stop Loss: Rs.{signal.stop_loss:.2f} ({((signal.stop_loss-signal.entry_price)/signal.entry_price*100):.1f}%)")
    print(f"Target:    Rs.{signal.target_price:.2f} ({((signal.target_price-signal.entry_price)/signal.entry_price*100):.1f}%)")
    print(f"R:R Ratio: {signal.risk_reward_ratio:.2f}:1")
    
    print(f"\n{'='*80}")

