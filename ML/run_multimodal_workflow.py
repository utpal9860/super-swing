"""
Complete Multi-Modal Workflow
One-click execution of the entire trading signal generation system
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from multimodal_signal_generator import MultiModalSignalGenerator
import pandas as pd
from datetime import datetime
import argparse
from utils.logger import setup_logger

logger = setup_logger("multimodal_workflow")


# Define stock universes
STOCK_UNIVERSES = {
    'test': [
        {'symbol': 'RELIANCE', 'name': 'Reliance Industries'},
        {'symbol': 'TCS', 'name': 'Tata Consultancy Services'},
        {'symbol': 'INFY', 'name': 'Infosys'},
    ],
    
    'fno_top20': [
        {'symbol': 'RELIANCE', 'name': 'Reliance Industries'},
        {'symbol': 'TCS', 'name': 'Tata Consultancy Services'},
        {'symbol': 'HDFCBANK', 'name': 'HDFC Bank'},
        {'symbol': 'INFY', 'name': 'Infosys'},
        {'symbol': 'ICICIBANK', 'name': 'ICICI Bank'},
        {'symbol': 'HINDUNILVR', 'name': 'Hindustan Unilever'},
        {'symbol': 'ITC', 'name': 'ITC Limited'},
        {'symbol': 'SBIN', 'name': 'State Bank of India'},
        {'symbol': 'BHARTIARTL', 'name': 'Bharti Airtel'},
        {'symbol': 'KOTAKBANK', 'name': 'Kotak Mahindra Bank'},
        {'symbol': 'LT', 'name': 'Larsen & Toubro'},
        {'symbol': 'AXISBANK', 'name': 'Axis Bank'},
        {'symbol': 'ASIANPAINT', 'name': 'Asian Paints'},
        {'symbol': 'MARUTI', 'name': 'Maruti Suzuki'},
        {'symbol': 'TITAN', 'name': 'Titan Company'},
        {'symbol': 'SUNPHARMA', 'name': 'Sun Pharmaceutical'},
        {'symbol': 'ULTRACEMCO', 'name': 'UltraTech Cement'},
        {'symbol': 'WIPRO', 'name': 'Wipro'},
        {'symbol': 'NESTLEIND', 'name': 'Nestle India'},
        {'symbol': 'HCLTECH', 'name': 'HCL Technologies'},
    ],
    
    'nifty50': 'AUTO_FETCH'  # Would fetch from NSE
}


def print_header(text):
    """Print formatted header"""
    print("\n" + "="*80)
    print(text.center(80))
    print("="*80 + "\n")


def display_signals(signals):
    """Display signals in a formatted table"""
    if not signals:
        print("No signals generated")
        return
    
    print(f"\n{'='*120}")
    print(f"{'Rank':<6}{'Stock':<12}{'Pattern':<18}{'Rec':<12}{'Conf':<8}{'Entry':<10}{'Target':<10}{'SL':<10}{'R:R':<8}")
    print(f"{'='*120}")
    
    for i, signal in enumerate(signals, 1):
        print(f"{i:<6}"
              f"{signal.ticker:<12}"
              f"{signal.pattern_type:<18}"
              f"{signal.recommendation:<12}"
              f"{signal.final_confidence*100:>6.1f}%  "
              f"{signal.entry_price:>8.2f}  "
              f"{signal.target_price:>8.2f}  "
              f"{signal.stop_loss:>8.2f}  "
              f"{signal.risk_reward_ratio:>6.2f}:1")
    
    print(f"{'='*120}\n")


def display_signal_details(signals):
    """Display detailed information for each signal"""
    for i, signal in enumerate(signals, 1):
        print(f"\n{'='*80}")
        print(f"SIGNAL #{i}: {signal.ticker} ({signal.company_name})")
        print(f"{'='*80}")
        
        print(f"\n[RECOMMENDATION] {signal.recommendation}")
        print(f"  Confidence: {signal.final_confidence:.1%}")
        print(f"  Position Size: {signal.position_size_pct:.2f}% of capital")
        
        print(f"\n[PATTERN ANALYSIS]")
        print(f"  Pattern: {signal.pattern_type}")
        print(f"  Quality: {signal.pattern_quality:.2f}")
        print(f"  Win Rate: {signal.pattern_win_rate:.0%}")
        print(f"  Score: {signal.pattern_score:.3f}")
        
        print(f"\n[SENTIMENT ANALYSIS]")
        print(f"  Sentiment: {signal.sentiment_raw:+.2f} ({signal.sentiment_label})")
        print(f"  Confidence: {signal.sentiment_confidence:.0%}")
        print(f"  Articles: {signal.num_articles}")
        print(f"  Score: {signal.sentiment_score:.3f}")
        
        print(f"\n[PRICE PREDICTION]")
        print(f"  Expected Return: {signal.predicted_return*100:+.1f}%")
        print(f"  Probability of Gain: {signal.probability_gain:.0%}")
        print(f"  Score: {signal.prediction_score:.3f}")
        
        print(f"\n[TRADE LEVELS]")
        print(f"  Entry:     Rs.{signal.entry_price:.2f}")
        print(f"  Stop Loss: Rs.{signal.stop_loss:.2f} ({((signal.stop_loss-signal.entry_price)/signal.entry_price*100):.1f}%)")
        print(f"  Target:    Rs.{signal.target_price:.2f} ({((signal.target_price-signal.entry_price)/signal.entry_price*100):.1f}%)")
        print(f"  R:R Ratio: {signal.risk_reward_ratio:.2f}:1")


def main():
    """Main workflow execution"""
    parser = argparse.ArgumentParser(description='Multi-Modal Trading Signal Generator')
    parser.add_argument(
        '--universe',
        type=str,
        default='test',
        choices=list(STOCK_UNIVERSES.keys()),
        help='Stock universe to scan (test, fno_top20, nifty50)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='multimodal_signals.csv',
        help='Output CSV file name'
    )
    parser.add_argument(
        '--details',
        action='store_true',
        help='Show detailed analysis for each signal'
    )
    
    args = parser.parse_args()
    
    # Print header
    print_header("MULTI-MODAL TRADING SIGNAL GENERATOR")
    print("100% FREE Implementation")
    print(f"  - Pattern Detection: TA-Lib")
    print(f"  - Sentiment Analysis: Gemini + Google Search")
    print(f"  - Price Prediction: StatsForecast")
    print(f"  - Signal Fusion: Weighted Ensemble\n")
    
    # Get stock universe
    universe = STOCK_UNIVERSES[args.universe]
    
    if universe == 'AUTO_FETCH':
        print(f"ERROR: Auto-fetch for {args.universe} not implemented yet")
        print(f"Use --universe test or --universe fno_top20")
        return
    
    print(f"Universe: {args.universe} ({len(universe)} stocks)")
    print(f"Output: {args.output}\n")
    
    # Initialize generator
    print("Initializing Multi-Modal Signal Generator...")
    try:
        generator = MultiModalSignalGenerator()
        print("[OK] Generator initialized\n")
    except ValueError as e:
        print(f"[ERROR] {e}")
        print("\nTo fix:")
        print("  1. Get a free Gemini API key from: https://makersuite.google.com/app/apikey")
        print("  2. Add to ML/.env file: GEMINI_API_KEY=your_key_here")
        return
    except Exception as e:
        print(f"[ERROR] Failed to initialize: {e}")
        return
    
    # Generate signals
    print_header("SCANNING STOCKS")
    
    start_time = datetime.now()
    signals = generator.generate_signals(universe)
    end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    
    # Display results
    print_header("RESULTS")
    
    print(f"Scan completed in {duration:.1f} seconds")
    print(f"Stocks scanned: {len(universe)}")
    print(f"Signals generated: {len(signals)}")
    
    if signals:
        # Sort by confidence
        strong_buy = [s for s in signals if s.recommendation == 'STRONG_BUY']
        buy = [s for s in signals if s.recommendation == 'BUY']
        weak_buy = [s for s in signals if s.recommendation == 'WEAK_BUY']
        
        print(f"\nBreakdown:")
        print(f"  STRONG_BUY: {len(strong_buy)}")
        print(f"  BUY:        {len(buy)}")
        print(f"  WEAK_BUY:   {len(weak_buy)}")
        
        # Display summary table
        display_signals(signals)
        
        # Display details if requested
        if args.details:
            print_header("DETAILED ANALYSIS")
            display_signal_details(signals)
        
        # Export to CSV
        generator.export_signals(signals, args.output)
        print(f"\n[OK] Signals exported to: {args.output}")
        
        # Display top 3 recommendations
        if len(signals) > 0:
            print_header("TOP RECOMMENDATIONS")
            for i, signal in enumerate(signals[:3], 1):
                print(f"\n{i}. {signal.ticker} - {signal.company_name}")
                print(f"   {signal.recommendation} | Confidence: {signal.final_confidence:.1%}")
                print(f"   Entry: Rs.{signal.entry_price:.2f} | Target: Rs.{signal.target_price:.2f} | SL: Rs.{signal.stop_loss:.2f}")
                print(f"   Pattern: {signal.pattern_type} | Sentiment: {signal.sentiment_label} ({signal.num_articles} articles)")
                print(f"   Predicted Return: {signal.predicted_return*100:+.1f}%")
    else:
        print("\nNo signals generated. This could mean:")
        print("  - No high-quality patterns detected")
        print("  - Signals didn't meet confidence thresholds")
        print("  - Market conditions unfavorable (check gate checks)")
    
    print("\n" + "="*80)
    print("Workflow complete!".center(80))
    print("="*80 + "\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user")
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()

