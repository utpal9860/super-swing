"""
BTST Exit Manager - Next-Day Exit Logic

This module handles the next-day exit management for BTST trades.
Runs between 9:15-9:45 AM IST to monitor and exit positions.

Exit Rules:
1. Take profit at 3-5% target
2. Exit if price falls below EMA(44) on first 15-min candle
3. Mandatory exit by 9:45 AM regardless of P&L
4. Stop loss if price breaks below breakout zone
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
from datetime import datetime, time
import yfinance as yf
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class BTSTExitManager:
    """
    Manages next-day exits for BTST positions
    """
    
    def __init__(self):
        self.exit_window_start = time(9, 15)  # 9:15 AM IST
        self.exit_window_end = time(9, 45)     # 9:45 AM IST
        self.ema_period = 44
        
        # Paths
        self.trades_dir = Path("webapp/data/trades")
        self.trades_dir.mkdir(parents=True, exist_ok=True)
    
    def monitor_and_exit(self, username: str = "demo_user", silent: bool = False) -> Dict:
        """
        Monitor BTST positions and execute exits
        
        Args:
            username: User identifier
            silent: If True, suppress console output
        
        Returns:
            Dict with exit summary
        """
        if not self._is_exit_window():
            if not silent:
                print("⚠️  Not in exit window (9:15-9:45 AM IST)")
            return {'status': 'outside_window', 'exits': []}
        
        # Load open BTST positions
        positions = self._load_btst_positions(username)
        
        if not positions:
            if not silent:
                print("ℹ️  No open BTST positions to monitor")
            return {'status': 'no_positions', 'exits': []}
        
        if not silent:
            print(f"\n{'='*70}")
            print(f"🎯 BTST EXIT MANAGER")
            print(f"{'='*70}")
            print(f"Monitoring {len(positions)} BTST position(s)")
            print(f"Time: {datetime.now().strftime('%H:%M:%S IST')}")
            print(f"{'='*70}\n")
        
        exits = []
        
        for position in positions:
            exit_action = self._evaluate_exit(position, silent=silent)
            
            if exit_action:
                # Execute exit
                exit_result = self._execute_exit(position, exit_action, username)
                exits.append(exit_result)
                
                if not silent:
                    self._print_exit_summary(exit_result)
        
        if not silent:
            print(f"\n{'='*70}")
            print(f"✅ Monitoring complete: {len(exits)} position(s) exited")
            print(f"{'='*70}\n")
        
        return {
            'status': 'success',
            'monitored': len(positions),
            'exited': len(exits),
            'exits': exits
        }
    
    def _evaluate_exit(self, position: Dict, silent: bool = False) -> Optional[Dict]:
        """
        Evaluate if position should be exited
        
        Returns:
            Dict with exit decision or None to hold
        """
        symbol = position['symbol']
        entry_price = position['entry_price']
        stop_loss = position['stop_loss']
        target = position['target']
        
        try:
            # Fetch current price and 5-min data
            df = self._fetch_intraday_data(symbol, interval='5m', days=1)
            
            if df is None or len(df) < 10:
                # Cannot fetch data, exit at market (safety)
                return {
                    'action': 'exit_market',
                    'reason': 'data_unavailable',
                    'exit_price': None
                }
            
            current_price = float(df['close'].iloc[-1])
            
            # 1. Check if target hit
            if current_price >= target:
                return {
                    'action': 'exit_market',
                    'reason': 'target_hit',
                    'exit_price': current_price,
                    'pnl_pct': ((current_price - entry_price) / entry_price) * 100
                }
            
            # 2. Check if stop loss hit
            if current_price <= stop_loss:
                return {
                    'action': 'exit_market',
                    'reason': 'stop_loss_hit',
                    'exit_price': current_price,
                    'pnl_pct': ((current_price - entry_price) / entry_price) * 100
                }
            
            # 3. Check first 15-min candle EMA(44) violation
            if self._check_ema_violation(df, current_price):
                return {
                    'action': 'exit_market',
                    'reason': 'ema_violation',
                    'exit_price': current_price,
                    'pnl_pct': ((current_price - entry_price) / entry_price) * 100
                }
            
            # 4. Check if time to force exit (9:45 AM approaching)
            now = datetime.now().time()
            force_exit_time = time(9, 43)  # Exit by 9:43 to ensure fill before 9:45
            
            if now >= force_exit_time:
                return {
                    'action': 'exit_market',
                    'reason': 'time_stop',
                    'exit_price': current_price,
                    'pnl_pct': ((current_price - entry_price) / entry_price) * 100
                }
            
            # 5. Check if breakout zone violated
            resistance_zone = position.get('resistance_zone')
            if resistance_zone and current_price < resistance_zone:
                return {
                    'action': 'exit_market',
                    'reason': 'breakout_failed',
                    'exit_price': current_price,
                    'pnl_pct': ((current_price - entry_price) / entry_price) * 100
                }
            
            # Hold position - no exit criteria met yet
            if not silent:
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                print(f"📊 {symbol}: ₹{current_price:.2f} ({pnl_pct:+.2f}%) - HOLDING")
            
            return None
            
        except Exception as e:
            if not silent:
                print(f"❌ Error evaluating {symbol}: {str(e)[:50]}")
            # On error, exit at market for safety
            return {
                'action': 'exit_market',
                'reason': 'error',
                'exit_price': None
            }
    
    def _check_ema_violation(self, df: pd.DataFrame, current_price: float) -> bool:
        """Check if first 15-min candle closed below EMA(44)"""
        try:
            if len(df) < self.ema_period:
                return False
            
            # Calculate EMA(44) on 5-min data
            ema_44 = df['close'].ewm(span=self.ema_period, adjust=False).mean()
            current_ema = float(ema_44.iloc[-1])
            
            # Check if current price is below EMA
            return current_price < current_ema
            
        except Exception:
            return False
    
    def _execute_exit(self, position: Dict, exit_action: Dict, username: str) -> Dict:
        """
        Execute exit for position
        
        Args:
            position: Position dict
            exit_action: Exit action dict
            username: User identifier
        
        Returns:
            Exit result dict
        """
        symbol = position['symbol']
        entry_price = position['entry_price']
        exit_price = exit_action.get('exit_price', entry_price)  # Fallback to entry if no price
        reason = exit_action['reason']
        
        # Calculate P&L
        pnl_pct = exit_action.get('pnl_pct', 0)
        shares = position.get('shares', 0)
        pnl_amount = (exit_price - entry_price) * shares if exit_price else 0
        
        # Create exit result
        exit_result = {
            'symbol': symbol,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'exit_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'reason': reason,
            'pnl_pct': pnl_pct,
            'pnl_amount': pnl_amount,
            'shares': shares,
            'holding_period': 'overnight',
            'strategy': 'improved_btst'
        }
        
        # Update position status in trades file
        self._update_trade_status(position['trade_id'], exit_result, username)
        
        return exit_result
    
    def _load_btst_positions(self, username: str) -> List[Dict]:
        """Load open BTST positions for user"""
        try:
            trades_file = self.trades_dir / f"{username}_trades.json"
            
            if not trades_file.exists():
                return []
            
            with open(trades_file, 'r') as f:
                all_trades = json.load(f)
            
            # Filter for open BTST trades
            btst_positions = [
                trade for trade in all_trades
                if trade.get('strategy') == 'improved_btst'
                and trade.get('status') == 'open'
                and self._is_btst_trade(trade)
            ]
            
            return btst_positions
            
        except Exception as e:
            print(f"Error loading BTST positions: {e}")
            return []
    
    def _is_btst_trade(self, trade: Dict) -> bool:
        """Check if trade is a BTST trade (entered yesterday)"""
        try:
            entry_date = datetime.strptime(trade['entry_date'], '%Y-%m-%d').date()
            today = datetime.now().date()
            
            # BTST trade is entered previous trading day
            return entry_date < today
            
        except Exception:
            return False
    
    def _update_trade_status(self, trade_id: str, exit_result: Dict, username: str):
        """Update trade status to closed"""
        try:
            trades_file = self.trades_dir / f"{username}_trades.json"
            
            if not trades_file.exists():
                return
            
            with open(trades_file, 'r') as f:
                all_trades = json.load(f)
            
            # Update the specific trade
            for trade in all_trades:
                if trade.get('trade_id') == trade_id:
                    trade['status'] = 'closed'
                    trade['exit_price'] = exit_result['exit_price']
                    trade['exit_date'] = exit_result['exit_time']
                    trade['exit_reason'] = exit_result['reason']
                    trade['pnl'] = exit_result['pnl_amount']
                    trade['pnl_pct'] = exit_result['pnl_pct']
                    break
            
            # Save updated trades
            with open(trades_file, 'w') as f:
                json.dump(all_trades, f, indent=2)
                
        except Exception as e:
            print(f"Error updating trade status: {e}")
    
    def _fetch_intraday_data(self, symbol: str, interval: str = '5m', days: int = 1) -> Optional[pd.DataFrame]:
        """Fetch intraday data"""
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
    
    def _is_exit_window(self) -> bool:
        """Check if current time is within exit window"""
        try:
            now = datetime.now().time()
            return self.exit_window_start <= now <= self.exit_window_end
        except:
            return False
    
    def _print_exit_summary(self, exit_result: Dict):
        """Print exit summary"""
        symbol = exit_result['symbol']
        entry = exit_result['entry_price']
        exit_price = exit_result['exit_price']
        reason = exit_result['reason']
        pnl_pct = exit_result['pnl_pct']
        pnl_amount = exit_result['pnl_amount']
        
        emoji = "🎯" if pnl_pct > 0 else "🛑"
        color_start = "\033[92m" if pnl_pct > 0 else "\033[91m"
        color_end = "\033[0m"
        
        print(f"\n{emoji} EXIT: {symbol}")
        print(f"   Entry: ₹{entry:.2f} → Exit: ₹{exit_price:.2f}")
        print(f"   Reason: {reason.replace('_', ' ').title()}")
        print(f"   P&L: {color_start}{pnl_pct:+.2f}% (₹{pnl_amount:+,.2f}){color_end}")


def run_btst_exit_monitor(username: str = "demo_user", silent: bool = False):
    """
    Standalone function to run BTST exit monitor
    
    This should be scheduled as a cron job or run manually during 9:15-9:45 AM IST
    """
    manager = BTSTExitManager()
    result = manager.monitor_and_exit(username=username, silent=silent)
    return result


if __name__ == "__main__":
    # Test the exit manager
    print("Testing BTST Exit Manager...")
    result = run_btst_exit_monitor(username="demo_user", silent=False)
    print(f"\nResult: {result}")











