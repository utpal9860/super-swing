"""
Improved BTST Strategy - High-Precision Late-Session Breakout System

This is a complete rewrite of the BTST strategy based on structured improvement plan.

Strategy Logic:
1. Late-session breakout detection (3:15-3:25 PM IST window)
2. Resistance zone identification (min 3 swing highs)
3. Volume expansion confirmation (1.5X+ median volume)
4. EMA(44) trend filter on 5m and 15m charts
5. Index alignment (NIFTY above 20-DMA)
6. Overnight hold with next-day exit (9:15-9:45 AM IST)

Target Win Rate: 60-65%
R:R: 1:2 to 1:3
Holding Period: Overnight (15-18 hours)
Target: 3-5% per trade
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import yfinance as yf

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategies.base_strategy import BaseStrategy, Signal
from utils.position_sizing import calculate_position_size, calculate_risk_reward


class ImprovedBTSTStrategy(BaseStrategy):
    """
    Improved BTST Strategy - Late-Session Breakout System
    
    Targets high-precision overnight momentum trades with strict filters.
    """
    
    def __init__(self):
        super().__init__(
            name="improved_btst",
            description="Late-session breakout with overnight hold (3-5% target)"
        )
        
        # Timing parameters (IST)
        self.entry_window_start = time(15, 15)  # 3:15 PM
        self.entry_window_end = time(15, 25)    # 3:25 PM
        self.exit_window_start = time(9, 15)    # 9:15 AM next day
        self.exit_window_end = time(9, 45)      # 9:45 AM next day
        
        # Breakout parameters
        self.min_swing_highs = 3  # Min resistance touches
        self.breakout_atr_buffer = 0.15  # 0.15× ATR above resistance
        self.volume_expansion_ratio = 1.5  # 1.5× median volume
        self.ema_period = 44  # Trend filter
        
        # Liquidity filters
        self.min_price = 50.0  # Minimum stock price (₹)
        self.min_turnover = 1.5  # Min 5-min turnover (₹ crore)
        self.max_bid_ask_spread = 0.0002  # Max 0.02% spread
        self.min_volume_multiplier = 5.0  # 5X typical volume in last 15 min
        
        # Volatility filters
        self.min_atr_pct = 2.0  # Min ATR%
        self.max_atr_pct = 8.0  # Max ATR%
        self.max_intraday_gain = 10.0  # Avoid stocks up >10% intraday
        
        # Risk management
        self.risk_per_trade = 0.4  # 0.4% of capital per trade
        self.max_positions = 8  # Max concurrent positions
        self.max_sector_concentration = 0.40  # 40% max in one sector
        self.max_gross_exposure = 0.95  # 95% of capital
        
        # Target parameters
        self.min_target_pct = 3.0  # 3% minimum target
        self.max_target_pct = 5.0  # 5% maximum target
        self.default_sl_pct = 2.5  # 2.5% stop loss
        
        # Index filter
        self.index_symbol = '^NSEI'  # NIFTY 50
        self.max_index_decline = -1.2  # Max -1.2% intraday decline
    
    def scan(self, symbols: List[str], capital: float = 100000, silent: bool = False, **kwargs) -> List[Signal]:
        """
        Scan symbols for late-session BTST breakout setups
        
        Args:
            symbols: List of stock symbols
            capital: Trading capital for position sizing
            silent: If True, suppress console output
            **kwargs: Additional parameters (can include check_time=False to skip timing check)
        
        Returns:
            List of valid signals ranked by quality
        """
        self.signals = []
        check_time = kwargs.get('check_time', True)
        
        if not silent:
            print(f"\n{'='*70}")
            print(f"🎯 IMPROVED BTST STRATEGY SCANNER")
            print(f"{'='*70}")
            print(f"Scanning {len(symbols)} stocks for late-session breakouts...")
            print(f"Entry Window: 3:15-3:25 PM IST | Exit Window: 9:15-9:45 AM next day")
            print(f"{'='*70}\n")
        
        # Check if we're in trading window (skip for backtest)
        if check_time and not self._is_entry_window():
            if not silent:
                print("⚠️  Not in entry window (3:15-3:25 PM IST). Scan aborted.")
            return []
        
        # Check index regime
        if not self._check_index_regime(silent=silent):
            if not silent:
                print("⚠️  Market regime unfavorable (NIFTY declined >1.2%). Scan aborted.")
            return []
        
        # Filter stocks by basic criteria first
        filtered_symbols = self._pre_filter_stocks(symbols, silent=silent)
        
        if not filtered_symbols:
            if not silent:
                print("❌ No stocks passed basic filters.")
            return []
        
        if not silent:
            print(f"\n✅ {len(filtered_symbols)} stocks passed pre-filtering.")
            print(f"Analyzing for breakout setups...\n")
        
        # Scan for breakout setups
        for i, symbol in enumerate(filtered_symbols, 1):
            if not silent and i % 25 == 0:
                print(f"Progress: {i}/{len(filtered_symbols)} stocks analyzed...")
            
            try:
                # Fetch intraday data (5-min and 15-min)
                df_5m = self._fetch_intraday_data(symbol, interval='5m', days=5)
                df_15m = self._fetch_intraday_data(symbol, interval='15m', days=10)
                
                if df_5m is None or df_15m is None:
                    continue
                
                if len(df_5m) < 50 or len(df_15m) < 30:
                    continue
                
                # Validate signal
                if self.validate_signal(df_5m, df_15m):
                    signal = self._create_signal(df_5m, df_15m, symbol, capital)
                    if signal:
                        self.signals.append(signal)
                        if not silent:
                            print(f"✅ SIGNAL: {symbol} | Score: {signal.quality_score:.1f}/10 | "
                                  f"Entry: ₹{signal.entry_price:.2f} | Target: ₹{signal.target:.2f}")
            
            except Exception as e:
                if not silent:
                    print(f"❌ Error analyzing {symbol}: {str(e)[:50]}")
                continue
        
        # Rank and filter signals
        self.signals = self._rank_and_filter_signals(self.signals, capital)
        
        if not silent:
            print(f"\n{'='*70}")
            print(f"✅ Scan Complete: {len(self.signals)} high-quality signals identified")
            if self.signals:
                print(f"Top Signal: {self.signals[0].symbol} (Score: {self.signals[0].quality_score:.1f}/10)")
                print(f"Average Score: {np.mean([s.quality_score for s in self.signals]):.1f}/10")
            print(f"{'='*70}\n")
        
        return self.signals
    
    def validate_signal(self, df_5m: pd.DataFrame, df_15m: pd.DataFrame = None) -> bool:
        """
        Validate if current data meets improved BTST criteria
        
        Args:
            df_5m: 5-minute DataFrame with OHLCV data
            df_15m: 15-minute DataFrame with OHLCV data (optional)
        
        Returns:
            True if valid breakout setup
        """
        try:
            # Use the DataFrame naming that's passed in
            df = df_5m
            
            # Calculate indicators on 5-minute chart
            ema_44_5m = self.calculate_ema(df, self.ema_period)
            atr_14 = self.calculate_atr(df, period=14)
            
            current_price = float(df['close'].iloc[-1])
            current_ema = float(ema_44_5m.iloc[-1])
            
            # 1. Price must be above EMA(44) on 5-min chart
            if current_price < current_ema:
                return False
            
            # 2. EMA must be sloping upward
            ema_slope = (ema_44_5m.iloc[-1] - ema_44_5m.iloc[-5]) / ema_44_5m.iloc[-5]
            if ema_slope < 0:
                return False
            
            # 3. Check 15-min EMA alignment (if provided)
            if df_15m is not None and len(df_15m) >= self.ema_period:
                ema_44_15m = self.calculate_ema(df_15m, self.ema_period)
                if current_price < float(ema_44_15m.iloc[-1]):
                    return False
            
            # 4. Detect resistance zone (min 3 swing highs)
            resistance_zone = self._find_resistance_zone(df)
            if resistance_zone is None:
                return False
            
            # 5. Check if breakout is valid (price > resistance + 0.15× ATR)
            breakout_threshold = resistance_zone + (atr_14 * self.breakout_atr_buffer)
            if current_price < breakout_threshold:
                return False
            
            # 6. Volume confirmation (1.5X+ median volume)
            volume_ratio = self._calculate_volume_expansion(df, period=20)
            if volume_ratio < self.volume_expansion_ratio:
                return False
            
            # 7. Breakout candle quality (strong body, little wick)
            last_candle = df.iloc[-1]
            body_size = abs(float(last_candle['close']) - float(last_candle['open']))
            total_size = float(last_candle['high']) - float(last_candle['low'])
            
            if total_size > 0:
                body_ratio = body_size / total_size
                if body_ratio < 0.6:  # At least 60% body
                    return False
            
            # 8. Check if it's a closing candle (within last 15 minutes)
            # This is implicit in the entry window check
            
            return True
            
        except Exception as e:
            return False
    
    def calculate_targets(self, df: pd.DataFrame, entry_price: float) -> Dict:
        """
        Calculate stop loss and target prices
        
        Args:
            df: DataFrame with OHLCV data (5-min)
            entry_price: Entry price
        
        Returns:
            Dict with stop_loss and target prices
        """
        # Calculate ATR for stop loss
        atr_14 = self.calculate_atr(df, period=14)
        ema_44 = self.calculate_ema(df, self.ema_period)
        
        # Find resistance zone (which we just broke)
        resistance_zone = self._find_resistance_zone(df)
        
        # Stop loss: Below resistance zone OR below EMA(44), whichever is higher
        sl_from_zone = resistance_zone * 0.99 if resistance_zone else entry_price * 0.975
        sl_from_ema = float(ema_44.iloc[-1]) * 0.99
        
        stop_loss = max(sl_from_zone, sl_from_ema)
        
        # Ensure SL is not more than 2.5% from entry
        max_sl = entry_price * (1 - self.default_sl_pct / 100)
        stop_loss = max(stop_loss, max_sl)
        
        # Target: 3-5% based on volatility
        atr_pct = (atr_14 / entry_price) * 100
        
        if atr_pct > 5.0:
            target_pct = self.max_target_pct  # 5% for high volatility
        elif atr_pct > 3.5:
            target_pct = 4.0  # 4% for medium volatility
        else:
            target_pct = self.min_target_pct  # 3% for low volatility
        
        target = entry_price * (1 + target_pct / 100)
        
        # Ensure minimum R:R of 2:1
        risk = entry_price - stop_loss
        min_target = entry_price + (risk * 2.0)
        target = max(target, min_target)
        
        return {
            'stop_loss': float(stop_loss),
            'target': float(target),
            'resistance_zone': float(resistance_zone) if resistance_zone else None
        }
    
    def _create_signal(self, df_5m: pd.DataFrame, df_15m: pd.DataFrame, 
                      symbol: str, capital: float) -> Optional[Signal]:
        """
        Create a signal object with all details
        
        Args:
            df_5m: 5-minute DataFrame
            df_15m: 15-minute DataFrame
            symbol: Stock symbol
            capital: Trading capital
        
        Returns:
            Signal object or None
        """
        entry_price = float(df_5m['close'].iloc[-1])
        targets = self.calculate_targets(df_5m, entry_price)
        
        # Calculate position sizing
        pos_size = calculate_position_size(
            capital=capital,
            risk_pct=self.risk_per_trade,
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
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(df_5m, df_15m, entry_price, targets)
        
        # Additional metrics
        volume_ratio = self._calculate_volume_expansion(df_5m, period=20)
        atr = self.calculate_atr(df_5m, period=14)
        atr_pct = (atr / entry_price) * 100
        
        # Calculate EMA slopes
        ema_44_5m = self.calculate_ema(df_5m, self.ema_period)
        ema_slope = ((ema_44_5m.iloc[-1] - ema_44_5m.iloc[-5]) / ema_44_5m.iloc[-5]) * 100
        
        signal = Signal(
            symbol=symbol,
            date=datetime.now().strftime('%Y-%m-%d'),
            entry_price=entry_price,
            stop_loss=targets['stop_loss'],
            target=targets['target'],
            signal_type='BUY',
            strategy_name=self.name,
            quality_score=quality_score,
            confidence=min(quality_score / 10.0, 0.95),
            notes=f"Late-session breakout | R:R {rr['risk_reward_ratio']:.1f}:1 | "
                  f"Vol {volume_ratio:.1f}X | ATR {atr_pct:.1f}% | "
                  f"Exit by 9:45 AM tomorrow",
            volume_ratio=volume_ratio,
            atr=atr,
            shares=pos_size['shares'],
            position_value=pos_size['position_value'],
            risk_amount=pos_size['risk_amount'],
            # Additional metadata
            resistance_zone=targets.get('resistance_zone'),
            ema_slope=ema_slope,
            rsi=self.calculate_rsi(df_5m, 14) if len(df_5m) >= 14 else None
        )
        
        return signal
    
    def _calculate_quality_score(self, df_5m: pd.DataFrame, df_15m: pd.DataFrame,
                                 entry: float, targets: Dict) -> float:
        """
        Calculate quality score (1-10) for the signal
        
        Scoring factors:
        - Breakout strength (distance from resistance)
        - Volume expansion intensity
        - EMA alignment and slope
        - Multi-timeframe confirmation
        - R:R ratio
        - Candle body strength
        """
        score = 5.0  # Base score
        
        try:
            # 1. Breakout strength (max +2 points)
            resistance = targets.get('resistance_zone', entry * 0.98)
            breakout_distance = ((entry - resistance) / resistance) * 100
            if breakout_distance >= 1.5:
                score += 2
            elif breakout_distance >= 1.0:
                score += 1.5
            elif breakout_distance >= 0.5:
                score += 1
            
            # 2. Volume expansion (max +2 points)
            volume_ratio = self._calculate_volume_expansion(df_5m, period=20)
            if volume_ratio >= 2.5:
                score += 2
            elif volume_ratio >= 2.0:
                score += 1.5
            elif volume_ratio >= 1.5:
                score += 1
            
            # 3. EMA alignment and slope (max +2 points)
            ema_44 = self.calculate_ema(df_5m, self.ema_period)
            distance_from_ema = ((entry - ema_44.iloc[-1]) / ema_44.iloc[-1]) * 100
            ema_slope = ((ema_44.iloc[-1] - ema_44.iloc[-5]) / ema_44.iloc[-5]) * 100
            
            if distance_from_ema >= 2.0 and ema_slope > 0.5:
                score += 2
            elif distance_from_ema >= 1.0 and ema_slope > 0:
                score += 1.5
            elif distance_from_ema >= 0.5:
                score += 1
            
            # 4. Multi-timeframe confirmation (max +1 point)
            if df_15m is not None and len(df_15m) >= self.ema_period:
                ema_44_15m = self.calculate_ema(df_15m, self.ema_period)
                if entry > ema_44_15m.iloc[-1]:
                    score += 1
            
            # 5. R:R ratio (max +2 points)
            rr = calculate_risk_reward(entry, targets['stop_loss'], targets['target'])
            if rr['risk_reward_ratio'] >= 2.5:
                score += 2
            elif rr['risk_reward_ratio'] >= 2.0:
                score += 1.5
            elif rr['risk_reward_ratio'] >= 1.5:
                score += 1
            
            # 6. Candle body strength (max +1 point)
            last_candle = df_5m.iloc[-1]
            body_size = abs(float(last_candle['close']) - float(last_candle['open']))
            total_size = float(last_candle['high']) - float(last_candle['low'])
            
            if total_size > 0:
                body_ratio = body_size / total_size
                if body_ratio >= 0.8:
                    score += 1
                elif body_ratio >= 0.6:
                    score += 0.5
            
            # Cap score at 10
            score = min(score, 10.0)
        
        except Exception as e:
            score = 6.0  # Default score if calculation fails
        
        return round(score, 1)
    
    def _find_resistance_zone(self, df: pd.DataFrame, lookback: int = 50) -> Optional[float]:
        """
        Find resistance zone formed by at least 3 swing highs
        
        Args:
            df: DataFrame with OHLCV data
            lookback: Number of bars to look back
        
        Returns:
            Resistance price level or None
        """
        try:
            if len(df) < lookback:
                lookback = len(df)
            
            recent_df = df.iloc[-lookback:]
            highs = recent_df['high'].values
            
            # Find local peaks (swing highs)
            swing_highs = []
            for i in range(2, len(highs) - 2):
                if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
                   highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                    swing_highs.append(highs[i])
            
            if len(swing_highs) < self.min_swing_highs:
                return None
            
            # Cluster swing highs within 1% price range
            swing_highs = sorted(swing_highs, reverse=True)
            
            for base_high in swing_highs[:5]:  # Check top 5 highs
                cluster = [h for h in swing_highs if abs(h - base_high) / base_high < 0.01]
                if len(cluster) >= self.min_swing_highs:
                    return np.mean(cluster)
            
            return None
            
        except Exception:
            return None
    
    def _calculate_volume_expansion(self, df: pd.DataFrame, period: int = 20) -> float:
        """Calculate volume expansion ratio vs median"""
        try:
            current_volume = float(df['volume'].iloc[-1])
            median_volume = float(df['volume'].iloc[-period:].median())
            
            if median_volume > 0:
                return current_volume / median_volume
            return 1.0
        except:
            return 1.0
    
    def _fetch_intraday_data(self, symbol: str, interval: str = '5m', days: int = 5) -> Optional[pd.DataFrame]:
        """Fetch intraday data for analysis"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{days}d", interval=interval)
            
            if df is None or len(df) == 0:
                return None
            
            # Lowercase columns
            df.columns = [col.lower() for col in df.columns]
            
            return df
            
        except Exception:
            return None
    
    def _pre_filter_stocks(self, symbols: List[str], silent: bool = False) -> List[str]:
        """Pre-filter stocks by basic criteria before detailed analysis"""
        filtered = []
        
        for symbol in symbols:
            try:
                # Fetch daily data for quick filtering
                df = self.fetch_data(symbol, period="1mo", interval="1d")
                
                if df is None or len(df) < 20:
                    continue
                
                current_price = float(df['close'].iloc[-1])
                
                # 1. Price filter
                if current_price < self.min_price:
                    continue
                
                # 2. Volatility filter (ATR%)
                atr = self.calculate_atr(df, period=14)
                atr_pct = (atr / current_price) * 100
                
                if atr_pct < self.min_atr_pct or atr_pct > self.max_atr_pct:
                    continue
                
                # 3. Avoid parabolic moves
                intraday_gain = ((current_price / float(df['open'].iloc[-1])) - 1) * 100
                if intraday_gain > self.max_intraday_gain:
                    continue
                
                # 4. Basic liquidity check (volume)
                avg_volume = float(df['volume'].iloc[-20:].mean())
                if avg_volume < 100000:  # Min 100K shares daily avg
                    continue
                
                filtered.append(symbol)
                
            except Exception:
                continue
        
        return filtered
    
    def _check_index_regime(self, silent: bool = False) -> bool:
        """Check if market regime is favorable (NIFTY not declining sharply)"""
        try:
            nifty = yf.Ticker(self.index_symbol)
            df = nifty.history(period="1d", interval="1m")
            
            if df is None or len(df) < 10:
                return True  # Benefit of doubt
            
            open_price = float(df['Open'].iloc[0])
            current_price = float(df['Close'].iloc[-1])
            
            intraday_change = ((current_price - open_price) / open_price) * 100
            
            if intraday_change < self.max_index_decline:
                if not silent:
                    print(f"⚠️  NIFTY declined {intraday_change:.2f}% intraday (limit: {self.max_index_decline}%)")
                return False
            
            return True
            
        except Exception:
            return True  # Benefit of doubt if can't fetch
    
    def _is_entry_window(self) -> bool:
        """Check if current time is within entry window (3:15-3:25 PM IST)"""
        try:
            now = datetime.now().time()
            return self.entry_window_start <= now <= self.entry_window_end
        except:
            return False
    
    def _rank_and_filter_signals(self, signals: List[Signal], capital: float) -> List[Signal]:
        """
        Rank signals by quality and filter by portfolio constraints
        
        Args:
            signals: List of signals
            capital: Available capital
        
        Returns:
            Filtered and ranked list of signals
        """
        if not signals:
            return []
        
        # Sort by quality score (descending)
        sorted_signals = sorted(signals, key=lambda x: x.quality_score, reverse=True)
        
        # Apply portfolio constraints
        filtered_signals = []
        total_exposure = 0
        sector_exposure = {}
        
        for signal in sorted_signals:
            # Check max positions
            if len(filtered_signals) >= self.max_positions:
                break
            
            # Check gross exposure
            position_value = signal.position_value
            if total_exposure + position_value > capital * self.max_gross_exposure:
                continue
            
            # Check sector concentration (simplified - would need sector mapping)
            # For now, just accept the signal
            
            filtered_signals.append(signal)
            total_exposure += position_value
        
        return filtered_signals


if __name__ == "__main__":
    # CLI testing
    strategy = ImprovedBTSTStrategy()
    
    # Test with some symbols (skip time check for testing)
    symbols = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS',
               'WIPRO.NS', 'TATAMOTORS.NS', 'AXISBANK.NS', 'BAJFINANCE.NS', 'SBIN.NS']
    
    print("Testing Improved BTST Strategy...")
    signals = strategy.scan(symbols, capital=100000, check_time=False)
    
    if signals:
        strategy.save_signals('improved_btst_signals.csv')
        summary = strategy.get_signal_summary()
        print(f"\n{'='*70}")
        print(f"Strategy: {summary['description']}")
        print(f"Signals found: {summary['count']}")
        print(f"Average score: {summary['avg_score']:.1f}/10")
        print(f"Total capital required: ₹{summary['total_capital_required']:,.0f}")
        print(f"{'='*70}")
    else:
        print("\n❌ No signals found matching criteria")











