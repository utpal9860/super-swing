"""
Pullback Entry Strategy

Strategy Logic:
1. Stock must be in uptrend (above 50-day SMA)
2. Pulls back to 20-day SMA (not breaking it)
3. RSI between 40-60 (not oversold, just resting)
4. Entry when price bounces off 20 SMA with volume spike
5. Stop loss below 20-day SMA (~5-6%)
6. Target at previous high + buffer

Win Rate: ~60-65% (higher than breakout strategies)
R:R: 1:2 to 1:2.5
Holding Period: 5-30 days
"""

import sys
from pathlib import Path
from typing import List, Dict
import pandas as pd
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategies.base_strategy import BaseStrategy, Signal
from utils.position_sizing import calculate_position_size, calculate_risk_reward


class PullbackEntryStrategy(BaseStrategy):
    """
    Pullback Entry Trading Strategy
    
    Enters on pullbacks in uptrending stocks.
    Higher win rate than breakout strategies.
    """
    
    def __init__(self):
        super().__init__(
            name="pullback_entry",
            description="Enter on pullbacks to 20-day SMA in uptrending stocks"
        )
        
        # Strategy parameters
        self.long_sma_period = 50  # Trend filter
        self.short_sma_period = 20  # Entry level
        self.rsi_period = 14
        self.volume_lookback = 20
        
        # Entry criteria
        self.min_rsi = 40
        self.max_rsi = 60
        self.min_volume_ratio = 1.2  # Volume should be 20% above average
        self.max_distance_from_sma = 3.0  # Max 3% from 20 SMA
        
        # Risk management
        self.sl_buffer = 1.02  # SL 2% below 20 SMA
        self.target_multiplier = 1.10  # Target at previous high + 10%
    
    def scan(self, symbols: List[str], capital: float = 100000, silent: bool = False, **kwargs) -> List[Signal]:
        """
        Scan symbols for pullback entry setups
        
        Args:
            symbols: List of stock symbols
            capital: Trading capital for position sizing
            silent: If True, suppress console output (for API usage)
            **kwargs: Additional parameters
        
        Returns:
            List of valid signals
        """
        self.signals = []
        
        if not silent:
            print(f"\n{'='*60}")
            print(f"Scanning {len(symbols)} stocks for Pullback Entry signals...")
            print(f"{'='*60}\n")
        
        for i, symbol in enumerate(symbols, 1):
            if not silent and i % 50 == 0:
                print(f"Progress: {i}/{len(symbols)} stocks scanned...")
            
            try:
                df = self.fetch_data(symbol, period="6mo", interval="1d")
                
                if df is None or len(df) < self.long_sma_period + 10:
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
        Validate if current data meets pullback entry criteria
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            True if valid pullback setup
        """
        # Calculate indicators
        sma_50 = self.calculate_sma(df, self.long_sma_period)
        sma_20 = self.calculate_sma(df, self.short_sma_period)
        
        current_price = df['close'].iloc[-1]
        current_sma_20 = sma_20.iloc[-1]
        current_sma_50 = sma_50.iloc[-1]
        
        # 1. Must be in uptrend (price above 50 SMA)
        if current_price < current_sma_50:
            return False
        
        # 2. Must be near 20 SMA (pullback zone)
        distance_from_sma = abs(current_price - current_sma_20) / current_sma_20 * 100
        if distance_from_sma > self.max_distance_from_sma:
            return False
        
        # 3. Price should be above 20 SMA or touching it (not below)
        if current_price < current_sma_20 * 0.98:  # Allow 2% below
            return False
        
        # 4. RSI should be in healthy range (not oversold)
        try:
            rsi = self.calculate_rsi(df, self.rsi_period)
            if rsi < self.min_rsi or rsi > self.max_rsi:
                return False
        except:
            return False
        
        # 5. Volume should show interest (bounce confirmation)
        volume_ratio = self.calculate_volume_ratio(df, self.volume_lookback)
        if volume_ratio < self.min_volume_ratio:
            return False
        
        # 6. Check if there was a recent pullback (price was higher in last 10 days)
        recent_high = self.get_recent_high(df, period=10)
        if recent_high < current_price * 1.03:  # Need at least 3% pullback
            return False
        
        # 7. 20 SMA should be above 50 SMA (uptrend confirmation)
        if current_sma_20 < current_sma_50:
            return False
        
        return True
    
    def calculate_targets(self, df: pd.DataFrame, entry_price: float) -> Dict:
        """
        Calculate stop loss and target prices
        
        Args:
            df: DataFrame with OHLCV data
            entry_price: Entry price
        
        Returns:
            Dict with stop_loss and target prices
        """
        # Stop loss: Below 20-day SMA with buffer
        sma_20 = self.calculate_sma(df, self.short_sma_period).iloc[-1]
        stop_loss = sma_20 / self.sl_buffer  # 2% below SMA
        
        # Ensure SL is at least 5% below entry (not too tight)
        min_sl = entry_price * 0.95
        stop_loss = min(stop_loss, min_sl)
        
        # Ensure SL is not more than 8% below entry (too wide)
        max_sl = entry_price * 0.92
        stop_loss = max(stop_loss, max_sl)
        
        # Target: Previous high + 10%
        previous_high = self.get_recent_high(df, period=20)
        target = previous_high * self.target_multiplier
        
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
            volume_ratio = self.calculate_volume_ratio(df, self.volume_lookback)
            atr = self.calculate_atr(df, period=14)
        except:
            rsi = 50
            volume_ratio = 1.0
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
            notes=f"Pullback to 20 SMA in uptrend. R:R {rr['risk_reward_ratio']:.1f}:1",
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
        - Trend strength (20 vs 50 SMA)
        - Volume confirmation
        - RSI level
        - R:R ratio
        - Distance from 20 SMA
        """
        score = 5.0  # Base score
        
        try:
            # 1. Trend strength (max +2 points)
            sma_20 = self.calculate_sma(df, self.short_sma_period).iloc[-1]
            sma_50 = self.calculate_sma(df, self.long_sma_period).iloc[-1]
            trend_strength = (sma_20 - sma_50) / sma_50 * 100
            if trend_strength > 5:
                score += 2
            elif trend_strength > 2:
                score += 1
            
            # 2. Volume confirmation (max +2 points)
            volume_ratio = self.calculate_volume_ratio(df, self.volume_lookback)
            if volume_ratio > 2.0:
                score += 2
            elif volume_ratio > 1.5:
                score += 1
            
            # 3. RSI level (max +1 point)
            rsi = self.calculate_rsi(df, self.rsi_period)
            if 45 <= rsi <= 55:  # Sweet spot
                score += 1
            elif 40 <= rsi <= 60:
                score += 0.5
            
            # 4. R:R ratio (max +2 points)
            rr = calculate_risk_reward(entry, targets['stop_loss'], targets['target'])
            if rr['risk_reward_ratio'] >= 2.5:
                score += 2
            elif rr['risk_reward_ratio'] >= 2.0:
                score += 1
            
            # 5. Distance from SMA (max +1 point)
            # Closer to SMA = better entry
            distance = abs(entry - sma_20) / sma_20 * 100
            if distance < 1.0:
                score += 1
            elif distance < 2.0:
                score += 0.5
            
            # Cap score at 10
            score = min(score, 10.0)
        
        except Exception as e:
            print(f"Error calculating quality score: {e}")
            score = 6.0  # Default score if calculation fails
        
        return round(score, 1)


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Pullback Entry Strategy Scanner')
    parser.add_argument('--symbols', nargs='+', help='Symbols to scan')
    parser.add_argument('--watchlist', type=str, help='Path to watchlist CSV file')
    parser.add_argument('--capital', type=float, default=100000, help='Trading capital')
    parser.add_argument('--output', type=str, default='pullback_opportunities.csv', help='Output filename')
    
    args = parser.args()
    
    # Get symbols
    if args.watchlist:
        import pandas as pd
        df = pd.read_csv(args.watchlist)
        symbols = df['symbol'].tolist() if 'symbol' in df.columns else df.iloc[:, 0].tolist()
    elif args.symbols:
        symbols = args.symbols
    else:
        # Default to some popular stocks for testing
        symbols = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS']
    
    # Run scanner
    strategy = PullbackEntryStrategy()
    signals = strategy.scan(symbols, capital=args.capital)
    
    # Save results
    if signals:
        strategy.save_signals(args.output)
        
        # Print summary
        summary = strategy.get_signal_summary()
        print(f"\nStrategy: {summary['description']}")
        print(f"Signals found: {summary['count']}")
        print(f"Average score: {summary['avg_score']:.1f}/10")
    else:
        print("\nNo signals found matching criteria")

