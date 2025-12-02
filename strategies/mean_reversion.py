"""
Mean Reversion Strategy

Strategy Logic:
1. Stock oversold (RSI < 30, Bollinger Band lower touch)
2. Quality stock in long-term uptrend (above 200 SMA)
3. Recent sharp selloff (-5% to -15% in 1-5 days)
4. Volume spike on selloff (panic selling)
5. Entry: On first green candle after selloff
6. Stop loss: Below recent low or -5%
7. Target: Mean (20 SMA) or +5-10%

Win Rate: ~65-70%
R:R: 1:1.5 to 1:2
Holding Period: 2-7 days
"""

import sys
from pathlib import Path
from typing import List, Dict
import pandas as pd
import numpy as np
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategies.base_strategy import BaseStrategy, Signal
from utils.position_sizing import calculate_position_size, calculate_risk_reward


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Trading Strategy
    
    Short-term bounce trades in quality oversold stocks.
    """
    
    def __init__(self):
        super().__init__(
            name="mean_reversion",
            description="2-7 day oversold bounce trades in quality stocks"
        )
        
        # Strategy parameters
        self.sma_short = 20
        self.sma_long = 200
        self.rsi_period = 14
        self.bb_period = 20
        self.bb_std = 2.0
        self.volume_period = 20
        
        # Entry criteria
        self.max_rsi = 30  # Oversold threshold
        self.min_selloff_pct = 5.0  # Minimum 5% selloff
        self.max_selloff_pct = 15.0  # Maximum 15% selloff
        self.min_volume_ratio = 1.5  # Volume spike confirmation
        
        # Risk management
        self.default_sl_pct = 5.0  # 5% stop loss
        self.min_target_pct = 5.0  # 5% minimum target
        self.max_target_pct = 10.0  # 10% maximum target
    
    def scan(self, symbols: List[str], capital: float = 100000, silent: bool = False, **kwargs) -> List[Signal]:
        """
        Scan symbols for mean reversion setups
        
        Args:
            symbols: List of stock symbols
            capital: Trading capital for position sizing
            silent: If True, suppress console output
            **kwargs: Additional parameters
        
        Returns:
            List of valid signals
        """
        self.signals = []
        
        if not silent:
            print(f"\n{'='*60}")
            print(f"Scanning {len(symbols)} stocks for Mean Reversion signals...")
            print(f"{'='*60}\n")
        
        for i, symbol in enumerate(symbols, 1):
            if not silent and i % 50 == 0:
                print(f"Progress: {i}/{len(symbols)} stocks scanned...")
            
            try:
                df = self.fetch_data(symbol, period="1y", interval="1d")
                
                if df is None or len(df) < self.sma_long + 10:
                    continue
                
                # Check if signal is valid
                if self.validate_signal(df):
                    signal = self._create_signal(df, symbol, capital)
                    if signal:
                        self.signals.append(signal)
                        if not silent:
                            print(f"✅ Signal found: {symbol} - Score: {signal.quality_score:.1f}/10")
            
            except Exception as e:
                if not silent:
                    print(f"Error scanning {symbol}: {e}")
                continue
        
        if not silent:
            print(f"\n{'='*60}")
            print(f"Scan complete: {len(self.signals)} signals found")
            print(f"{'='*60}\n")
        
        return self.signals
    
    def validate_signal(self, df: pd.DataFrame) -> bool:
        """
        Validate if current data meets mean reversion criteria
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            True if valid oversold bounce setup
        """
        try:
            # Calculate indicators
            sma_20 = self.calculate_sma(df, self.sma_short)
            sma_200 = self.calculate_sma(df, self.sma_long)
            rsi = self.calculate_rsi(df, self.rsi_period)
            
            current_price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-2]
            current_sma_200 = sma_200.iloc[-1]
            
            # 1. Long-term uptrend (price above 200 SMA)
            if current_price < current_sma_200:
                return False
            
            # 2. RSI oversold (< 30)
            if rsi > self.max_rsi:
                return False
            
            # 3. Recent selloff (5-15% decline in last 5 days)
            recent_high = df['high'].iloc[-5:].max()
            selloff_pct = ((current_price - recent_high) / recent_high) * 100
            
            if selloff_pct > -self.min_selloff_pct or selloff_pct < -self.max_selloff_pct:
                return False
            
            # 4. Bollinger Band lower touch
            try:
                bb_df = self.calculate_bollinger_bands(df, period=self.bb_period, std_dev=self.bb_std)
                bb_lower = bb_df['bb_lower'].iloc[-1]
                
                if current_price > bb_lower * 1.02:  # Allow 2% above lower band
                    return False
            except:
                pass  # BB not critical
            
            # 5. Volume spike (panic selling confirmation)
            volume_ratio = self.calculate_volume_ratio(df, self.volume_period)
            if volume_ratio < self.min_volume_ratio:
                return False
            
            # 6. First green candle (reversal confirmation)
            if current_price <= prev_price:
                return False
            
            # 7. Check for bullish candlestick pattern (optional)
            try:
                body_size = abs(current_price - df['open'].iloc[-1])
                candle_range = df['high'].iloc[-1] - df['low'].iloc[-1]
                
                # Strong bullish candle (body > 50% of range)
                if body_size < candle_range * 0.5:
                    return False
            except:
                pass
            
            return True
            
        except Exception as e:
            return False
    
    def calculate_targets(self, df: pd.DataFrame, entry_price: float) -> Dict:
        """
        Calculate stop loss and target prices
        
        Args:
            df: DataFrame with OHLCV data
            entry_price: Entry price
        
        Returns:
            Dict with stop_loss and target prices
        """
        # Stop loss: Below recent low with buffer
        recent_low = df['low'].iloc[-5:].min()
        stop_loss = recent_low * 0.98  # 2% below recent low
        
        # Ensure SL not too wide
        max_sl = entry_price * (1 - self.default_sl_pct / 100)
        stop_loss = max(stop_loss, max_sl)
        
        # Target: Mean (20 SMA)
        sma_20 = self.calculate_sma(df, self.sma_short).iloc[-1]
        
        # If SMA is above entry, use it as target
        if sma_20 > entry_price:
            target = sma_20
        else:
            # Otherwise, use fixed % target
            target = entry_price * (1 + self.min_target_pct / 100)
        
        # Cap target at max %
        max_target = entry_price * (1 + self.max_target_pct / 100)
        target = min(target, max_target)
        
        # Ensure minimum R:R of 1.5:1
        risk = entry_price - stop_loss
        min_target = entry_price + (risk * 1.5)
        target = max(target, min_target)
        
        return {
            'stop_loss': float(stop_loss),
            'target': float(target)
        }
    
    def _create_signal(self, df: pd.DataFrame, symbol: str, capital: float) -> Signal:
        """
        Create a signal object with all details
        
        Args:
            df: DataFrame with OHLCV data
            symbol: Stock symbol
            capital: Trading capital
        
        Returns:
            Signal object or None
        """
        entry_price = float(df['close'].iloc[-1])
        targets = self.calculate_targets(df, entry_price)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(df, entry_price, targets)
        
        # Calculate position sizing
        pos_size = calculate_position_size(
            capital=capital,
            risk_pct=2.0,
            entry_price=entry_price,
            stop_loss=targets['stop_loss']
        )
        
        if not pos_size:
            return None
        
        # Calculate R:R
        rr = calculate_risk_reward(
            entry_price=entry_price,
            stop_loss=targets['stop_loss'],
            target=targets['target']
        )
        
        # Additional metrics
        try:
            rsi = self.calculate_rsi(df, self.rsi_period)
            volume_ratio = self.calculate_volume_ratio(df, self.volume_period)
            atr = self.calculate_atr(df, period=14)
        except:
            rsi = 25
            volume_ratio = 1.5
            atr = entry_price * 0.02
        
        signal = Signal(
            symbol=symbol,
            date=datetime.now().strftime('%Y-%m-%d'),
            entry_price=entry_price,
            stop_loss=targets['stop_loss'],
            target=targets['target'],
            signal_type='BUY',
            strategy_name=self.name,
            quality_score=quality_score,
            confidence=quality_score / 10.0,
            notes=f"Oversold bounce setup. R:R {rr['risk_reward_ratio']:.1f}:1",
            rsi=rsi,
            volume_ratio=volume_ratio,
            atr=atr,
            shares=pos_size['shares'],
            position_value=pos_size['position_value'],
            risk_amount=pos_size['risk_amount']
        )
        
        return signal
    
    def _calculate_quality_score(self, df: pd.DataFrame, entry: float, targets: Dict) -> float:
        """
        Calculate quality score (1-10) for the signal
        
        Higher score = Better setup
        
        Scoring factors:
        - RSI oversold level
        - Selloff magnitude
        - Volume spike intensity
        - Distance from 200 SMA
        - R:R ratio
        """
        score = 5.0  # Base score
        
        try:
            # 1. RSI oversold level (max +2 points)
            rsi = self.calculate_rsi(df, self.rsi_period)
            if rsi < 20:
                score += 2
            elif rsi < 25:
                score += 1.5
            elif rsi < 30:
                score += 1
            
            # 2. Selloff magnitude (max +2 points)
            recent_high = df['high'].iloc[-5:].max()
            selloff_pct = abs(((entry - recent_high) / recent_high) * 100)
            
            if selloff_pct > 12:
                score += 2
            elif selloff_pct > 8:
                score += 1.5
            elif selloff_pct > 5:
                score += 1
            
            # 3. Volume spike (max +2 points)
            volume_ratio = self.calculate_volume_ratio(df, self.volume_period)
            if volume_ratio >= 2.5:
                score += 2
            elif volume_ratio >= 2.0:
                score += 1.5
            elif volume_ratio >= 1.5:
                score += 1
            
            # 4. Distance above 200 SMA (max +2 points)
            # Closer to 200 SMA in downtrend = more risky
            sma_200 = self.calculate_sma(df, self.sma_long).iloc[-1]
            distance_from_200 = ((entry - sma_200) / sma_200) * 100
            
            if distance_from_200 > 20:
                score += 2
            elif distance_from_200 > 10:
                score += 1.5
            elif distance_from_200 > 5:
                score += 1
            
            # 5. R:R ratio (max +1 point)
            rr = calculate_risk_reward(entry, targets['stop_loss'], targets['target'])
            if rr['risk_reward_ratio'] >= 2.0:
                score += 1
            elif rr['risk_reward_ratio'] >= 1.5:
                score += 0.5
            
            # Cap score at 10
            score = min(score, 10.0)
        
        except Exception as e:
            score = 6.0  # Default score if calculation fails
        
        return round(score, 1)


if __name__ == "__main__":
    # CLI testing
    strategy = MeanReversionStrategy()
    symbols = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS']
    
    signals = strategy.scan(symbols, capital=100000)
    
    if signals:
        strategy.save_signals('mean_reversion_opportunities.csv')
        summary = strategy.get_signal_summary()
        print(f"\nStrategy: {summary['description']}")
        print(f"Signals found: {summary['count']}")
        print(f"Average score: {summary['avg_score']:.1f}/10")
    else:
        print("\nNo signals found matching criteria")











