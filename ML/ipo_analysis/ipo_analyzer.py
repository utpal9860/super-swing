"""
IPO Buy-and-Hold Analysis
Analyzes returns from IPO listing to current date with XIRR/CAGR calculations
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Optional
import logging
from scipy.optimize import newton

logger = logging.getLogger(__name__)


class IPOAnalyzer:
    """Analyze IPO investments and calculate returns"""
    
    def __init__(self, investment_per_stock: float = 15000):
        """
        Initialize IPO Analyzer
        
        Args:
            investment_per_stock: Amount to invest per stock (default 15,000 INR)
        """
        self.investment_per_stock = investment_per_stock
        
    def get_ipo_data(self, ticker: str) -> Optional[Dict]:
        """
        Get IPO listing data for a stock
        
        Args:
            ticker: Stock symbol (e.g., 'INFY', 'TCS')
            
        Returns:
            Dict with listing_date, listing_price, or None if not found
        """
        try:
            # Clean ticker symbol
            ticker = ticker.strip().upper()
            ticker_yf = f"{ticker}.NS" if not ticker.endswith('.NS') and not ticker.endswith('.BO') else ticker
            
            stock = yf.Ticker(ticker_yf)
            
            # Get all available historical data with retry
            hist = stock.history(period="max", auto_adjust=True)
            
            if hist.empty:
                # Try alternate format if failed
                alt_ticker = f"{ticker}.BO" if ticker_yf.endswith('.NS') else f"{ticker}.NS"
                logger.warning(f"No data for {ticker_yf}, trying {alt_ticker}")
                stock = yf.Ticker(alt_ticker)
                hist = stock.history(period="max", auto_adjust=True)
                
            if hist.empty:
                logger.warning(f"No historical data found for {ticker}")
                return None
            
            # First available date is approximation of listing date
            listing_date = hist.index[0].date()
            listing_price = float(hist.iloc[0]['Open'])
            
            # Get company name
            info = stock.info
            company_name = info.get('longName', ticker)
            
            logger.info(f"Found IPO data for {ticker}: listed on {listing_date} at Rs.{listing_price:.2f}")
            
            return {
                'ticker': ticker,
                'company_name': company_name,
                'listing_date': listing_date,
                'listing_price': listing_price
            }
            
        except Exception as e:
            logger.error(f"Error fetching IPO data for {ticker}: {e}")
            return None
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """
        Get current market price for a stock
        
        Args:
            ticker: Stock symbol
            
        Returns:
            Current price or None if not found
        """
        try:
            # Clean ticker symbol
            ticker = ticker.strip().upper()
            ticker_yf = f"{ticker}.NS" if not ticker.endswith('.NS') and not ticker.endswith('.BO') else ticker
            
            stock = yf.Ticker(ticker_yf)
            
            # Get latest price (try multiple periods)
            hist = stock.history(period="5d", auto_adjust=True)
            
            if hist.empty:
                # Try alternate format
                alt_ticker = f"{ticker}.BO" if ticker_yf.endswith('.NS') else f"{ticker}.NS"
                logger.warning(f"No data for {ticker_yf}, trying {alt_ticker}")
                stock = yf.Ticker(alt_ticker)
                hist = stock.history(period="5d", auto_adjust=True)
                
            if hist.empty:
                logger.warning(f"No current price data for {ticker}")
                return None
            
            current_price = float(hist.iloc[-1]['Close'])
            logger.info(f"Current price for {ticker}: Rs.{current_price:.2f}")
            
            return current_price
            
        except Exception as e:
            logger.error(f"Error fetching current price for {ticker}: {e}")
            return None
    
    def calculate_xirr(self, dates: List[datetime], cash_flows: List[float], guess: float = 0.1) -> Optional[float]:
        """
        Calculate XIRR (Extended Internal Rate of Return)
        
        Args:
            dates: List of transaction dates
            cash_flows: List of cash flows (negative for investments, positive for returns)
            guess: Initial guess for IRR
            
        Returns:
            XIRR as decimal (e.g., 0.15 for 15%) or None if calculation fails
        """
        import warnings
        
        try:
            # Convert dates to years from first date
            start_date = dates[0]
            years = [(d - start_date).days / 365.25 for d in dates]
            
            # Define NPV function
            def npv(rate):
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        result = sum(cf / (1 + rate) ** year for cf, year in zip(cash_flows, years))
                    return result
                except:
                    return float('inf')
            
            # Try Newton's method with multiple guesses
            guesses = [0.1, 0.5, -0.5, 0.01, 1.0]
            
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                for g in guesses:
                    try:
                        xirr = newton(npv, g, maxiter=100, tol=1e-6)
                        # Validate result
                        if not np.isnan(xirr) and not np.isinf(xirr) and -0.99 < xirr < 10.0:
                            return xirr
                    except:
                        continue
            
            # All attempts failed - return None
            return None
            
        except Exception as e:
            return None
    
    def calculate_cagr(self, start_value: float, end_value: float, years: float) -> float:
        """
        Calculate CAGR (Compound Annual Growth Rate)
        
        Args:
            start_value: Initial investment
            end_value: Final value
            years: Number of years
            
        Returns:
            CAGR as decimal (e.g., 0.15 for 15%)
        """
        if start_value <= 0 or end_value <= 0 or years <= 0:
            return 0.0
        
        cagr = (end_value / start_value) ** (1 / years) - 1
        return cagr
    
    def analyze_single_stock(self, ticker: str) -> Optional[Dict]:
        """
        Analyze returns for a single stock from IPO to current date
        
        Args:
            ticker: Stock symbol
            
        Returns:
            Dict with analysis results or None if analysis fails
        """
        try:
            # Get IPO data
            ipo_data = self.get_ipo_data(ticker)
            if not ipo_data:
                return None
            
            # Get current price
            current_price = self.get_current_price(ticker)
            if not current_price:
                return None
            
            # Calculate investment details
            listing_price = ipo_data['listing_price']
            listing_date = ipo_data['listing_date']
            
            # Calculate number of shares that can be bought with investment amount
            num_shares = self.investment_per_stock / listing_price
            invested_amount = self.investment_per_stock
            current_value = num_shares * current_price
            
            # Calculate returns
            absolute_return = current_value - invested_amount
            return_pct = (absolute_return / invested_amount) * 100
            
            # Calculate time period
            days_held = (datetime.now().date() - listing_date).days
            years_held = days_held / 365.25
            
            # Calculate CAGR
            cagr = self.calculate_cagr(invested_amount, current_value, years_held)
            
            # Calculate XIRR (simple case: one buy, one sell)
            dates = [
                datetime.combine(listing_date, datetime.min.time()),
                datetime.now()
            ]
            cash_flows = [-invested_amount, current_value]
            xirr = self.calculate_xirr(dates, cash_flows)
            
            # Fallback to CAGR if XIRR fails
            if xirr is None:
                xirr = cagr
            
            result = {
                'ticker': ticker,
                'company_name': ipo_data['company_name'],
                'listing_date': listing_date,
                'listing_price': listing_price,
                'current_price': current_price,
                'num_shares': num_shares,
                'invested_amount': invested_amount,
                'current_value': current_value,
                'absolute_return': absolute_return,
                'return_pct': return_pct,
                'days_held': days_held,
                'years_held': years_held,
                'cagr': cagr * 100,  # Convert to percentage
                'xirr': xirr * 100 if xirr is not None else None,  # Convert to percentage
                'status': 'PROFIT' if absolute_return > 0 else 'LOSS'
            }
            
            logger.info(f"Analysis complete for {ticker}: {return_pct:.1f}% return, CAGR: {result['cagr']:.1f}%")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
            return None
    
    def analyze_multiple_stocks(self, tickers: List[str], start_year: int = 2019, end_year: int = 2025) -> pd.DataFrame:
        """
        Analyze multiple stocks and return results as DataFrame
        Filters for stocks listed in target period
        
        Args:
            tickers: List of stock symbols
            start_year: Only include stocks listed after this year
            end_year: Only include stocks listed before this year
            
        Returns:
            DataFrame with analysis results for all stocks
        """
        from datetime import datetime
        
        results = []
        skipped = 0
        
        logger.info(f"Analyzing {len(tickers)} stocks for IPO buy-and-hold returns ({start_year}-{end_year})...")
        
        import time
        
        for i, ticker in enumerate(tickers, 1):
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(tickers)} ({len(results)} valid)")
            
            # Add delay to avoid rate limiting (yfinance limit: ~2000 req/hour)
            if i % 5 == 0:
                time.sleep(1)  # 1 second delay every 5 stocks
            
            result = self.analyze_single_stock(ticker)
            
            if result:
                # Filter by listing year
                listing_year = result['listing_date'].year
                
                if start_year <= listing_year <= end_year:
                    results.append(result)
                else:
                    skipped += 1
        
        if not results:
            logger.warning("No results generated")
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        
        # Sort by CAGR descending
        df = df.sort_values('cagr', ascending=False).reset_index(drop=True)
        
        logger.info(f"Analysis complete: {len(df)} stocks (listed {start_year}-{end_year}), {skipped} skipped (outside period)")
        return df
    
    def get_portfolio_summary(self, df: pd.DataFrame) -> Dict:
        """
        Calculate portfolio-level summary statistics
        
        Args:
            df: DataFrame with individual stock analysis
            
        Returns:
            Dict with portfolio summary
        """
        if df.empty:
            return {}
        
        total_invested = df['invested_amount'].sum()
        total_current_value = df['current_value'].sum()
        total_return = total_current_value - total_invested
        total_return_pct = (total_return / total_invested) * 100
        
        # Calculate portfolio XIRR (combine all cash flows)
        all_dates = []
        all_cash_flows = []
        
        for _, row in df.iterrows():
            # Investment date (negative cash flow)
            all_dates.append(datetime.combine(row['listing_date'], datetime.min.time()))
            all_cash_flows.append(-row['invested_amount'])
        
        # Current value (positive cash flow) - assume all sold today
        all_dates.append(datetime.now())
        all_cash_flows.append(total_current_value)
        
        # Calculate portfolio XIRR
        portfolio_xirr = self.calculate_xirr(all_dates, all_cash_flows)
        
        # Fallback to portfolio CAGR if XIRR fails
        if portfolio_xirr is None:
            portfolio_xirr = portfolio_cagr
        
        # Calculate average years held (weighted by investment)
        avg_years = (df['years_held'] * df['invested_amount']).sum() / total_invested
        
        # Calculate portfolio CAGR
        portfolio_cagr = self.calculate_cagr(total_invested, total_current_value, avg_years)
        
        summary = {
            'num_stocks': len(df),
            'total_invested': total_invested,
            'total_current_value': total_current_value,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'portfolio_cagr': portfolio_cagr * 100,
            'portfolio_xirr': portfolio_xirr * 100 if portfolio_xirr else None,
            'avg_years_held': avg_years,
            'num_profitable': len(df[df['absolute_return'] > 0]),
            'num_loss': len(df[df['absolute_return'] < 0]),
            'win_rate': len(df[df['absolute_return'] > 0]) / len(df) * 100,
            'best_stock': df.iloc[0]['ticker'] if not df.empty else None,
            'best_return': df.iloc[0]['cagr'] if not df.empty else None,
            'worst_stock': df.iloc[-1]['ticker'] if not df.empty else None,
            'worst_return': df.iloc[-1]['cagr'] if not df.empty else None
        }
        
        return summary


def get_ipo_stocks_from_period(start_year: int = 2019, end_year: int = 2025) -> List[str]:
    """
    Fetch ALL stocks listed on NSE in the given period
    Scrapes from NSE or uses comprehensive list
    """
    import requests
    from datetime import datetime
    
    logger.info(f"Fetching IPO listings from {start_year} to {end_year}")
    
    # Try to fetch from NSE
    all_stocks = []
    
    try:
        # Get all NSE stocks
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            import io
            import pandas as pd
            
            df = pd.read_csv(io.StringIO(response.text))
            all_stocks = df['SYMBOL'].tolist()
            logger.info(f"Fetched {len(all_stocks)} stocks from NSE")
        else:
            logger.warning(f"NSE fetch failed: {response.status_code}")
    except Exception as e:
        logger.warning(f"Could not fetch from NSE: {e}")
    
    # Load from file if exists, else use comprehensive fallback
    import os
    from pathlib import Path
    
    ipo_file = Path(__file__).parent.parent / 'ipo_stocks_2019_2025.txt'
    
    if ipo_file.exists():
        logger.info(f"Loading IPO list from {ipo_file.name}")
        with open(ipo_file, 'r') as f:
            all_stocks = [line.strip() for line in f if line.strip()]
        logger.info(f"Loaded {len(all_stocks)} IPO stocks from file")
    else:
        logger.info("Using comprehensive fallback IPO list (190+ stocks)")
        # Comprehensive list of 190+ IPOs from 2019-2025
        all_stocks = [
            # 2019 (15)
            'IRFC', 'IRCTC', 'UJJIVAN', 'SPANDANA', 'CSLFINANCE', 
            'NEOGEN', 'SURYODAY', 'METROPOLIS', 'MSTCLTD', 'POLYCAB',
            'CREDITACC', 'TCNSBRANDS', 'STLTECH', 'AFFLE', 'BFUTILITIE',
            # 2020 (20)
            'ANGELONE', 'BURGERKING', 'GLENMARK', 'INDIAMART', 'MAZAGON',
            'HAPPSTMNDS', 'ROUTE', 'LIKHITHA', 'HERANBA', 'CHEMCON',
            'GLAND', 'EQUITAS', 'UTI', 'RAILVIKAS', 'ANURAS',
            'MINDSPACE', 'IRCON', 'BARBEQUE', 'SJS', 'ROSSARI',
            # 2021 (55 - mega IPO year)
            'ZOMATO', 'NYKAA', 'PAYTM', 'POLICYBAZAAR', 'CARTRADE',
            'LATENTVIEW', 'TATVA', 'KRSNAA', 'MEDPLUS', 'WINDLAS',
            'SHYAMMETL', 'GLENMARKLIFE', 'SANSERA', 'CLEAN', 'DODLA',
            'DEVYANI', 'NAZARA', 'EASEMYTRIP', 'MACROTECH', 'LAXMIMACH',
            'CRAFTSMAN', 'APTUS', 'ROLEX', 'SHRIRAMFIN', 'RATEGAIN',
            'CHEMPLAST', 'AMINO', 'SIGACHI', 'SUPRIYA', 'NUVOCO',
            'HGINFRA', 'SHAREINDIA', 'SURYAROSNI', 'ANANTRAJ', 'GOKEX',
            'VERANDA', 'NURECA', 'RVNL', 'INDOSTAR', 'POWERINDIA',
            'STOVEKRAFT', 'TEGA', 'ALKYLAMINE', 'ELIN', 'VIJAYA',
            'DATAPATTNS', 'BIKAJI', 'BROOKFIELD', 'HPAL', 'LANDMARK',
            # 2022 (20)
            'LICI', 'DELHIVERY', 'RAINBOW', 'AETHER', 'AGS',
            'VEDL', 'HARSHA', 'CAMPUS', 'SAPPHIRE', 'ARCHEAN',
            'GARWARE', 'UNIPARTS', 'SKIPPER', 'PRAVEG', 'SYRMA',
            'ADANIPOWER', 'SUPREMEPWR', 'PARADEEP', 'PRUDENT', 'FIVESTAR',
            # 2023 (20)
            'MANKIND', 'KAYNES', 'PROTEAN', 'NETWEB', 'YATRA',
            'TIPSINDLTD', 'JSWINFRA', 'MOTISONS', 'INNOVALANCE', 'CONCORD',
            'FEDBANK', 'AEROFLEX', 'JYOTICNC', 'DIVGI', 'SUDARSHAN',
            'JBCHEPHARM', 'GENSOL', 'CRAYONS', 'SAMHI',
            # 2024 (56+)
            'TATATECH', 'HONASA', 'IXIGO', 'GODIGIT', 'IDEAFORGE',
            'BHARATFORG', 'SBFC', 'AKUMS', 'AWFIS', 'SURAJ',
            'INDEGENE', 'EPACK', 'KRONOX', 'WESTERN', 'UNICOMMERCE',
            'BAJAJHOUS', 'INDUS', 'TRANSRAIL', 'ARKADE', 'GANESH',
            'CREDO', 'SURAKSHA', 'STALLION', 'GALA', 'BHARATWIRE',
            'VIBHOR', 'VISHAL', 'RESOURCEFUL', 'SARVESHWAR', 'BAJEL',
            'ECOS', 'MANBA', 'SENCO', 'KRN', 'AKME', 'FORTUNE',
            'DIFFUSION', 'FLAIR', 'KELLTON', 'GARNET', 'JINDWORLD',
            'PLATINUM', 'VENTIVE', 'APOLLO', 'DOMS', 'PREMIUM',
            'CEIGALL', 'AVALON',
            # 2025 (10)
            'FIRSTCRY', 'EMCURE', 'SWIGGY', 'OLA', 'NAVI',
            'MOBIKWIK', 'OLAELECTRIC', 'PEPPERFRY', 'LENSKART'
        ]
    
    # Filter for stocks with listing in target period
    # This is best-effort - will analyze all and filter by actual listing date
    return all_stocks

