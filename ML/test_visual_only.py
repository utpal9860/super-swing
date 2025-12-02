"""Test pattern detection with visual chart - NO API calls"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from datetime import datetime, timedelta
from pattern_detection.data_fetcher import batch_fetch_data
from pattern_detection.talib_patterns import batch_scan_patterns, filter_high_quality_patterns
from visualization.pattern_charts import PatternChartGenerator
import yfinance as yf

# Fetch data
ticker = 'RELIANCE'
end_date = datetime.now()
start_date = end_date - timedelta(days=200)
stock_data = batch_fetch_data([ticker], start_date, end_date, save_csv=False)

if ticker in stock_data:
    df = stock_data[ticker]
    print(f"[OK] Fetched {len(df)} rows for {ticker}")
    
    # Detect patterns
    all_patterns = batch_scan_patterns([ticker], stock_data)
    high_quality = filter_high_quality_patterns(all_patterns)
    
    print(f"[OK] Found {len(high_quality)} high-quality patterns")
    
    if high_quality:
        # Show first 3 patterns
        for i, p in enumerate(high_quality[:3], 1):
            print(f"\n{i}. Pattern: {p['pattern_type']}")
            print(f"   Date: {p['detection_date']}")
            print(f"   Price: Rs.{p['price_at_detection']:.2f}")
            print(f"   Confidence: {p['confidence_score']:.2%}")
        
        # Create mock signal for visualization
        from fusion.signal_fusion import MultiModalSignal
        
        pattern = high_quality[0]
        current_price = float(df['close'].iloc[-1])
        
        mock_signal = MultiModalSignal(
            ticker=ticker,
            company_name='Reliance Industries',
            date=pattern['detection_date'],
            pattern_type=pattern['pattern_type'],
            pattern_quality=pattern['confidence_score'],
            pattern_win_rate=0.65,
            pattern_score=0.75,
            sentiment_raw=0.0,
            sentiment_label='NEUTRAL',
            sentiment_confidence=0.5,
            sentiment_score=0.5,
            num_articles=0,
            predicted_return=0.05,
            prediction_confidence=0.6,
            probability_gain=0.65,
            prediction_score=0.65,
            final_confidence=0.68,
            recommendation='BUY',
            position_size_pct=2.5,
            entry_price=current_price,
            stop_loss=current_price * 0.97,
            target_price=current_price * 1.05,
            risk_reward_ratio=1.67
        )
        
        # Generate chart
        chart_gen = PatternChartGenerator()
        chart_html = chart_gen.create_pattern_chart(df.tail(50), mock_signal, show_volume=True)
        
        # Save to file
        html_file = Path('test_chart.html')
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(f"""
<!DOCTYPE html>
<html>
<head>
    <title>Pattern Visualization Test - {ticker}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <h1>{ticker} - {pattern['pattern_type']}</h1>
    <p>Detected: {pattern['detection_date']} | Confidence: {pattern['confidence_score']:.1%}</p>
    {chart_html}
</body>
</html>
""")
        
        print(f"\n[OK] Chart saved to: {html_file.absolute()}")
        print(f"[OK] Open in browser to see pattern visualization!")
        
        # Try to open
        import webbrowser
        webbrowser.open(str(html_file.absolute()))
    else:
        print("[ERROR] No high-quality patterns found")
else:
    print("[ERROR] Failed to fetch data")

