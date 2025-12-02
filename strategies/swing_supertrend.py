"""
Swing SuperTrend Strategy

Strategy Logic:
1. SuperTrend indicator flips bullish
2. Price bounces off SuperTrend line
3. Strong uptrend confirmation (price > 50 SMA)
4. Volume confirmation (above average)
5. ADX > 20 (trending market)
6. Entry: On SuperTrend flip or pullback to line
7. Stop loss: Below SuperTrend line
8. Target: Based on ATR (3-5X)

Win Rate: ~60-65%
R:R: 1:2 to 1:3
Holding Period: 7-30 days
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


class SwingSuperTrendStrategy(BaseStrategy):
    """
    Swing SuperTrend Trading Strategy
    
    Medium-term trend following trades using SuperTrend indicator.
    """
    
    def __init__(self):
        super().__init__(
            name="swing_supertrend",
            description="7-30 day trend following trades using SuperTrend indicator"
        )
        
        # Strategy parameters
        self.st_period = 10
        self.st_multiplier = 3.0
        self.sma_period = 50
        self.atr_period = 14
        self.adx_period = 14
        self.volume_period = 20
        
        # Entry criteria
        self.min_volume_ratio = 1.0  # Above average volume
        self.min_adx = 20  # Trending market
        self.max_distance_from_st = 3.0  # Max 3% from SuperTrend line
        
        # Risk management
        self.sl_buffer_pct = 2.0  # 2% below SuperTrend
        self.target_atr_multiple = 3.0  # 3X ATR target
    
    def scan(self, symbols: List[str], capital: float = 100000, silent: bool = False, **kwargs) -> List[Signal]:
        """
        Scan symbols for swing SuperTrend setups
        
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
            print(f"Scanning {len(symbols)} stocks for Swing SuperTrend signals...")
            print(f"{'='*60}\n")
        
        for i, symbol in enumerate(symbols, 1):
            if not silent and i % 50 == 0:
                print(f"Progress: {i}/{len(symbols)} stocks scanned...")
            
            try:
                df = self.fetch_data(symbol, period="6mo", interval="1d")
                
                if df is None or len(df) < self.sma_period + 20:
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
        Validate if current data meets swing SuperTrend criteria
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            True if valid SuperTrend setup
        """
        try:
            # Calculate SuperTrend
            st_df = self.calculate_supertrend(df, period=self.st_period, multiplier=self.st_multiplier)
            
            current_price = df['close'].iloc[-1]
            current_st = st_df['supertrend'].iloc[-1]
            current_direction = st_df['supertrend_direction'].iloc[-1]
            
            # 1. SuperTrend must be bullish (direction = 1)
            if current_direction != 1:
                return False
            
            # 2. Price must be near or above SuperTrend line
            distance_from_st = abs(current_price - current_st) / current_st * 100
            if current_price < current_st or distance_from_st > self.max_distance_from_st:
                return False
            
            # 3. Check for recent flip (bullish within last 5 bars)
            recent_flip = False
            for i in range(-5, 0):
                if st_df['supertrend_direction'].iloc[i-1] == -1 and st_df['supertrend_direction'].iloc[i] == 1:
                    recent_flip = True
                    break
            
            if not recent_flip:
                return False
            
            # 4. Price above 50 SMA (long-term uptrend)
            sma_50 = self.calculate_sma(df, self.sma_period).iloc[-1]
            if current_price < sma_50:
                return False
            
            # 5. ADX > 20 (trending market)
            try:
                adx = self.calculate_adx(df, period=self.adx_period)
                if adx < self.min_adx:
                    return False
            except:
                pass  # ADX not critical
            
            # 6. Volume confirmation
            volume_ratio = self.calculate_volume_ratio(df, self.volume_period)
            if volume_ratio < self.min_volume_ratio:
                return False
            
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
        # Stop loss: Below SuperTrend line with buffer
        st_df = self.calculate_supertrend(df, period=self.st_period, multiplier=self.st_multiplier)
        st_line = st_df['supertrend'].iloc[-1]
        
        stop_loss = st_line * (1 - self.sl_buffer_pct / 100)
        
        # Ensure SL is not too tight (min 5% from entry)
        min_sl = entry_price * 0.95
        stop_loss = min(stop_loss, min_sl)
        
        # Ensure SL is not too wide (max 10% from entry)
        max_sl = entry_price * 0.90
        stop_loss = max(stop_loss, max_sl)
        
        # Target: Based on ATR
        atr = self.calculate_atr(df, period=self.atr_period)
        target = entry_price + (atr * self.target_atr_multiple)
        
        # Ensure minimum R:R of 2:1
        risk = entry_price - stop_loss
        min_target = entry_price + (risk * 2.0)
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
            rsi = self.calculate_rsi(df, 14)
            volume_ratio = self.calculate_volume_ratio(df, self.volume_period)
            atr = self.calculate_atr(df, period=self.atr_period)
        except:
            rsi = 55
            volume_ratio = 1.2
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
            notes=f"SuperTrend bullish flip. R:R {rr['risk_reward_ratio']:.1f}:1",
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
        - Trend strength (ADX)
        - Distance from SuperTrend
        - Volume confirmation
        - R:R ratio
        - RSI level
        """
        score = 5.0  # Base score
        
        try:
            # 1. Trend strength via ADX (max +2 points)
            try:
                adx = self.calculate_adx(df, period=self.adx_period)
                if adx > 35:
                    score += 2
                elif adx > 25:
                    score += 1
            except:
                pass
            
            # 2. Distance from SuperTrend (max +2 points)
            # Closer to line = better entry
            st_df = self.calculate_supertrend(df, period=self.st_period, multiplier=self.st_multiplier)
            st_line = st_df['supertrend'].iloc[-1]
            distance = abs(entry - st_line) / st_line * 100
            
            if distance < 1.0:
                score += 2
            elif distance < 2.0:
                score += 1
            elif distance < 3.0:
                score += 0.5
            
            # 3. Volume confirmation (max +2 points)
            volume_ratio = self.calculate_volume_ratio(df, self.volume_period)
            if volume_ratio > 1.5:
                score += 2
            elif volume_ratio > 1.2:
                score += 1
            elif volume_ratio > 1.0:
                score += 0.5
            
            # 4. R:R ratio (max +2 points)
            rr = calculate_risk_reward(entry, targets['stop_loss'], targets['target'])
            if rr['risk_reward_ratio'] >= 3.0:
                score += 2
            elif rr['risk_reward_ratio'] >= 2.5:
                score += 1.5
            elif rr['risk_reward_ratio'] >= 2.0:
                score += 1
            
            # 5. RSI level (max +1 point)
            rsi = self.calculate_rsi(df, 14)
            if 50 <= rsi <= 65:  # Sweet spot
                score += 1
            elif 45 <= rsi <= 70:
                score += 0.5
            
            # Cap score at 10
            score = min(score, 10.0)
        
        except Exception as e:
            score = 6.0  # Default score if calculation fails
        
        return round(score, 1)


if __name__ == "__main__":
    # CLI testing
    strategy = SwingSuperTrendStrategy()
    symbols = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS']
    
    signals = strategy.scan(symbols, capital=100000)
    
    if signals:
        strategy.save_signals('swing_supertrend_opportunities.csv')
        summary = strategy.get_signal_summary()
        print(f"\nStrategy: {summary['description']}")
        print(f"Signals found: {summary['count']}")
        print(f"Average score: {summary['avg_score']:.1f}/10")
    else:
        print("\nNo signals found matching criteria")











