"""Test pattern-only mode (no Gemini sentiment)"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from multimodal_signal_generator import MultiModalSignalGenerator

# Test stock universe
test_stocks = [
    {'symbol': 'RELIANCE', 'name': 'Reliance Industries'},
    {'symbol': 'TCS', 'name': 'Tata Consultancy Services'},
]

print("=" * 60)
print("TESTING: Pattern + Price Prediction (NO SENTIMENT)")
print("=" * 60)

# Initialize with skip_sentiment=True
generator = MultiModalSignalGenerator(
    skip_sentiment=True,  # No Gemini API needed
    max_patterns_per_stock=2  # Process 2 patterns per stock
)

print("\n[START] Generating signals...")
signals = generator.generate_signals(test_stocks, lookback_days=200)

print(f"\n[DONE] Generated {len(signals)} signals\n")

# Display results
for i, signal in enumerate(signals, 1):
    print(f"\n{'='*60}")
    print(f"SIGNAL #{i}: {signal.ticker} - {signal.company_name}")
    print(f"{'='*60}")
    print(f"Pattern:       {signal.pattern_type}")
    print(f"Recommendation: {signal.recommendation}")
    print(f"Confidence:    {signal.final_confidence:.1%}")
    print(f"Entry:         Rs.{signal.entry_price:.2f}")
    print(f"Target:        Rs.{signal.target_price:.2f} (+{((signal.target_price/signal.entry_price)-1)*100:.1f}%)")
    print(f"Stop Loss:     Rs.{signal.stop_loss:.2f} (-{((signal.entry_price/signal.stop_loss)-1)*100:.1f}%)")
    print(f"R:R Ratio:     {signal.risk_reward_ratio:.2f}:1")
    print(f"Position Size: {signal.position_size_pct:.1f}%")
    print(f"\nScores Breakdown:")
    print(f"  Pattern:     {signal.pattern_score:.2f}")
    print(f"  Sentiment:   {signal.sentiment_score:.2f} (SKIPPED)")
    print(f"  Prediction:  {signal.prediction_score:.2f}")
    print(f"  -> Final:    {signal.final_confidence:.2f}")

print(f"\n{'='*60}")
print(f"Test completed successfully!")
print(f"{'='*60}\n")


