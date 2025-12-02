"""
AI-Powered Stock Scanner
Uses Google Gemini to recommend stocks based on market analysis and trading criteria
"""

import sys
import json
import logging
from datetime import datetime
from typing import List, Dict
import pandas as pd
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


def create_ai_scanner_prompt(strategy: str, market_cap: str, sector: str = None, max_stocks: int = 10) -> str:
    """Create prompt for AI to recommend stocks"""
    
    sector_filter = f"Focus on {sector} sector only." if sector else "Consider all sectors."
    
    prompt = f"""You are an expert Indian stock market analyst with deep knowledge of NSE/BSE listed companies.

**Task:** Recommend {max_stocks} high-quality stocks for **{strategy}** trading strategy based on current market conditions.

**Market Context (As of October 2025):**
Analyze the current Indian stock market scenario and recommend stocks that fit the strategy.

**Strategy Requirements:**

{get_strategy_requirements(strategy)}

**Stock Selection Criteria:**
- Market Cap: {market_cap}
- {sector_filter}
- Must be liquid (good trading volume)
- Must have clear technical setup matching the strategy
- Consider both fundamentals and technicals

**Analysis Required for Each Stock:**
1. Why this stock fits the {strategy} strategy
2. Current technical setup (trend, indicators, levels)
3. Fundamental strength (earnings, growth, sector position)
4. Entry, Stop Loss, and Target levels
5. Key risks to watch
6. Confidence level (1-10)

**Response Format (JSON ONLY):**
{{
  "market_overview": {{
    "nifty_outlook": "Current NIFTY trend and market sentiment",
    "sector_rotation": "Which sectors are strong/weak currently",
    "risk_sentiment": "Risk-on or risk-off environment"
  }},
  "recommended_stocks": [
    {{
      "symbol": "RELIANCE",
      "name": "Reliance Industries",
      "sector": "Oil & Gas",
      "current_price": 2450.00,
      "entry": 2450.00,
      "stop_loss": 2385.00,
      "target": 2580.00,
      "confidence": 8.5,
      "technical_setup": "Strong uptrend, above all EMAs, MACD positive crossover, RSI 65",
      "fundamental_strength": "✓ Q2 earnings beat, ✓ 15% revenue growth, ✓ Debt reduced by 20%",
      "why_now": "Breaking out of consolidation with high volume, sector momentum strong",
      "risk_factors": ["Crude oil price volatility", "Global economic slowdown"],
      "strategy_fit": "Perfect for momentum strategy - strong trend + volume confirmation"
    }}
    // ... {max_stocks - 1} more stocks
  ],
  "scan_summary": {{
    "total_opportunities": {max_stocks},
    "high_confidence_count": 0,
    "best_sectors": ["IT", "Banking"],
    "market_advice": "Overall market assessment and trading advice"
  }}
}}

**CRITICAL REQUIREMENTS:**
1. Recommend REAL Indian stocks (NSE/BSE) - no made-up symbols
2. Provide REALISTIC price levels based on current market
3. Be HONEST - if market conditions don't favor this strategy, say so
4. Use your knowledge of recent market trends, earnings, sector performance
5. Confidence should reflect both technical AND fundamental quality
6. All prices should end with .NS for NSE listing (e.g., RELIANCE.NS)

**Strategy-Specific Focus:**
{get_strategy_specific_focus(strategy)}

Provide ONLY the JSON response, no additional text or markdown."""
    
    return prompt


def get_strategy_requirements(strategy: str) -> str:
    """Get requirements for different strategies"""
    
    requirements = {
        "momentum_btst": """
- Strong intraday momentum (last 1-2 hours of trading)
- Volume spike (>1.5x average)
- Price above key moving averages
- Positive MACD crossover
- RSI between 50-70 (strong but not overbought)
- Clear breakout or strong trend
        """,
        
        "swing_supertrend": """
- Clear trend on daily timeframe
- SuperTrend indicator showing trend direction
- Price above/below SuperTrend line (based on direction)
- Good risk:reward ratio (minimum 1:2)
- Moderate volatility (ATR-based)
- Volume confirming trend
        """,
        
        "mean_reversion": """
- Stock in oversold territory (RSI < 30)
- Price near lower Bollinger Band
- Strong support level nearby
- Fundamentally sound company (no bad news)
- Temporary selloff, not structural decline
- High probability bounce setup
        """,
        
        "pullback_entry": """
- Overall uptrend on daily chart
- Recent pullback to support/moving average
- Pullback is shallow (not breakdown)
- Volume declining during pullback
- Ready to resume uptrend
- Risk:reward favorable
        """,
        
        "swing_breakout_india": """
- Consolidation breakout pattern
- Volume surge on breakout
- Price above resistance with conviction
- Relative strength vs NIFTY
- Support base below entry
- Measured move target possible
        """,
        
        "improved_btst": """
- Late-session breakout (3:15-3:25 PM IST)
- Volume spike (>1.5x average)
- Price breaking resistance
- All EMAs aligned bullishly
- RSI not overbought
- Clear closing strength
        """
    }
    
    return requirements.get(strategy, "General swing trading setup with good risk:reward")


def get_strategy_specific_focus(strategy: str) -> str:
    """Get strategy-specific focus points"""
    
    focus = {
        "momentum_btst": "Focus on stocks with STRONG closing momentum, ideal for overnight holds.",
        "swing_supertrend": "Focus on stocks in CLEAR TRENDS with good risk management via SuperTrend.",
        "mean_reversion": "Focus on QUALITY stocks in temporary oversold conditions.",
        "pullback_entry": "Focus on stocks in UPTRENDS having healthy pullbacks.",
        "swing_breakout_india": "Focus on stocks BREAKING OUT of consolidation with volume.",
        "improved_btst": "Focus on stocks with LATE SESSION BREAKOUTS for next-day gap potential."
    }
    
    return focus.get(strategy, "Focus on high-quality trading opportunities.")


def scan_with_ai(
    api_key: str,
    strategy: str = "momentum_btst",
    market_cap: str = "Large Cap",
    sector: str = None,
    max_stocks: int = 10,
    model: str = "gemini-1.5-flash"
) -> Dict:
    """
    Use AI to scan and recommend stocks
    
    Args:
        api_key: Gemini API key
        strategy: Trading strategy name
        market_cap: Market cap filter (Large Cap, Mid Cap, Small Cap, All)
        sector: Sector filter (optional)
        max_stocks: Maximum number of stocks to recommend
        model: Gemini model to use
        
    Returns:
        Dictionary with market overview and recommended stocks
    """
    try:
        logger.info(f"Starting AI scan for strategy: {strategy}")
        logger.info(f"Filters: {market_cap}, Sector: {sector or 'All'}, Max: {max_stocks}")
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Create model with JSON response
        generation_config = {
            "temperature": 0.4,  # Slightly higher for creative stock picking
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 4096,  # More tokens for multiple stocks
            "response_mime_type": "application/json",
        }
        
        gemini_model = genai.GenerativeModel(
            model_name=model,
            generation_config=generation_config
        )
        
        # Create prompt
        prompt = create_ai_scanner_prompt(strategy, market_cap, sector, max_stocks)
        
        logger.info("Sending request to Gemini AI...")
        
        # Generate response
        response = gemini_model.generate_content(prompt)
        
        # Extract and parse response
        response_text = response.text
        
        # Clean markdown if present
        cleaned_text = response_text.strip()
        if cleaned_text.startswith('```'):
            lines = cleaned_text.split('\n')
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned_text = '\n'.join(lines).strip()
        
        # Parse JSON
        result = json.loads(cleaned_text)
        
        logger.info(f"AI scan complete! Found {len(result.get('recommended_stocks', []))} stocks")
        
        return {
            'success': True,
            'strategy': strategy,
            'market_overview': result.get('market_overview', {}),
            'stocks': result.get('recommended_stocks', []),
            'scan_summary': result.get('scan_summary', {}),
            'timestamp': datetime.now().isoformat()
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        return {
            'success': False,
            'error': 'Failed to parse AI recommendations'
        }
    
    except Exception as e:
        logger.error(f"AI scan error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == '__main__':
    # Test example
    print("\n=== AI Stock Scanner Test ===\n")
    
    # Get API key from environment or user input
    api_key = input("Enter your Gemini API key: ").strip()
    
    if not api_key:
        print("No API key provided. Exiting.")
        exit(1)
    
    # Run scan
    result = scan_with_ai(
        api_key=api_key,
        strategy="momentum_btst",
        market_cap="Large Cap",
        max_stocks=5
    )
    
    if result['success']:
        print("\n📊 Market Overview:")
        print(json.dumps(result['market_overview'], indent=2))
        
        print(f"\n🎯 Recommended Stocks ({len(result['stocks'])}):")
        for i, stock in enumerate(result['stocks'], 1):
            print(f"\n{i}. {stock['symbol']} - {stock['name']}")
            print(f"   Entry: ₹{stock['entry']}, Target: ₹{stock['target']}, SL: ₹{stock['stop_loss']}")
            print(f"   Confidence: {stock['confidence']}/10")
            print(f"   Setup: {stock['technical_setup']}")
        
        print("\n📈 Scan Summary:")
        print(json.dumps(result['scan_summary'], indent=2))
    else:
        print(f"\n❌ Scan failed: {result['error']}")











