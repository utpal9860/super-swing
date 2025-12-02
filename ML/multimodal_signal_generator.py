"""
Multi-Modal Signal Generator
Combines Pattern Detection + Sentiment Analysis + Price Prediction
100% FREE implementation using TA-Lib + Gemini + StatsForecast
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
import time
from dotenv import load_dotenv

# Import our modules
from pattern_detection.data_fetcher import batch_fetch_data
from pattern_detection.talib_patterns import batch_scan_patterns, filter_high_quality_patterns
from sentiment_analysis.gemini_news_analyzer import GeminiNewsAnalyzer
from price_prediction.statsforecast_predictor import StatsForecastPredictor
from fusion.signal_fusion import SignalFusion, MultiModalSignal
from utils.logger import setup_logger
from config import SIGNAL_CONFIG

logger = setup_logger("multimodal_signal_generator")

# Load environment variables
load_dotenv()


class MultiModalSignalGenerator:
    """
    Complete multi-modal trading signal generator
    
    Uses 100% FREE models:
    - Pattern Detection: TA-Lib
    - Sentiment Analysis: Gemini + Google Search
    - Price Prediction: StatsForecast
    - Fusion: Weighted ensemble
    """
    
    def __init__(self, gemini_api_key: Optional[str] = None, skip_sentiment: bool = False, max_patterns_per_stock: int = 3, enable_multitimeframe: bool = False, enable_parallel: bool = False):
        """
        Initialize all three models
        
        Args:
            gemini_api_key: Gemini API key (or from .env)
            skip_sentiment: Skip sentiment analysis (faster, no Gemini API calls)
            max_patterns_per_stock: Max patterns to process per stock (default: 3)
            enable_multitimeframe: Enable multi-timeframe pattern scanning (1W, 1D, 4H, 1H)
            enable_parallel: Enable parallel processing (MUCH faster for large universes)
        """
        self.skip_sentiment = skip_sentiment
        self.max_patterns_per_stock = max_patterns_per_stock
        self.enable_multitimeframe = enable_multitimeframe
        self.enable_parallel = enable_parallel
        # Get API key
        self.gemini_api_key = gemini_api_key or os.getenv('GEMINI_API_KEY')
        
        if not skip_sentiment and not self.gemini_api_key:
            raise ValueError(
                "Gemini API key required! "
                "Set GEMINI_API_KEY in .env or pass skip_sentiment=True"
            )
        
        # Initialize models
        logger.info("Initializing Multi-Modal Signal Generator...")
        if not skip_sentiment:
            logger.info("  [1/3] Sentiment Analyzer (Gemini + Google Search)...")
            self.sentiment_analyzer = GeminiNewsAnalyzer(api_key=self.gemini_api_key)
        else:
            logger.info("  [1/3] Sentiment Analyzer SKIPPED (faster mode)")
            self.sentiment_analyzer = None
        
        logger.info("  [2/3] Price Predictor (StatsForecast)...")
        self.price_predictor = StatsForecastPredictor()
        
        logger.info("  [3/3] Signal Fusion Layer...")
        self.fusion = SignalFusion()
        
        logger.info("Multi-Modal Signal Generator ready!")
    
    def generate_signals(self, stock_universe: List[Dict[str, str]], 
                        lookback_days: int = 200) -> List[MultiModalSignal]:
        """
        Generate trading signals for a universe of stocks
        
        Args:
            stock_universe: List of dicts with 'symbol' and 'name' keys
                           Example: [{'symbol': 'RELIANCE', 'name': 'Reliance Industries'}]
            lookback_days: Days of historical data for patterns/prediction
        
        Returns:
            List of MultiModalSignal objects with recommendations
        """
        # Use parallel processing if enabled (MUCH faster)
        if self.enable_parallel:
            return self._generate_signals_parallel(stock_universe, lookback_days)
        
        # Sequential processing (original)
        signals = []
        
        logger.info(f"Scanning {len(stock_universe)} stocks (SEQUENTIAL mode)...")
        logger.warning("TIP: Enable parallel processing for 3-5x speed boost!")
        
        for i, stock in enumerate(stock_universe, 1):
            ticker = stock['symbol']
            company_name = stock['name']
            
            logger.info(f"\n{'='*80}")
            logger.info(f"[{i}/{len(stock_universe)}] Analyzing {ticker} ({company_name})")
            logger.info(f"{'='*80}")
            
            try:
                # PHASE 1: Pattern Detection
                logger.info(f"Phase 1: Detecting patterns...")
                patterns = self._detect_patterns(ticker, lookback_days)
                
                if not patterns:
                    logger.info(f"  No high-quality patterns found for {ticker}")
                    continue
                
                logger.info(f"  Found {len(patterns)} pattern(s)")
                
                # Process each pattern (limit based on config)
                limit = min(len(patterns), self.max_patterns_per_stock)
                for idx, pattern in enumerate(patterns[:limit], 1):
                    logger.info(f"\n  Processing pattern {idx}/{limit}: {pattern['pattern_type']}")
                    
                    # PHASE 2: Sentiment Analysis
                    if self.skip_sentiment:
                        logger.info(f"  Phase 2: Sentiment analysis SKIPPED")
                        sentiment_data = {
                            'overall_sentiment': 0.0,
                            'sentiment_label': 'NEUTRAL',
                            'confidence': 0.5,
                            'num_articles': 0,
                            'positive_count': 0,
                            'negative_count': 0,
                            'neutral_count': 0,
                            'key_positive_factors': [],
                            'key_negative_factors': [],
                            'key_themes': []
                        }
                    else:
                        logger.info(f"  Phase 2: Analyzing sentiment...")
                        try:
                            sentiment_result = self.sentiment_analyzer.fetch_and_analyze_sentiment(
                                stock_symbol=ticker,
                                company_name=company_name,
                                days_back=7
                            )
                        except Exception as sent_error:
                            logger.error(f"    Sentiment API error: {sent_error}")
                            # Use neutral sentiment as fallback
                            sentiment_result = {
                                'success': True,
                                'data': {
                                    'overall_sentiment': 0.0,
                                    'sentiment_label': 'NEUTRAL',
                                    'confidence': 0.5,
                                    'num_articles': 0,
                                    'positive_count': 0,
                                    'negative_count': 0,
                                    'neutral_count': 0,
                                    'key_positive_factors': [],
                                    'key_negative_factors': [],
                                    'key_themes': []
                                }
                            }
                            logger.warning(f"    Using neutral sentiment fallback")
                        
                        if not sentiment_result['success']:
                            logger.warning(f"    Sentiment analysis failed: {sentiment_result.get('error')}")
                            logger.warning(f"    Skipping pattern {pattern['pattern_type']}")
                            continue
                        
                        sentiment_data = sentiment_result['data']
                        logger.info(f"    Sentiment: {sentiment_data['overall_sentiment']:.2f} "
                                   f"({sentiment_data['sentiment_label']}), "
                                   f"{sentiment_data['num_articles']} articles")
                    
                    # PHASE 3: Price Prediction
                    logger.info(f"  Phase 3: Forecasting price...")
                    price_data = self._fetch_price_data(ticker, lookback_days)
                    
                    if price_data is None or len(price_data) < 50:
                        logger.warning(f"    Insufficient price data")
                        continue
                    
                    prediction_result = self.price_predictor.forecast_stock_price(
                        price_data,
                        horizon=10
                    )
                    
                    if 'error' in prediction_result:
                        logger.warning(f"    Price prediction failed: {prediction_result['error']}")
                        continue
                    
                    logger.info(f"    Predicted return: {prediction_result['expected_return']*100:+.1f}%, "
                               f"Probability: {prediction_result['probability_gain']*100:.0f}%")
                    
                    # PHASE 4: Fusion
                    logger.info(f"  Phase 4: Fusing signals...")
                    
                    # Get market data
                    market_data = self._get_market_data()
                    
                    # Fuse all signals
                    signal = self.fusion.fuse_signals(
                        pattern_data=pattern,
                        sentiment_data=sentiment_data,
                        prediction_data=prediction_result,
                        market_data=market_data
                    )
                    
                    logger.info(f"    Final Confidence: {signal.final_confidence:.1%}")
                    logger.info(f"    Recommendation: {signal.recommendation}")
                    
                    # Include signals with confidence >= 55% (regardless of recommendation)
                    # This allows HOLD signals with good confidence to be displayed
                    confidence_threshold = 0.55  # 55% minimum confidence
                    if signal.final_confidence >= confidence_threshold:
                        signals.append(signal)
                        logger.info(f"    [OK] Signal added! (Confidence: {signal.final_confidence:.1%})")
                    else:
                        logger.info(f"    [SKIP] Confidence {signal.final_confidence:.1%} below threshold {confidence_threshold:.1%}")
            
            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # Add delay to avoid rate limiting (only if not the last stock)
            if i < len(stock_universe):
                logger.info(f"  Waiting 5s to avoid rate limits...")
                time.sleep(5)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"SCAN COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"Stocks scanned: {len(stock_universe)}")
        logger.info(f"Signals generated: {len(signals)}")
        
        # Sort by confidence
        signals.sort(key=lambda x: x.final_confidence, reverse=True)
        
        return signals
    
    def _generate_signals_parallel(self, stock_universe: List[Dict[str, str]], 
                                   lookback_days: int) -> List[MultiModalSignal]:
        """
        Generate signals using PARALLEL processing (3-5x faster!)
        
        Uses ThreadPoolExecutor to process multiple stocks simultaneously
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        signals = []
        signals_lock = threading.Lock()
        
        logger.info(f"Scanning {len(stock_universe)} stocks in PARALLEL mode...")
        logger.info(f"Using up to 4 parallel workers")
        
        def process_stock(stock_info):
            """Process a single stock (thread-safe)"""
            ticker = stock_info['symbol']
            company_name = stock_info['name']
            
            try:
                logger.info(f"[PARALLEL] Processing {ticker}...")
                
                # PHASE 1: Pattern Detection
                patterns = self._detect_patterns(ticker, lookback_days)
                
                if not patterns:
                    logger.info(f"[PARALLEL] {ticker}: No patterns found")
                    return []
                
                stock_signals = []
                
                # Process patterns for this stock
                limit = min(len(patterns), self.max_patterns_per_stock)
                for pattern in patterns[:limit]:
                    pattern['company_name'] = company_name
                    
                    # PHASE 2: Sentiment (if not skipped)
                    if self.skip_sentiment:
                        sentiment_data = {
                            'overall_sentiment': 0.0,
                            'sentiment_label': 'NEUTRAL',
                            'confidence': 0.5,
                            'num_articles': 0,
                            'positive_count': 0,
                            'negative_count': 0,
                            'neutral_count': 0,
                            'key_positive_factors': [],
                            'key_negative_factors': [],
                            'key_themes': []
                        }
                    else:
                        try:
                            sentiment_result = self.sentiment_analyzer.fetch_and_analyze_sentiment(
                                stock_symbol=ticker,
                                company_name=company_name,
                                days_back=7
                            )
                            if not sentiment_result['success']:
                                continue
                            sentiment_data = sentiment_result['data']
                        except Exception:
                            sentiment_data = {
                                'overall_sentiment': 0.0,
                                'sentiment_label': 'NEUTRAL',
                                'confidence': 0.5,
                                'num_articles': 0,
                                'positive_count': 0,
                                'negative_count': 0,
                                'neutral_count': 0,
                                'key_positive_factors': [],
                                'key_negative_factors': [],
                                'key_themes': []
                            }
                    
                    # PHASE 3: Price Prediction
                    price_data = self._fetch_price_data(ticker, lookback_days)
                    if price_data is None or len(price_data) < 50:
                        continue
                    
                    prediction_result = self.price_predictor.forecast_stock_price(
                        price_data, horizon=10
                    )
                    
                    if 'error' in prediction_result:
                        continue
                    
                    # PHASE 4: Fusion
                    market_data = self._get_market_data()
                    signal = self.fusion.fuse_signals(
                        pattern_data=pattern,
                        sentiment_data=sentiment_data,
                        prediction_data=prediction_result,
                        market_data=market_data
                    )
                    
                    # Filter by confidence
                    if signal.final_confidence >= 0.55:
                        stock_signals.append(signal)
                
                logger.info(f"[PARALLEL] {ticker}: Generated {len(stock_signals)} signals")
                return stock_signals
            
            except Exception as e:
                logger.error(f"[PARALLEL] Error processing {ticker}: {e}")
                return []
        
        # Execute in parallel (max 4 workers to avoid rate limits)
        max_workers = 4 if not self.skip_sentiment else 8  # More workers when no API calls
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all stocks
            future_to_stock = {
                executor.submit(process_stock, stock): stock 
                for stock in stock_universe
            }
            
            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_stock):
                completed += 1
                stock = future_to_stock[future]
                try:
                    stock_signals = future.result()
                    with signals_lock:
                        signals.extend(stock_signals)
                    logger.info(f"Progress: {completed}/{len(stock_universe)} stocks completed")
                except Exception as e:
                    logger.error(f"Error processing {stock['symbol']}: {e}")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"PARALLEL SCAN COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"Stocks scanned: {len(stock_universe)}")
        logger.info(f"Signals generated: {len(signals)}")
        
        # Sort by confidence
        signals.sort(key=lambda x: x.final_confidence, reverse=True)
        
        return signals
    
    def _detect_patterns(self, ticker: str, lookback_days: int) -> List[Dict]:
        """
        Detect patterns for a single stock
        Supports both single timeframe and multi-timeframe detection
        
        Returns:
            List of pattern dictionaries
        """
        try:
            # Multi-timeframe detection if enabled
            if self.enable_multitimeframe:
                return self._detect_patterns_multitimeframe(ticker)
            
            # Standard single timeframe detection (daily)
            # Fetch data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)
            stock_data = batch_fetch_data([ticker], start_date, end_date, save_csv=False)
            
            if ticker not in stock_data or stock_data[ticker] is None:
                return []
            
            df = stock_data[ticker]
            
            # Scan for patterns
            all_patterns = batch_scan_patterns([ticker], stock_data)
            
            if not all_patterns:
                return []
            
            # Filter high quality (all_patterns is already a list for this ticker)
            high_quality = filter_high_quality_patterns(all_patterns)
            
            if not high_quality:
                return []
            
            # Format patterns
            patterns = []
            current_price = float(df['close'].iloc[-1])
            
            for pattern in high_quality:
                # Estimate support/resistance (simplified)
                recent_low = float(df['low'].tail(20).min())
                recent_high = float(df['high'].tail(20).max())
                
                patterns.append({
                    'ticker': ticker,
                    'company_name': ticker,  # Will be updated by caller
                    'date': pattern.get('detection_date', datetime.now().strftime('%Y-%m-%d')),
                    'pattern_type': pattern['pattern_type'],
                    'timeframe': '1D',  # Default timeframe
                    'quality': pattern.get('confidence_score', 0.7),
                    'win_rate': 0.60,  # Default, would come from historical data
                    'current_price': pattern.get('price_at_detection', current_price),
                    'support': recent_low,
                    'resistance': recent_high,
                    'target': current_price * 1.05  # 5% default target
                })
            
            return patterns
        
        except Exception as e:
            logger.error(f"Pattern detection error for {ticker}: {e}")
            return []
    
    def _detect_patterns_multitimeframe(self, ticker: str) -> List[Dict]:
        """
        Detect patterns across multiple timeframes (1W, 1D, 4H, 1H)
        
        Returns:
            List of multi-timeframe pattern dictionaries
        """
        try:
            from pattern_detection.multitimeframe_scanner import scan_all_timeframes, combine_multitimeframe_signals
            
            logger.info(f"  Multi-timeframe scan enabled...")
            
            # Scan all timeframes
            tf_patterns = scan_all_timeframes(ticker)
            
            # Combine into unified signals
            multitf_signals = combine_multitimeframe_signals(ticker, tf_patterns, min_confidence=0.5)
            
            if not multitf_signals:
                return []
            
            # Format for multimodal system
            patterns = []
            for signal in multitf_signals:
                patterns.append({
                    'ticker': ticker,
                    'company_name': ticker,
                    'date': signal['detection_date'],
                    'pattern_type': signal['pattern_type'],
                    'timeframe': signal['primary_timeframe'],
                    'timeframe_alignment': signal.get('timeframe_alignment', {}),
                    'aligned_timeframes': signal.get('aligned_timeframes', 0),
                    'quality': signal['multitimeframe_confidence'],
                    'win_rate': 0.60 + (signal.get('aligned_timeframes', 0) * 0.05),  # Boost for alignment
                    'current_price': signal['price_at_detection'],
                    'support': signal['price_at_detection'] * 0.95,  # Simplified
                    'resistance': signal['price_at_detection'] * 1.05,  # Simplified
                    'target': signal['price_at_detection'] * 1.05
                })
            
            logger.info(f"  Found {len(patterns)} multi-timeframe patterns")
            return patterns
        
        except Exception as e:
            logger.error(f"Multi-timeframe detection error for {ticker}: {e}")
            # Fallback to single timeframe
            return []
    
    def _fetch_price_data(self, ticker: str, days: int) -> Optional[pd.Series]:
        """
        Fetch price data for prediction
        
        Returns:
            Series with DatetimeIndex and close prices
        """
        try:
            import yfinance as yf
            
            # Add .NS suffix if not present
            if not ticker.endswith('.NS'):
                ticker_yf = f"{ticker}.NS"
            else:
                ticker_yf = ticker
            
            # Fetch data
            stock = yf.Ticker(ticker_yf)
            data = stock.history(period=f"{days}d")
            
            if data.empty:
                return None
            
            # Return close prices as Series
            prices = data['Close']
            return prices
        
        except Exception as e:
            logger.error(f"Price fetch error for {ticker}: {e}")
            return None
    
    def _get_market_data(self) -> Dict:
        """
        Get market context (Nifty, VIX, etc.)
        
        Returns:
            Dict with market condition data
        """
        try:
            import yfinance as yf
            
            # Fetch Nifty 50
            nifty = yf.Ticker("^NSEI")
            nifty_data = nifty.history(period="10d")
            
            if not nifty_data.empty and len(nifty_data) >= 6:
                current = nifty_data['Close'].iloc[-1]
                five_days_ago = nifty_data['Close'].iloc[-6]
                nifty_change_5d = (current - five_days_ago) / five_days_ago
            else:
                nifty_change_5d = 0.0
            
            # Fetch India VIX
            vix = yf.Ticker("^INDIAVIX")
            vix_data = vix.history(period="5d")
            
            if not vix_data.empty:
                current_vix = vix_data['Close'].iloc[-1]
            else:
                current_vix = 15.0  # Default
            
            return {
                'nifty_change_5d': float(nifty_change_5d),
                'vix': float(current_vix),
                'major_event_risk': False  # Would need calendar integration
            }
        
        except Exception as e:
            logger.warning(f"Market data fetch error: {e}")
            return {
                'nifty_change_5d': 0.0,
                'vix': 15.0,
                'major_event_risk': False
            }
    
    def export_signals(self, signals: List[MultiModalSignal], 
                      output_file: str = "multimodal_signals.csv"):
        """
        Export signals to CSV for review
        
        Args:
            signals: List of signals
            output_file: Output file path
        """
        if not signals:
            logger.info("No signals to export")
            return
        
        # Convert to DataFrame
        data = []
        for signal in signals:
            data.append({
                'Ticker': signal.ticker,
                'Company': signal.company_name,
                'Pattern': signal.pattern_type,
                'Recommendation': signal.recommendation,
                'Confidence': f"{signal.final_confidence:.1%}",
                'Position_Size': f"{signal.position_size_pct:.2f}%",
                'Entry': f"Rs.{signal.entry_price:.2f}",
                'Stop_Loss': f"Rs.{signal.stop_loss:.2f}",
                'Target': f"Rs.{signal.target_price:.2f}",
                'R:R': f"{signal.risk_reward_ratio:.2f}:1",
                'Pattern_Score': f"{signal.pattern_score:.3f}",
                'Sentiment': f"{signal.sentiment_raw:+.2f} ({signal.sentiment_label})",
                'Predicted_Return': f"{signal.predicted_return*100:+.1f}%",
                'Articles': signal.num_articles
            })
        
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)
        
        logger.info(f"Signals exported to: {output_file}")


# Example usage
if __name__ == '__main__':
    print("="*80)
    print("MULTI-MODAL SIGNAL GENERATOR")
    print("100% FREE - Pattern Detection + Sentiment + Price Prediction")
    print("="*80)
    
    # Initialize generator
    generator = MultiModalSignalGenerator()
    
    # Test with a few stocks
    test_universe = [
        {'symbol': 'RELIANCE', 'name': 'Reliance Industries'},
        {'symbol': 'TCS', 'name': 'Tata Consultancy Services'},
        {'symbol': 'HDFCBANK', 'name': 'HDFC Bank'},
    ]
    
    print(f"\nScanning {len(test_universe)} stocks...")
    
    # Generate signals
    signals = generator.generate_signals(test_universe)
    
    # Display results
    if signals:
        print(f"\n{'='*80}")
        print("SIGNALS GENERATED")
        print(f"{'='*80}")
        
        for i, signal in enumerate(signals, 1):
            print(f"\n{i}. {signal.ticker} ({signal.company_name})")
            print(f"   Recommendation: {signal.recommendation} (Confidence: {signal.final_confidence:.1%})")
            print(f"   Entry: Rs.{signal.entry_price:.2f} | Target: Rs.{signal.target_price:.2f} | SL: Rs.{signal.stop_loss:.2f}")
            print(f"   Pattern: {signal.pattern_type} | Sentiment: {signal.sentiment_label} | Predicted: {signal.predicted_return*100:+.1f}%")
        
        # Export to CSV
        generator.export_signals(signals, "test_signals.csv")
    else:
        print("\nNo signals generated")

