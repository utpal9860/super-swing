"""
Base Strategy Abstract Class

Defines the interface for all trading strategies.
All strategy scanners should inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import yfinance as yf


@dataclass
class Signal:
    """Trading signal data structure"""
    symbol: str
    date: str
    entry_price: float
    stop_loss: float
    target: float
    signal_type: str  # 'BUY', 'SELL'
    strategy_name: str
    
    # Optional fields
    quality_score: Optional[float] = None
    confidence: Optional[float] = None
    notes: Optional[str] = None
    
    # Technical indicators
    rsi: Optional[float] = None
    volume_ratio: Optional[float] = None
    atr: Optional[float] = None
    
    # Position sizing (calculated by caller)
    shares: Optional[int] = None
    position_value: Optional[float] = None
    risk_amount: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert signal to dictionary"""
        return {
            'symbol': self.symbol,
            'date': self.date,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'target': self.target,
            'signal_type': self.signal_type,
            'strategy_name': self.strategy_name,
            'quality_score': self.quality_score,
            'confidence': self.confidence,
            'notes': self.notes,
            'rsi': self.rsi,
            'volume_ratio': self.volume_ratio,
            'atr': self.atr,
            'shares': self.shares,
            'position_value': self.position_value,
            'risk_amount': self.risk_amount
        }


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    All strategies must implement:
    - scan(): Find signals in given symbols
    - validate_signal(): Check if signal meets criteria
    - calculate_targets(): Calculate SL and targets
    """
    
    def __init__(self, name: str, description: str):
        """
        Initialize strategy
        
        Args:
            name: Strategy name (e.g., "pullback_entry")
            description: Brief description of strategy
        """
        self.name = name
        self.description = description
        self.signals = []
    
    @abstractmethod
    def scan(self, symbols: List[str], **kwargs) -> List[Signal]:
        """
        Scan symbols for trading signals
        
        Args:
            symbols: List of stock symbols to scan
            **kwargs: Additional parameters (lookback, capital, etc.)
        
        Returns:
            List of Signal objects
        """
        pass
    
    @abstractmethod
    def validate_signal(self, df: pd.DataFrame) -> bool:
        """
        Validate if current data meets signal criteria
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            True if signal is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def calculate_targets(self, df: pd.DataFrame, entry_price: float) -> Dict:
        """
        Calculate stop loss and target prices
        
        Args:
            df: DataFrame with OHLCV data
            entry_price: Entry price for the trade
        
        Returns:
            Dict with 'stop_loss' and 'target' prices
        """
        pass
    
    def fetch_data(
        self, 
        symbol: str, 
        period: str = "3mo", 
        interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol
        
        Args:
            symbol: Stock symbol
            period: Time period (1mo, 3mo, 6mo, 1y, etc.)
            interval: Data interval (1d, 1wk, etc.)
        
        Returns:
            DataFrame with OHLCV data or None if error
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                return None
            
            # Clean column names
            df.columns = [col.lower() for col in df.columns]
            
            return df
        
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return None
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate Average True Range (ATR)
        
        Args:
            df: DataFrame with OHLCV data
            period: ATR period
        
        Returns:
            ATR value
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        
        return float(atr)
    
    def calculate_sma(self, df: pd.DataFrame, period: int) -> pd.Series:
        """
        Calculate Simple Moving Average
        
        Args:
            df: DataFrame with OHLCV data
            period: SMA period
        
        Returns:
            Series with SMA values
        """
        return df['close'].rolling(window=period).mean()
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate Relative Strength Index (RSI)
        
        Args:
            df: DataFrame with OHLCV data
            period: RSI period
        
        Returns:
            Current RSI value
        """
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi.iloc[-1])
    
    def calculate_volume_ratio(self, df: pd.DataFrame, period: int = 20) -> float:
        """
        Calculate current volume vs average volume
        
        Args:
            df: DataFrame with OHLCV data
            period: Period for average volume
        
        Returns:
            Volume ratio
        """
        avg_volume = df['volume'].rolling(window=period).mean().iloc[-1]
        current_volume = df['volume'].iloc[-1]
        
        if avg_volume > 0:
            return float(current_volume / avg_volume)
        return 1.0
    
    def is_above_sma(self, df: pd.DataFrame, period: int) -> bool:
        """
        Check if current price is above SMA
        
        Args:
            df: DataFrame with OHLCV data
            period: SMA period
        
        Returns:
            True if above SMA, False otherwise
        """
        sma = self.calculate_sma(df, period)
        current_price = df['close'].iloc[-1]
        
        return current_price > sma.iloc[-1]
    
    def get_recent_high(self, df: pd.DataFrame, period: int = 20) -> float:
        """
        Get highest price in recent period
        
        Args:
            df: DataFrame with OHLCV data
            period: Lookback period
        
        Returns:
            Highest price
        """
        return float(df['high'].tail(period).max())
    
    def get_recent_low(self, df: pd.DataFrame, period: int = 20) -> float:
        """
        Get lowest price in recent period
        
        Args:
            df: DataFrame with OHLCV data
            period: Lookback period
        
        Returns:
            Lowest price
        """
        return float(df['low'].tail(period).min())
    
    def save_signals(self, filename: str) -> None:
        """
        Save signals to CSV file
        
        Args:
            filename: Output filename
        """
        if not self.signals:
            print(f"No signals to save for {self.name}")
            return
        
        df = pd.DataFrame([s.to_dict() for s in self.signals])
        df.to_csv(filename, index=False)
        print(f"Saved {len(self.signals)} signals to {filename}")
    
    def get_signal_summary(self) -> Dict:
        """
        Get summary of found signals
        
        Returns:
            Dict with summary statistics
        """
        if not self.signals:
            return {
                'count': 0,
                'avg_score': 0,
                'strategy': self.name
            }
        
        scores = [s.quality_score for s in self.signals if s.quality_score is not None]
        
        return {
            'count': len(self.signals),
            'avg_score': sum(scores) / len(scores) if scores else 0,
            'strategy': self.name,
            'description': self.description
        }


# Example usage
if __name__ == "__main__":
    # This is an abstract class, so it can't be instantiated directly
    # Concrete strategies will inherit from this
    print("BaseStrategy is an abstract class.")
    print("Use concrete implementations like PullbackEntryStrategy or SwingSuperTrendStrategy")

