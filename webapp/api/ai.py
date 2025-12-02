"""
AI Analysis API Endpoints
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from utils.ai_analyzer import analyze_trade

router = APIRouter()

logger = logging.getLogger(__name__)


class AnalyzeTradeRequest(BaseModel):
    """Request model for trade analysis"""
    symbol: str
    strategy: str
    current_price: float
    stop_loss: float
    target: float
    capital: Optional[float] = 100000


@router.post("/analyze-trade")
async def analyze_trade_endpoint(
    request: AnalyzeTradeRequest,
    x_ai_provider: str = Header(..., alias="X-AI-Provider"),
    x_ai_key: str = Header(..., alias="X-AI-Key"),
    x_ai_model: str = Header(..., alias="X-AI-Model"),
    x_ai_auth_mode: str = Header('api_key', alias="X-AI-Auth-Mode")
):
    """
    Analyze a trade setup using AI (Claude or OpenAI)
    
    Headers:
        X-AI-Provider: 'claude' or 'openai'
        X-AI-Auth-Mode: 'api_key' or 'bearer_token'
        X-AI-Key: API key or bearer token (based on auth mode)
        X-AI-Model: Model name (e.g., 'claude-3-5-haiku-20241022', 'gpt-3.5-turbo')
        
    Body:
        symbol: Stock symbol (e.g., 'RELIANCE.NS')
        strategy: Trading strategy name
        current_price: Current stock price
        stop_loss: Suggested stop loss
        target: Suggested target
        capital: Available capital (optional)
        
    Returns:
        Analysis result with recommendations
    """
    try:
        logger.info(f"Analyzing trade: {request.symbol} with {x_ai_provider} (auth: {x_ai_auth_mode})")
        
        # Validate provider
        if x_ai_provider.lower() not in ['claude', 'openai', 'gemini']:
            raise HTTPException(status_code=400, detail="Invalid AI provider. Use 'claude', 'openai', or 'gemini'")
        
        # Validate auth mode
        if x_ai_auth_mode not in ['api_key', 'bearer_token']:
            raise HTTPException(status_code=400, detail="Invalid auth mode. Use 'api_key' or 'bearer_token'")
        
        # Validate credentials
        if not x_ai_key or len(x_ai_key) < 10:
            raise HTTPException(status_code=400, detail="Invalid credentials")
        
        # Call AI analyzer
        result = analyze_trade(
            symbol=request.symbol,
            strategy=request.strategy,
            current_price=request.current_price,
            stop_loss=request.stop_loss,
            target=request.target,
            provider=x_ai_provider,
            api_key=x_ai_key,
            model=x_ai_model,
            auth_mode=x_ai_auth_mode
        )
        
        if not result.get('success'):
            raise HTTPException(status_code=500, detail=result.get('error', 'AI analysis failed'))
        
        return result
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error in analyze_trade_endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-connection")
async def test_ai_connection(
    provider: str,
    api_key: str,
    model: str
):
    """
    Test AI provider connection
    
    Query params:
        provider: 'claude' or 'openai'
        api_key: API key
        model: Model name
        
    Returns:
        Connection test result
    """
    try:
        # Simple test with minimal tokens
        result = analyze_trade(
            symbol='RELIANCE.NS',
            strategy='test',
            current_price=2450.00,
            stop_loss=2400.00,
            target=2500.00,
            provider=provider,
            api_key=api_key,
            model=model
        )
        
        if result.get('success'):
            return {
                'success': True,
                'message': f'Connection successful! Cost: ${result["analysis"]["cost"]:.6f}',
                'provider': provider,
                'model': model
            }
        else:
            return {
                'success': False,
                'error': result.get('error', 'Connection test failed')
            }
    
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

