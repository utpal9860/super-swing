"""
Realistic backtesting engine for Indian markets
Implements all real-world constraints and costs
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from utils.logger import setup_logger
from utils.market_utils import (
    is_trading_day, 
    check_circuit_breaker,
    calculate_transaction_costs
)
from config import BACKTEST_CONFIG, NSE_HOLIDAYS

logger = setup_logger("backtest_engine")

@dataclass
class Position:
    """Represents an open trading position"""
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: int
    stop_loss: float
    target: float
    pattern_id: str = ""
    days_held: int = 0
    current_price: float = 0.0
    max_gain_pct: float = 0.0
    max_loss_pct: float = 0.0
    
    def update(self, current_bar: Dict):
        """Update position with current bar data"""
        self.current_price = current_bar['close']
        self.days_held += 1
        
        # Update max gain/loss
        gain_pct = (current_bar['high'] - self.entry_price) / self.entry_price * 100
        loss_pct = (current_bar['low'] - self.entry_price) / self.entry_price * 100
        
        self.max_gain_pct = max(self.max_gain_pct, gain_pct)
        self.max_loss_pct = min(self.max_loss_pct, loss_pct)
    
    def check_exit(self, current_bar: Dict, max_days: int = 20) -> Tuple[bool, str, float]:
        """
        Check if position should be exited
        
        Returns:
            (should_exit, reason, exit_price)
        """
        # Stop loss hit (use LOW of day)
        if current_bar['low'] <= self.stop_loss:
            return True, "STOP_HIT", self.stop_loss
        
        # Target hit (use HIGH of day)
        if current_bar['high'] >= self.target:
            return True, "TARGET_HIT", self.target
        
        # Max holding period
        if self.days_held >= max_days:
            return True, "TIME_STOP", current_bar['close']
        
        return False, "", 0.0
    
    def calculate_pnl(self, exit_price: float, costs: Dict) -> Dict:
        """Calculate P&L with all costs"""
        gross_pnl = (exit_price - self.entry_price) * self.shares
        total_costs = costs['total_round_trip']
        net_pnl = gross_pnl - total_costs
        
        return {
            'gross_pnl': gross_pnl,
            'costs': total_costs,
            'net_pnl': net_pnl,
            'net_pnl_pct': (net_pnl / (self.entry_price * self.shares)) * 100
        }

@dataclass
class BacktestResult:
    """Stores backtest results"""
    trades: List[Dict] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    dates: List[datetime] = field(default_factory=list)
    
    def add_trade(self, trade: Dict):
        """Add a completed trade"""
        self.trades.append(trade)
    
    def calculate_metrics(self) -> Dict:
        """Calculate performance metrics"""
        if not self.trades:
            return {}
        
        df_trades = pd.DataFrame(self.trades)
        
        # Basic metrics
        total_trades = len(df_trades)
        winning_trades = len(df_trades[df_trades['net_pnl'] > 0])
        losing_trades = len(df_trades[df_trades['net_pnl'] < 0])
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # P&L metrics
        total_pnl = df_trades['net_pnl'].sum()
        avg_win = df_trades[df_trades['net_pnl'] > 0]['net_pnl'].mean() if winning_trades > 0 else 0
        avg_loss = df_trades[df_trades['net_pnl'] < 0]['net_pnl'].mean() if losing_trades > 0 else 0
        
        # Profit factor
        gross_profit = df_trades[df_trades['net_pnl'] > 0]['net_pnl'].sum()
        gross_loss = abs(df_trades[df_trades['net_pnl'] < 0]['net_pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Holding period
        avg_holding_days = df_trades['holding_days'].mean()
        
        # Drawdown
        equity_series = pd.Series(self.equity_curve)
        running_max = equity_series.cummax()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown = drawdown.min()
        
        metrics = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'avg_holding_days': avg_holding_days,
            'max_drawdown': max_drawdown,
            'final_equity': self.equity_curve[-1] if self.equity_curve else 0,
        }
        
        return metrics

class BacktestEngine:
    """
    Realistic backtesting engine with Indian market constraints
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize backtest engine
        
        Args:
            config: Backtest configuration (defaults to BACKTEST_CONFIG)
        """
        self.config = config or BACKTEST_CONFIG
        self.initial_capital = self.config['initial_capital']
        self.capital = self.initial_capital
        self.positions: List[Position] = []
        self.results = BacktestResult()
        
        logger.info(f"Backtest Engine initialized with ₹{self.initial_capital:,.0f} capital")
    
    def can_open_position(self) -> bool:
        """Check if we can open a new position"""
        return len(self.positions) < self.config['max_positions']
    
    def calculate_position_size(self, price: float) -> Tuple[int, float]:
        """
        Calculate position size based on available capital
        
        Returns:
            (shares, position_value)
        """
        position_value = self.capital * self.config['position_size']
        shares = int(position_value / price)
        actual_value = shares * price
        
        return shares, actual_value
    
    def apply_slippage(self, price: float, side: str = "BUY") -> float:
        """Apply slippage to price"""
        slippage_pct = self.config['slippage_pct']
        
        if side == "BUY":
            return price * (1 + slippage_pct)
        else:  # SELL
            return price * (1 - slippage_pct)
    
    def execute_entry(
        self, 
        ticker: str,
        entry_date: datetime,
        entry_price: float,
        stop_loss: float,
        target: float,
        pattern_id: str = ""
    ) -> Optional[Position]:
        """
        Execute entry for a pattern signal
        
        Returns:
            Position object if successful, None otherwise
        """
        # Check if we can open position
        if not self.can_open_position():
            logger.debug(f"Max positions reached, skipping {ticker}")
            return None
        
        # Apply slippage
        actual_entry = self.apply_slippage(entry_price, "BUY")
        
        # Calculate position size
        shares, position_value = self.calculate_position_size(actual_entry)
        
        if shares == 0:
            logger.debug(f"Insufficient capital for {ticker}")
            return None
        
        # Calculate costs
        costs = calculate_transaction_costs(position_value, is_intraday=False)
        total_cost = position_value + costs['total_one_way']
        
        # Check if we have enough capital
        if total_cost > self.capital:
            logger.debug(f"Insufficient capital for {ticker} (need ₹{total_cost:,.0f})")
            return None
        
        # Create position
        position = Position(
            ticker=ticker,
            entry_date=entry_date,
            entry_price=actual_entry,
            shares=shares,
            stop_loss=stop_loss,
            target=target,
            pattern_id=pattern_id,
            current_price=actual_entry
        )
        
        # Deduct capital
        self.capital -= total_cost
        self.positions.append(position)
        
        logger.info(f"ENTRY: {ticker} @ ₹{actual_entry:.2f} x {shares} shares (₹{position_value:,.0f})")
        
        return position
    
    def execute_exit(
        self,
        position: Position,
        exit_date: datetime,
        exit_price: float,
        exit_reason: str
    ) -> Dict:
        """
        Execute exit for a position
        
        Returns:
            Trade dictionary
        """
        # Apply slippage
        actual_exit = self.apply_slippage(exit_price, "SELL")
        
        # Calculate costs
        position_value = position.shares * position.entry_price
        costs = calculate_transaction_costs(position_value, is_intraday=False)
        
        # Calculate P&L
        pnl_data = position.calculate_pnl(actual_exit, costs)
        
        # Return capital
        exit_value = position.shares * actual_exit
        self.capital += exit_value
        
        # Create trade record
        trade = {
            'ticker': position.ticker,
            'pattern_id': position.pattern_id,
            'entry_date': position.entry_date,
            'entry_price': position.entry_price,
            'exit_date': exit_date,
            'exit_price': actual_exit,
            'shares': position.shares,
            'holding_days': position.days_held,
            'exit_reason': exit_reason,
            'gross_pnl': pnl_data['gross_pnl'],
            'costs': pnl_data['costs'],
            'net_pnl': pnl_data['net_pnl'],
            'net_pnl_pct': pnl_data['net_pnl_pct'],
            'max_gain_pct': position.max_gain_pct,
            'max_loss_pct': position.max_loss_pct,
        }
        
        logger.info(f"EXIT: {position.ticker} @ ₹{actual_exit:.2f} | {exit_reason} | P&L: ₹{pnl_data['net_pnl']:,.0f} ({pnl_data['net_pnl_pct']:.2f}%)")
        
        # Remove position
        self.positions.remove(position)
        
        # Add to results
        self.results.add_trade(trade)
        
        return trade
    
    def run_backtest(
        self,
        signals: pd.DataFrame,
        market_data: Dict[str, pd.DataFrame]
    ) -> BacktestResult:
        """
        Run backtest on signals
        
        Args:
            signals: DataFrame with columns [date, ticker, entry_price, stop_loss, target, pattern_id]
            market_data: Dictionary of {ticker: DataFrame with OHLCV}
        
        Returns:
            BacktestResult object
        """
        logger.info("="*60)
        logger.info("Starting Backtest")
        logger.info("="*60)
        
        # Sort signals by date
        signals = signals.sort_values('date').reset_index(drop=True)
        
        # Get date range
        start_date = signals['date'].min()
        end_date = signals['date'].max()
        
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"Signals: {len(signals)}")
        logger.info(f"Initial Capital: ₹{self.initial_capital:,.0f}")
        
        # Iterate through each trading day
        current_date = start_date
        
        while current_date <= end_date:
            if not is_trading_day(current_date):
                current_date += timedelta(days=1)
                continue
            
            # Process new signals for today
            today_signals = signals[signals['date'] == current_date]
            
            for _, signal in today_signals.iterrows():
                ticker = signal['ticker']
                
                # Check if we have data for this ticker
                if ticker not in market_data:
                    continue
                
                # Entry at next day's open
                next_date = current_date + timedelta(days=1)
                df = market_data[ticker]
                df['date'] = pd.to_datetime(df['date'])
                
                next_day_data = df[df['date'] == next_date]
                if next_day_data.empty:
                    continue
                
                entry_price = next_day_data.iloc[0]['open']
                
                # Execute entry
                self.execute_entry(
                    ticker=ticker,
                    entry_date=next_date,
                    entry_price=entry_price,
                    stop_loss=signal['stop_loss'],
                    target=signal['target'],
                    pattern_id=signal.get('pattern_id', '')
                )
            
            # Update and check existing positions
            positions_to_exit = []
            
            for position in self.positions:
                ticker = position.ticker
                
                if ticker not in market_data:
                    continue
                
                df = market_data[ticker]
                df['date'] = pd.to_datetime(df['date'])
                
                # Get today's bar
                today_bar = df[df['date'] == current_date]
                if today_bar.empty:
                    continue
                
                bar_dict = today_bar.iloc[0].to_dict()
                
                # Update position
                position.update(bar_dict)
                
                # Check exit conditions
                should_exit, exit_reason, exit_price = position.check_exit(
                    bar_dict,
                    max_days=self.config['max_holding_days']
                )
                
                if should_exit:
                    positions_to_exit.append((position, exit_reason, exit_price))
            
            # Execute exits
            for position, reason, price in positions_to_exit:
                self.execute_exit(position, current_date, price, reason)
            
            # Record equity curve
            total_equity = self.capital + sum(
                pos.shares * pos.current_price for pos in self.positions
            )
            self.results.equity_curve.append(total_equity)
            self.results.dates.append(current_date)
            
            current_date += timedelta(days=1)
        
        # Close any remaining positions
        for position in list(self.positions):
            ticker = position.ticker
            df = market_data[ticker]
            final_price = df.iloc[-1]['close']
            self.execute_exit(position, end_date, final_price, "END_OF_BACKTEST")
        
        # Calculate final metrics
        metrics = self.results.calculate_metrics()
        
        logger.info("="*60)
        logger.info("Backtest Complete!")
        logger.info("="*60)
        logger.info(f"Total Trades: {metrics.get('total_trades', 0)}")
        logger.info(f"Win Rate: {metrics.get('win_rate', 0):.2%}")
        logger.info(f"Total P&L: ₹{metrics.get('total_pnl', 0):,.0f}")
        logger.info(f"Final Equity: ₹{metrics.get('final_equity', 0):,.0f}")
        logger.info(f"Max Drawdown: {metrics.get('max_drawdown', 0):.2f}%")
        logger.info("="*60)
        
        return self.results

if __name__ == "__main__":
    print("Realistic Backtesting Engine for Indian Markets")
    print("=" * 50)
    print(f"Configuration: {BACKTEST_CONFIG}")

