"""
SuperTrend Trading Platform - Web Application
FastAPI-based web interface for the SuperTrend trading system

Features:
- Dashboard with P&L tracking
- Quality watchlist management
- Weekly signal scanner
- Paper trading system
- Trade history and analytics
"""

from fastapi import FastAPI, Request, Form, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sys
import logging
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from webapp.api import paper_trading, scanner, watchlist, analytics, eod_monitor, auth_api, zerodha_api, orders_api, backtest, ai
from webapp.database import init_db

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SuperTrend Trading Platform",
    description="Professional trading platform for NSE stocks with SuperTrend strategy",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()
    logger.info("✅ Database initialized")

# Include API routers
# Authentication & User Management
app.include_router(auth_api.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(zerodha_api.router, prefix="/api/zerodha", tags=["Zerodha Integration"])
app.include_router(orders_api.router, prefix="/api/orders", tags=["Live Orders"])

# Trading Features
app.include_router(paper_trading.router, prefix="/api/trades", tags=["Paper Trading"])
app.include_router(scanner.router, prefix="/api/scanner", tags=["Scanner"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["Watchlist"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["Backtest"])
app.include_router(eod_monitor.router, prefix="/api/eod", tags=["EOD Monitor"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI Analysis"])


# Helper function to check if user is authenticated
def is_authenticated(request: Request) -> bool:
    """Check if user has auth token in cookies or localStorage will handle it"""
    # Since we use localStorage for JWT, we'll let JavaScript handle the redirect
    # But we can check for the cookie if we decide to use it
    return True  # For now, let JavaScript handle it


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page"""
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """User profile and settings page"""
    return templates.TemplateResponse("profile.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root path - redirect to login or dashboard"""
    # Redirect to login page, JavaScript will handle further routing
    return RedirectResponse(url="/login", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/scanner", response_class=HTMLResponse)
async def scanner_page(request: Request):
    """Weekly scanner page"""
    return templates.TemplateResponse("scanner.html", {"request": request})


@app.get("/trades", response_class=HTMLResponse)
async def trades_page(request: Request):
    """Paper trades page"""
    return templates.TemplateResponse("trades.html", {"request": request})


@app.get("/watchlist", response_class=HTMLResponse)
async def watchlist_page(request: Request):
    """Quality watchlist page"""
    return templates.TemplateResponse("watchlist.html", {"request": request})


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Analytics and performance page"""
    return templates.TemplateResponse("analytics.html", {"request": request})


@app.get("/backtest", response_class=HTMLResponse)
async def backtest_page(request: Request):
    """Backtest page"""
    return templates.TemplateResponse("backtest.html", {"request": request})


@app.get("/eod-monitor", response_class=HTMLResponse)
async def eod_monitor_page(request: Request):
    """EOD Monitor page"""
    return templates.TemplateResponse("eod_monitor.html", {"request": request})


@app.get("/market-insights", response_class=HTMLResponse)
async def market_insights_page(request: Request):
    """Market Insights page"""
    return templates.TemplateResponse("market_insights.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "app": "SuperTrend Trading Platform", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    logger.info("="*80)
    logger.info("🚀 Starting SuperTrend Trading Platform")
    logger.info("="*80)
    logger.info("📊 Dashboard: http://localhost:8000")
    logger.info("📡 API Docs: http://localhost:8000/docs")
    logger.info("="*80)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

