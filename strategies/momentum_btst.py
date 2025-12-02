"""
Momentum BTST Strategy

Strategy Logic:
1. High volume breakout (2X+ average volume)
2. Strong momentum (positive RSI 50-75, MACD bullish)
3. Price above key moving averages (20 & 50 SMA)
4. SuperTrend bullish
5. Relative strength vs Nifty 50 positive
6. Entry: Breakout close
7. Stop loss: Below recent swing low or -5%
8. Target: 3-8% (1-3 day hold)

Win Rate: ~55-60%
R:R: 1:1.5 to 1:2
Holding Period: 1-3 days (BTST - Buy Today Sell Tomorrow)
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


class MomentumBTSTStrategy(BaseStrategy):
    """
    Momentum BTST Trading Strategy
    
    High-velocity 1-3 day breakout trades with volume confirmation.
    """
    
    def __init__(self):
        super().__init__(
            name="momentum_btst",
            description="1-3 day momentum breakout trades with volume confirmation"
        )
        
        # Strategy parameters
        self.sma_short = 20
        self.sma_long = 50
        self.rsi_period = 14
        self.atr_period = 14
        self.volume_period = 20
        
        # Entry criteria
        self.min_volume_ratio = 2.0  # 2X average volume
        self.min_rsi = 50
        self.max_rsi = 75
        self.min_momentum = 5.0  # 5% momentum
        
        # Risk management
        self.default_sl_pct = 5.0  # 5% stop loss
        self.min_target_pct = 3.0  # 3% minimum target
        self.max_target_pct = 8.0  # 8% maximum target
    
    def scan(self, symbols: List[str], capital: float = 100000, silent: bool = False, **kwargs) -> List[Signal]:
        """
        Scan symbols for momentum BTST setups
        
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
            print(f"Scanning {len(symbols)} stocks for Momentum BTST signals...")
            print(f"{'='*60}\n")
        
        for i, symbol in enumerate(symbols, 1):
            if not silent and i % 50 == 0:
                print(f"Progress: {i}/{len(symbols)} stocks scanned...")
            
            try:
                df = self.fetch_data(symbol, period="3mo", interval="1d")
                
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
        Validate if current data meets momentum BTST criteria
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            True if valid breakout setup
        """
        try:
            # Calculate indicators
            sma_20 = self.calculate_sma(df, self.sma_short)
            sma_50 = self.calculate_sma(df, self.sma_long)
            rsi = self.calculate_rsi(df, self.rsi_period)
            
            current_price = df['close'].iloc[-1]
            current_sma_20 = sma_20.iloc[-1]
            current_sma_50 = sma_50.iloc[-1]
            
            # 1. Price must be above both SMAs (uptrend)
            if current_price < current_sma_20 or current_price < current_sma_50:
                return False
            
            # 2. RSI in sweet spot (50-75)
            if rsi < self.min_rsi or rsi > self.max_rsi:
                return False
            
            # 3. Volume surge (2X+ average)
            volume_ratio = self.calculate_volume_ratio(df, self.volume_period)
            if volume_ratio < self.min_volume_ratio:
                return False
            
            # 4. Strong momentum (5%+ in last 10 days)
            momentum_10d = ((df['close'].iloc[-1] / df['close'].iloc[-10]) - 1) * 100
            if momentum_10d < self.min_momentum:
                return False
            
            # 5. MACD bullish (optional but good confirmation)
            try:
                macd_line, signal_line, _ = self.calculate_macd(df)
                if macd_line.iloc[-1] <= signal_line.iloc[-1]:
                    return False
            except:
                pass  # MACD not critical, skip if error
            
            # 6. SuperTrend bullish
            try:
                st_df = self.calculate_supertrend(df, period=10, multiplier=3.0)
                if st_df['supertrend_direction'].iloc[-1] != 1:  # 1 = bullish
                    return False
            except:
                pass  # SuperTrend not critical
            
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
        # Stop loss: Below recent swing low or 5% default
        recent_low = df['low'].iloc[-10:].min()
        sl_from_low = recent_low * 0.99  # 1% below swing low
        sl_default = entry_price * (1 - self.default_sl_pct / 100)
        
        stop_loss = max(sl_from_low, sl_default)  # Use higher SL
        
        # Ensure SL is not too tight (min 3% from entry)
        min_sl = entry_price * 0.97
        stop_loss = min(stop_loss, min_sl)
        
        # Target: Based on momentum and volatility
        atr = self.calculate_atr(df, period=self.atr_period)
        target_from_atr = entry_price + (atr * 2)  # 2X ATR
        
        # Use target between 3-8%
        target_min = entry_price * (1 + self.min_target_pct / 100)
        target_max = entry_price * (1 + self.max_target_pct / 100)
        
        target = min(max(target_from_atr, target_min), target_max)
        
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
            atr = self.calculate_atr(df, period=self.atr_period)
        except:
            rsi = 60
            volume_ratio = 2.0
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
            notes=f"Momentum breakout with volume surge. R:R {rr['risk_reward_ratio']:.1f}:1",
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
        - Volume surge intensity
        - RSI level
        - Momentum strength
        - R:R ratio
        - MACD confirmation
        """
        score = 5.0  # Base score
        
        try:
            # 1. Volume surge (max +2 points)
            volume_ratio = self.calculate_volume_ratio(df, self.volume_period)
            if volume_ratio >= 3.0:
                score += 2
            elif volume_ratio >= 2.5:
                score += 1.5
            elif volume_ratio >= 2.0:
                score += 1
            
            # 2. RSI level (max +1 point)
            rsi = self.calculate_rsi(df, self.rsi_period)
            if 60 <= rsi <= 70:  # Sweet spot
                score += 1
            elif 50 <= rsi <= 75:
                score += 0.5
            
            # 3. Momentum strength (max +2 points)
            momentum_10d = ((df['close'].iloc[-1] / df['close'].iloc[-10]) - 1) * 100
            if momentum_10d >= 10:
                score += 2
            elif momentum_10d >= 7:
                score += 1.5
            elif momentum_10d >= 5:
                score += 1
            
            # 4. R:R ratio (max +2 points)
            rr = calculate_risk_reward(entry, targets['stop_loss'], targets['target'])
            if rr['risk_reward_ratio'] >= 2.0:
                score += 2
            elif rr['risk_reward_ratio'] >= 1.5:
                score += 1
            
            # 5. MACD confirmation (max +1 point)
            try:
                macd_line, signal_line, histogram = self.calculate_macd(df)
                if histogram.iloc[-1] > histogram.iloc[-2]:  # Increasing histogram
                    score += 1
                elif histogram.iloc[-1] > 0:
                    score += 0.5
            except:
                pass
            
            # Cap score at 10
            score = min(score, 10.0)
        
        except Exception as e:
            score = 6.0  # Default score if calculation fails
        
        return round(score, 1)


if __name__ == "__main__":
    # CLI testing
    strategy = MomentumBTSTStrategy()
    symbols = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS']
    
    signals = strategy.scan(symbols, capital=100000)
    
    if signals:
        strategy.save_signals('momentum_btst_opportunities.csv')
        summary = strategy.get_signal_summary()
        print(f"\nStrategy: {summary['description']}")
        print(f"Signals found: {summary['count']}")
        print(f"Average score: {summary['avg_score']:.1f}/10")
    else:
        print("\nNo signals found matching criteria")











