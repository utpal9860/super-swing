"""
Gemini-Powered Real-Time News & Sentiment Analysis
Uses Google Search grounding to fetch latest news and analyze sentiment
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import google.generativeai as genai
from datetime import datetime, timedelta
import json
import time
from typing import Dict, List, Optional
from utils.logger import setup_logger

logger = setup_logger("gemini_news_analyzer")


class GeminiNewsAnalyzer:
    """
    Real-time news fetching and sentiment analysis using Gemini with Google Search
    """
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        """
        Initialize Gemini with Google Search grounding
        
        Args:
            api_key: Your Gemini API key
            model: Gemini model (use gemini-2.0-flash-exp for search)
        """
        genai.configure(api_key=api_key)
        
        # Configure model with Google Search tool
        self.model = genai.GenerativeModel(
            model_name=model,
            tools='google_search_retrieval'  # Enable Google Search!
        )
        
        logger.info(f"Gemini News Analyzer initialized with {model}")
    
    def fetch_and_analyze_sentiment(self, stock_symbol: str, company_name: str, 
                                    days_back: int = 7) -> Dict:
        """
        Fetch real-time news and analyze sentiment for a stock
        
        Args:
            stock_symbol: Stock symbol (e.g., 'RELIANCE', 'TCS')
            company_name: Full company name (e.g., 'Reliance Industries')
            days_back: How many days of news to analyze (default: 7)
        
        Returns:
            {
                'success': True,
                'data': {
                    'overall_sentiment': 0.68,  # -1 to +1
                    'sentiment_label': 'BULLISH',
                    'confidence': 0.82,
                    'num_articles': 12,
                    'positive_count': 8,
                    'negative_count': 2,
                    'neutral_count': 2,
                    'key_positive_factors': [...],
                    'key_negative_factors': [...],
                    ...
                }
            }
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Create prompt for Gemini with search grounding
            prompt = f"""
Search for the latest news and information about {company_name} ({stock_symbol}) 
stock from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}.

Focus on:
1. **Corporate announcements**: Earnings, dividends, bonuses, splits, buybacks
2. **Business developments**: New contracts, partnerships, expansions
3. **Management updates**: Guidance changes, strategic shifts
4. **Analyst reports**: Upgrades, downgrades, target price changes
5. **News coverage**: Major news from MoneyControl, Economic Times, Business Standard
6. **Regulatory filings**: NSE/BSE announcements, SEBI updates
7. **FII/DII activity**: Institutional buying/selling patterns

After gathering the information, provide a comprehensive sentiment analysis in JSON format:

{{
  "overall_sentiment": <float between -1 (very bearish) and +1 (very bullish)>,
  "sentiment_label": <"VERY_BULLISH" | "BULLISH" | "NEUTRAL" | "BEARISH" | "VERY_BEARISH">,
  "confidence": <float between 0 and 1>,
  "num_articles": <number of relevant news articles found>,
  "positive_count": <number of positive news>,
  "negative_count": <number of negative news>,
  "neutral_count": <number of neutral news>,
  
  "key_positive_factors": [
    "<Specific positive news with date, e.g., 'Oct 25: Q2 earnings beat estimates by 5%'>",
    "<Another positive factor with details>"
  ],
  
  "key_negative_factors": [
    "<Specific negative news with date, e.g., 'Oct 20: Margin pressure noted in analyst report'>",
    "<Another negative factor>"
  ],
  
  "recent_events": [
    {{
      "date": "2025-10-25",
      "event": "Q2 Results Announced",
      "sentiment": "positive",
      "impact": "high",
      "summary": "Beat earnings by 5%, raised FY guidance"
    }}
  ],
  
  "news_summary": "<2-3 sentence summary of overall news sentiment and key themes>",
  
  "earnings_analysis": {{
    "recent_quarter": "Q2 FY25",
    "beat_or_miss": "beat",
    "revenue_growth": "+12%",
    "profit_growth": "+15%",
    "guidance": "raised"
  }},
  
  "institutional_activity": {{
    "fii_action": "buying",
    "dii_action": "buying",
    "trend": "accumulation"
  }},
  
  "analyst_sentiment": {{
    "upgrades": 2,
    "downgrades": 0,
    "maintained": 5,
    "avg_target_price": 3580,
    "current_price": 3565,
    "upside_potential": "+0.4%"
  }},
  
  "risk_factors": [
    "<Specific risk mentioned in news>",
    "<Another risk factor>"
  ],
  
  "catalysts": [
    "<Upcoming positive event>",
    "<Another catalyst>"
  ]
}}

**IMPORTANT**:
- Base sentiment ONLY on actual news found, not general knowledge
- If no significant news found, state clearly and return neutral sentiment
- Include specific dates and sources for credibility
- Distinguish between rumors and confirmed news
- Weight earnings/guidance changes more heavily than regular news
- For Indian stocks, prioritize NSE/BSE announcements over general news

Provide ONLY the JSON response, no additional text or markdown.
"""
            
            # Generate response with Google Search grounding (with retry logic)
            logger.info(f"Fetching news for {stock_symbol} using Google Search...")
            
            max_retries = 3
            retry_delay = 5  # Start with 5 seconds
            
            for attempt in range(max_retries):
                try:
                    response = self.model.generate_content(prompt)
                    break  # Success!
                except Exception as api_error:
                    error_str = str(api_error)
                    
                    # Check if it's a rate limit error
                    if '429' in error_str or 'rate' in error_str.lower() or 'quota' in error_str.lower():
                        if attempt < max_retries - 1:
                            logger.warning(f"Rate limit hit for {stock_symbol}. Waiting {retry_delay}s before retry {attempt+2}/{max_retries}...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            logger.error(f"Rate limit persists after {max_retries} attempts for {stock_symbol}")
                            raise
                    else:
                        # Not a rate limit error, raise immediately
                        raise
            
            # Extract and parse JSON
            response_text = response.text.strip()
            
            # Clean markdown if present
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                if lines:
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                response_text = '\n'.join(lines).strip()
            
            # Parse JSON
            sentiment_data = json.loads(response_text)
            
            logger.info(f"Sentiment analysis complete for {stock_symbol}")
            logger.info(f"Overall sentiment: {sentiment_data['overall_sentiment']} ({sentiment_data['sentiment_label']})")
            logger.info(f"Articles analyzed: {sentiment_data['num_articles']}")
            
            return {
                'success': True,
                'data': sentiment_data,
                'timestamp': datetime.now().isoformat(),
                'source': 'gemini_google_search'
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            logger.error(f"Response: {response_text}")
            return {
                'success': False,
                'error': 'Failed to parse sentiment analysis',
                'raw_response': response_text
            }
        
        except Exception as e:
            logger.error(f"Error in sentiment analysis for {stock_symbol}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_sentiment_score_normalized(self, sentiment_result: Dict) -> float:
        """
        Get normalized sentiment score (0-1) for fusion layer
        
        Args:
            sentiment_result: Output from fetch_and_analyze_sentiment
        
        Returns:
            Sentiment score normalized to 0-1 scale
        """
        if not sentiment_result.get('success'):
            return 0.5  # Neutral if analysis failed
        
        # Convert -1 to +1 scale to 0 to 1 scale
        raw_sentiment = sentiment_result['data']['overall_sentiment']
        normalized = (raw_sentiment + 1) / 2
        
        return normalized
    
    def batch_analyze_stocks(self, stock_list: List[Dict[str, str]], 
                            days_back: int = 7) -> Dict[str, Dict]:
        """
        Analyze sentiment for multiple stocks
        
        Args:
            stock_list: List of dicts with 'symbol' and 'name' keys
            days_back: Days of news history
        
        Returns:
            Dictionary mapping symbol to sentiment data
        """
        results = {}
        
        for stock in stock_list:
            symbol = stock['symbol']
            name = stock['name']
            
            logger.info(f"Analyzing {symbol} ({name})...")
            
            sentiment = self.fetch_and_analyze_sentiment(
                stock_symbol=symbol,
                company_name=name,
                days_back=days_back
            )
            
            results[symbol] = sentiment
        
        return results


# Test code
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in .env file")
        exit(1)
    
    # Test with L&T
    analyzer = GeminiNewsAnalyzer(api_key=api_key)
    
    result = analyzer.fetch_and_analyze_sentiment(
        stock_symbol='LT',
        company_name='Larsen & Toubro',
        days_back=7
    )
    
    if result['success']:
        print("\n" + "="*80)
        print("SENTIMENT ANALYSIS RESULT")
        print("="*80)
        data = result['data']
        print(f"\nOverall Sentiment: {data['overall_sentiment']:.2f} ({data['sentiment_label']})")
        print(f"Confidence: {data['confidence']:.2f}")
        print(f"Articles Analyzed: {data['num_articles']}")
        print(f"\nPositive: {data['positive_count']}, Negative: {data['negative_count']}, Neutral: {data['neutral_count']}")
        
        print(f"\nKey Positive Factors:")
        for factor in data.get('key_positive_factors', [])[:3]:
            print(f"  + {factor}")
        
        print(f"\nKey Negative Factors:")
        for factor in data.get('key_negative_factors', [])[:3]:
            print(f"  - {factor}")
        
        print(f"\nNews Summary:")
        print(f"  {data.get('news_summary', 'N/A')}")
    else:
        print(f"\nERROR: {result['error']}")

