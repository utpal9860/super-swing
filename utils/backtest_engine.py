"""
Backtest Engine

Comprehensive backtesting framework for testing trading strategies on historical data.

Features:
- Strategy backtesting with historical data
- Position sizing and risk management
- Performance metrics calculation
- Trade log generation
- Multiple strategy comparison
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from strategies.base_strategy import BaseStrategy, Signal
from utils.performance_tracker import StrategyMetrics, TradeResult

# Setup logging
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

logger = logging.getLogger("backtest")
logger.setLevel(logging.INFO)

# File handler
log_file = logs_dir / "backtest.log"
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)


@dataclass
class BacktestConfig:
    """Backtest configuration"""
    start_date: str
    end_date: str
    initial_capital: float
    risk_per_trade: float = 2.0  # % of capital to risk per trade
    max_positions: int = 5  # Maximum concurrent positions
    brokerage_per_trade: float = 20.0  # Fixed brokerage per trade (buy + sell)
    
    def to_dict(self):
        return asdict(self)


@dataclass
class BacktestTrade:
    """Individual trade in backtest"""
    trade_id: int
    symbol: str
    entry_date: str
    entry_price: float
    shares: int
    stop_loss: float
    target: float
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    profit_loss: Optional[float] = None
    profit_loss_pct: Optional[float] = None
    holding_days: Optional[int] = None
    
    def to_dict(self):
        return asdict(self)


@dataclass
class BacktestResult:
    """Backtest results"""
    strategy_name: str
    config: BacktestConfig
    
    # Capital metrics
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    
    # Trade metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # Performance metrics
    avg_win: float
    avg_loss: float
    avg_return: float
    profit_factor: float
    expectancy: float
    
    # Risk metrics
    max_drawdown: float
    sharpe_ratio: Optional[float]
    
    # Trade list
    trades: List[Dict]
    
    # Equity curve
    equity_curve: List[Dict]  # List of {date, capital}
    
    def to_dict(self):
        return {
            'strategy_name': self.strategy_name,
            'config': self.config.to_dict(),
            'initial_capital': self.initial_capital,
            'final_capital': self.final_capital,
            'total_return': self.total_return,
            'total_return_pct': self.total_return_pct,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'avg_return': self.avg_return,
            'profit_factor': self.profit_factor,
            'expectancy': self.expectancy,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': self.sharpe_ratio,
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }


class BacktestEngine:
    """
    Backtest trading strategies on historical data
    
    Simulates real trading with:
    - Position sizing
    - Risk management
    - Multiple position tracking
    - Realistic entry/exit
    """
    
    def __init__(self, config: BacktestConfig):
        """
        Initialize backtest engine
        
        Args:
            config: Backtest configuration
        """
        self.config = config
        self.capital = config.initial_capital
        self.trades: List[BacktestTrade] = []
        self.open_positions: List[BacktestTrade] = []
        self.equity_curve: List[Dict] = []
        self.trade_counter = 0
    
    def run(
        self,
        strategy: BaseStrategy,
        symbols: List[str],
        progress_callback: Optional[callable] = None
    ) -> BacktestResult:
        """
        Run backtest for a strategy
        
        Args:
            strategy: Trading strategy to backtest
            symbols: List of symbols to trade
            progress_callback: Optional callback for progress updates
            
        Returns:
            BacktestResult object
        """
        logger.info("="*70)
        logger.info(f"BACKTESTING: {strategy.name}")
        logger.info(f"Period: {self.config.start_date} to {self.config.end_date}")
        logger.info(f"Symbols: {len(symbols)}")
        logger.info(f"Initial Capital: ₹{self.config.initial_capital:,.0f}")
        logger.info("="*70)
        
        # Convert dates
        start_date = datetime.fromisoformat(self.config.start_date)
        end_date = datetime.fromisoformat(self.config.end_date)
        
        # Iterate through each trading day
        current_date = start_date
        day_count = 0
        
        while current_date <= end_date:
            day_count += 1
            
            # Progress update
            if progress_callback and day_count % 30 == 0:
                progress = int(((current_date - start_date).days / (end_date - start_date).days) * 100)
                progress_callback(progress, current_date.strftime('%Y-%m-%d'))
                logger.info(f"Progress: {progress}% - {current_date.strftime('%Y-%m-%d')} - Open positions: {len(self.open_positions)} - Trades: {len(self.trades)}")
            
            # Check for exits on open positions
            self._check_exits(current_date)
            
            # Look for new entries if we have capacity
            if len(self.open_positions) < self.config.max_positions:
                self._check_entries(strategy, symbols, current_date)
            
            # Record equity
            self.equity_curve.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'capital': self.capital
            })
            
            # Next trading day
            current_date += timedelta(days=1)
        
        # Close all remaining positions at end date
        self._close_all_positions(end_date, "backtest_end")
        
        # Calculate results
        result = self._calculate_results(strategy.name)
        
        logger.info("="*70)
        logger.info(f"BACKTEST COMPLETE: {strategy.name}")
        logger.info(f"Total Trades: {result.total_trades}")
        logger.info(f"Win Rate: {result.win_rate:.2f}%")
        logger.info(f"Total Return: ₹{result.total_return:,.0f} ({result.total_return_pct:.2f}%)")
        logger.info(f"Final Capital: ₹{result.final_capital:,.0f}")
        logger.info("="*70)
        
        return result
    
    def _check_entries(self, strategy: BaseStrategy, symbols: List[str], current_date: datetime):
        """Check for new trade entries"""
        # For each symbol, check if it has a valid signal on this date
        for symbol in symbols:
            if len(self.open_positions) >= self.config.max_positions:
                break
            
            # Skip if we already have a position in this symbol
            if any(pos.symbol == symbol for pos in self.open_positions):
                continue
            
            # Get historical data up to current_date
            try:
                df = self._get_historical_data(symbol, current_date)
                
                if df is None or len(df) < 50:  # Need enough data for indicators
                    continue
                
                # Prepare DataFrame for strategy validation
                # Ensure it has lowercase column names expected by strategies
                df_for_strategy = df.copy()
                if 'Close' in df_for_strategy.columns:
                    df_for_strategy.columns = df_for_strategy.columns.str.lower()
                
                # Check if strategy validates this as a signal
                if not strategy.validate_signal(df_for_strategy):
                    continue
                
                # Calculate entry price and targets
                entry_price = float(df_for_strategy['close'].iloc[-1])
                targets = strategy.calculate_targets(df_for_strategy, entry_price)
                
                stop_loss = targets['stop_loss']
                target = targets['target']
                
                # Calculate position size
                risk_amount = self.capital * (self.config.risk_per_trade / 100)
                price_risk = entry_price - stop_loss
                
                if price_risk <= 0:
                    continue
                
                shares = int(risk_amount / price_risk)
                
                if shares <= 0:
                    continue
                
                # Check if we have enough capital
                required_capital = shares * entry_price + self.config.brokerage_per_trade
                
                if required_capital > self.capital:
                    # Reduce shares to fit available capital
                    shares = int((self.capital - self.config.brokerage_per_trade) / entry_price)
                
                if shares <= 0:
                    continue
                
                # Create trade
                trade = BacktestTrade(
                    trade_id=len(self.trades) + len(self.open_positions) + 1,
                    symbol=symbol,
                    entry_date=current_date.strftime('%Y-%m-%d'),
                    entry_price=entry_price,
                    shares=shares,
                    stop_loss=stop_loss,
                    target=target
                )
                
                # Update capital
                investment = shares * entry_price + self.config.brokerage_per_trade
                self.capital -= investment
                
                self.open_positions.append(trade)
                
                logger.info(f"  Entry: {symbol} @ ₹{entry_price:.2f} | Shares: {shares} | Investment: ₹{investment:,.0f}")
                    
            except Exception as e:
                # Silent fail for individual symbols to keep backtest running
                continue
    
    def _check_exits(self, current_date: datetime):
        """Check if any open positions hit SL/Target or time stop"""
        for position in self.open_positions[:]:  # Copy list to allow removal during iteration
            # Fetch OHLC for current date
            ohlc = self._get_ohlc_for_date(position.symbol, current_date)
            
            if not ohlc:
                continue
            
            # Check if SL hit
            if ohlc['low'] <= position.stop_loss:
                self._close_position(position, current_date, position.stop_loss, "stop_loss")
                continue
            
            # Check if target hit
            if ohlc['high'] >= position.target:
                self._close_position(position, current_date, position.target, "target")
                continue
            
            # Check time stop (e.g., 30 days for swing trades)
            entry_date = datetime.fromisoformat(position.entry_date)
            holding_days = (current_date - entry_date).days
            
            if holding_days >= 30:  # Configurable time stop
                self._close_position(position, current_date, ohlc['close'], "time_stop")
    
    def _close_position(self, position: BacktestTrade, exit_date: datetime, exit_price: float, exit_reason: str):
        """Close an open position"""
        position.exit_date = exit_date.strftime('%Y-%m-%d')
        position.exit_price = exit_price
        position.exit_reason = exit_reason
        
        # Calculate P&L
        gross_pl = (exit_price - position.entry_price) * position.shares
        net_pl = gross_pl - self.config.brokerage_per_trade  # Deduct brokerage
        
        position.profit_loss = net_pl
        position.profit_loss_pct = ((exit_price - position.entry_price) / position.entry_price) * 100
        
        # Calculate holding days
        entry_dt = datetime.fromisoformat(position.entry_date)
        exit_dt = exit_date
        position.holding_days = (exit_dt - entry_dt).days
        
        # Update capital
        self.capital += net_pl
        
        # Move to closed trades
        self.trades.append(position)
        self.open_positions.remove(position)
        
        logger.info(f"  Closed: {position.symbol} | P&L: ₹{net_pl:,.0f} ({position.profit_loss_pct:.2f}%) | Reason: {exit_reason}")
    
    def _close_all_positions(self, exit_date: datetime, reason: str):
        """Close all open positions"""
        for position in self.open_positions[:]:
            ohlc = self._get_ohlc_for_date(position.symbol, exit_date)
            exit_price = ohlc['close'] if ohlc else position.entry_price
            self._close_position(position, exit_date, exit_price, reason)
    
    
    def _get_historical_data(self, symbol: str, current_date: datetime) -> Optional[pd.DataFrame]:
        """
        Get historical data for a symbol up to current_date (for backtesting).
        This simulates what data would have been available on that date.
        """
        try:
            # Get data from 1 year before current_date to ensure enough history for indicators
            start = current_date - timedelta(days=365)
            end = current_date
            
            df = yf.download(symbol, start=start, end=end, progress=False)
            
            if df.empty or len(df) < 50:
                return None
            
            # Flatten multi-level columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Reset index to have Date as a column
            df = df.reset_index()
            df['symbol'] = symbol
            
            return df
            
        except Exception as e:
            return None
    
    def _get_ohlc_for_date(self, symbol: str, date: datetime) -> Optional[Dict]:
        """Get OHLC data for a specific date"""
        try:
            # Fetch a small window around the date
            start = date - timedelta(days=5)
            end = date + timedelta(days=1)
            
            df = yf.download(symbol, start=start, end=end, progress=False)
            
            if df.empty:
                return None
            
            # Find the row for the specific date
            date_str = date.strftime('%Y-%m-%d')
            
            if date_str in df.index.astype(str):
                row = df.loc[date_str]
                return {
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': float(row['Volume'])
                }
            
            return None
        except:
            return None
    
    def _calculate_results(self, strategy_name: str) -> BacktestResult:
        """Calculate backtest results"""
        closed_trades = [t for t in self.trades if t.exit_date]
        
        if not closed_trades:
            return BacktestResult(
                strategy_name=strategy_name,
                config=self.config,
                initial_capital=self.config.initial_capital,
                final_capital=self.capital,
                total_return=0,
                total_return_pct=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                avg_win=0,
                avg_loss=0,
                avg_return=0,
                profit_factor=0,
                expectancy=0,
                max_drawdown=0,
                sharpe_ratio=None,
                trades=[],
                equity_curve=self.equity_curve
            )
        
        # Calculate metrics
        total_trades = len(closed_trades)
        wins = [t for t in closed_trades if t.profit_loss > 0]
        losses = [t for t in closed_trades if t.profit_loss <= 0]
        
        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        total_return = self.capital - self.config.initial_capital
        total_return_pct = (total_return / self.config.initial_capital) * 100
        
        avg_win = sum(t.profit_loss for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.profit_loss for t in losses) / len(losses) if losses else 0
        avg_return = sum(t.profit_loss_pct for t in closed_trades) / total_trades if total_trades > 0 else 0
        
        total_wins = sum(t.profit_loss for t in wins)
        total_losses = abs(sum(t.profit_loss for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        win_pct = win_rate / 100
        loss_pct = 1 - win_pct
        expectancy = (win_pct * avg_win) - (loss_pct * abs(avg_loss))
        
        # Calculate max drawdown
        max_dd = self._calculate_max_drawdown()
        
        # Calculate Sharpe ratio
        returns = [t.profit_loss_pct for t in closed_trades]
        sharpe_ratio = None
        if len(returns) > 1:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
            std_dev = variance ** 0.5
            sharpe_ratio = (mean_return / std_dev) if std_dev > 0 else 0
        
        return BacktestResult(
            strategy_name=strategy_name,
            config=self.config,
            initial_capital=self.config.initial_capital,
            final_capital=self.capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_return=avg_return,
            profit_factor=profit_factor,
            expectancy=expectancy,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe_ratio,
            trades=[t.to_dict() for t in closed_trades],
            equity_curve=self.equity_curve
        )
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from equity curve"""
        if not self.equity_curve:
            return 0.0
        
        peak = self.equity_curve[0]['capital']
        max_dd = 0
        
        for point in self.equity_curve:
            capital = point['capital']
            
            if capital > peak:
                peak = capital
            
            dd = ((peak - capital) / peak) * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return max_dd


# Example usage
if __name__ == "__main__":
    # Example configuration
    config = BacktestConfig(
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_capital=100000,
        risk_per_trade=2.0,
        max_positions=5,
        brokerage_per_trade=20.0
    )
    
    logger.info("Backtest Engine initialized")
    logger.info(f"Period: {config.start_date} to {config.end_date}")
    logger.info(f"Capital: ₹{config.initial_capital:,.0f}")
    logger.info(f"Risk per trade: {config.risk_per_trade}%")
    logger.info(f"Max positions: {config.max_positions}")


