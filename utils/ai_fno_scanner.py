"""
AI-Powered F&O (Futures & Options) Scanner
Uses Google Gemini to recommend F&O trades with comprehensive analysis
"""

import sys
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
import google.generativeai as genai
import yfinance as yf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Windows console UTF-8 fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def get_latest_market_data(symbol: str) -> Dict:
    """
    Fetch latest market data for a symbol to determine data freshness
    
    Returns:
        Dict with latest candle data and timestamp
    """
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        
        # Get latest intraday data (5-minute bars for freshness)
        hist_5m = ticker.history(period="1d", interval="5m")
        
        # Get daily data for context
        hist_daily = ticker.history(period="30d", interval="1d")
        
        if hist_5m.empty:
            return {
                'last_candle_time': None,
                'data_available': False,
                'error': 'No intraday data available'
            }
        
        latest_5m = hist_5m.iloc[-1]
        latest_daily = hist_daily.iloc[-1] if not hist_daily.empty else None
        
        return {
            'symbol': symbol,
            'last_candle_time': hist_5m.index[-1].strftime('%Y-%m-%d %H:%M:%S IST'),
            'last_candle_type': '5-minute',
            'current_price': float(latest_5m['Close']),
            'volume': int(latest_5m['Volume']),
            'high': float(latest_5m['High']),
            'low': float(latest_5m['Low']),
            'open': float(latest_5m['Open']),
            'data_available': True,
            'daily_close': float(latest_daily['Close']) if latest_daily is not None else None,
            'daily_volume': int(latest_daily['Volume']) if latest_daily is not None else None
        }
    
    except Exception as e:
        logger.error(f"Error fetching market data for {symbol}: {e}")
        return {
            'last_candle_time': None,
            'data_available': False,
            'error': str(e)
        }


def create_fno_ai_prompt(
    trade_type: str,
    index_or_stock: str,
    strategy: str,
    risk_appetite: str,
    max_trades: int = 5,
    live_data: Dict = None
) -> str:
    """
    Create prompt for AI to recommend F&O trades
    
    Args:
        trade_type: futures, call_options, put_options, or mixed
        index_or_stock: NIFTY, BANKNIFTY, or Stock
        strategy: intraday, swing, or hedging
        risk_appetite: low, medium, high
        max_trades: Maximum number of trade recommendations
        live_data: Live market data from yfinance
    """
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    
    # Format live market data for prompt
    market_data_str = ""
    if live_data and 'error' not in live_data:
        nifty = live_data.get('nifty', {})
        banknifty = live_data.get('banknifty', {})
        vix = live_data.get('vix', {})
        
        market_data_str = f"""
**LIVE MARKET DATA (FETCHED NOW):**
- NIFTY 50: {nifty.get('level', 'N/A')} (Change: {nifty.get('change', 0):+.2f})
  High: {nifty.get('high', 'N/A')}, Low: {nifty.get('low', 'N/A')}
  Volume: {nifty.get('volume', 'N/A'):,}
  Last Update: {nifty.get('timestamp', 'N/A')}

- BANKNIFTY: {banknifty.get('level', 'N/A')} (Change: {banknifty.get('change', 0):+.2f})
  High: {banknifty.get('high', 'N/A')}, Low: {banknifty.get('low', 'N/A')}
  Volume: {banknifty.get('volume', 'N/A'):,}
  Last Update: {banknifty.get('timestamp', 'N/A')}

- INDIA VIX: {vix.get('level', 'N/A')} (Change: {vix.get('change', 0):+.2f})
  Last Update: {vix.get('timestamp', 'N/A')}

**Data Fetch Time:** {live_data.get('fetch_time', current_time)}

**IMPORTANT:** Use THESE EXACT LEVELS in your analysis. These are REAL, LIVE market prices fetched just now.
Base your strike price recommendations, entry prices, and support/resistance levels around THESE CURRENT PRICES.
"""
    else:
        market_data_str = """
**LIVE MARKET DATA:** Unable to fetch live data. Please use your most recent knowledge and clearly state data limitations.
"""
    
    prompt = f"""You are an expert F&O (Futures & Options) trader with deep knowledge of Indian derivatives market (NSE).

**Current Time:** {current_time}

{market_data_str}

**Task:** Recommend {max_trades} high-quality F&O trades based on the following criteria:

**Trade Preferences:**
- Trade Type: {trade_type}
- Focus: {index_or_stock}
- Strategy: {strategy}
- Risk Appetite: {risk_appetite}

**F&O Market Context:**
Use the LIVE MARKET DATA provided above to analyze.

**CRITICAL:** Your recommendations MUST be based on the LIVE DATA provided above. Strike prices should be ATM/OTM/ITM relative to CURRENT LEVELS shown in the live data.

**Trade Type Requirements:**

{get_fno_trade_requirements(trade_type, strategy)}

**Risk Management for {risk_appetite.upper()} Risk:**
{get_risk_parameters(risk_appetite)}

**For Each Trade, Provide:**

1. **Instrument Details:**
   - Symbol (e.g., NIFTY, BANKNIFTY, RELIANCE)
   - Contract Type (Futures/Call/Put)
   - Strike Price (for options)
   - Expiry Date (weekly/monthly)
   - Lot Size
   - Current Premium/Price

2. **Entry Strategy:**
   - Recommended entry price/range
   - Entry timeframe (immediate/on dip/on breakout)
   - Entry confirmation signals

3. **Exit Strategy:**
   - Target 1 (conservative)
   - Target 2 (aggressive)
   - Stop Loss (strict)
   - Trailing SL logic
   - Time-based exit (if any)

4. **Greeks Analysis (for Options):**
   - Delta (directional risk)
   - Gamma (delta sensitivity)
   - Theta (time decay per day)
   - Vega (volatility sensitivity)
   - IV (Implied Volatility) - high/low

5. **Technical Analysis:**
   - Chart pattern/setup
   - Support and resistance levels
   - Trend analysis (timeframes)
   - Volume analysis
   - Key indicators (RSI, MACD, etc.)

6. **Fundamental Triggers:**
   - Any news/events driving the move
   - Sector outlook
   - Upcoming events (earnings, policy, etc.)

7. **Risk-Reward:**
   - Position size (lots)
   - Margin required (approximate)
   - Risk per trade (₹)
   - Potential profit (₹)
   - Risk:Reward ratio

8. **Market Context:**
   - Why this trade NOW
   - Market sentiment alignment
   - Correlation with broader indices
   - VIX impact

9. **Data Freshness:**
   - Last candle/data point analyzed
   - Data timestamp (latest available)
   - Any data limitations

10. **Trade Management:**
    - Position adjustments (if any)
    - Hedging suggestions
    - What to watch during trade
    - Exit triggers

**Response Format (JSON ONLY):**
{{
  "market_context": {{
    "nifty_level": 19850,
    "nifty_trend": "Bullish consolidation near highs",
    "banknifty_level": 44500,
    "banknifty_trend": "Strong uptrend, outperforming NIFTY",
    "vix_level": 12.5,
    "vix_trend": "Low and declining - favorable for bulls",
    "pcr_ratio": 1.15,
    "pcr_interpretation": "Bullish - more puts than calls",
    "fii_dii_activity": "FII long buildup in index futures",
    "expiry_context": "Weekly expiry on Thu, Monthly on Oct 31",
    "overall_sentiment": "Bullish with low volatility",
    "data_freshness": "Analysis based on data till 2025-10-27 15:30 IST",
    "last_candle_analyzed": "2025-10-27 15:25 IST (5-min candle)"
  }},
  "recommended_trades": [
    {{
      "rank": 1,
      "instrument": {{
        "symbol": "NIFTY",
        "type": "Call Option",
        "strike": 19900,
        "expiry": "2025-10-31 (Weekly)",
        "lot_size": 50,
        "current_premium": 145.50,
        "contract_value": 7275
      }},
      "entry": {{
        "recommended_price": 145.50,
        "entry_range": "142-148",
        "entry_timing": "Immediate - momentum favors bulls",
        "entry_confirmation": "Above 19850 spot, rising volume",
        "lots_suggested": 1
      }},
      "exit": {{
        "target_1": 180.00,
        "target_1_reasoning": "Conservative - breakout to 20000",
        "target_2": 220.00,
        "target_2_reasoning": "Aggressive - rally to 20100",
        "stop_loss": 120.00,
        "stop_loss_reasoning": "Below key support at 19800",
        "trailing_sl": "Trail by 20 points once T1 hit",
        "time_exit": "Exit before 3:15 PM on expiry day if no momentum"
      }},
      "greeks": {{
        "delta": 0.45,
        "delta_interpretation": "Moderate directional exposure",
        "gamma": 0.015,
        "theta": -8.5,
        "theta_interpretation": "₹8.5 decay per day - time is enemy",
        "vega": 12.3,
        "iv": "18% - moderate",
        "iv_assessment": "Fair value - not overpriced"
      }},
      "technical_analysis": {{
        "setup": "Bullish consolidation breakout setup",
        "support_levels": [19800, 19750, 19700],
        "resistance_levels": [19900, 20000, 20100],
        "trend": "Uptrend on 15m, 1h, Daily",
        "volume": "Above average - confirming bullish move",
        "indicators": "RSI 62, MACD positive crossover, EMA aligned"
      }},
      "fundamentals": {{
        "news": "No major negative news",
        "sector_outlook": "IT and Banking leading rally",
        "upcoming_events": "US Fed decision on Nov 1",
        "triggers": "Positive global cues, strong domestic data"
      }},
      "risk_reward": {{
        "position_size": "1 lot",
        "margin_required": 8000,
        "risk_per_trade": 1275,
        "potential_profit_t1": 1725,
        "potential_profit_t2": 3725,
        "rr_ratio_t1": "1:1.35",
        "rr_ratio_t2": "1:2.92"
      }},
      "reasoning": {{
        "why_now": "NIFTY consolidating near highs with low VIX. Weekly expiry provides short-term opportunity. Technical setup favors upside breakout.",
        "market_alignment": "Aligned with bullish market sentiment and FII activity",
        "risk_factors": ["US Fed decision uncertainty", "Time decay (theta)", "Volatility spike risk"],
        "confidence": 8.5
      }},
      "trade_management": {{
        "position_adjustments": "Book 50% at T1, trail rest",
        "hedging": "Optional: Buy 19800 Put for hedge (costs 80)",
        "watch_for": "NIFTY spot holding 19850, VIX staying below 13",
        "exit_triggers": "Break below 19800, sudden VIX spike above 15"
      }},
      "data_freshness": {{
        "last_candle": "2025-10-27 15:25 IST",
        "data_type": "5-minute intraday",
        "data_reliability": "High - recent real-time data",
        "analysis_timestamp": "2025-10-27 15:30 IST"
      }}
    }}
    // ... {max_trades - 1} more trades
  ],
  "scan_summary": {{
    "total_opportunities": {max_trades},
    "high_confidence_count": 3,
    "avg_rr_ratio": "1:2.1",
    "total_margin_required": 35000,
    "best_strategy": "{strategy}",
    "market_advice": "Favorable conditions for {trade_type} with {risk_appetite} risk",
    "key_levels_to_watch": [19800, 19900, 20000],
    "data_as_of": "2025-10-27 15:30 IST"
  }}
}}

**CRITICAL REQUIREMENTS:**
1. Recommend REAL F&O contracts trading on NSE
2. Use CURRENT expiry dates (check NSE calendar)
3. Provide REALISTIC strike prices and premiums
4. Greeks must be mathematically consistent
5. Consider actual lot sizes (NIFTY=50, BANKNIFTY=15, etc.)
6. Margin calculations should be approximate but realistic
7. **CLEARLY STATE DATA FRESHNESS** - last candle timestamp analyzed
8. If real-time data unavailable, use last known data and mention it
9. Be HONEST about data limitations and market hours
10. All timestamps in IST

**Strategy-Specific Focus:**
{get_fno_strategy_focus(strategy, trade_type)}

**Risk Level Adjustments:**
{get_risk_level_guidance(risk_appetite)}

Provide ONLY the JSON response, no additional text or markdown."""
    
    return prompt


def get_fno_trade_requirements(trade_type: str, strategy: str) -> str:
    """Get requirements for different F&O trade types"""
    
    requirements = {
        "futures": """
**Futures Trading:**
- High liquidity contracts only
- Clear trend direction
- Strong volume confirmation
- Reasonable margin requirements
- Good risk:reward (min 1:2)
        """,
        
        "call_options": """
**Call Options:**
- Bullish setup required
- Strike selection based on trend strength
- ITM/ATM/OTM based on risk appetite
- Favorable Greeks (high delta, manageable theta)
- Reasonable IV (not inflated)
- Time to expiry consideration
        """,
        
        "put_options": """
**Put Options:**
- Bearish setup required
- Strike selection based on downside potential
- ITM/ATM/OTM based on risk appetite
- Favorable Greeks (high delta for puts)
- VIX consideration (higher VIX helps puts)
- Hedge vs directional trade clarity
        """,
        
        "mixed": """
**Mixed Strategy (Futures + Options):**
- Can include spreads (bull/bear spreads)
- Can include straddles/strangles if high volatility expected
- Can include covered positions
- Clear logic for each leg
- Net margin and risk:reward for combined position
        """
    }
    
    return requirements.get(trade_type, requirements["mixed"])


def get_risk_parameters(risk_appetite: str) -> str:
    """Get risk parameters based on risk appetite"""
    
    params = {
        "low": """
- Risk per trade: 1-2% of capital
- Prefer ITM or ATM options (higher delta, lower risk)
- Avoid far OTM options (low probability)
- Strict stop losses
- Conservative targets (1:1.5 to 1:2 R:R)
- Prefer longer expiries (less theta decay)
        """,
        
        "medium": """
- Risk per trade: 2-3% of capital
- Mix of ATM and slightly OTM options
- Balanced risk:reward (1:2 to 1:3)
- Moderate position sizing
- Consider weekly expiries
- Active trade management
        """,
        
        "high": """
- Risk per trade: 3-5% of capital
- OTM options for leverage
- Aggressive targets (1:3 to 1:5 R:R)
- Larger position sizes
- Weekly or shorter expiries
- High conviction trades only
- May use multiple lots
        """
    }
    
    return params.get(risk_appetite, params["medium"])


def get_fno_strategy_focus(strategy: str, trade_type: str) -> str:
    """Get strategy-specific focus"""
    
    focus = {
        "intraday": f"Focus on {trade_type} with INTRADAY setup - high volume, clear momentum, tight stops, exit before 3:20 PM.",
        "swing": f"Focus on {trade_type} for SWING trading (2-5 days) - strong trend, upcoming catalysts, reasonable theta decay.",
        "hedging": f"Focus on {trade_type} for HEDGING - protective positions, risk mitigation, portfolio insurance."
    }
    
    return focus.get(strategy, f"Focus on high-quality {trade_type} opportunities.")


def get_risk_level_guidance(risk_appetite: str) -> str:
    """Get risk level specific guidance"""
    
    guidance = {
        "low": "Prioritize capital preservation. Suggest only high-probability setups with strong technical and fundamental support.",
        "medium": "Balance risk and reward. Suggest good probability setups with reasonable leverage.",
        "high": "Focus on high-reward opportunities. User accepts higher risk for potentially larger gains."
    }
    
    return guidance.get(risk_appetite, guidance["medium"])


def fetch_live_market_data() -> Dict:
    """Fetch live market data for NIFTY, BANKNIFTY, and VIX"""
    try:
        import yfinance as yf
        from datetime import datetime
        
        data = {}
        
        # Fetch NIFTY
        try:
            logger.info("Fetching NIFTY data...")
            nifty = yf.Ticker("^NSEI")
            nifty_hist = nifty.history(period="5d", interval="5m")
            
            if not nifty_hist.empty:
                latest = nifty_hist.iloc[-1]
                data['nifty'] = {
                    'level': float(latest['Close']),
                    'change': float(latest['Close'] - nifty_hist.iloc[-2]['Close']) if len(nifty_hist) > 1 else 0,
                    'high': float(latest['High']),
                    'low': float(latest['Low']),
                    'volume': int(latest['Volume']),
                    'timestamp': nifty_hist.index[-1].strftime('%Y-%m-%d %H:%M:%S IST')
                }
                logger.info(f"NIFTY fetched: {data['nifty']['level']} @ {data['nifty']['timestamp']}")
            else:
                logger.warning("NIFTY history is empty")
                data['nifty'] = {'level': 'N/A', 'timestamp': 'N/A'}
        except Exception as e:
            logger.error(f"Could not fetch NIFTY data: {e}")
            data['nifty'] = {'level': 'N/A', 'timestamp': 'N/A'}
        
        # Fetch BANKNIFTY
        try:
            banknifty = yf.Ticker("^NSEBANK")
            bn_hist = banknifty.history(period="5d", interval="5m")
            if not bn_hist.empty:
                latest = bn_hist.iloc[-1]
                data['banknifty'] = {
                    'level': float(latest['Close']),
                    'change': float(latest['Close'] - bn_hist.iloc[-2]['Close']) if len(bn_hist) > 1 else 0,
                    'high': float(latest['High']),
                    'low': float(latest['Low']),
                    'volume': int(latest['Volume']),
                    'timestamp': bn_hist.index[-1].strftime('%Y-%m-%d %H:%M:%S IST')
                }
        except Exception as e:
            logger.warning(f"Could not fetch BANKNIFTY data: {e}")
            data['banknifty'] = {'level': 'N/A', 'timestamp': 'N/A'}
        
        # Fetch INDIA VIX (if available)
        try:
            vix = yf.Ticker("^INDIAVIX")
            vix_hist = vix.history(period="5d")
            if not vix_hist.empty:
                latest = vix_hist.iloc[-1]
                data['vix'] = {
                    'level': float(latest['Close']),
                    'change': float(latest['Close'] - vix_hist.iloc[-2]['Close']) if len(vix_hist) > 1 else 0,
                    'timestamp': vix_hist.index[-1].strftime('%Y-%m-%d')
                }
        except Exception as e:
            logger.warning(f"Could not fetch VIX data: {e}")
            data['vix'] = {'level': 'N/A', 'timestamp': 'N/A'}
        
        data['fetch_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        logger.info(f"Live market data fetched: NIFTY={data.get('nifty', {}).get('level')}, BANKNIFTY={data.get('banknifty', {}).get('level')}, VIX={data.get('vix', {}).get('level')}")
        
        return data
    
    except Exception as e:
        logger.error(f"Error fetching live market data: {e}")
        return {'error': str(e)}


def scan_fno_with_ai(
    api_key: str,
    trade_type: str = "call_options",
    index_or_stock: str = "NIFTY",
    strategy: str = "intraday",
    risk_appetite: str = "medium",
    max_trades: int = 3,  # Reduced default to avoid truncation
    model: str = "gemini-1.5-flash"
) -> Dict:
    """
    Use AI to scan and recommend F&O trades
    
    Args:
        api_key: Gemini API key
        trade_type: futures, call_options, put_options, mixed
        index_or_stock: NIFTY, BANKNIFTY, or Stock
        strategy: intraday, swing, hedging
        risk_appetite: low, medium, high
        max_trades: Maximum number of trades to recommend
        model: Gemini model to use
        
    Returns:
        Dictionary with market context and recommended F&O trades
    """
    try:
        logger.info(f"Starting F&O AI scan: {trade_type}, {index_or_stock}, {strategy}, {risk_appetite}")
        
        # Fetch live market data
        live_data = fetch_live_market_data()
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Create model with JSON response
        generation_config = {
            "temperature": 0.2,  # Even lower for more precise JSON
            "top_p": 0.9,
            "top_k": 20,
            "max_output_tokens": 8192,  # Increase to avoid truncation
            "response_mime_type": "application/json",
        }
        
        gemini_model = genai.GenerativeModel(
            model_name=model,
            generation_config=generation_config
        )
        
        # Create prompt with live data
        prompt = create_fno_ai_prompt(
            trade_type, index_or_stock, strategy, risk_appetite, max_trades, live_data
        )
        
        logger.info("Sending F&O analysis request to Gemini AI...")
        
        # Generate response
        response = gemini_model.generate_content(prompt)
        
        if not response or not response.text:
            raise Exception("Empty response from AI")
        
        # Extract and parse response
        response_text = response.text
        
        logger.info("="*80)
        logger.info("Gemini F&O raw response:")
        logger.info(response_text[:1000] if len(response_text) > 1000 else response_text)
        logger.info("="*80)
        
        # Clean markdown if present
        cleaned_text = response_text.strip()
        if cleaned_text.startswith('```'):
            lines = cleaned_text.split('\n')
            # Remove ```json or ``` from first line
            if lines and (lines[0].strip() == '```' or lines[0].strip().startswith('```')):
                lines = lines[1:]
            # Remove closing ```
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned_text = '\n'.join(lines).strip()
        
        # Additional cleaning for common JSON issues
        import re
        
        # Remove trailing commas before closing braces/brackets
        cleaned_text = re.sub(r',(\s*[}\]])', r'\1', cleaned_text)
        
        # Try to extract JSON if wrapped in extra text
        if not cleaned_text.startswith('{'):
            json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(0)
        
        logger.info("Cleaned text for parsing:")
        logger.info(cleaned_text[:1000] if len(cleaned_text) > 1000 else cleaned_text)
        
        # Parse JSON
        try:
            result = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            logger.error(f"Error at position {e.pos}")
            logger.error(f"Error line {e.lineno}, column {e.colno}")
            
            # Show context around error
            if e.pos and e.pos < len(cleaned_text):
                start = max(0, e.pos - 100)
                end = min(len(cleaned_text), e.pos + 100)
                logger.error(f"Context around error: ...{cleaned_text[start:end]}...")
            
            # Try more aggressive regex fallback
            json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
            if json_match:
                try:
                    extracted_json = json_match.group(0)
                    # Try one more cleanup
                    extracted_json = re.sub(r',(\s*[}\]])', r'\1', extracted_json)
                    result = json.loads(extracted_json)
                    logger.info("Successfully parsed with regex extraction")
                except json.JSONDecodeError as e2:
                    logger.error(f"Regex extraction also failed: {e2}")
                    raise Exception(f"Could not parse JSON from AI response. Error: {e}")
            else:
                raise Exception(f"Could not extract valid JSON from AI response. Error: {e}")
        
        logger.info(f"F&O AI scan complete! Found {len(result.get('recommended_trades', []))} trades")
        
        return {
            'success': True,
            'trade_type': trade_type,
            'index_or_stock': index_or_stock,
            'strategy': strategy,
            'risk_appetite': risk_appetite,
            'market_context': result.get('market_context', {}),
            'trades': result.get('recommended_trades', []),
            'scan_summary': result.get('scan_summary', {}),
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"F&O AI scan error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == '__main__':
    # Test example
    print("\n=== F&O AI Scanner Test ===\n")
    
    # Get API key from user
    api_key = input("Enter your Gemini API key: ").strip()
    
    if not api_key:
        print("No API key provided. Exiting.")
        exit(1)
    
    # Run F&O scan
    result = scan_fno_with_ai(
        api_key=api_key,
        trade_type="call_options",
        index_or_stock="NIFTY",
        strategy="intraday",
        risk_appetite="medium",
        max_trades=3
    )
    
    if result['success']:
        print("\n📊 Market Context:")
        print(json.dumps(result['market_context'], indent=2))
        
        print(f"\n🎯 Recommended F&O Trades ({len(result['trades'])}):")
        for i, trade in enumerate(result['trades'], 1):
            inst = trade['instrument']
            print(f"\n{i}. {inst['symbol']} {inst['type']} {inst.get('strike', 'N/A')} - {inst['expiry']}")
            print(f"   Entry: ₹{trade['entry']['recommended_price']}, Target: ₹{trade['exit']['target_1']}, SL: ₹{trade['exit']['stop_loss']}")
            print(f"   R:R: {trade['risk_reward']['rr_ratio_t1']}, Confidence: {trade['reasoning']['confidence']}/10")
            print(f"   Why: {trade['reasoning']['why_now'][:100]}...")
            if 'data_freshness' in trade:
                print(f"   📅 Data as of: {trade['data_freshness'].get('last_candle', 'N/A')}")
        
        print("\n📈 Scan Summary:")
        print(json.dumps(result['scan_summary'], indent=2))
    else:
        print(f"\n❌ Scan failed: {result['error']}")

