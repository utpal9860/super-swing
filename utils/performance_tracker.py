"""
Strategy Performance Tracker

Tracks and analyzes performance metrics for trading strategies:
- Trade outcomes (win/loss)
- Win rate, average return, profit factor
- R:R ratio, expectancy
- Sharpe ratio, max drawdown
- Strategy comparison
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


@dataclass
class TradeResult:
    """Individual trade result"""
    trade_id: str
    symbol: str
    strategy: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    shares: int
    profit_loss: float
    profit_loss_pct: float
    holding_days: int
    exit_reason: str  # 'target', 'stop_loss', 'time_stop', 'manual'
    
    def to_dict(self):
        return asdict(self)


@dataclass
class StrategyMetrics:
    """Performance metrics for a strategy"""
    strategy_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # Return metrics
    total_profit_loss: float
    avg_win: float
    avg_loss: float
    avg_return: float
    best_trade: float
    worst_trade: float
    
    # Risk metrics
    profit_factor: float  # Total wins / Total losses
    expectancy: float  # (Win% * Avg Win) - (Loss% * Avg Loss)
    risk_reward_ratio: float
    
    # Advanced metrics
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_streak: int = 0
    loss_streak: int = 0
    
    # Time metrics
    avg_holding_days: float = 0
    
    def to_dict(self):
        return asdict(self)


class StrategyPerformanceTracker:
    """Track and analyze strategy performance"""
    
    def __init__(self, data_dir: str = "data/performance"):
        """
        Initialize tracker
        
        Args:
            data_dir: Directory to store performance data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.trades_file = self.data_dir / "trade_results.json"
        self.metrics_file = self.data_dir / "strategy_metrics.json"
        
        # Load existing data
        self.trades = self._load_trades()
        self.metrics_cache = {}
    
    def add_trade_result(self, trade: TradeResult) -> None:
        """
        Add a completed trade to the tracker
        
        Args:
            trade: TradeResult object
        """
        self.trades.append(trade.to_dict())
        self._save_trades()
        
        # Invalidate cache for this strategy
        if trade.strategy in self.metrics_cache:
            del self.metrics_cache[trade.strategy]
    
    def add_trade_from_dict(self, trade_data: Dict) -> None:
        """
        Add a trade from dictionary (from paper trading system)
        
        Args:
            trade_data: Dictionary with trade details
        """
        # Calculate profit/loss
        entry_price = float(trade_data['entry_price'])
        exit_price = float(trade_data.get('exit_price', entry_price))
        shares = int(trade_data.get('shares', 0))
        
        profit_loss = (exit_price - entry_price) * shares
        profit_loss_pct = ((exit_price - entry_price) / entry_price) * 100
        
        # Calculate holding days
        entry_date = datetime.fromisoformat(trade_data['entry_date'].replace(' ', 'T'))
        exit_date = datetime.fromisoformat(trade_data.get('exit_date', trade_data['entry_date']).replace(' ', 'T'))
        holding_days = (exit_date - entry_date).days
        
        trade = TradeResult(
            trade_id=trade_data.get('id', f"TRADE_{datetime.now().timestamp()}"),
            symbol=trade_data['symbol'],
            strategy=trade_data.get('strategy', 'unknown'),
            entry_date=trade_data['entry_date'],
            entry_price=entry_price,
            exit_date=trade_data.get('exit_date', trade_data['entry_date']),
            exit_price=exit_price,
            shares=shares,
            profit_loss=profit_loss,
            profit_loss_pct=profit_loss_pct,
            holding_days=holding_days,
            exit_reason=trade_data.get('exit_reason', 'manual')
        )
        
        self.add_trade_result(trade)
    
    def calculate_metrics(self, strategy: str) -> Optional[StrategyMetrics]:
        """
        Calculate performance metrics for a strategy
        
        Args:
            strategy: Strategy name
            
        Returns:
            StrategyMetrics object or None if no trades
        """
        # Check cache
        if strategy in self.metrics_cache:
            return self.metrics_cache[strategy]
        
        # Filter trades for this strategy
        strategy_trades = [t for t in self.trades if t['strategy'] == strategy]
        
        if not strategy_trades:
            return None
        
        # Calculate metrics
        total_trades = len(strategy_trades)
        wins = [t for t in strategy_trades if t['profit_loss'] > 0]
        losses = [t for t in strategy_trades if t['profit_loss'] <= 0]
        
        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Return metrics
        total_pl = sum(t['profit_loss'] for t in strategy_trades)
        avg_win = sum(t['profit_loss'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['profit_loss'] for t in losses) / len(losses) if losses else 0
        avg_return = sum(t['profit_loss_pct'] for t in strategy_trades) / total_trades if total_trades > 0 else 0
        
        best_trade = max((t['profit_loss_pct'] for t in strategy_trades), default=0)
        worst_trade = min((t['profit_loss_pct'] for t in strategy_trades), default=0)
        
        # Risk metrics
        total_wins = sum(t['profit_loss'] for t in wins)
        total_losses = abs(sum(t['profit_loss'] for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        win_pct = win_rate / 100
        loss_pct = 1 - win_pct
        expectancy = (win_pct * avg_win) - (loss_pct * abs(avg_loss))
        
        # Calculate average R:R
        rr_ratios = []
        for t in strategy_trades:
            if t['profit_loss'] > 0:
                # For wins, R:R is actual_gain / risk_taken
                rr_ratios.append(abs(t['profit_loss_pct']))
            else:
                # For losses, it's 0
                rr_ratios.append(0)
        
        avg_rr = sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0
        
        # Streaks
        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        
        for t in sorted(strategy_trades, key=lambda x: x['exit_date']):
            if t['profit_loss'] > 0:
                if current_streak >= 0:
                    current_streak += 1
                else:
                    current_streak = 1
                max_win_streak = max(max_win_streak, current_streak)
            else:
                if current_streak <= 0:
                    current_streak -= 1
                else:
                    current_streak = -1
                max_loss_streak = max(max_loss_streak, abs(current_streak))
        
        # Time metrics
        avg_holding = sum(t['holding_days'] for t in strategy_trades) / total_trades if total_trades > 0 else 0
        
        # Calculate Sharpe Ratio (simplified - daily returns / std dev)
        returns = [t['profit_loss_pct'] for t in strategy_trades]
        sharpe_ratio = None
        if len(returns) > 1:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
            std_dev = variance ** 0.5
            sharpe_ratio = (mean_return / std_dev) if std_dev > 0 else 0
        
        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(strategy_trades)
        
        metrics = StrategyMetrics(
            strategy_name=strategy,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_profit_loss=total_pl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_return=avg_return,
            best_trade=best_trade,
            worst_trade=worst_trade,
            profit_factor=profit_factor,
            expectancy=expectancy,
            risk_reward_ratio=avg_rr,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_streak=max_win_streak,
            loss_streak=max_loss_streak,
            avg_holding_days=avg_holding
        )
        
        # Cache it
        self.metrics_cache[strategy] = metrics
        
        return metrics
    
    def get_all_strategies(self) -> List[str]:
        """Get list of all strategies with trades"""
        return list(set(t['strategy'] for t in self.trades))
    
    def get_strategy_comparison(self) -> pd.DataFrame:
        """
        Compare all strategies side-by-side
        
        Returns:
            DataFrame with strategy comparison
        """
        strategies = self.get_all_strategies()
        
        if not strategies:
            return pd.DataFrame()
        
        data = []
        for strategy in strategies:
            metrics = self.calculate_metrics(strategy)
            if metrics:
                data.append(metrics.to_dict())
        
        df = pd.DataFrame(data)
        
        # Sort by total return
        if not df.empty and 'total_profit_loss' in df.columns:
            df = df.sort_values('total_profit_loss', ascending=False)
        
        return df
    
    def get_trades_by_strategy(self, strategy: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get trades for a specific strategy
        
        Args:
            strategy: Strategy name
            limit: Maximum number of trades to return (most recent first)
            
        Returns:
            List of trade dictionaries
        """
        trades = [t for t in self.trades if t['strategy'] == strategy]
        trades = sorted(trades, key=lambda x: x['exit_date'], reverse=True)
        
        if limit:
            trades = trades[:limit]
        
        return trades
    
    def get_recent_trades(self, days: int = 30, strategy: Optional[str] = None) -> List[Dict]:
        """
        Get recent trades across all or specific strategy
        
        Args:
            days: Number of days to look back
            strategy: Optional strategy filter
            
        Returns:
            List of trade dictionaries
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        trades = [t for t in self.trades if t['exit_date'] >= cutoff_date]
        
        if strategy:
            trades = [t for t in trades if t['strategy'] == strategy]
        
        return sorted(trades, key=lambda x: x['exit_date'], reverse=True)
    
    def _calculate_max_drawdown(self, trades: List[Dict]) -> float:
        """Calculate maximum drawdown percentage"""
        if not trades:
            return 0.0
        
        # Sort by exit date
        sorted_trades = sorted(trades, key=lambda x: x['exit_date'])
        
        # Calculate cumulative P&L
        cumulative_pl = []
        total = 0
        for t in sorted_trades:
            total += t['profit_loss']
            cumulative_pl.append(total)
        
        # Find max drawdown
        max_dd = 0
        peak = cumulative_pl[0]
        
        for pl in cumulative_pl:
            if pl > peak:
                peak = pl
            
            dd = ((peak - pl) / abs(peak)) * 100 if peak != 0 else 0
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    def _load_trades(self) -> List[Dict]:
        """Load trades from file"""
        if self.trades_file.exists():
            try:
                with open(self.trades_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_trades(self) -> None:
        """Save trades to file"""
        with open(self.trades_file, 'w') as f:
            json.dump(self.trades, f, indent=2)
    
    def export_metrics(self, output_file: str) -> None:
        """
        Export strategy metrics to CSV
        
        Args:
            output_file: Output CSV filename
        """
        df = self.get_strategy_comparison()
        if not df.empty:
            df.to_csv(output_file, index=False)
            print(f"Exported metrics to {output_file}")
        else:
            print("No metrics to export")


# Example usage
if __name__ == "__main__":
    tracker = StrategyPerformanceTracker()
    
    # Example: Add sample trades
    sample_trades = [
        {
            'id': 'TRADE_1',
            'symbol': 'RELIANCE.NS',
            'strategy': 'momentum_btst',
            'entry_date': '2025-10-20 09:15:00',
            'entry_price': 2500,
            'exit_date': '2025-10-22 15:30:00',
            'exit_price': 2600,
            'shares': 10,
            'exit_reason': 'target'
        },
        {
            'id': 'TRADE_2',
            'symbol': 'TCS.NS',
            'strategy': 'swing_supertrend',
            'entry_date': '2025-10-15 09:15:00',
            'entry_price': 3000,
            'exit_date': '2025-10-25 15:30:00',
            'exit_price': 3150,
            'shares': 5,
            'exit_reason': 'target'
        }
    ]
    
    for trade in sample_trades:
        tracker.add_trade_from_dict(trade)
    
    # Get metrics
    print("\n" + "="*70)
    print("STRATEGY PERFORMANCE TRACKER")
    print("="*70 + "\n")
    
    for strategy in tracker.get_all_strategies():
        metrics = tracker.calculate_metrics(strategy)
        if metrics:
            print(f"\nStrategy: {metrics.strategy_name}")
            print(f"  Total Trades: {metrics.total_trades}")
            print(f"  Win Rate: {metrics.win_rate:.1f}%")
            print(f"  Total P&L: ₹{metrics.total_profit_loss:,.0f}")
            print(f"  Avg Return: {metrics.avg_return:.2f}%")
            print(f"  Profit Factor: {metrics.profit_factor:.2f}")
            print(f"  Expectancy: ₹{metrics.expectancy:.0f}")
    
    # Export comparison
    df = tracker.get_strategy_comparison()
    if not df.empty:
        print("\n" + "="*70)
        print("STRATEGY COMPARISON")
        print("="*70)
        print(df[['strategy_name', 'total_trades', 'win_rate', 'total_profit_loss', 'avg_return', 'profit_factor']].to_string(index=False))

