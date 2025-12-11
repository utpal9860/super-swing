"""
SL Strategy Backtesting Script
Tests different SL levels on historical trades to find optimal strategy
"""
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Add webapp to path
sys.path.insert(0, str(Path(__file__).parent))

# Import only what we need without FastAPI dependencies
import logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise

try:
    from openchart import NSEData
    OPENCHART_AVAILABLE = True
except ImportError:
    OPENCHART_AVAILABLE = False
    print("⚠️  openchart not available")

# Copy construct_nse_option_symbol function to avoid FastAPI dependency
def construct_nse_option_symbol(symbol: str, strike: float, option_type: str, expiry_date_str: str) -> Optional[str]:
    """Construct NSE option symbol format"""
    try:
        INDEX_SYMBOLS = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'NIFTYNXT50', 'SENSEX', 'BANKEX', 'SENSEX50']
        INDEX_EXPIRY_SCHEDULE = {
            'NIFTY': (1, 'weekly'),
            'BANKNIFTY': (1, 'monthly'),
            'FINNIFTY': (1, 'monthly'),
            'MIDCPNIFTY': (1, 'monthly'),
            'NIFTYNXT50': (1, 'monthly'),
            'SENSEX': (3, 'weekly'),
            'BANKEX': (1, 'monthly'),
            'SENSEX50': (1, 'monthly'),
        }
        
        expiry_date = datetime.strptime(expiry_date_str, '%d-%b-%Y')
        year_short = expiry_date.strftime('%y')
        month = expiry_date.strftime('%b').upper()
        day = expiry_date.strftime('%d')
        strike_int = int(round(float(strike)))
        opt_type = option_type.upper()
        
        symbol_upper = symbol.upper().replace(".NS", "")
        is_index = symbol_upper in INDEX_SYMBOLS
        is_weekly = False
        if is_index:
            expiry_day, expiry_type = INDEX_EXPIRY_SCHEDULE.get(symbol_upper, (0, 'monthly'))
            is_weekly = expiry_type == 'weekly'
        
        if is_weekly:
            constructed_symbol = f"{symbol_upper}{day}{month}{strike_int}{opt_type}"
        else:
            constructed_symbol = f"{symbol_upper}{year_short}{month}{strike_int}{opt_type}"
        
        return constructed_symbol
    except Exception as e:
        print(f"Failed to construct option symbol: {e}")
        return None

class SLBacktester:
    def __init__(self, trades_file: str):
        """Initialize backtester with trades data"""
        self.trades_file = trades_file
        self.trades = self.load_trades()
        self.results = {}
        self._openchart_instance = None
    
    def get_openchart_instance(self):
        """Get or create openchart instance"""
        if not OPENCHART_AVAILABLE:
            return None
        if self._openchart_instance is None:
            try:
                self._openchart_instance = NSEData()
                self._openchart_instance.download()
            except Exception as e:
                print(f"Failed to initialize openchart: {e}")
                return None
        return self._openchart_instance
    
    def fetch_option_historical_ohlc(self, symbol: str, strike: float, option_type: str, 
                                     expiry_date_str: str, start_date: datetime) -> Optional[Dict]:
        """Fetch historical OHLC data for option"""
        if not OPENCHART_AVAILABLE:
            return None
        
        symbol_upper = symbol.upper().replace(".NS", "")
        is_bse_index = symbol_upper in ['SENSEX', 'BANKEX', 'SENSEX50']
        
        if is_bse_index:
            return None
        
        try:
            nse = self.get_openchart_instance()
            if nse is None:
                return None
            
            option_symbol = construct_nse_option_symbol(symbol, strike, option_type, expiry_date_str)
            if not option_symbol:
                return None
            
            search_data = nse.nfo_data
            option_match = search_data[search_data['Symbol'] == option_symbol]
            
            if option_match.empty:
                strike_str = str(int(strike))
                search_pattern = f".*{strike_str}.*{option_type.upper()}"
                option_match = search_data[
                    (search_data['Symbol'].str.contains(symbol.upper(), case=False, na=False) &
                     search_data['Symbol'].str.contains(search_pattern, case=False, regex=True, na=False))
                ]
            
            if option_match.empty:
                return None
            
            option_info = option_match.iloc[0]
            scrip_code = int(option_info['ScripCode'])
            
            end_date = datetime.now()
            start_dt = start_date - timedelta(days=1)
            max_days_back = 30
            if (end_date - start_dt).days > max_days_back:
                start_dt = end_date - timedelta(days=max_days_back)
            
            import json
            payload = {
                'exch': 'D',
                'instrType': 'D',
                'scripCode': scrip_code,
                'ulToken': scrip_code,
                'fromDate': int(start_dt.timestamp()),
                'toDate': int(end_date.timestamp()),
                'timeInterval': '1',
                'chartPeriod': 'D',
                'chartStart': 0
            }
            
            nse.session.get('https://www.nseindia.com', timeout=5)
            response = nse.session.post(
                'https://charting.nseindia.com//Charts/symbolhistoricaldata/',
                data=json.dumps(payload),
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('s') != 'Ok' or not data.get('data'):
                return None
            
            ohlc_list = []
            max_high = start_date.timestamp()  # Will be updated
            min_low = float('inf')
            
            for row in data['data']:
                timestamp = row[0] / 1000
                dt = datetime.fromtimestamp(timestamp)
                open_price = row[1]
                high = row[2]
                low = row[3]
                close = row[4]
                
                ohlc_list.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close
                })
                
                if high > max_high:
                    max_high = high
                if low < min_low:
                    min_low = low
            
            return {
                'data': ohlc_list,
                'max_high': max_high if max_high != start_date.timestamp() else None,
                'min_low': min_low if min_low != float('inf') else None,
                'current_price': ohlc_list[-1]['close'] if ohlc_list else None
            }
        except Exception as e:
            print(f"Error fetching OHLC: {e}")
            return None
        
    def load_trades(self) -> List[Dict]:
        """Load trades from JSON file"""
        with open(self.trades_file, 'r') as f:
            return json.load(f)
    
    def parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime"""
        try:
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d')
            except:
                return datetime.now()
    
    def simulate_sl(self, 
                   entry_price: float,
                   target_price: float,
                   sl_price: float,
                   ohlc_data: List[Dict]) -> Dict:
        """
        Simulate trade with SL and return result
        
        Args:
            entry_price: Entry price
            target_price: Target price
            sl_price: Stop loss price
            ohlc_data: List of OHLC data points (daily)
            
        Returns:
            Dict with:
            - hit_sl: bool (True if SL hit before target)
            - hit_target: bool (True if target hit)
            - exit_price: float (price at exit)
            - exit_reason: str ('sl' or 'target')
            - max_drawdown: float (max % drawdown from entry)
            - days_to_exit: int (days from entry to exit)
        """
        max_drawdown = 0.0
        hit_sl = False
        hit_target = False
        exit_price = entry_price
        exit_reason = None
        days_to_exit = 0
        
        # Sort OHLC data by date (oldest first)
        sorted_data = sorted(ohlc_data, key=lambda x: x.get('date', ''))
        
        for i, day_data in enumerate(sorted_data):
            high = day_data.get('high', entry_price)
            low = day_data.get('low', entry_price)
            close = day_data.get('close', entry_price)
            
            # Calculate drawdown for this day
            day_drawdown = ((entry_price - low) / entry_price) * 100
            max_drawdown = max(max_drawdown, day_drawdown)
            
            # Check if SL hit (check low first)
            if low <= sl_price:
                hit_sl = True
                exit_price = sl_price
                exit_reason = 'sl'
                days_to_exit = i + 1
                break
            
            # Check if target hit (check high)
            if high >= target_price:
                hit_target = True
                exit_price = target_price
                exit_reason = 'target'
                days_to_exit = i + 1
                break
        
        # If neither hit, use last close price
        if not hit_sl and not hit_target and sorted_data:
            exit_price = sorted_data[-1].get('close', entry_price)
            exit_reason = 'end_of_data'
            days_to_exit = len(sorted_data)
        
        return {
            'hit_sl': hit_sl,
            'hit_target': hit_target,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'max_drawdown': max_drawdown,
            'days_to_exit': days_to_exit
        }
    
    def backtest_trade(self, trade: Dict, sl_percentage: float) -> Optional[Dict]:
        """
        Backtest a single trade with given SL percentage
        
        Args:
            trade: Trade dictionary
            sl_percentage: SL percentage (e.g., 25.0 for 25%)
            
        Returns:
            Backtest result dict or None if data unavailable
        """
        # Only test closed trades
        if trade.get('status') != 'closed':
            return None
        
        # Get trade details
        entry_price = float(trade.get('entry_price', 0))
        target_price = float(trade.get('target', 0))
        entry_date_str = trade.get('entry_date')
        exit_date_str = trade.get('exit_date')
        
        if not entry_price or not target_price or not entry_date_str:
            return None
        
        # Calculate SL price
        sl_price = entry_price * (1 - sl_percentage / 100)
        
        # Get option details
        symbol = trade.get('symbol', '').replace('.NS', '')
        strike = trade.get('option_strike')
        option_type = trade.get('option_type')
        expiry_month = trade.get('option_expiry_month')
        
        if not strike or not option_type or not expiry_month:
            return None
        
        # Parse dates
        try:
            entry_date = self.parse_date(entry_date_str)
            exit_date = self.parse_date(exit_date_str) if exit_date_str else datetime.now()
        except Exception as e:
            print(f"Error parsing dates for trade {trade.get('id')}: {e}")
            return None
        
        # Fetch historical OHLC data
        print(f"\n📊 Backtesting: {symbol} {strike} {option_type} | Entry: ₹{entry_price:.2f}, Target: ₹{target_price:.2f}, SL: {sl_percentage}% (₹{sl_price:.2f})")
        print(f"   Date range: {entry_date.strftime('%Y-%m-%d')} to {exit_date.strftime('%Y-%m-%d')}")
        
        try:
            hist_ohlc = self.fetch_option_historical_ohlc(
                symbol=symbol,
                strike=float(strike),
                option_type=option_type,
                expiry_date_str=expiry_month,
                start_date=entry_date
            )
            
            if not hist_ohlc or not hist_ohlc.get('data'):
                print(f"   ⚠️  No historical data available")
                return None
            
            # Filter OHLC data to entry_date to exit_date range
            ohlc_data = hist_ohlc.get('data', [])
            filtered_data = []
            
            for day_data in ohlc_data:
                day_date_str = day_data.get('date', '')
                try:
                    day_date = datetime.strptime(day_date_str, '%Y-%m-%d')
                    if entry_date.date() <= day_date.date() <= exit_date.date():
                        filtered_data.append(day_data)
                except:
                    continue
            
            if not filtered_data:
                print(f"   ⚠️  No data in date range")
                return None
            
            print(f"   ✅ Fetched {len(filtered_data)} days of OHLC data")
            
            # Simulate trade with SL
            result = self.simulate_sl(
                entry_price=entry_price,
                target_price=target_price,
                sl_price=sl_price,
                ohlc_data=filtered_data
            )
            
            # Calculate P&L
            lot_size = trade.get('lot_size', 1)
            shares = trade.get('shares', 1)
            quantity = shares * lot_size
            
            gross_pnl = (result['exit_price'] - entry_price) * quantity
            brokerage = 40.0  # Buy + Sell
            net_pnl = gross_pnl - brokerage
            
            result['trade_id'] = trade.get('id')
            result['symbol'] = symbol
            result['entry_price'] = entry_price
            result['target_price'] = target_price
            result['sl_price'] = sl_price
            result['sl_percentage'] = sl_percentage
            result['gross_pnl'] = gross_pnl
            result['net_pnl'] = net_pnl
            result['quantity'] = quantity
            result['actual_exit_reason'] = trade.get('exit_reason')
            result['actual_net_pnl'] = trade.get('net_pnl', 0)
            
            # Print result
            if result['hit_sl']:
                print(f"   ❌ SL HIT at ₹{sl_price:.2f} on day {result['days_to_exit']} | Max DD: {result['max_drawdown']:.2f}% | P&L: ₹{net_pnl:.2f}")
            elif result['hit_target']:
                print(f"   ✅ TARGET HIT at ₹{target_price:.2f} on day {result['days_to_exit']} | Max DD: {result['max_drawdown']:.2f}% | P&L: ₹{net_pnl:.2f}")
            else:
                print(f"   ⚠️  Neither hit | Exit: ₹{result['exit_price']:.2f} | Max DD: {result['max_drawdown']:.2f}% | P&L: ₹{net_pnl:.2f}")
            
            return result
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def backtest_all_sl_levels(self, sl_levels: List[float] = None) -> Dict:
        """
        Backtest all trades with different SL levels
        
        Args:
            sl_levels: List of SL percentages to test (default: [15, 20, 25, 30, 35, 40])
            
        Returns:
            Dict with results for each SL level
        """
        if sl_levels is None:
            sl_levels = [15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
        
        results = {}
        
        for sl_pct in sl_levels:
            print(f"\n{'='*80}")
            print(f"🧪 TESTING SL LEVEL: {sl_pct}%")
            print(f"{'='*80}")
            
            trade_results = []
            for trade in self.trades:
                result = self.backtest_trade(trade, sl_pct)
                if result:
                    trade_results.append(result)
            
            # Calculate statistics
            total_trades = len(trade_results)
            if total_trades == 0:
                print(f"⚠️  No trades to backtest for SL {sl_pct}%")
                continue
                
            sl_hits = sum(1 for r in trade_results if r['hit_sl'])
            target_hits = sum(1 for r in trade_results if r['hit_target'])
            win_rate = (target_hits / total_trades * 100) if total_trades > 0 else 0
            
            total_net_pnl = sum(r['net_pnl'] for r in trade_results)
            avg_pnl = total_net_pnl / total_trades if total_trades > 0 else 0
            
            # Compare to actual (no SL)
            actual_total_pnl = sum(r['actual_net_pnl'] for r in trade_results)
            pnl_difference = total_net_pnl - actual_total_pnl
            pnl_change_pct = (pnl_difference / abs(actual_total_pnl) * 100) if actual_total_pnl != 0 else 0
            
            avg_drawdown = sum(r['max_drawdown'] for r in trade_results) / total_trades if total_trades > 0 else 0
            max_drawdown = max((r['max_drawdown'] for r in trade_results), default=0)
            
            results[sl_pct] = {
                'sl_percentage': sl_pct,
                'total_trades': total_trades,
                'sl_hits': sl_hits,
                'target_hits': target_hits,
                'win_rate': win_rate,
                'total_net_pnl': total_net_pnl,
                'avg_pnl': avg_pnl,
                'actual_total_pnl': actual_total_pnl,
                'pnl_difference': pnl_difference,
                'pnl_change_pct': pnl_change_pct,
                'avg_drawdown': avg_drawdown,
                'max_drawdown': max_drawdown,
                'trade_results': trade_results
            }
            
            print(f"\n📈 SL {sl_pct}% Summary:")
            print(f"   Total Trades: {total_trades}")
            print(f"   SL Hits: {sl_hits} ({sl_hits/total_trades*100:.1f}%)")
            print(f"   Target Hits: {target_hits} ({target_hits/total_trades*100:.1f}%)")
            print(f"   Win Rate: {win_rate:.1f}%")
            print(f"   Total P&L: ₹{total_net_pnl:,.2f}")
            print(f"   Avg P&L: ₹{avg_pnl:,.2f}")
            print(f"   Actual P&L (no SL): ₹{actual_total_pnl:,.2f}")
            print(f"   P&L Difference: ₹{pnl_difference:,.2f} ({pnl_change_pct:+.1f}%)")
            print(f"   Avg Drawdown: {avg_drawdown:.2f}%")
            print(f"   Max Drawdown: {max_drawdown:.2f}%")
        
        return results
    
    def print_recommendation(self, results: Dict):
        """Print recommendation based on backtest results"""
        print(f"\n{'='*80}")
        print(f"🎯 RECOMMENDATION")
        print(f"{'='*80}\n")
        
        if not results:
            print("⚠️  No results to analyze")
            return
        
        # Find best SL level (highest win rate with acceptable P&L)
        best_sl = None
        best_score = -float('inf')
        
        for sl_pct, stats in results.items():
            # Score = win_rate * 0.4 + (pnl_change_pct if positive) * 0.3 + (100 - avg_drawdown) * 0.3
            score = (
                stats['win_rate'] * 0.4 +
                max(0, stats['pnl_change_pct']) * 0.3 +
                (100 - min(100, stats['avg_drawdown'])) * 0.3
            )
            
            if score > best_score:
                best_score = score
                best_sl = sl_pct
        
        if best_sl:
            best_stats = results[best_sl]
            print(f"✅ RECOMMENDED SL: {best_sl}%")
            print(f"\n   Win Rate: {best_stats['win_rate']:.1f}%")
            print(f"   Total P&L: ₹{best_stats['total_net_pnl']:,.2f}")
            print(f"   P&L vs Actual: ₹{best_stats['pnl_difference']:+,.2f} ({best_stats['pnl_change_pct']:+.1f}%)")
            print(f"   Avg Drawdown: {best_stats['avg_drawdown']:.2f}%")
            print(f"   Max Drawdown: {best_stats['max_drawdown']:.2f}%")
            print(f"   SL Hits: {best_stats['sl_hits']} trades")
        
        # Print comparison table
        print(f"\n{'='*80}")
        print(f"📊 COMPARISON TABLE")
        print(f"{'='*80}\n")
        print(f"{'SL %':<8} {'Win Rate':<12} {'Total P&L':<15} {'P&L Diff':<15} {'Avg DD':<12} {'SL Hits':<10}")
        print(f"{'-'*80}")
        
        for sl_pct in sorted(results.keys()):
            stats = results[sl_pct]
            print(f"{sl_pct:<8.0f} {stats['win_rate']:<12.1f} ₹{stats['total_net_pnl']:<14,.0f} "
                  f"₹{stats['pnl_difference']:<14,.0f} {stats['avg_drawdown']:<12.2f} {stats['sl_hits']:<10}")


def main():
    """Main function to run backtest"""
    # Path to trades file
    trades_file = "webapp/data/users/user_iYew5t9Qqn0Uw1yXCzfd-A/trades.json"
    
    print("🚀 Starting SL Strategy Backtest")
    print(f"📁 Loading trades from: {trades_file}\n")
    
    backtester = SLBacktester(trades_file)
    
    # Run backtest for all SL levels
    results = backtester.backtest_all_sl_levels(
        sl_levels=[15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
    )
    
    # Print recommendation
    backtester.print_recommendation(results)
    
    # Save results to JSON
    output_file = "sl_backtest_results.json"
    with open(output_file, 'w') as f:
        # Remove trade_results for cleaner output
        clean_results = {
            sl: {k: v for k, v in stats.items() if k != 'trade_results'}
            for sl, stats in results.items()
        }
        json.dump(clean_results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")


if __name__ == "__main__":
    main()

