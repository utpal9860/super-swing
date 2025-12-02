"""
Multi-Modal Trading System - Web Application
Interactive UI for pattern detection, sentiment analysis, and price prediction
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import pandas as pd
import yfinance as yf
from datetime import datetime
import os
from dotenv import load_dotenv
import json
import pickle
import uuid

# Import our modules
from multimodal_signal_generator import MultiModalSignalGenerator
from visualization.pattern_charts import PatternChartGenerator
from utils.logger import setup_logger

# Import stock universes
sys.path.append(str(Path(__file__).parent.parent / 'config'))
from stock_universes import STOCK_UNIVERSES, UNIVERSE_INFO

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'multimodal-trading-system-secret-key-change-in-production')
CORS(app)

# Initialize logger
logger = setup_logger("web_app")

# Create temp directory for storing large session data
TEMP_DIR = Path(__file__).parent / 'temp_results'
TEMP_DIR.mkdir(exist_ok=True)


def save_results_to_file(data: dict) -> str:
    """
    Save large result data to file instead of session cookie
    Returns unique ID for retrieval
    """
    result_id = str(uuid.uuid4())
    file_path = TEMP_DIR / f"{result_id}.pkl"
    
    with open(file_path, 'wb') as f:
        pickle.dump(data, f)
    
    logger.info(f"Saved results to file: {result_id}")
    return result_id


def load_results_from_file(result_id: str) -> dict:
    """
    Load result data from file using ID
    """
    file_path = TEMP_DIR / f"{result_id}.pkl"
    
    if not file_path.exists():
        logger.warning(f"Result file not found: {result_id}")
        return None
    
    with open(file_path, 'rb') as f:
        data = pickle.load(f)
    
    logger.info(f"Loaded results from file: {result_id}")
    return data


def cleanup_old_results(max_age_hours: int = 24):
    """
    Clean up old result files to prevent disk bloat
    """
    from time import time
    now = time()
    
    for file_path in TEMP_DIR.glob("*.pkl"):
        file_age_hours = (now - file_path.stat().st_mtime) / 3600
        if file_age_hours > max_age_hours:
            file_path.unlink()
            logger.info(f"Cleaned up old result file: {file_path.name}")


@app.route('/')
def index():
    """Home page"""
    return render_template('index.html', universes=STOCK_UNIVERSES.keys(), universe_info=UNIVERSE_INFO)


@app.route('/scan', methods=['POST'])
def scan_stocks():
    """Scan stocks and generate signals"""
    try:
        # CRITICAL: Clear ALL old session data to prevent showing stale results
        session.clear()
        session.modified = True
        
        # Get parameters
        universe_name = request.form.get('universe', 'test')
        skip_sentiment = request.form.get('skip_sentiment', 'false') == 'true'
        max_patterns = int(request.form.get('max_patterns', '3'))
        enable_multitimeframe = request.form.get('enable_multitimeframe', 'false') == 'true'
        
        # Handle custom stock list
        if universe_name == 'custom':
            custom_stocks_str = request.form.get('custom_stocks', '').strip()
            if not custom_stocks_str:
                return jsonify({
                    'success': False,
                    'error': 'Please enter stock symbols for custom list'
                })
            
            # Parse custom stock list (comma or newline separated)
            import re
            symbols = re.split(r'[,\n]+', custom_stocks_str)
            symbols = [s.strip().upper() for s in symbols if s.strip()]
            
            if not symbols:
                return jsonify({
                    'success': False,
                    'error': 'No valid stock symbols found in custom list'
                })
            
            # Create universe from custom symbols
            universe = [{'symbol': sym, 'name': sym} for sym in symbols]
            logger.info(f"Custom stock list: {symbols}")
        else:
            universe = STOCK_UNIVERSES.get(universe_name, STOCK_UNIVERSES['test'])
        
        logger.info(f"Starting NEW scan for universe: {universe_name} ({len(universe)} stocks)")
        logger.info(f"Options: skip_sentiment={skip_sentiment}, max_patterns={max_patterns}, multi_timeframe={enable_multitimeframe}")
        
        # Check Gemini API key (only if sentiment enabled)
        gemini_key = os.getenv('GEMINI_API_KEY')
        if not skip_sentiment and (not gemini_key or gemini_key == 'your_gemini_api_key_here'):
            return jsonify({
                'success': False,
                'error': 'Gemini API key not configured. Enable "Skip Sentiment" or add GEMINI_API_KEY to ML/.env file.'
            })
        
        # Initialize generator with PARALLEL execution enabled
        generator = MultiModalSignalGenerator(
            gemini_api_key=gemini_key,
            skip_sentiment=skip_sentiment,
            max_patterns_per_stock=max_patterns,
            enable_multitimeframe=enable_multitimeframe,
            enable_parallel=True  # NEW: Enable parallel processing
        )
        
        # Generate signals
        start_time = datetime.now()
        signals = generator.generate_signals(universe, lookback_days=200)
        end_time = datetime.now()
        scan_duration = (end_time - start_time).total_seconds()
        
        logger.info(f"Scan completed in {scan_duration:.1f} seconds")
        
        # Store FRESH signals in session - force overwrite
        session.pop('signals', None)  # Remove old data explicitly
        session.pop('universe_name', None)
        session['signals'] = [_signal_to_dict(s) for s in signals]
        session['universe_name'] = universe_name  # Store CURRENT universe
        session['scan_time'] = end_time.isoformat()
        session['multitimeframe'] = enable_multitimeframe
        session['scan_duration'] = scan_duration
        session.modified = True  # Force session update
        
        logger.info(f"Session updated: universe={universe_name}, signals={len(signals)}")
        
        logger.info(f"Scan complete. Generated {len(signals)} NEW signals")
        
        return jsonify({
            'success': True,
            'num_signals': len(signals),
            'universe': universe_name,
            'num_stocks': len(universe),
            'scan_duration': f"{scan_duration:.1f}s",
            'redirect': '/results'
        })
    
    except Exception as e:
        logger.error(f"Scan error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/results')
def show_results():
    """Show scan results"""
    try:
        # Get signals from session
        signals_data = session.get('signals', [])
        
        if not signals_data:
            return render_template('results.html', signals=[], no_signals=True)
        
        # Convert back to signal objects
        from fusion.signal_fusion import MultiModalSignal
        signals = [_dict_to_signal(d) for d in signals_data]
        
        logger.info(f"Rendering results for {len(signals)} signals")
        
        # CRITICAL FIX: Generate charts ONLY for top N signals to avoid bottleneck
        # User can filter/scroll to see all signals
        MAX_CHARTS_TO_GENERATE = 50  # Limit to first 50 for performance
        
        chart_gen = PatternChartGenerator(theme='plotly_white')
        signals_with_charts = []
        
        # Process only top N signals for chart generation
        signals_to_chart = signals[:MAX_CHARTS_TO_GENERATE]
        logger.info(f"Generating charts for top {len(signals_to_chart)} signals (out of {len(signals)} total)")
        
        for signal in signals_to_chart:
            # Fetch stock data
            try:
                ticker_yf = f"{signal.ticker}.NS"
                stock = yf.Ticker(ticker_yf)
                df = stock.history(period="3mo")
                
                if df.empty:
                    logger.warning(f"No data for {signal.ticker}, adding without chart")
                    # Add signal without chart
                    signals_with_charts.append({
                        'signal': signal,
                        'chart': None
                    })
                    continue
                
                df.columns = df.columns.str.lower()
                
                # Generate chart
                chart_html = chart_gen.create_pattern_chart(df.tail(50), signal, show_volume=True)
                
                signals_with_charts.append({
                    'signal': signal,
                    'chart': chart_html
                })
            
            except Exception as e:
                logger.error(f"Error creating chart for {signal.ticker}: {e}")
                # Add signal without chart
                signals_with_charts.append({
                    'signal': signal,
                    'chart': None
                })
        
        # Add remaining signals WITHOUT charts (for filtering/display)
        if len(signals) > MAX_CHARTS_TO_GENERATE:
            logger.info(f"Adding {len(signals) - MAX_CHARTS_TO_GENERATE} additional signals without charts")
            for signal in signals[MAX_CHARTS_TO_GENERATE:]:
                signals_with_charts.append({
                    'signal': signal,
                    'chart': None
                })
        
        scan_info = {
            'universe': session.get('universe_name', 'unknown'),
            'scan_time': session.get('scan_time', ''),
            'num_signals': len(signals),
            'num_charted': min(len(signals), MAX_CHARTS_TO_GENERATE)
        }
        
        logger.info(f"Results ready: {len(signals_with_charts)} signals total, {scan_info['num_charted']} with charts")
        
        return render_template('results.html',
                             signals_with_charts=signals_with_charts,
                             scan_info=scan_info,
                             no_signals=len(signals_with_charts) == 0)
    
    except Exception as e:
        logger.error(f"Results error: {e}")
        import traceback
        traceback.print_exc()
        return render_template('error.html', error=str(e))


@app.route('/signal/<ticker>')
def signal_detail(ticker):
    """Show detailed view of a single signal"""
    try:
        signals_data = session.get('signals', [])
        
        # Find signal for ticker
        signal_data = next((s for s in signals_data if s['ticker'] == ticker), None)
        
        if not signal_data:
            return render_template('error.html', error=f"Signal not found for {ticker}")
        
        from fusion.signal_fusion import MultiModalSignal
        signal = _dict_to_signal(signal_data)
        
        # Fetch stock data
        ticker_yf = f"{ticker}.NS"
        stock = yf.Ticker(ticker_yf)
        df = stock.history(period="3mo")
        df.columns = df.columns.str.lower()
        
        # Generate chart
        chart_gen = PatternChartGenerator(theme='plotly_white')
        chart_html = chart_gen.create_pattern_chart(df.tail(50), signal, show_volume=True)
        
        return render_template('signal_detail.html', signal=signal, chart=chart_html)
    
    except Exception as e:
        logger.error(f"Signal detail error: {e}")
        return render_template('error.html', error=str(e))


@app.route('/api/scan_status')
def scan_status():
    """Get current scan status"""
    signals = session.get('signals', [])
    return jsonify({
        'has_signals': len(signals) > 0,
        'num_signals': len(signals),
        'scan_time': session.get('scan_time', '')
    })


def _signal_to_dict(signal):
    """Convert MultiModalSignal to dict for JSON serialization"""
    return {
        'ticker': signal.ticker,
        'company_name': signal.company_name,
        'date': signal.date,
        'pattern_type': signal.pattern_type,
        'pattern_quality': signal.pattern_quality,
        'pattern_win_rate': signal.pattern_win_rate,
        'pattern_score': signal.pattern_score,
        'sentiment_raw': signal.sentiment_raw,
        'sentiment_label': signal.sentiment_label,
        'sentiment_confidence': signal.sentiment_confidence,
        'sentiment_score': signal.sentiment_score,
        'num_articles': signal.num_articles,
        'predicted_return': signal.predicted_return,
        'prediction_confidence': signal.prediction_confidence,
        'probability_gain': signal.probability_gain,
        'prediction_score': signal.prediction_score,
        'final_confidence': signal.final_confidence,
        'recommendation': signal.recommendation,
        'position_size_pct': signal.position_size_pct,
        'entry_price': signal.entry_price,
        'stop_loss': signal.stop_loss,
        'target_price': signal.target_price,
        'risk_reward_ratio': signal.risk_reward_ratio
    }


def _dict_to_signal(data):
    """Convert dict back to MultiModalSignal"""
    from fusion.signal_fusion import MultiModalSignal
    return MultiModalSignal(**data)


# ============================================================================
# IPO BUY-AND-HOLD ANALYSIS ROUTES
# ============================================================================

@app.route('/ipo-analysis')
def ipo_analysis_home():
    """IPO Analysis home page"""
    return render_template('ipo_analysis.html')


@app.route('/ipo-analysis/analyze', methods=['POST'])
def analyze_ipos():
    """Analyze IPO investments and calculate returns"""
    try:
        # Get parameters
        stock_list_type = request.form.get('stock_list', 'sample')
        investment_amount = float(request.form.get('investment_amount', 15000))
        
        # Import IPO analyzer
        sys.path.append(str(Path(__file__).parent.parent / 'ipo_analysis'))
        from ipo_analyzer import IPOAnalyzer, get_ipo_stocks_from_period
        
        # Get stock list
        if stock_list_type == 'custom':
            custom_stocks_str = request.form.get('custom_stocks', '').strip()
            if not custom_stocks_str:
                return jsonify({
                    'success': False,
                    'error': 'Please enter stock symbols for custom list'
                })
            
            import re
            tickers = re.split(r'[,\n]+', custom_stocks_str)
            tickers = [s.strip().upper() for s in tickers if s.strip()]
            start_year = 2019
            end_year = 2025
        else:
            # Fetch ALL stocks from NSE/BSE
            tickers = get_ipo_stocks_from_period(2019, 2025)
            start_year = 2019
            end_year = 2025
        
        logger.info(f"Starting IPO analysis for {len(tickers)} stocks with Rs.{investment_amount} per stock")
        
        # Initialize analyzer
        analyzer = IPOAnalyzer(investment_per_stock=investment_amount)
        
        # Analyze stocks (will filter for 2019-2025 listings automatically)
        df = analyzer.analyze_multiple_stocks(tickers, start_year=start_year, end_year=end_year)
        
        if df.empty:
            return jsonify({
                'success': False,
                'error': 'No data found for the selected stocks'
            })
        
        # Get portfolio summary
        summary = analyzer.get_portfolio_summary(df)
        
        # CRITICAL FIX: Store results in FILE instead of session cookie (too large!)
        # Session cookies have 4KB limit, IPO results can be 5KB+
        results_data = {
            'results': df.to_dict('records'),
            'summary': summary,
            'investment_amount': investment_amount,
            'timestamp': datetime.now().isoformat()
        }
        
        result_id = save_results_to_file(results_data)
        
        # Store only the ID in session (tiny!)
        session['ipo_result_id'] = result_id
        session.modified = True
        
        # Cleanup old files
        cleanup_old_results(max_age_hours=24)
        
        logger.info(f"IPO analysis complete: {len(df)} stocks, Total Return: {summary['total_return_pct']:.1f}%")
        
        return jsonify({
            'success': True,
            'num_stocks': len(df),
            'total_return_pct': f"{summary['total_return_pct']:.1f}",
            'portfolio_cagr': f"{summary['portfolio_cagr']:.1f}",
            'redirect': '/ipo-analysis/results'
        })
    
    except Exception as e:
        logger.error(f"IPO analysis error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/ipo-analysis/results')
def show_ipo_results():
    """Show IPO analysis results with charts"""
    try:
        # CRITICAL FIX: Load results from file instead of session
        result_id = session.get('ipo_result_id')
        
        if not result_id:
            return render_template('ipo_results.html', no_results=True)
        
        # Load data from file
        data = load_results_from_file(result_id)
        
        if not data:
            return render_template('ipo_results.html', no_results=True)
        
        results_data = data['results']
        summary = data['summary']
        
        # Convert to DataFrame
        df = pd.DataFrame(results_data)
        
        # Import chart generator
        sys.path.append(str(Path(__file__).parent.parent / 'ipo_analysis'))
        from ipo_charts import IPOChartGenerator
        
        chart_gen = IPOChartGenerator(theme='plotly_white')
        
        # Generate charts
        returns_bar = chart_gen.create_returns_bar_chart(df, top_n=20)
        portfolio_growth = chart_gen.create_portfolio_growth_chart(df, summary)
        profit_loss_pie = chart_gen.create_profit_loss_pie_chart(df)
        returns_dist = chart_gen.create_returns_distribution_histogram(df)
        timeline_gantt = chart_gen.create_investment_timeline_gantt(df)
        
        charts = {
            'returns_bar': returns_bar,
            'portfolio_growth': portfolio_growth,
            'profit_loss_pie': profit_loss_pie,
            'returns_dist': returns_dist,
            'timeline_gantt': timeline_gantt
        }
        
        # Convert DataFrame to list of dicts for template
        results = df.to_dict('records')
        
        logger.info(f"Rendering IPO results for {len(results)} stocks")
        
        return render_template('ipo_results.html',
                             results=results,
                             summary=summary,
                             charts=charts,
                             no_results=False)
    
    except Exception as e:
        logger.error(f"IPO results error: {e}")
        import traceback
        traceback.print_exc()
        return render_template('error.html', error=str(e))


@app.route('/ipo-analysis/export-csv')
def export_ipo_csv():
    """Export IPO analysis results to CSV"""
    try:
        # Load results from file
        result_id = session.get('ipo_result_id')
        
        if not result_id:
            return "No results to export", 404
        
        data = load_results_from_file(result_id)
        
        if not data:
            return "Results not found", 404
        
        results_data = data['results']
        df = pd.DataFrame(results_data)
        
        # Create CSV
        from flask import make_response
        csv_data = df.to_csv(index=False)
        
        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=ipo_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response
    
    except Exception as e:
        logger.error(f"CSV export error: {e}")
        return str(e), 500


if __name__ == '__main__':
    print("="*80)
    print("MULTI-MODAL TRADING SYSTEM - WEB INTERFACE")
    print("="*80)
    print("\n🚀 Starting web server...")
    print("📊 Navigate to: http://localhost:5001")
    print("\n💡 Features:")
    print("   - Pattern Detection (TA-Lib)")
    print("   - Sentiment Analysis (Gemini + Google Search)")
    print("   - Price Prediction (StatsForecast)")
    print("   - Interactive Charts (Plotly)")
    print("   - IPO Buy-and-Hold Analysis (NEW!)")
    print("\n📈 Routes:")
    print("   /                  - Trading signals scanner")
    print("   /ipo-analysis      - IPO buy-and-hold analysis")
    print("\n⚠️  Make sure GEMINI_API_KEY is set in ML/.env")
    print("="*80 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5001)

