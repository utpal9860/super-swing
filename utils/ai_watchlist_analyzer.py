"""
AI-Powered Custom Watchlist Scanner
Analyzes user-specified stocks with deep AI analysis
"""

import sys
import json
import logging
from datetime import datetime
from typing import List, Dict
import pandas as pd
import yfinance as yf
import google.generativeai as genai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Windows console UTF-8 fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def fetch_stock_data(symbol: str) -> Dict:
    """Fetch comprehensive stock data for analysis"""
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        
        # Get historical data
        hist_1d = ticker.history(period="1d", interval="5m")  # Intraday
        hist_1mo = ticker.history(period="1mo")  # Daily for 1 month
        hist_3mo = ticker.history(period="3mo")  # Daily for 3 months
        
        if hist_1mo.empty:
            return {'error': f'No data available for {symbol}'}
        
        latest = hist_1mo.iloc[-1]
        
        # Calculate technical indicators
        df = hist_1mo.copy()
        
        # Moving averages
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean() if len(df) >= 50 else None
        df['EMA_9'] = df['Close'].ewm(span=9).mean()
        df['EMA_21'] = df['Close'].ewm(span=21).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema_12 = df['Close'].ewm(span=12).mean()
        ema_26 = df['Close'].ewm(span=26).mean()
        df['MACD'] = ema_12 - ema_26
        df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
        
        # ATR (Average True Range)
        high_low = df['High'] - df['Low']
        high_close = abs(df['High'] - df['Close'].shift())
        low_close = abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['ATR'] = true_range.rolling(14).mean()
        
        # Bollinger Bands
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        
        latest_row = df.iloc[-1]
        
        # Get last candle timestamp
        last_candle = hist_1d.index[-1].strftime('%Y-%m-%d %H:%M:%S IST') if not hist_1d.empty else hist_1mo.index[-1].strftime('%Y-%m-%d')
        
        # Try to get company info
        try:
            info = ticker.info
            company_name = info.get('longName', symbol)
            sector = info.get('sector', 'N/A')
            industry = info.get('industry', 'N/A')
            market_cap = info.get('marketCap', 0)
            pe_ratio = info.get('trailingPE', 'N/A')
            pb_ratio = info.get('priceToBook', 'N/A')
        except:
            company_name = symbol
            sector = 'N/A'
            industry = 'N/A'
            market_cap = 0
            pe_ratio = 'N/A'
            pb_ratio = 'N/A'
        
        data = {
            'symbol': symbol,
            'company_name': company_name,
            'sector': sector,
            'industry': industry,
            'current_price': float(latest['Close']),
            'open': float(latest['Open']),
            'high': float(latest['High']),
            'low': float(latest['Low']),
            'volume': int(latest['Volume']),
            'last_candle': last_candle,
            
            # Technical indicators
            'sma_20': float(latest_row['SMA_20']) if pd.notna(latest_row['SMA_20']) else None,
            'sma_50': float(latest_row['SMA_50']) if pd.notna(latest_row.get('SMA_50')) else None,
            'ema_9': float(latest_row['EMA_9']) if pd.notna(latest_row['EMA_9']) else None,
            'ema_21': float(latest_row['EMA_21']) if pd.notna(latest_row['EMA_21']) else None,
            'rsi': float(latest_row['RSI']) if pd.notna(latest_row['RSI']) else None,
            'macd': float(latest_row['MACD']) if pd.notna(latest_row['MACD']) else None,
            'macd_signal': float(latest_row['MACD_Signal']) if pd.notna(latest_row['MACD_Signal']) else None,
            'atr': float(latest_row['ATR']) if pd.notna(latest_row['ATR']) else None,
            'bb_upper': float(latest_row['BB_Upper']) if pd.notna(latest_row['BB_Upper']) else None,
            'bb_middle': float(latest_row['BB_Middle']) if pd.notna(latest_row['BB_Middle']) else None,
            'bb_lower': float(latest_row['BB_Lower']) if pd.notna(latest_row['BB_Lower']) else None,
            
            # Fundamental data
            'market_cap': market_cap,
            'pe_ratio': pe_ratio,
            'pb_ratio': pb_ratio,
            
            # Recent price action
            'week_high': float(hist_1mo['High'].max()),
            'week_low': float(hist_1mo['Low'].min()),
            'month_return': float(((latest['Close'] - hist_1mo.iloc[0]['Close']) / hist_1mo.iloc[0]['Close']) * 100) if len(hist_1mo) > 1 else 0,
            '3month_return': float(((latest['Close'] - hist_3mo.iloc[0]['Close']) / hist_3mo.iloc[0]['Close']) * 100) if len(hist_3mo) > 20 else None,
        }
        
        return data
    
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return {'error': str(e)}


def create_watchlist_analysis_prompt(stocks_data: List[Dict], strategy: str = "swing") -> str:
    """Create AI prompt for custom watchlist analysis"""
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    
    # Format stock data
    stocks_str = ""
    for stock in stocks_data:
        if 'error' in stock:
            stocks_str += f"\n**{stock.get('symbol', 'Unknown')}:** Data unavailable - {stock['error']}\n"
            continue
        
        stocks_str += f"""
**{stock['symbol']} - {stock['company_name']}**
Sector: {stock['sector']} | Industry: {stock['industry']}
Current Price: ₹{stock['current_price']:.2f} | Volume: {stock['volume']:,}
Last Update: {stock['last_candle']}

Technical Indicators:
- SMA 20: {f"₹{stock['sma_20']:.2f}" if stock.get('sma_20') is not None else 'N/A'} | SMA 50: {f"₹{stock['sma_50']:.2f}" if stock.get('sma_50') is not None else 'N/A'}
- EMA 9: {f"₹{stock['ema_9']:.2f}" if stock.get('ema_9') is not None else 'N/A'} | EMA 21: {f"₹{stock['ema_21']:.2f}" if stock.get('ema_21') is not None else 'N/A'}
- RSI: {f"{stock['rsi']:.1f}" if stock.get('rsi') is not None else 'N/A'}
- MACD: {f"{stock['macd']:.2f}" if stock.get('macd') is not None else 'N/A'} | Signal: {f"{stock['macd_signal']:.2f}" if stock.get('macd_signal') is not None else 'N/A'}
- ATR: {f"₹{stock['atr']:.2f}" if stock.get('atr') is not None else 'N/A'}
- Bollinger Bands: Upper {f"₹{stock['bb_upper']:.2f}" if stock.get('bb_upper') is not None else 'N/A'}, Middle {f"₹{stock['bb_middle']:.2f}" if stock.get('bb_middle') is not None else 'N/A'}, Lower {f"₹{stock['bb_lower']:.2f}" if stock.get('bb_lower') is not None else 'N/A'}

Price Action:
- High/Low (1mo): ₹{stock['week_high']:.2f} / ₹{stock['week_low']:.2f}
- 1-Month Return: {stock['month_return']:+.2f}%
- 3-Month Return: {f"{stock.get('3month_return'):+.2f}%" if isinstance(stock.get('3month_return'), (int, float)) else 'N/A'}

Fundamentals:
- Market Cap: {f"₹{stock['market_cap']:,.0f}" if isinstance(stock.get('market_cap'), (int, float)) and stock['market_cap'] else 'N/A'}
- P/E Ratio: {f"{stock['pe_ratio']:.2f}" if isinstance(stock.get('pe_ratio'), (int, float)) and stock['pe_ratio'] else 'N/A'}
- P/B Ratio: {f"{stock['pb_ratio']:.2f}" if isinstance(stock.get('pb_ratio'), (int, float)) and stock['pb_ratio'] else 'N/A'}

"""
    
    # Add strategy-specific context
    strategy_context = ""
    if strategy == "fno":
        strategy_context = """
**F&O Trading Context:**
The user wants to trade these stocks in F&O (Futures & Options). Your analysis should:
- Focus on volatility and liquidity (F&O requires good volumes)
- Recommend specific strike prices for options (ATM/OTM/ITM based on setup)
- Consider IV (Implied Volatility) if stock has active options
- Suggest futures if clearer directional play
- Mention lot sizes and margin requirements if known
- Consider expiry timing (weekly/monthly)
- Focus on shorter timeframes (intraday to few days for options)
"""
    elif strategy == "intraday":
        strategy_context = """
**Intraday Trading Context:**
The user wants SAME DAY trades. Your analysis should:
- Focus on intraday momentum and volatility
- Tighter stop losses (0.5-1% typically)
- Quick targets (1-3% typically)
- Entry/exit within trading hours (9:15 AM - 3:30 PM IST)
- Consider intraday support/resistance
"""
    elif strategy == "long_term":
        strategy_context = """
**Long-Term Investment Context:**
The user wants to INVEST for months/years. Your analysis should:
- Focus heavily on fundamentals (company quality, sector growth)
- Technical entry point matters less (accumulation zones)
- Wider stop losses (10-20% or fundamentals-based)
- Higher targets (20%+ or long-term price targets)
- Consider dividend yield, management quality, competitive moats
"""
    else:  # swing
        strategy_context = """
**Swing Trading Context:**
The user wants trades lasting days to weeks. Your analysis should:
- Balance technical and fundamental analysis
- Typical holding: 3-30 days
- Stop losses: 3-7% based on volatility
- Targets: 5-15% based on setup
- Consider both short-term momentum and medium-term trends
"""
    
    prompt = f"""You are an expert stock analyst with deep knowledge of Indian equity markets and technical analysis.

**Current Time:** {current_time}

{strategy_context}

**User's Custom Watchlist:**
The user is specifically interested in ONLY THESE STOCKS. 
Analyze ONLY the stocks listed below. DO NOT add any other stocks.

{stocks_str}

**Analysis Requirements:**

For EACH stock listed above (and ONLY those stocks), provide:

1. **Current Setup (Technical):**
   - Trend analysis (uptrend/downtrend/sideways)
   - Price vs moving averages (bullish/bearish)
   - RSI interpretation (overbought/oversold/neutral)
   - MACD signal (bullish/bearish crossover)
   - Bollinger Band position (breakout/breakdown/middle)
   - Support and resistance levels (calculate from price action)

2. **Entry/Exit Recommendation:**
   - Is it a BUY, SELL, or HOLD right now?
   - Best entry price (if buy)
   - Stop loss level
   - Target price(s)
   - Risk:Reward ratio
   - Expected holding period

3. **Why/Why Not:**
   - Reasons supporting the trade
   - Risks and concerns
   - Catalyst or trigger

4. **Fundamental View:**
   - Company strength (based on fundamentals)
   - Sector outlook
   - Valuation (expensive/fair/cheap based on P/E, P/B)

5. **Confidence & Priority:**
   - Confidence level (1-10)
   - Priority ranking among the stocks in watchlist
   - Trade quality (A/B/C grade)

6. **Data Freshness:**
   - Last data update timestamp
   - Data reliability

**Response Format (JSON ONLY):**
{{
  "analysis_timestamp": "{current_time}",
  "strategy": "{strategy}",
  "stocks": [
    {{
      "symbol": "RELIANCE",
      "company_name": "Reliance Industries",
      "recommendation": "BUY",
      "confidence": 8.5,
      "priority": 1,
      "grade": "A",
      "entry_price": 2450.00,
      "stop_loss": 2385.00,
      "target_1": 2550.00,
      "target_2": 2680.00,
      "risk_reward": "1:2.5",
      "holding_period": "2-4 weeks",
      "technical_setup": {{
        "trend": "Strong uptrend",
        "price_vs_ma": "Above all major MAs - bullish",
        "rsi": "65 - healthy, not overbought",
        "macd": "Positive crossover - bullish signal",
        "bb_position": "Near upper band - strong momentum",
        "support_levels": [2400, 2350, 2300],
        "resistance_levels": [2500, 2550, 2600]
      }},
      "reasoning": {{
        "why_buy": "Strong technical setup with all indicators aligned bullishly. Breaking consolidation with volume.",
        "risks": ["Market correction risk", "Crude oil price volatility"],
        "catalyst": "Upcoming Q2 results expected to be strong"
      }},
      "fundamental_view": {{
        "company_strength": "Very Strong - Market leader, diversified",
        "sector_outlook": "Positive - Energy and retail both doing well",
        "valuation": "Fair - PE at 25x, reasonable for growth"
      }},
      "data_freshness": {{
        "last_update": "2025-10-27 15:25:00 IST",
        "reliability": "High - recent data"
      }}
    }}
    // ... more stocks
  ],
  "summary": {{
    "total_stocks": 5,
    "buy_count": 3,
    "hold_count": 1,
    "sell_count": 1,
    "avg_confidence": 7.5,
    "top_pick": "RELIANCE",
    "market_advice": "Overall market bullish, good time for selective trades"
  }}
}}

**CRITICAL REQUIREMENTS:**
1. Analyze EVERY stock provided
2. Give specific entry/exit prices based on CURRENT DATA
3. Support/Resistance from actual price levels
4. Be HONEST - if setup is weak, say HOLD or SELL
5. Use the REAL data provided, not generic analysis
6. Confidence should reflect technical + fundamental + market conditions

Provide ONLY the JSON response, no additional text."""
    
    return prompt


def analyze_custom_watchlist(
    api_key: str,
    symbols: List[str],
    strategy: str = "swing",
    model: str = "gemini-1.5-flash"
) -> Dict:
    """
    Analyze user's custom stock watchlist with AI
    
    Args:
        api_key: Gemini API key
        symbols: List of stock symbols (without .NS)
        strategy: Trading strategy (swing, intraday, fno, long_term)
        model: Gemini model to use
        
    Returns:
        Detailed AI analysis for each stock
    """
    try:
        logger.info(f"Analyzing custom watchlist: {symbols}")
        
        # Fetch data for all stocks
        stocks_data = []
        for symbol in symbols:
            logger.info(f"Fetching data for {symbol}...")
            data = fetch_stock_data(symbol)
            stocks_data.append(data)
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }
        
        gemini_model = genai.GenerativeModel(
            model_name=model,
            generation_config=generation_config
        )
        
        # Create prompt
        prompt = create_watchlist_analysis_prompt(stocks_data, strategy)
        
        logger.info("Sending custom watchlist analysis to Gemini AI...")
        
        # Generate response
        response = gemini_model.generate_content(prompt)
        
        if not response or not response.text:
            raise Exception("Empty response from AI")
        
        # Parse response
        response_text = response.text.strip()
        
        # Clean markdown
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            if lines and lines[0].strip().startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            response_text = '\n'.join(lines).strip()
        
        # Remove trailing commas
        import re
        response_text = re.sub(r',(\s*[}\]])', r'\1', response_text)
        
        # Parse JSON
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Response: {response_text[:500]}")
            raise Exception(f"Could not parse AI response: {e}")
        
        logger.info(f"Custom watchlist analysis complete! Analyzed {len(result.get('stocks', []))} stocks")
        
        # Enrich stocks with current_price from fetched data
        # IMPORTANT: Only include stocks that were actually requested by the user
        requested_symbols = [s.upper() for s in symbols]  # Normalize to uppercase
        enriched_stocks = []
        
        for stock in result.get('stocks', []):
            stock_symbol = stock.get('symbol', '').upper().replace('.NS', '')  # Normalize
            
            # Filter: Only include if this stock was requested
            if stock_symbol not in requested_symbols:
                logger.warning(f"AI returned unexpected stock: {stock_symbol}. Skipping.")
                continue
            
            # Find matching stock data
            matching_data = next((s for s in stocks_data if s['symbol'] == stock['symbol']), None)
            if matching_data:
                # Add current_price if not provided by AI
                if stock.get('entry_price') is None or stock.get('current_price') is None:
                    stock['current_price'] = matching_data.get('current_price', None)
                    # If AI didn't provide entry_price, use current_price as fallback
                    if stock.get('entry_price') is None:
                        stock['entry_price'] = stock['current_price']
            enriched_stocks.append(stock)
        
        # Log if AI added extra stocks
        if len(enriched_stocks) < len(result.get('stocks', [])):
            logger.info(f"Filtered out {len(result.get('stocks', [])) - len(enriched_stocks)} stocks that were not requested")
        
        # Update summary to reflect actual filtered count
        summary = result.get('summary', {})
        if summary:
            summary['total_stocks'] = len(enriched_stocks)
        
        return {
            'success': True,
            'strategy': strategy,
            'stocks': enriched_stocks,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Custom watchlist analysis error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == '__main__':
    # Test
    print("\n=== Custom Watchlist AI Analyzer Test ===\n")
    
    api_key = input("Enter your Gemini API key: ").strip()
    if not api_key:
        print("No API key provided.")
        exit(1)
    
    symbols_input = input("Enter stock symbols (comma-separated, e.g., RELIANCE,TCS,INFY): ").strip()
    symbols = [s.strip().upper() for s in symbols_input.split(',')]
    
    result = analyze_custom_watchlist(
        api_key=api_key,
        symbols=symbols,
        strategy="swing"
    )
    
    if result['success']:
        print(f"\n✅ Analyzed {len(result['stocks'])} stocks\n")
        for stock in result['stocks']:
            print(f"\n{stock['symbol']} - {stock['recommendation']}")
            print(f"   Confidence: {stock['confidence']}/10, Grade: {stock['grade']}")
            print(f"   Entry: ₹{stock['entry_price']}, Target: ₹{stock['target_1']}, SL: ₹{stock['stop_loss']}")
            print(f"   {stock['reasoning']['why_buy'][:100]}...")
        
        print(f"\n📊 Top Pick: {result['summary']['top_pick']}")
    else:
        print(f"\n❌ Error: {result['error']}")

