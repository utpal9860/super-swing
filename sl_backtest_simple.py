"""
SL Strategy Backtesting Script (Simple Version)
Uses lowest_price from trades data to simulate SL impact
"""
import json
from typing import Dict, List

def analyze_sl_strategy(trades_file: str):
    """Analyze SL strategy using existing trade data"""
    
    with open(trades_file, 'r') as f:
        trades = json.load(f)
    
    # Include both closed and open trades for analysis
    closed_trades = [t for t in trades if t.get('status') == 'closed']
    open_trades = [t for t in trades if t.get('status') == 'open']
    
    print(f"📊 Analyzing {len(closed_trades)} closed trades")
    if open_trades:
        print(f"   (Also found {len(open_trades)} open trade(s) - will analyze separately)\n")
    
    print(f"📊 Analyzing {len(closed_trades)} closed trades\n")
    
    sl_levels = [15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
    results = {}
    
    for sl_pct in sl_levels:
        sl_hits = 0
        target_hits = 0
        total_pnl = 0.0
        actual_total_pnl = 0.0
        max_drawdowns = []
        open_trade_sl_hits = 0
        
        # Analyze closed trades
        for trade in closed_trades:
            entry_price = float(trade.get('entry_price', 0))
            target_price = float(trade.get('target', 0))
            lowest_price = float(trade.get('lowest_price', entry_price))
            actual_pnl = float(trade.get('net_pnl', 0))
            
            if not entry_price or not target_price:
                continue
            
            # Calculate SL price
            sl_price = entry_price * (1 - sl_pct / 100)
            
            # Calculate drawdown
            drawdown = ((entry_price - lowest_price) / entry_price) * 100
            max_drawdowns.append(drawdown)
            
            # Check if SL would have been hit
            if lowest_price <= sl_price:
                sl_hits += 1
                # Calculate P&L if SL hit
                lot_size = trade.get('lot_size', 1)
                shares = trade.get('shares', 1)
                quantity = shares * lot_size
                gross_pnl = (sl_price - entry_price) * quantity
                net_pnl = gross_pnl - 40.0  # Brokerage
                total_pnl += net_pnl
            else:
                # Target would have been hit (since trade was profitable)
                target_hits += 1
                total_pnl += actual_pnl
            
            actual_total_pnl += actual_pnl
        
        # Analyze open trades (for drawdown analysis)
        for trade in open_trades:
            entry_price = float(trade.get('entry_price', 0))
            lowest_price = float(trade.get('lowest_price', entry_price))
            
            if not entry_price:
                continue
            
            # Calculate SL price
            sl_price = entry_price * (1 - sl_pct / 100)
            
            # Calculate drawdown
            drawdown = ((entry_price - lowest_price) / entry_price) * 100
            max_drawdowns.append(drawdown)
            
            # Check if SL would have been hit
            if lowest_price <= sl_price:
                open_trade_sl_hits += 1
        
        total_trades = len(closed_trades) + len(open_trades)
        total_sl_hits = sl_hits + open_trade_sl_hits
        
        win_rate = (target_hits / len(closed_trades) * 100) if closed_trades else 0
        avg_drawdown = sum(max_drawdowns) / len(max_drawdowns) if max_drawdowns else 0
        max_drawdown = max(max_drawdowns) if max_drawdowns else 0
        pnl_diff = total_pnl - actual_total_pnl
        pnl_change_pct = (pnl_diff / abs(actual_total_pnl) * 100) if actual_total_pnl != 0 else 0
        
        results[sl_pct] = {
            'sl_percentage': sl_pct,
            'total_trades': total_trades,
            'closed_trades': len(closed_trades),
            'open_trades': len(open_trades),
            'sl_hits': total_sl_hits,
            'closed_sl_hits': sl_hits,
            'open_sl_hits': open_trade_sl_hits,
            'target_hits': target_hits,
            'win_rate': win_rate,
            'total_net_pnl': total_pnl,
            'actual_total_pnl': actual_total_pnl,
            'pnl_difference': pnl_diff,
            'pnl_change_pct': pnl_change_pct,
            'avg_drawdown': avg_drawdown,
            'max_drawdown': max_drawdown
        }
    
    # Print results
    print(f"{'='*80}")
    print(f"📊 SL STRATEGY BACKTEST RESULTS")
    print(f"{'='*80}\n")
    
    print(f"{'SL %':<8} {'Win Rate':<12} {'Total P&L':<15} {'P&L Diff':<15} {'Avg DD':<12} {'Max DD':<12} {'SL Hits':<12}")
    print(f"{'-'*85}")
    
    for sl_pct in sorted(results.keys()):
        stats = results[sl_pct]
        sl_hits_str = f"{stats['sl_hits']} ({stats['closed_sl_hits']}C/{stats['open_sl_hits']}O)"
        print(f"{sl_pct:<8.0f} {stats['win_rate']:<12.1f} ₹{stats['total_net_pnl']:<14,.0f} "
              f"₹{stats['pnl_difference']:<14,.0f} {stats['avg_drawdown']:<12.2f} {stats['max_drawdown']:<12.2f} {sl_hits_str:<12}")
    
    # Find best SL
    print(f"\n{'='*80}")
    print(f"🎯 RECOMMENDATION")
    print(f"{'='*80}\n")
    
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
        print(f"   Actual P&L (no SL): ₹{best_stats['actual_total_pnl']:,.2f}")
        print(f"   P&L Difference: ₹{best_stats['pnl_difference']:+,.2f} ({best_stats['pnl_change_pct']:+.1f}%)")
        print(f"   Avg Drawdown: {best_stats['avg_drawdown']:.2f}%")
        print(f"   Max Drawdown: {best_stats['max_drawdown']:.2f}%")
        print(f"   SL Hits: {best_stats['sl_hits']} trades ({best_stats['closed_sl_hits']} closed, {best_stats['open_sl_hits']} open)")
        if best_stats['open_sl_hits'] > 0:
            print(f"   ⚠️  {best_stats['open_sl_hits']} open trade(s) would have been stopped out")
    
    # Save results
    output_file = "sl_backtest_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    return results

if __name__ == "__main__":
    trades_file = "webapp/data/users/user_iYew5t9Qqn0Uw1yXCzfd-A/trades.json"
    analyze_sl_strategy(trades_file)

