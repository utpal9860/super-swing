"""
AI Trade Analyzer - Claude & OpenAI Integration
Uses numeric data (OHLCV + indicators) for efficient AI analysis
"""

import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import yfinance as yf
import pandas as pd
import numpy as np
from anthropic import Anthropic
from openai import OpenAI
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


def fetch_stock_data(symbol: str, days: int = 60) -> Optional[pd.DataFrame]:
    """
    Fetch historical stock data with indicators
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE.NS')
        days: Number of days of historical data
        
    Returns:
        DataFrame with OHLCV and calculated indicators
    """
    try:
        logger.info(f"Fetching data for {symbol}")
        
        # Add .NS if not present
        if not symbol.endswith('.NS'):
            symbol = f"{symbol}.NS"
        
        # Fetch data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        stock = yf.Ticker(symbol)
        df = stock.history(start=start_date, end=end_date)
        
        if df.empty:
            logger.error(f"No data found for {symbol}")
            return None
        
        # Calculate indicators
        df = calculate_indicators(df)
        
        return df
    
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return None


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate technical indicators"""
    
    # SMA
    df['sma_20'] = df['Close'].rolling(window=20).mean()
    df['sma_50'] = df['Close'].rolling(window=50).mean()
    
    # EMA
    df['ema_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # MACD
    df['ema_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['ema_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['macd'] = df['ema_12'] - df['ema_26']
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    # ATR (Average True Range)
    df['high_low'] = df['High'] - df['Low']
    df['high_close'] = abs(df['High'] - df['Close'].shift())
    df['low_close'] = abs(df['Low'] - df['Close'].shift())
    df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    df['atr_14'] = df['true_range'].rolling(window=14).mean()
    
    # Volume indicators
    df['volume_sma_20'] = df['Volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['Volume'] / df['volume_sma_20']
    
    # Bollinger Bands
    df['bb_middle'] = df['Close'].rolling(window=20).mean()
    df['bb_std'] = df['Close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (2 * df['bb_std'])
    df['bb_lower'] = df['bb_middle'] - (2 * df['bb_std'])
    
    return df


def prepare_data_for_ai(symbol: str, strategy: str, current_price: float, 
                        stop_loss: float, target: float) -> Dict:
    """
    Prepare stock data for AI analysis
    
    Returns:
        Dictionary with formatted data for AI prompt
    """
    df = fetch_stock_data(symbol, days=60)
    
    if df is None or df.empty:
        return {
            'error': 'Unable to fetch stock data',
            'symbol': symbol
        }
    
    # Get latest values
    latest = df.iloc[-1]
    
    # Recent price action (last 20 days)
    recent_df = df.tail(20)
    recent_ohlc = []
    for idx, row in recent_df.iterrows():
        recent_ohlc.append({
            'date': idx.strftime('%Y-%m-%d'),
            'open': round(row['Open'], 2),
            'high': round(row['High'], 2),
            'low': round(row['Low'], 2),
            'close': round(row['Close'], 2),
            'volume': int(row['Volume'])
        })
    
    # Calculate price momentum
    price_change_5d = ((latest['Close'] - df['Close'].iloc[-6]) / df['Close'].iloc[-6] * 100) if len(df) >= 6 else 0
    price_change_20d = ((latest['Close'] - df['Close'].iloc[-21]) / df['Close'].iloc[-21] * 100) if len(df) >= 21 else 0
    
    # Prepare data structure
    data = {
        'symbol': symbol,
        'strategy': strategy,
        'current_price': round(current_price, 2),
        'suggested_stop_loss': round(stop_loss, 2),
        'suggested_target': round(target, 2),
        'suggested_rr_ratio': round((target - current_price) / (current_price - stop_loss), 2),
        'indicators': {
            'sma_20': round(latest['sma_20'], 2) if not pd.isna(latest['sma_20']) else None,
            'sma_50': round(latest['sma_50'], 2) if not pd.isna(latest['sma_50']) else None,
            'ema_20': round(latest['ema_20'], 2) if not pd.isna(latest['ema_20']) else None,
            'rsi_14': round(latest['rsi_14'], 2) if not pd.isna(latest['rsi_14']) else None,
            'macd': round(latest['macd'], 2) if not pd.isna(latest['macd']) else None,
            'macd_signal': round(latest['macd_signal'], 2) if not pd.isna(latest['macd_signal']) else None,
            'macd_histogram': round(latest['macd_histogram'], 2) if not pd.isna(latest['macd_histogram']) else None,
            'atr_14': round(latest['atr_14'], 2) if not pd.isna(latest['atr_14']) else None,
            'volume_ratio': round(latest['volume_ratio'], 2) if not pd.isna(latest['volume_ratio']) else None,
            'bb_upper': round(latest['bb_upper'], 2) if not pd.isna(latest['bb_upper']) else None,
            'bb_lower': round(latest['bb_lower'], 2) if not pd.isna(latest['bb_lower']) else None,
        },
        'momentum': {
            'price_change_5d': round(price_change_5d, 2),
            'price_change_20d': round(price_change_20d, 2),
        },
        'recent_ohlc': recent_ohlc[-10:]  # Last 10 days
    }
    
    return data


def create_ai_prompt(data: Dict) -> str:
    """Create structured prompt for AI analysis"""
    
    prompt = f"""You are an expert stock market analyst specializing in Indian markets (NSE/BSE). Analyze this trade setup with DEEP analysis.

**Stock Details:**
Symbol: {data['symbol']}
Strategy: {data['strategy']}
Current Price: ₹{data['current_price']}

**Suggested Levels:**
Entry: ₹{data['current_price']}
Stop Loss: ₹{data['suggested_stop_loss']} ({((data['suggested_stop_loss'] - data['current_price']) / data['current_price'] * 100):.2f}%)
Target: ₹{data['suggested_target']} (+{((data['suggested_target'] - data['current_price']) / data['current_price'] * 100):.2f}%)
Risk:Reward Ratio: {data['suggested_rr_ratio']}:1

**Technical Indicators:**
- SMA(20): ₹{data['indicators']['sma_20']}
- SMA(50): ₹{data['indicators']['sma_50']}
- EMA(20): ₹{data['indicators']['ema_20']}
- RSI(14): {data['indicators']['rsi_14']}
- MACD: {data['indicators']['macd']} (Signal: {data['indicators']['macd_signal']}, Histogram: {data['indicators']['macd_histogram']})
- ATR(14): {data['indicators']['atr_14']}
- Volume Ratio: {data['indicators']['volume_ratio']}x (vs 20-day avg)
- Bollinger Bands: Upper ₹{data['indicators']['bb_upper']}, Lower ₹{data['indicators']['bb_lower']}

**Price Momentum:**
- 5-day change: {data['momentum']['price_change_5d']}%
- 20-day change: {data['momentum']['price_change_20d']}%

**Recent Price Action (Last 10 Days):**
{json.dumps(data['recent_ohlc'], indent=2)}

**DEEP ANALYSIS REQUIRED:**

Perform comprehensive multi-dimensional analysis:

1. **Price Action & Technical Analysis:**
   - Trend direction (uptrend/downtrend/sideways)
   - Support and resistance levels
   - Chart patterns (if any)
   - Price relative to moving averages
   - Candlestick patterns in recent data

2. **Technical Indicators Assessment:**
   - RSI: Overbought (>70) / Oversold (<30) / Neutral?
   - MACD: Bullish/Bearish crossover? Divergence?
   - Volume: Confirming price move or diverging?
   - Bollinger Bands: Price position and volatility
   - Moving average alignment (golden/death cross?)

3. **Fundamental Analysis (use your knowledge):**
   - Company business model and sector
   - Recent earnings performance (if known)
   - Revenue and profit growth trends
   - Debt levels and financial health
   - Competitive position in sector
   - Any recent news or events affecting the stock

4. **Sector & Market Analysis:**
   - How is this sector performing currently?
   - Sector rotation trends (money flowing in/out?)
   - Comparison with NIFTY/broader market
   - Sector-specific tailwinds or headwinds
   - Peer comparison (if applicable)

5. **Risk Assessment:**
   - Is stop loss logical given ATR/volatility?
   - Is target realistic given recent price action?
   - What could go wrong? (reversals, gaps, earnings, news)
   - Position sizing concerns?
   - Event risks (earnings, policy changes, etc.)

6. **Strategy & Timing:**
   - Does this match the stated strategy ({data['strategy']})?
   - Is timing right for this strategy?
   - Market conditions favorable?
   - Better to wait for confirmation?

7. **Entry Quality:**
   - Is this a good entry point or wait?
   - Better entry levels nearby?
   - Risk:reward acceptable (minimum 1:2)?

**Based on ALL above factors, provide:**
- Whether this is a valid, high-quality trade setup
- Your confidence (1-10): Consider ALL factors above
- Optimized entry, SL, target (can differ from suggested)
- Clear reasoning explaining your decision
- Specific risk factors the trader should monitor

**Response Format (JSON ONLY):**
{{
  "valid": true/false,
  "confidence": 7.5,
  "entry": 2450.00,
  "stop_loss": 2385.00,
  "target": 2580.00,
  "reasoning": "COMPREHENSIVE 4-5 sentence explanation covering: (1) Technical setup and trend, (2) Fundamental outlook if known, (3) Sector context, (4) Why this specific entry/exit makes sense, (5) Key catalysts or concerns",
  "risk_factors": [
    "SPECIFIC technical risk with levels (e.g., 'RSI at 78 indicates overbought - potential pullback to ₹2400 support')", 
    "SPECIFIC fundamental/news risk (e.g., 'Upcoming earnings on 15th Jan could create volatility')",
    "SPECIFIC market/sector risk (e.g., 'IT sector facing headwinds from weak US demand')"
  ],
  "technical_analysis": {{
    "trend": "Detailed trend assessment with evidence (e.g., 'Strong uptrend - price above all EMAs, higher highs and higher lows')",
    "support_resistance": "Specific levels with reasoning (e.g., 'Support at ₹2385 (20-day low), Resistance at ₹2580 (previous high)')",
    "indicator_summary": "Comprehensive indicator view (e.g., 'RSI 65 (bullish but not overbought), MACD positive crossover, Volume 2.5x avg')",
    "price_action": "Specific patterns observed (e.g., 'Bullish engulfing candle with high volume, breaking consolidation')"
  }},
  "fundamental_analysis": {{
    "company_overview": "Brief company description and sector (e.g., 'Leading IT services company in software development')",
    "earnings_trend": "Recent earnings performance with ✓ or ✗ (e.g., '✓ Q2: 15% revenue growth, ✓ profit up 20%, ✓ beat estimates' OR '✗ Declining margins, ✗ revenue miss')",
    "financial_health": "Key metrics if known (e.g., 'Debt-free, ROE 18%, good cash flow' OR 'Data not available for penny stock')",
    "sector_outlook": "Sector performance and trends (e.g., '✓ IT sector outperforming NIFTY by 5% this quarter')",
    "recent_news": "Any known catalysts or concerns (e.g., 'Won ₹500Cr contract last week' OR 'No recent major news')"
  }},
  "market_context": {{
    "nifty_correlation": "How stock relates to broader market (e.g., 'Moving with NIFTY' or 'Outperforming NIFTY by 3%')",
    "sector_strength": "Sector momentum (e.g., 'Banking sector leading market rally' or 'Defensive sector in consolidation')",
    "risk_sentiment": "Market risk appetite (e.g., 'High risk-on sentiment favors this trade' or 'Defensive mode, risky for small-caps')"
  }}
}}

**CRITICAL INSTRUCTIONS:**
1. "reasoning" must be 4-5 FULL sentences covering technical + fundamental + sector + timing
2. "risk_factors" must be SPECIFIC with actual levels, dates, or events - NOT generic warnings
3. "technical_analysis" - analyze ALL the indicators provided, be thorough
4. "fundamental_analysis" - use your knowledge of the company/sector:
   - If it's a well-known company: provide earnings, growth, sector info
   - If it's a penny stock or unknown: state "Limited fundamental data available for small-cap"
   - Use ✓ for positive factors, ✗ for negative factors
5. "market_context" - consider broader market conditions
6. Be HONEST - if you don't know fundamentals, say so. Don't make up data.
7. Be CRITICAL - reject setups with weak technicals OR poor fundamentals OR bad timing

Provide ONLY the JSON response, no additional text or markdown."""
    
    return prompt


def analyze_with_claude(api_key: str, model: str, data: Dict) -> Dict:
    """
    Analyze trade using Claude (Anthropic)
    
    Args:
        api_key: Anthropic API key
        model: Model name (e.g., 'claude-3-5-haiku-20241022')
        data: Prepared stock data
        
    Returns:
        Analysis results with cost
    """
    try:
        client = Anthropic(api_key=api_key)
        prompt = create_ai_prompt(data)
        
        logger.info(f"Analyzing with Claude: {model}")
        logger.info("="*80)
        logger.info("PROMPT SENT TO AI:")
        logger.info(prompt)
        logger.info("="*80)
        
        # Call Claude API
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract response text
        response_text = response.content[0].text
        
        # Parse JSON response
        analysis = json.loads(response_text)
        
        # Calculate cost
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        
        # Haiku pricing: $0.25/1M input, $1.25/1M output
        cost = (input_tokens * 0.25 / 1_000_000) + (output_tokens * 1.25 / 1_000_000)
        
        analysis['cost'] = cost
        analysis['tokens_used'] = {
            'input': input_tokens,
            'output': output_tokens
        }
        
        logger.info(f"Analysis complete. Cost: ${cost:.6f}")
        
        return {
            'success': True,
            'analysis': analysis,
            'provider': 'claude',
            'model': model
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response: {e}")
        logger.error(f"Response text: {response_text}")
        return {
            'success': False,
            'error': 'Failed to parse AI response. Please try again.',
            'raw_response': response_text
        }
    
    except Exception as e:
        logger.error(f"Claude analysis error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def analyze_with_openai(api_key: str, model: str, data: Dict) -> Dict:
    """
    Analyze trade using OpenAI (GPT)
    
    Args:
        api_key: OpenAI API key
        model: Model name (e.g., 'gpt-3.5-turbo', 'gpt-4')
        data: Prepared stock data
        
    Returns:
        Analysis results with cost
    """
    try:
        client = OpenAI(api_key=api_key)
        prompt = create_ai_prompt(data)
        
        logger.info(f"Analyzing with OpenAI: {model}")
        logger.info("="*80)
        logger.info("PROMPT SENT TO AI:")
        logger.info(prompt)
        logger.info("="*80)
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert stock market analyst specializing in Indian markets."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1024
        )
        
        # Extract response text
        response_text = response.choices[0].message.content
        
        # Parse JSON response
        analysis = json.loads(response_text)
        
        # Calculate cost (approximate)
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        
        # GPT-3.5 pricing: $0.50/1M input, $1.50/1M output
        # GPT-4 pricing: $30/1M input, $60/1M output (adjust as needed)
        if 'gpt-4' in model.lower():
            cost = (input_tokens * 30 / 1_000_000) + (output_tokens * 60 / 1_000_000)
        else:
            cost = (input_tokens * 0.50 / 1_000_000) + (output_tokens * 1.50 / 1_000_000)
        
        analysis['cost'] = cost
        analysis['tokens_used'] = {
            'input': input_tokens,
            'output': output_tokens
        }
        
        logger.info(f"Analysis complete. Cost: ${cost:.6f}")
        
        return {
            'success': True,
            'analysis': analysis,
            'provider': 'openai',
            'model': model
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI response: {e}")
        logger.error(f"Response text: {response_text}")
        return {
            'success': False,
            'error': 'Failed to parse AI response. Please try again.',
            'raw_response': response_text
        }
    
    except Exception as e:
        logger.error(f"OpenAI analysis error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def analyze_with_openai_bearer(bearer_token: str, model: str, data: Dict) -> Dict:
    """
    Analyze trade using OpenAI with bearer token (experimental)
    
    IMPORTANT: Web UI session tokens (from chat.openai.com) DO NOT WORK with the official API.
    You need an actual API key from platform.openai.com.
    
    This function is kept for future implementation of web UI scraping.
    
    Args:
        bearer_token: Bearer token from browser
        model: Model name (e.g., 'gpt-3.5-turbo', 'gpt-4')
        data: Prepared stock data
        
    Returns:
        Error message explaining the limitation
    """
    return {
        'success': False,
        'error': '''OpenAI web UI tokens don't work with the API.

The token you copied from chat.openai.com is a SESSION token for the web interface, not an API key.

**Two Options:**

1. **Use API Key (Recommended):**
   - Go to platform.openai.com/api-keys
   - Create an API key (starts with "sk-...")
   - Add $5 minimum credit
   - Use "API Key" mode in profile

2. **Use Claude Instead (Free):**
   - Get API key from console.anthropic.com
   - Has free tier
   - Works better for trading analysis

Sorry for the confusion! Web UI bearer tokens require complex web scraping which isn't implemented yet.'''
    }


def analyze_with_claude_bearer(bearer_token: str, model: str, data: Dict) -> Dict:
    """
    Analyze trade using Claude with bearer token (not yet implemented)
    
    Args:
        bearer_token: Bearer token from browser
        model: Model name
        data: Prepared stock data
        
    Returns:
        Error message (not implemented)
    """
    return {
        'success': False,
        'error': 'Claude bearer token support not yet implemented. Please use API key or switch to Gemini (free!).'
    }


def analyze_with_gemini(api_key: str, model: str, data: Dict) -> Dict:
    """
    Analyze trade using Google Gemini
    
    Args:
        api_key: Gemini API key
        model: Model name (e.g., 'gemini-2.5-flash', 'gemini-pro')
        data: Prepared stock data
        
    Returns:
        Analysis results with cost
    """
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Create model instance with JSON response config
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
            "response_mime_type": "application/json",
        }
        
        gemini_model = genai.GenerativeModel(
            model_name=model,
            generation_config=generation_config
        )
        
        prompt = create_ai_prompt(data)
        
        logger.info(f"Analyzing with Gemini: {model}")
        logger.info("="*80)
        # logger.info("PROMPT SENT TO AI:")
        # logger.info(prompt)
        logger.info("="*80)
        
        # Generate response
        response = gemini_model.generate_content(prompt)
        
        # Check if response is valid
        if not response or not hasattr(response, 'text'):
            logger.error(f"Invalid response from Gemini: {response}")
            return {
                'success': False,
                'error': 'Gemini returned invalid response'
            }
        
        # Extract response text
        response_text = response.text
        
        if not response_text or not response_text.strip():
            logger.error("Gemini returned empty response")
            return {
                'success': False,
                'error': 'Gemini returned empty response. Try again.'
            }
        
        logger.info(f"Gemini raw response: {response_text[:200]}...")  # Log first 200 chars
        
        # Clean the response - Gemini might wrap JSON in markdown code blocks
        cleaned_text = response_text.strip()
        
        # Remove markdown code blocks if present
        if cleaned_text.startswith('```'):
            # Find the actual JSON content
            lines = cleaned_text.split('\n')
            # Remove first line (```json or ```)
            if lines:
                lines = lines[1:]
            # Remove last line (```)
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned_text = '\n'.join(lines).strip()
        
        logger.info(f"Cleaned text: {cleaned_text[:200]}...")  # Log cleaned version
        
        # Parse JSON response
        try:
            analysis = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON. Error: {e}")
            logger.error(f"Full cleaned text: {cleaned_text}")
            # Try to extract JSON from text if it contains it
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_text, re.DOTALL)
            if json_match:
                try:
                    analysis = json.loads(json_match.group())
                except:
                    logger.error(f"Regex extraction also failed")
                    raise
            else:
                raise
        
        # Gemini pricing (as of 2025):
        # Free tier: 500 requests/day, 250k tokens/min
        # Paid: $1.25 per million input tokens, $10.00 per million output tokens
        # For free tier, cost is $0
        
        # Estimate token usage (approximate)
        input_tokens = len(prompt) // 4  # Rough estimate
        output_tokens = len(response_text) // 4
        
        # Calculate cost (free tier = $0, paid tier calculation)
        cost = (input_tokens * 1.25 / 1_000_000) + (output_tokens * 10.00 / 1_000_000)
        
        analysis['cost'] = cost
        analysis['tokens_used'] = {
            'input': input_tokens,
            'output': output_tokens
        }
        analysis['free_tier'] = True  # Assuming free tier usage
        
        logger.info(f"Analysis complete. Cost: ${cost:.6f} (likely free tier)")
        
        return {
            'success': True,
            'analysis': analysis,
            'provider': 'gemini',
            'model': model
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response: {e}")
        # Try to log the cleaned text if it exists
        try:
            logger.error(f"Cleaned text: {cleaned_text}")
        except:
            logger.error(f"Response text: {response_text}")
        return {
            'success': False,
            'error': 'Failed to parse AI response. Please try again.',
            'raw_response': response_text if 'response_text' in locals() else 'No response'
        }
    
    except Exception as e:
        logger.error(f"Gemini analysis error: {e}")
        
        # Provide helpful error messages
        error_msg = str(e)
        if 'API_KEY_INVALID' in error_msg or 'invalid api key' in error_msg.lower():
            return {
                'success': False,
                'error': 'Invalid Gemini API key. Please check your API key in Profile settings.'
            }
        elif 'RATE_LIMIT' in error_msg or 'quota' in error_msg.lower():
            return {
                'success': False,
                'error': 'Gemini API rate limit exceeded. Free tier: 500 requests/day. Please wait or upgrade.'
            }
        else:
            return {
                'success': False,
                'error': f'Gemini error: {error_msg}'
            }


def analyze_trade(symbol: str, strategy: str, current_price: float,
                 stop_loss: float, target: float, provider: str,
                 api_key: str, model: str, auth_mode: str = 'api_key') -> Dict:
    """
    Main entry point for AI trade analysis
    
    Args:
        symbol: Stock symbol
        strategy: Trading strategy name
        current_price: Current stock price
        stop_loss: Suggested stop loss
        target: Suggested target
        provider: 'claude' or 'openai'
        api_key: API key or bearer token (depending on auth_mode)
        model: Model name
        auth_mode: 'api_key' or 'bearer_token' (default: 'api_key')
        
    Returns:
        Analysis result dictionary
    """
    # Prepare data
    data = prepare_data_for_ai(symbol, strategy, current_price, stop_loss, target)
    
    if 'error' in data:
        return {
            'success': False,
            'error': data['error']
        }
    
    # Call appropriate AI provider
    if provider.lower() == 'claude':
        if auth_mode == 'bearer_token':
            return analyze_with_claude_bearer(api_key, model, data)
        else:
            return analyze_with_claude(api_key, model, data)
    elif provider.lower() == 'openai':
        if auth_mode == 'bearer_token':
            return analyze_with_openai_bearer(api_key, model, data)
        else:
            return analyze_with_openai(api_key, model, data)
    elif provider.lower() == 'gemini':
        return analyze_with_gemini(api_key, model, data)
    else:
        return {
            'success': False,
            'error': f'Unknown provider: {provider}'
        }


if __name__ == '__main__':
    # Test example
    print("\n=== AI Trade Analyzer Test ===\n")
    
    # This would normally come from user config
    test_api_key = "your_api_key_here"
    
    result = analyze_trade(
        symbol='RELIANCE.NS',
        strategy='momentum_btst',
        current_price=2450.50,
        stop_loss=2385.00,
        target=2580.00,
        provider='claude',
        api_key=test_api_key,
        model='claude-3-5-haiku-20241022'
    )
    
    print(json.dumps(result, indent=2))

