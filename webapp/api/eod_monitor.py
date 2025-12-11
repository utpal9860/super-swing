"""
EOD Monitor API
Endpoints for running end-of-day trade checks and viewing results
**NOW WITH TRADE HEALTH MONITORING!**
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import yfinance as yf
import subprocess
import logging

# Add parent directory to path for src imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from webapp.api.paper_trading import load_trades
from webapp.utils.options import get_option_ltp, get_option_lot_size
from webapp.api.auth_api import get_current_user
from webapp.database import User

# Import openchart for historical option OHLC data
try:
    from openchart import NSEData
    OPENCHART_AVAILABLE = True
except ImportError:
    OPENCHART_AVAILABLE = False
    logger.warning("openchart not available - historical option OHLC data will not be fetched")

logger = logging.getLogger(__name__)

# Import trade health monitor
try:
    from trade_health_monitor import TradeHealthMonitor
    HEALTH_CHECK_ENABLED = True
except ImportError:
    logger.warning("Trade health monitor not available")
    HEALTH_CHECK_ENABLED = False

router = APIRouter()

DATA_DIR = Path("webapp/data")
EOD_LOG_FILE = DATA_DIR / "eod_monitor_log.csv"

# Global openchart instance (lazy loaded)
_openchart_instance = None

def get_openchart_instance():
    """Get or create openchart NSEData instance"""
    global _openchart_instance
    if not OPENCHART_AVAILABLE:
        return None
    if _openchart_instance is None:
        try:
            _openchart_instance = NSEData()
            _openchart_instance.download()
        except Exception as e:
            logger.error(f"Failed to initialize openchart: {e}")
            return None
    return _openchart_instance


def construct_nse_option_symbol(symbol: str, strike: float, option_type: str, expiry_date_str: str) -> Optional[str]:
    """
    Construct NSE option symbol format from trade data.
    
    Format rules:
    - For weekly contracts (SENSEX, NIFTY): SYMBOL + DD + MON + STRIKE + TYPE
      Example: SENSEX, 84500, CE, "11-Dec-2025" -> "SENSEX11DEC84500CE"
    - For monthly contracts (stocks, monthly indices): SYMBOL + YY + MON + STRIKE + TYPE
      Example: PRESTIGE, 1680, CE, "30-Dec-2025" -> "PRESTIGE25DEC1680CE"
    
    Args:
        symbol: Underlying symbol (e.g., "PRESTIGE", "SENSEX")
        strike: Strike price (e.g., 1680)
        option_type: "CE" or "PE"
        expiry_date_str: Expiry date string (e.g., "30-Dec-2025")
    
    Returns:
        NSE option symbol (e.g., "PRESTIGE25DEC1680CE" or "SENSEX25DEC1184500CE") or None if parsing fails
    """
    try:
        from webapp.utils.options import INDEX_SYMBOLS, INDEX_EXPIRY_SCHEDULE
        
        # Parse expiry date
        expiry_date = datetime.strptime(expiry_date_str, '%d-%b-%Y')
        year_short = expiry_date.strftime('%y')
        month = expiry_date.strftime('%b').upper()
        day = expiry_date.strftime('%d')  # Day as 2-digit string (e.g., "11", "25")
        strike_int = int(round(float(strike)))
        opt_type = option_type.upper()
        
        # Check if this is a weekly contract (needs day in symbol)
        symbol_upper = symbol.upper().replace(".NS", "")
        is_index = symbol_upper in INDEX_SYMBOLS
        is_weekly = False
        if is_index:
            expiry_day, expiry_type = INDEX_EXPIRY_SCHEDULE.get(symbol_upper, (0, 'monthly'))
            is_weekly = expiry_type == 'weekly'
        
        # For weekly contracts, include day in symbol format
        # Format: SENSEX11DEC84500CE (symbol + DD + MON + strike + type)
        # Note: Weekly contracts use DD+MON format (day before month), no year
        if is_weekly:
            # Format: SENSEX11DEC84500CE (symbol + DD + MON + strike + type)
            constructed_symbol = f"{symbol_upper}{day}{month}{strike_int}{opt_type}"
        else:
            # Format: PRESTIGE25DEC1680CE (symbol + YY + MON + strike + type) - no day for monthly
            constructed_symbol = f"{symbol_upper}{year_short}{month}{strike_int}{opt_type}"
        
        logger.info(f"[OHLC] Constructed symbol: {symbol} {strike} {option_type} expiry={expiry_date_str} (weekly={is_weekly}) -> {constructed_symbol}")
        return constructed_symbol
    except Exception as e:
        logger.error(f"Failed to construct option symbol from expiry '{expiry_date_str}': {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


def fetch_option_historical_ohlc(symbol: str, strike: float, option_type: str, expiry_date_str: str, start_date: datetime, debug_logs=None) -> Optional[dict]:
    """
    Fetch historical OHLC data for an option using openchart.
    
    Note: BSE indices (SENSEX, BANKEX, SENSEX50) are not supported by openchart
    as it only provides NFO data, not BFO data. For BSE indices, this function
    will return None and the EOD monitor will use LTP only.
    
    Args:
        symbol: Underlying symbol
        strike: Strike price
        option_type: CE or PE
        expiry_date_str: Expiry date string
        start_date: Start date for historical data
        debug_logs: Optional list to append debug messages to
    
    Returns:
        Dict with 'max_high', 'min_low', 'current_price', 'data' (list of daily OHLC)
        or None if fetch fails
    """
    if debug_logs is None:
        debug_logs = []
    if not OPENCHART_AVAILABLE:
        return None
    
    # Check if this is a BSE index - openchart doesn't support BFO data
    symbol_upper = symbol.upper().replace(".NS", "")
    is_bse_index = symbol_upper in ['SENSEX', 'BANKEX', 'SENSEX50']
    
    if is_bse_index:
        log_msg = f"[OHLC] BSE index {symbol_upper} detected. openchart only supports NFO data (not BFO), so historical OHLC is not available. Will use LTP only."
        logger.warning(log_msg)
        print(log_msg)
        debug_logs.append(log_msg)
        return None
    
    try:
        nse = get_openchart_instance()
        if nse is None:
            return None
        
        # Construct option symbol - log the expiry being used for debugging
        log_msg = f"[OHLC] Constructing symbol with expiry: {expiry_date_str} for {symbol} {strike} {option_type}"
        logger.info(log_msg)
        print(log_msg)
        debug_logs.append(log_msg)
        
        option_symbol = construct_nse_option_symbol(symbol, strike, option_type, expiry_date_str)
        if option_symbol is None:
            log_msg = f"[OHLC] Failed to construct option symbol for {symbol} {strike} {option_type} with expiry {expiry_date_str}"
            logger.warning(log_msg)
            print(log_msg)
            debug_logs.append(log_msg)
            return None
        log_msg = f"[OHLC] Constructed option symbol: {option_symbol}"
        logger.info(log_msg)
        print(log_msg)
        debug_logs.append(log_msg)
        
        # Determine if this is a BSE index (SENSEX, BANKEX, SENSEX50)
        # BSE indices are in BFO segment, not NFO
        symbol_upper = symbol.upper().replace(".NS", "")
        is_bse_index = symbol_upper in ['SENSEX', 'BANKEX', 'SENSEX50']
        
        # Parse expiry date to extract day and month for search patterns
        try:
            expiry_date = datetime.strptime(expiry_date_str, '%d-%b-%Y')
            day = expiry_date.strftime('%d')
            month = expiry_date.strftime('%b').upper()
        except:
            day = None
            month = None
        
        # Select the appropriate data source
        if is_bse_index:
            # For BSE indices, try BFO data if available, otherwise fall back to NFO
            search_data = getattr(nse, 'bfo_data', None) or nse.nfo_data
            log_msg = f"[OHLC] Searching for BSE index {symbol_upper} in {'BFO' if hasattr(nse, 'bfo_data') else 'NFO'} data"
            logger.info(log_msg)
            print(log_msg)
            debug_logs.append(log_msg)
        else:
            # For NSE indices and stocks, use NFO data
            search_data = nse.nfo_data
        
        # Search for the option in the appropriate data source
        # Try exact match first
        option_match = search_data[search_data['Symbol'] == option_symbol]
        
        # If exact match fails, try partial match (for cases where symbol format might differ)
        if option_match.empty:
            # Try searching by strike and type in the symbol name
            strike_str = str(int(strike))
            search_pattern = f".*{strike_str}.*{option_type.upper()}"
            option_match = search_data[
                (search_data['Symbol'].str.contains(symbol.upper(), case=False, na=False) &
                 search_data['Symbol'].str.contains(search_pattern, case=False, regex=True, na=False)) |
                (search_data['Name'].str.contains(symbol.upper(), case=False, na=False) &
                 search_data['Name'].str.contains(search_pattern, case=False, regex=True, na=False))
            ]
        
        if option_match.empty:
            # Try alternative search patterns for indices (especially BSE indices like SENSEX)
            if is_bse_index:
                # BSE indices might have different symbol formats
                # Try searching without year/month prefix, or with different date format
                # Try multiple patterns
                patterns = [
                    f"{symbol_upper}.*{int(strike)}.*{option_type.upper()}",  # SENSEX.*84500.*CE
                ]
                if day and month:
                    patterns.append(f"{symbol_upper}.*{day}.*{month}.*{int(strike)}.*{option_type.upper()}")  # SENSEX.*11.*DEC.*84500.*CE
                patterns.append(f"{symbol_upper}.*{int(strike)}")  # Just symbol and strike
                
                for pattern in patterns:
                    option_match = search_data[
                        search_data['Symbol'].str.contains(pattern, case=False, regex=True, na=False) |
                        search_data['Name'].str.contains(pattern, case=False, regex=True, na=False)
                    ]
                    if not option_match.empty:
                        log_msg = f"[OHLC] Found {symbol_upper} option using pattern: {pattern}"
                        logger.info(log_msg)
                        print(log_msg)
                        debug_logs.append(log_msg)
                        break
            
            # If still empty, try broader search
            if option_match.empty:
                strike_str = str(int(strike))
                search_pattern = f".*{strike_str}.*{option_type.upper()}"
                option_match = search_data[
                    (search_data['Symbol'].str.contains(symbol.upper(), case=False, na=False) &
                     search_data['Symbol'].str.contains(search_pattern, case=False, regex=True, na=False)) |
                    (search_data['Name'].str.contains(symbol.upper(), case=False, na=False) &
                     search_data['Name'].str.contains(search_pattern, case=False, regex=True, na=False))
                ]
        
        if option_match.empty:
            log_msg = f"[OHLC] Option symbol {option_symbol} not found in NFO master data. Tried: {symbol} {strike} {option_type}"
            logger.warning(log_msg)
            print(log_msg)
            debug_logs.append(log_msg)
            
            # Log available options for debugging - ALWAYS do this for indices
            if symbol_upper in ['BANKNIFTY', 'NIFTY', 'SENSEX', 'FINNIFTY', 'MIDCPNIFTY']:
                # Search for all options with this symbol in the appropriate data source
                index_options = search_data[
                    (search_data['Symbol'].str.contains(symbol_upper, case=False, na=False)) |
                    (search_data['Name'].str.contains(symbol_upper, case=False, na=False))
                ]
                if len(index_options) > 0:
                    # Filter to options with matching strike
                    strike_int = int(round(float(strike)))
                    matching_strike = index_options[
                        index_options['Symbol'].str.contains(str(strike_int), case=False, na=False) |
                        index_options['Name'].str.contains(str(strike_int), case=False, na=False)
                    ]
                    
                    log_msg2 = f"[OHLC] Found {len(index_options)} total {symbol_upper} options in NFO"
                    logger.info(log_msg2)
                    print(log_msg2)
                    debug_logs.append(log_msg2)
                    
                    if len(matching_strike) > 0:
                        # Show options with matching strike
                        sample = matching_strike[['Symbol', 'Name']].head(20).to_dict('records')
                        log_msg3 = f"[OHLC] Found {len(matching_strike)} {symbol_upper} options with strike {strike_int}. Sample: {sample}"
                        logger.info(log_msg3)
                        print(log_msg3)
                        debug_logs.append(log_msg3)
                    else:
                        # Show all options to see what's available
                        sample = index_options[['Symbol', 'Name']].head(30).to_dict('records')
                        log_msg3 = f"[OHLC] No {symbol_upper} options found with strike {strike_int}. Available options (first 30): {sample}"
                        logger.warning(log_msg3)
                        print(log_msg3)
                        debug_logs.append(log_msg3)
                else:
                    # Check if BFO data exists and search there for BSE indices
                    if is_bse_index and hasattr(nse, 'bfo_data'):
                        bfo_options = nse.bfo_data[
                            (nse.bfo_data['Symbol'].str.contains(symbol_upper, case=False, na=False)) |
                            (nse.bfo_data['Name'].str.contains(symbol_upper, case=False, na=False))
                        ]
                        if len(bfo_options) > 0:
                            log_msg2 = f"[OHLC] Found {len(bfo_options)} {symbol_upper} options in BFO data (not NFO)"
                            logger.info(log_msg2)
                            print(log_msg2)
                            debug_logs.append(log_msg2)
                            sample = bfo_options[['Symbol', 'Name']].head(30).to_dict('records')
                            log_msg3 = f"[OHLC] BFO options sample: {sample}"
                            logger.info(log_msg3)
                            print(log_msg3)
                            debug_logs.append(log_msg3)
                        else:
                            log_msg2 = f"[OHLC] No {symbol_upper} options found in NFO or BFO master data!"
                            logger.warning(log_msg2)
                            print(log_msg2)
                            debug_logs.append(log_msg2)
                    else:
                        log_msg2 = f"[OHLC] No {symbol_upper} options found in {'BFO' if is_bse_index else 'NFO'} master data at all!"
                        logger.warning(log_msg2)
                        print(log_msg2)
                        debug_logs.append(log_msg2)
            return None
        
        log_msg = f"[OHLC] Found option in NFO: {option_match.iloc[0]['Symbol']}, ScripCode: {option_match.iloc[0]['ScripCode']}"
        logger.info(log_msg)
        print(log_msg)
        debug_logs.append(log_msg)
        
        option_info = option_match.iloc[0]
        scrip_code = int(option_info['ScripCode'])
        
        # Fetch historical data
        end_date = datetime.now()
        # For same-day entries, go back a few days to ensure we get some data
        # If entry is today, try to get at least 5 days of data
        days_back = 1
        if start_date.date() == end_date.date():
            # Entry is today - try to get last 5 days to ensure we have data
            days_back = 5
            log_msg = f"[OHLC] Entry date is today ({start_date.date()}), fetching last {days_back} days of data"
            logger.info(log_msg)
            print(log_msg)
            debug_logs.append(log_msg)
        
        start_dt = start_date - timedelta(days=days_back)
        
        # Ensure start date is not too far in the past (limit to 30 days)
        max_days_back = 30
        if (end_date - start_dt).days > max_days_back:
            start_dt = end_date - timedelta(days=max_days_back)
        
        payload = {
            'exch': 'D',  # NFO
            'instrType': 'D',  # Derivatives
            'scripCode': scrip_code,
            'ulToken': scrip_code,
            'fromDate': int(start_dt.timestamp()),
            'toDate': int(end_date.timestamp()),
            'timeInterval': '1',
            'chartPeriod': 'D',
            'chartStart': 0
        }
        
        log_msg = f"[OHLC] Requesting historical data: fromDate={start_dt.strftime('%Y-%m-%d')}, toDate={end_date.strftime('%Y-%m-%d')}, scripCode={scrip_code}"
        logger.info(log_msg)
        print(log_msg)
        debug_logs.append(log_msg)
        
        # Make API request
        nse.session.get('https://www.nseindia.com', timeout=5)
        response = nse.session.post(
            'https://charting.nseindia.com//Charts/symbolhistoricaldata/',
            data=json.dumps(payload),
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        # Check response
        if data.get('s') != 'Ok':
            log_msg = f"[OHLC] API returned error status: s={data.get('s')}, message={data.get('message', 'N/A')}"
            logger.warning(log_msg)
            print(log_msg)
            debug_logs.append(log_msg)
            return None
        
        timestamps = data.get('t', [])
        if not timestamps:
            # No timestamps - might be because:
            # 1. Option is too new (listed today)
            # 2. No trading data yet
            # 3. Date range issue
            log_msg = f"[OHLC] No historical data returned for {option_symbol}. Response: s={data.get('s')}, has_timestamps=False. This might be because the option was listed today or has no trading data yet."
            logger.warning(log_msg)
            print(log_msg)
            debug_logs.append(log_msg)
            # For same-day entries, this is expected - return None and use current LTP
            return None
        
        # Process the data: data['t'] = timestamps, data['h'] = highs, data['l'] = lows, etc.
        highs = data.get('h', [])
        lows = data.get('l', [])
        opens = data.get('o', [])
        closes = data.get('c', [])
        volumes = data.get('v', [])
        
        # Convert timestamps to datetime and create daily data
        # Filter to only include data from entry date onwards
        daily_data = []
        max_high = None
        min_low = None
        current_price = None
        entry_date_only = start_date.date()  # Compare dates only (not time)
        
        for i, ts in enumerate(timestamps):
            date = datetime.fromtimestamp(ts)
            date_only = date.date()
            
            # Only include data from entry date onwards
            if date_only < entry_date_only:
                continue
            
            high = float(highs[i]) if i < len(highs) else None
            low = float(lows[i]) if i < len(lows) else None
            open_price = float(opens[i]) if i < len(opens) else None
            close = float(closes[i]) if i < len(closes) else None
            volume = int(volumes[i]) if i < len(volumes) else None
            
            daily_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
            
            if high is not None:
                max_high = high if max_high is None else max(max_high, high)
            if low is not None:
                min_low = low if min_low is None else min(min_low, low)
            
            # Current price is the last close
            if close is not None:
                current_price = close
        
        # If no data after filtering, return None
        if not daily_data:
            log_msg = f"[OHLC] No data found after filtering from entry date {entry_date_only} onwards for {option_symbol}"
            logger.warning(log_msg)
            print(log_msg)
            debug_logs.append(log_msg)
            return None
        
        log_msg = f"[OHLC] Processed {len(daily_data)} days of data for {option_symbol}: max_high={max_high}, min_low={min_low}, current_price={current_price}"
        logger.info(log_msg)
        print(log_msg)
        debug_logs.append(log_msg)
        
        return {
            'max_high': max_high,
            'min_low': min_low,
            'current_price': current_price,
            'data': daily_data
        }
        
    except Exception as e:
        logger.error(f"Error fetching option historical OHLC: {e}", exc_info=True)
        return None


def fetch_historical_ohlc(symbol, start_date):
    """Fetch historical OHLC data from start_date to today"""
    try:
        ticker = yf.Ticker(symbol)
        end_date = (datetime.now()).strftime('%Y-%m-%d')
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        start_dt = start_dt - timedelta(days=1)
        start_date_adj = start_dt.strftime('%Y-%m-%d')
        
        log_msg = f"[OHLC] Fetching data for {symbol}: start_date={start_date}, adjusted_start={start_date_adj}, end_date={end_date}"
        logger.info(log_msg)
        print(log_msg)
        
        hist = ticker.history(start=start_date_adj, end=end_date, interval="1d")
        
        if hist.empty:
            log_msg = f"[OHLC] No historical data for {symbol} from {start_date_adj} to {end_date}"
            logger.warning(log_msg)
            print(log_msg)
            return None
        
        first_date = hist.index[0].strftime('%Y-%m-%d')
        last_date = hist.index[-1].strftime('%Y-%m-%d')
        max_high = float(hist['High'].max())
        min_low = float(hist['Low'].min())
        latest_close = float(hist.iloc[-1]['Close'])
        
        log_msg = f"[OHLC] Fetched {len(hist)} days for {symbol}: first_date={first_date}, last_date={last_date}, max_high={max_high}, min_low={min_low}, latest_close={latest_close}"
        logger.info(log_msg)
        print(log_msg)
        log_msg2 = f"[OHLC] Date range: {first_date} to {last_date} (requested: {start_date} to {end_date})"
        logger.info(log_msg2)
        print(log_msg2)
        
        return hist
    except Exception as e:
        logger.error(f"[OHLC] Error fetching historical data for {symbol}: {e}", exc_info=True)
        return None


def check_trade_status(
    trade,
    hist_data,
    brokerage_per_trade=20,
    include_time_stop: bool = False,
    time_stop_days: int = 120
):
    """Check if trade hit SL or Target anytime after entry"""
    entry_price = float(trade['entry_price'])
    entry_date = datetime.strptime(trade['entry_date'], '%Y-%m-%d %H:%M:%S')
    entry_date_str = entry_date.strftime('%Y-%m-%d')
    
    stop_loss_raw = trade.get('stop_loss', 0)
    if isinstance(stop_loss_raw, dict):
        stop_loss = float(stop_loss_raw.get('parsedValue', 0) or stop_loss_raw.get('source', 0) or 0)
    else:
        stop_loss = float(stop_loss_raw or 0)
    
    target_raw = trade.get('target', 0)
    if isinstance(target_raw, dict):
        target = float(target_raw.get('parsedValue', 0) or target_raw.get('source', 0) or 0)
    else:
        target = float(target_raw or 0)
    
    shares = 1
    is_option = trade.get('instrument_type') == 'option'
    if is_option:
        lot_size = trade.get('lot_size')
        if not lot_size or lot_size == 1:
            try:
                symbol = trade.get('symbol', '').replace('.NS', '')
                lot_size = get_option_lot_size(symbol)
            except Exception:
                lot_size = 1
        effective_qty = shares * int(lot_size)
    else:
        effective_qty = shares
    
    symbol = trade.get('symbol', 'UNKNOWN')
    
    if hist_data is None or hist_data.empty:
        logger.warning(f"[CHECK_STATUS] {symbol}: No historical data available, using entry_price as fallback")
        current_price = entry_price
        max_high = entry_price
        min_low = entry_price
        latest_date = entry_date_str
    else:
        latest = hist_data.iloc[-1]
        latest_date = hist_data.index[-1].strftime('%Y-%m-%d')
        first_date = hist_data.index[0].strftime('%Y-%m-%d')
        current_price = float(latest['Close'])
        max_high = float(hist_data['High'].max())
        min_low = float(hist_data['Low'].min())
        
        log_msg = f"[CHECK_STATUS] {symbol}: entry_date={entry_date_str}, data_range={first_date} to {latest_date}, max_high={max_high}, min_low={min_low}, current={current_price}, target={target}, sl={stop_loss}"
        logger.info(log_msg)
        print(log_msg)
    
    days_held = (datetime.now() - entry_date).days
    
    # =====================================================================
    # TIME-SEQUENCED CHECK: Which hit first - SL or Target?
    # =====================================================================
    # For equity trades, check if we have intraday data or use daily data
    
    # Check target first (more favorable), but verify SL wasn't hit first if we have time-series data
    target_hit = target > 0 and max_high >= target
    sl_hit = stop_loss > 0 and min_low <= stop_loss
    
    if target_hit and not sl_hit:
        # Target hit, SL never hit - safe to exit at target
        gross_pnl = (target - entry_price) * effective_qty
        net_pnl = gross_pnl - (brokerage_per_trade * 2)
        position_value = entry_price * effective_qty
        pnl_pct = (net_pnl / position_value) * 100 if position_value > 0 else 0
        symbol = trade.get('symbol', 'UNKNOWN')
        logger.info(f"TARGET_HIT: {symbol} entry={entry_price}, target={target}, max_high={max_high}, qty={effective_qty}, gross={gross_pnl}, net={net_pnl}, pct={pnl_pct:.2f}%")
        return {
            'status': 'TARGET_HIT',
            'exit_price': target,
            'exit_reason': 'target',
            'current_price': current_price,
            'max_high': max_high,
            'pnl_pct': pnl_pct,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'effective_qty': effective_qty,
            'days_held': days_held
        }
    
    if sl_hit and not target_hit:
        # SL hit, target never hit - exit at SL
        gross_pnl = (stop_loss - entry_price) * effective_qty
        net_pnl = gross_pnl - (brokerage_per_trade * 2)
        position_value = entry_price * effective_qty
        pnl_pct = (net_pnl / position_value) * 100 if position_value > 0 else 0
        symbol = trade.get('symbol', 'UNKNOWN')
        logger.info(f"STOP_LOSS_HIT: {symbol} entry={entry_price}, sl={stop_loss}, min_low={min_low}, qty={effective_qty}, gross={gross_pnl}, net={net_pnl}, pct={pnl_pct:.2f}%")
        return {
            'status': 'STOP_LOSS_HIT',
            'exit_price': stop_loss,
            'exit_reason': 'stop_loss',
            'current_price': current_price,
            'min_low': min_low,
            'pnl_pct': pnl_pct,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'effective_qty': effective_qty,
            'days_held': days_held
        }
    
    if target_hit and sl_hit:
        # Both hit - need to check which came first using time-series data
        # For daily data, we can't determine intraday sequence, so use conservative approach:
        # If both hit on same day, check if entry was after price movement
        # If entry was at 10 and price was already at 5, then moved to 15, target wins
        # If entry was at 10 and price moved to 7 then 15, SL wins (price had to go down first)
        
        # Conservative approach: If both hit, assume SL hit first (protect capital)
        # This is safer - if price touched SL, it's a risk signal
        log_msg = f"[EOD] {symbol}: Both SL and Target hit. Using conservative approach: SL hit first."
        logger.warning(log_msg)
        print(log_msg)
        
        gross_pnl = (stop_loss - entry_price) * effective_qty
        net_pnl = gross_pnl - (brokerage_per_trade * 2)
        position_value = entry_price * effective_qty
        pnl_pct = (net_pnl / position_value) * 100 if position_value > 0 else 0
        
        return {
            'status': 'STOP_LOSS_HIT',
            'exit_price': stop_loss,
            'exit_reason': 'stop_loss',
            'current_price': current_price,
            'min_low': min_low,
            'pnl_pct': pnl_pct,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'effective_qty': effective_qty,
            'days_held': days_held,
            'note': 'Both SL and Target hit - conservative exit at SL'
        }
    
    if include_time_stop and days_held >= time_stop_days:
        gross_pnl = (current_price - entry_price) * effective_qty
        net_pnl = gross_pnl - (brokerage_per_trade * 2)
        # Calculate percentage based on position value (capital invested), not just price change
        position_value = entry_price * effective_qty
        pnl_pct = (net_pnl / position_value) * 100 if position_value > 0 else 0
        return {
            'status': 'TIME_STOP',
            'exit_price': current_price,
            'exit_reason': 'time_stop',
            'current_price': current_price,
            'max_high': max_high,
            'pnl_pct': pnl_pct,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'days_held': days_held
        }
    
    unrealized_pnl = (current_price - entry_price) * effective_qty
    # Calculate percentage based on position value (capital invested), not just price change
    position_value = entry_price * effective_qty
    pnl_pct = (unrealized_pnl / position_value) * 100 if position_value > 0 else 0
    return {
        'status': 'OPEN',
        'current_price': current_price,
        'max_high': max_high,
        'min_low': min_low,
        'pnl_pct': pnl_pct,
        'unrealized_pnl': unrealized_pnl,
        'days_held': days_held,
        'effective_qty': effective_qty
    }


def option_status_from_ltp(trade, brokerage_per_trade=20, debug_logs=None):
    """Check option trade status using historical OHLC data from openchart
    
    Args:
        trade: Trade dict
        brokerage_per_trade: Brokerage per trade
        debug_logs: Optional list to append debug messages to
    """
    if debug_logs is None:
        debug_logs = []
    entry_price = float(trade['entry_price'])
    entry_date = datetime.strptime(trade['entry_date'], '%Y-%m-%d %H:%M:%S')
    
    stop_loss_raw = trade.get('stop_loss', 0)
    if isinstance(stop_loss_raw, dict):
        stop_loss = float(stop_loss_raw.get('parsedValue', 0) or stop_loss_raw.get('source', 0) or 0)
    else:
        stop_loss = float(stop_loss_raw or 0)
    
    target_raw = trade.get('target', 0)
    if isinstance(target_raw, dict):
        target = float(target_raw.get('parsedValue', 0) or target_raw.get('source', 0) or 0)
    else:
        target = float(target_raw or 0)
    
    shares = 1
    # Extract symbol early (needed for lot_size lookup and logging)
    symbol = trade.get('symbol', '').replace('.NS', '')
    lot_size = trade.get('lot_size')
    # If lot_size is None or 1, try to look it up (might have been missing when trade was created)
    if not lot_size or lot_size == 1:
        try:
            lot_size = get_option_lot_size(symbol)
            if lot_size == 1:
                logger.warning(f"Option lot size lookup returned 1 for {symbol} - this may be incorrect. Check static file webapp/data/lot_sizes.json")
        except Exception as e:
            logger.warning(f"Failed to lookup lot size for {symbol}: {e}")
            lot_size = 1
    qty = shares * int(lot_size)
    
    # Debug log for P&L calculation
    log_msg = f"[P&L] {symbol} option: entry={entry_price}, target={target}, lot_size={lot_size}, shares={shares}, qty={qty}, brokerage={brokerage_per_trade * 2}"
    logger.info(log_msg)
    print(log_msg)
    
    # Get current LTP as fallback
    result = get_option_ltp(
        symbol=trade.get('symbol', '').replace('.NS', ''),
        strike=trade.get('option_strike'),
        option_type=trade.get('option_type'),
        expiry_month=trade.get('option_expiry_month')
    )
    
    # Handle both old format (ltp, expiry) and new format (ltp, expiry, today_high, today_low)
    if len(result) == 2:
        ltp, resolved_expiry = result
    else:
        ltp, resolved_expiry, _, _ = result
    
    # Try to fetch historical OHLC data using openchart
    # symbol already defined above
    strike = trade.get('option_strike')
    option_type = trade.get('option_type')
    stored_expiry = trade.get('option_expiry_month')
    
    # Check if stored expiry is a month name (like "DECEMBER") or a date format (like "30-Dec-2025")
    # Month names are 3-9 characters, date format has hyphens and is longer
    is_month_name = stored_expiry and len(stored_expiry) <= 9 and '-' not in stored_expiry
    is_date_format = stored_expiry and '-' in stored_expiry
    
    # Check if this is a weekly contract (SENSEX, NIFTY are weekly)
    from webapp.utils.options import INDEX_SYMBOLS, INDEX_EXPIRY_SCHEDULE
    is_weekly_contract = symbol in INDEX_SYMBOLS and INDEX_EXPIRY_SCHEDULE.get(symbol, (0, 'monthly'))[1] == 'weekly'
    
    # IMPORTANT: For weekly contracts, always recalculate expiry to ensure correctness
    # Don't trust stored expiry or resolved_expiry from API as they might be wrong
    # (e.g., API might return monthly expiry instead of weekly, or wrong date like "25-Dec-2025" instead of "11-Dec-2025")
    # This fixes existing trades that have wrong expiry dates stored
    if is_weekly_contract:
        # For weekly contracts, always recalculate based on entry_date
        # This ensures existing trades with wrong expiry (e.g., "25-Dec-2025") get corrected
        expiry_date_str = None  # Will be recalculated below
        log_msg = f"[EOD] {symbol} option: Weekly contract detected, will recalculate expiry from entry_date={entry_date.date()} (stored={stored_expiry}, resolved={resolved_expiry})"
        logger.info(log_msg)
        print(log_msg)
        debug_logs.append(log_msg)
    elif is_date_format:
        # For non-weekly contracts, if stored expiry is already in date format, use it directly
        expiry_date_str = stored_expiry
        log_msg = f"[EOD] {symbol} option: Using stored date format expiry: {expiry_date_str} (ignoring resolved_expiry={resolved_expiry})"
        logger.info(log_msg)
        print(log_msg)
        debug_logs.append(log_msg)
    elif is_month_name:
        # For month names, always recalculate
        expiry_date_str = None  # Will be recalculated below
        log_msg = f"[EOD] {symbol} option: Stored expiry is month name ({stored_expiry}), will recalculate (ignoring resolved_expiry={resolved_expiry})"
        logger.info(log_msg)
        print(log_msg)
        debug_logs.append(log_msg)
    elif resolved_expiry:
        # Use resolved expiry from API (only if stored was not a month name and not date format)
        expiry_date_str = resolved_expiry
    else:
        # Stored value is None - need to resolve
        expiry_date_str = None
    
    # Debug log
    log_msg = f"[EOD] {symbol} option: expiry_from_trade={stored_expiry}, is_month_name={is_month_name}, is_date_format={is_date_format}, resolved_expiry={resolved_expiry}, final_expiry={expiry_date_str}"
    logger.info(log_msg)
    print(log_msg)
    debug_logs.append(log_msg)
    
    hist_ohlc = None
    if OPENCHART_AVAILABLE:
        # If expiry_date_str is None, try to resolve it from option chain
        if not expiry_date_str:
            try:
                # Calculate expiry date based on NSE rules
                from webapp.utils.options import calculate_option_expiry
                # For weekly contracts: Always pass None as hint (don't use stored expiry even if it's a date)
                # This ensures we recalculate from entry_date, not use potentially wrong stored expiry
                # For month names: Use stored_expiry as hint (e.g., "DECEMBER")
                # For others: Use None
                if is_weekly_contract:
                    expiry_hint = None  # Always recalculate for weekly contracts, ignore stored expiry
                elif is_month_name:
                    expiry_hint = stored_expiry  # Use month name as hint (e.g., "DECEMBER")
                else:
                    expiry_hint = None
                log_msg = f"[EOD] {symbol} option: Calculating expiry date (hint: {expiry_hint}, entry_date: {entry_date.date()})..."
                logger.info(log_msg)
                print(log_msg)
                debug_logs.append(log_msg)
                
                # For weekly contracts, force recalculation even if stored expiry is in date format
                expiry_date_str = calculate_option_expiry(
                    symbol=symbol,
                    expiry_month=expiry_hint,
                    reference_date=entry_date,
                    force_recalculate=is_weekly_contract  # Force recalculation for weekly contracts
                )
                
                if expiry_date_str:
                    log_msg = f"[EOD] {symbol} option: Calculated expiry: {expiry_date_str}"
                    logger.info(log_msg)
                    print(log_msg)
                    debug_logs.append(log_msg)
                else:
                    log_msg = f"[EOD] {symbol} option: Could not calculate expiry"
                    logger.warning(log_msg)
                    print(log_msg)
                    debug_logs.append(log_msg)
            except Exception as e:
                log_msg = f"[EOD] {symbol} option: Error calculating expiry: {e}"
                logger.warning(log_msg)
                print(log_msg)
                debug_logs.append(log_msg)
        
        # Final check: Log what expiry_date_str will be used for OHLC fetch
        log_msg = f"[EOD] {symbol} option: Final expiry_date_str before OHLC fetch: {expiry_date_str}"
        logger.info(log_msg)
        print(log_msg)
        debug_logs.append(log_msg)
        
        if expiry_date_str:
            try:
                # CRITICAL: Log the exact expiry being passed to OHLC fetch
                log_msg = f"[EOD] {symbol} option: About to fetch OHLC with expiry_date_str='{expiry_date_str}' (type: {type(expiry_date_str)})"
                logger.info(log_msg)
                print(log_msg)
                debug_logs.append(log_msg)
                
                log_msg = f"[EOD] {symbol} option: Fetching historical OHLC from {entry_date.strftime('%Y-%m-%d')} to now..."
                logger.info(log_msg)
                print(log_msg)
                debug_logs.append(log_msg)
                hist_ohlc = fetch_option_historical_ohlc(
                    symbol=symbol,
                    strike=strike,
                    option_type=option_type,
                    expiry_date_str=expiry_date_str,
                    start_date=entry_date,
                    debug_logs=debug_logs
                )
                if hist_ohlc is None:
                    log_msg = f"[EOD] {symbol} option: Failed to fetch historical OHLC - will use current LTP only"
                    logger.warning(log_msg)
                    print(log_msg)
                    debug_logs.append(log_msg)
                else:
                    log_msg = f"[EOD] {symbol} option: Successfully fetched historical OHLC: max_high={hist_ohlc.get('max_high')}, min_low={hist_ohlc.get('min_low')}, days={len(hist_ohlc.get('data', []))}"
                    logger.info(log_msg)
                    print(log_msg)
                    debug_logs.append(log_msg)
            except Exception as e:
                log_msg = f"[EOD] {symbol} option: Error fetching historical OHLC: {e}"
                logger.error(log_msg, exc_info=True)
                print(log_msg)
                debug_logs.append(log_msg)
        else:
            log_msg = f"[EOD] {symbol} option: No expiry date available - cannot fetch historical OHLC"
            logger.warning(log_msg)
            print(log_msg)
            debug_logs.append(log_msg)
    
    # Determine current price, max_high, and min_low
    if hist_ohlc and hist_ohlc.get('current_price') is not None:
        current_price = hist_ohlc['current_price']
        max_high = hist_ohlc.get('max_high') or entry_price
        min_low = hist_ohlc.get('min_low') or entry_price
    elif ltp is not None:
        current_price = float(ltp)
        # Fallback to stored values if no historical data
        stored_max_high = float(trade.get('highest_price') or entry_price)
        stored_min_low = float(trade.get('lowest_price') or entry_price)
        max_high = max(current_price, stored_max_high, entry_price)
        min_low = min(current_price, stored_min_low, entry_price)
    else:
        current_price = entry_price
        stored_max_high = float(trade.get('highest_price') or entry_price)
        stored_min_low = float(trade.get('lowest_price') or entry_price)
        max_high = stored_max_high
        min_low = stored_min_low
    
    # Update stored max/min with historical data if available
    if hist_ohlc:
        max_high = hist_ohlc.get('max_high') or max_high
        min_low = hist_ohlc.get('min_low') or min_low
    
    days_held = (datetime.now() - entry_date).days
    
    # =====================================================================
    # TIME-SEQUENCED CHECK: Which hit first - SL or Target?
    # =====================================================================
    # Use historical OHLC data to check the sequence of events
    # This ensures we correctly identify which level was hit first
    
    if hist_ohlc and hist_ohlc.get('data') and len(hist_ohlc.get('data', [])) > 0:
        # We have time-series data - check sequence
        ohlc_data = hist_ohlc.get('data', [])
        
        # Sort by date (oldest first)
        sorted_data = sorted(ohlc_data, key=lambda x: x.get('date', ''))
        
        # Find first occurrence of SL or Target hit
        sl_hit_first = None
        target_hit_first = None
        entry_day = entry_date.strftime('%Y-%m-%d')
        
        for day_data in sorted_data:
            day_date_str = day_data.get('date', '')
            high = day_data.get('high', entry_price)
            low = day_data.get('low', entry_price)
            open_price = day_data.get('open', entry_price)
            close_price = day_data.get('close', entry_price)
            
            # Skip entry day if entry was placed after price movement
            # Edge case: If entry is on a day when price already moved, check entry time
            if day_date_str == entry_day:
                # On entry day, check if entry was placed before or after price movement
                # If entry price is same as day's open, entry was likely at market open
                # If entry price is higher than day's open, entry was likely after price moved up
                
                # Conservative check: If entry price >= day's open, assume entry was at or after open
                # If target was already hit on entry day (high >= target), and entry >= open,
                # then target was likely hit before entry (price moved up, then entry placed)
                if target > 0 and high >= target:
                    if entry_price >= open_price:
                        # Price likely moved to target before entry
                        # Don't count this as target hit (entry wasn't active yet)
                        log_msg = f"[EOD] {symbol} option: Target hit on entry day ({day_date_str}), but entry price ({entry_price}) >= open ({open_price}). Price likely moved to target before entry. Not counting as target hit."
                        logger.info(log_msg)
                        debug_logs.append(log_msg)
                        continue
                
                # Similar check for SL
                if stop_loss > 0 and low <= stop_loss:
                    if entry_price <= open_price:
                        # Price likely moved to SL before entry
                        log_msg = f"[EOD] {symbol} option: SL hit on entry day ({day_date_str}), but entry price ({entry_price}) <= open ({open_price}). Price likely moved to SL before entry. Not counting as SL hit."
                        logger.info(log_msg)
                        debug_logs.append(log_msg)
                        continue
            
            # Check if target was hit on this day (check high)
            if target > 0 and high >= target and target_hit_first is None:
                target_hit_first = day_date_str
            
            # Check if SL was hit on this day (check low)
            if stop_loss > 0 and low <= stop_loss and sl_hit_first is None:
                sl_hit_first = day_date_str
        
        # Determine which hit first
        if sl_hit_first and target_hit_first:
            # Both hit - check which came first
            if sl_hit_first < target_hit_first:
                # SL hit first
                log_msg = f"[EOD] {symbol} option: SL hit FIRST on {sl_hit_first}, target hit later on {target_hit_first}. Exiting at SL."
                logger.info(log_msg)
                print(log_msg)
                debug_logs.append(log_msg)
                
                gross_pnl = (stop_loss - entry_price) * qty
                net_pnl = gross_pnl - (brokerage_per_trade * 2)
                position_value = entry_price * qty
                pnl_pct = (net_pnl / position_value) * 100 if position_value > 0 else 0
                
                return {
                    'status': 'STOP_LOSS_HIT',
                    'exit_price': stop_loss,
                    'exit_reason': 'stop_loss',
                    'current_price': current_price,
                    'min_low': min_low,
                    'pnl_pct': pnl_pct,
                    'gross_pnl': gross_pnl,
                    'net_pnl': net_pnl,
                    'effective_qty': qty,
                    'lot_size': lot_size,
                    'days_held': days_held,
                    'sl_hit_date': sl_hit_first,
                    'target_hit_date': target_hit_first,
                    'note': 'SL hit before target'
                }
            else:
                # Target hit first
                log_msg = f"[EOD] {symbol} option: Target hit FIRST on {target_hit_first}, SL hit later on {sl_hit_first}. Exiting at target."
                logger.info(log_msg)
                print(log_msg)
                debug_logs.append(log_msg)
                
                gross_pnl = (target - entry_price) * qty
                net_pnl = gross_pnl - (brokerage_per_trade * 2)
                position_value = entry_price * qty
                pnl_pct = (net_pnl / position_value) * 100 if position_value > 0 else 0
                
                return {
                    'status': 'TARGET_HIT',
                    'exit_price': target,
                    'exit_reason': 'target',
                    'current_price': current_price,
                    'max_high': max_high,
                    'pnl_pct': pnl_pct,
                    'gross_pnl': gross_pnl,
                    'net_pnl': net_pnl,
                    'effective_qty': qty,
                    'lot_size': lot_size,
                    'days_held': days_held,
                    'sl_hit_date': sl_hit_first,
                    'target_hit_date': target_hit_first,
                    'note': 'Target hit before SL'
                }
        elif sl_hit_first:
            # Only SL hit
            log_msg = f"[EOD] {symbol} option: SL hit on {sl_hit_first}, target never hit."
            logger.info(log_msg)
            print(log_msg)
            debug_logs.append(log_msg)
            
            gross_pnl = (stop_loss - entry_price) * qty
            net_pnl = gross_pnl - (brokerage_per_trade * 2)
            position_value = entry_price * qty
            pnl_pct = (net_pnl / position_value) * 100 if position_value > 0 else 0
            
            return {
                'status': 'STOP_LOSS_HIT',
                'exit_price': stop_loss,
                'exit_reason': 'stop_loss',
                'current_price': current_price,
                'min_low': min_low,
                'pnl_pct': pnl_pct,
                'gross_pnl': gross_pnl,
                'net_pnl': net_pnl,
                'effective_qty': qty,
                'lot_size': lot_size,
                'days_held': days_held,
                'sl_hit_date': sl_hit_first
            }
        elif target_hit_first:
            # Only target hit
            log_msg = f"[EOD] {symbol} option: Target hit on {target_hit_first}, SL never hit."
            logger.info(log_msg)
            print(log_msg)
            debug_logs.append(log_msg)
            
            gross_pnl = (target - entry_price) * qty
            net_pnl = gross_pnl - (brokerage_per_trade * 2)
            position_value = entry_price * qty
            pnl_pct = (net_pnl / position_value) * 100 if position_value > 0 else 0
            
            return {
                'status': 'TARGET_HIT',
                'exit_price': target,
                'exit_reason': 'target',
                'current_price': current_price,
                'max_high': max_high,
                'pnl_pct': pnl_pct,
                'gross_pnl': gross_pnl,
                'net_pnl': net_pnl,
                'effective_qty': qty,
                'lot_size': lot_size,
                'days_held': days_held,
                'target_hit_date': target_hit_first
            }
    
    # Fallback to original logic if no time-series data available
    # (Check target first as it's more favorable)
    if target > 0 and max_high >= target:
        gross_pnl = (target - entry_price) * qty
        net_pnl = gross_pnl - (brokerage_per_trade * 2)
        position_value = entry_price * qty
        pnl_pct = (net_pnl / position_value) * 100 if position_value > 0 else 0
        return {
            'status': 'TARGET_HIT',
            'exit_price': target,
            'exit_reason': 'target',
            'current_price': current_price,
            'max_high': max_high,
            'pnl_pct': pnl_pct,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'effective_qty': qty,
            'lot_size': lot_size,
            'days_held': days_held
        }
    
    if stop_loss > 0 and min_low <= stop_loss:
        gross_pnl = (stop_loss - entry_price) * qty
        net_pnl = gross_pnl - (brokerage_per_trade * 2)
        position_value = entry_price * qty
        pnl_pct = (net_pnl / position_value) * 100 if position_value > 0 else 0
        return {
            'status': 'STOP_LOSS_HIT',
            'exit_price': stop_loss,
            'exit_reason': 'stop_loss',
            'current_price': current_price,
            'min_low': min_low,
            'pnl_pct': pnl_pct,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'effective_qty': qty,
            'lot_size': lot_size,
            'days_held': days_held
        }
    
    unrealized_pnl = (current_price - entry_price) * qty
    # Calculate percentage based on position value (capital invested), not just price change
    position_value = entry_price * qty
    pnl_pct = (unrealized_pnl / position_value) * 100 if position_value > 0 else 0
    return {
        'status': 'OPEN',
        'current_price': current_price,
        'max_high': max_high,
        'min_low': min_low,
        'pnl_pct': pnl_pct,
        'unrealized_pnl': unrealized_pnl,
        'effective_qty': qty,
        'lot_size': lot_size,
        'days_held': days_held,
        'historical_data_used': hist_ohlc is not None
    }


@router.get("/check", summary="Run EOD check on all open trades")
async def run_eod_check(
    current_user: User = Depends(get_current_user),
    include_time_stop: bool = False,
    time_stop_days: int = 120
):
    """
    Check all open trades for SL/Target hits
    **NEW: Also checks trade health (momentum, volume, trend)**
    Returns detailed status for each trade
    """
    try:
        # Load user-specific trades
        all_trades = load_trades(current_user.id)
        
        # Filter open trades
        open_trades = [t for t in all_trades if t['status'] == 'open']
        
        if not open_trades:
            return JSONResponse({
                'success': True,
                'message': 'No open trades to check',
                'trades_checked': 0,
                'trades_to_close': [],
                'trades_still_open': [],
                'health_warnings': [],
                'debug_logs': ['[EOD] No open trades to check']
            })
        
        # Initialize health monitor
        health_monitor = None
        if HEALTH_CHECK_ENABLED:
            health_monitor = TradeHealthMonitor()
        
        trades_to_close = []
        trades_still_open = []
        health_warnings = []  # Tracks with WARNING or CRITICAL health
        debug_logs = []  # Collect debug logs for response
        
        # Check each trade
        for trade in open_trades:
            symbol = trade['symbol']
            entry_date = datetime.strptime(trade['entry_date'], '%Y-%m-%d %H:%M:%S')
            entry_date_str = entry_date.strftime('%Y-%m-%d')
            
            if trade.get('instrument_type') == 'option':
                entry_price = float(trade.get('entry_price', 0))
                log_msg = f"[EOD] Processing option trade: {symbol}, entry_date={entry_date_str}, entry_price={entry_price}"
                logger.info(log_msg)
                print(log_msg)
                debug_logs.append(log_msg)
                
                # Get stored max_high and min_low from trade (persisted across checks)
                # Initialize to entry_price if not set (first time check)
                if 'highest_price' not in trade or trade.get('highest_price') is None:
                    trade['highest_price'] = entry_price
                if 'lowest_price' not in trade or trade.get('lowest_price') is None:
                    trade['lowest_price'] = entry_price
                
                stored_max_high = float(trade.get('highest_price', entry_price))
                stored_min_low = float(trade.get('lowest_price', entry_price))
                
                status = option_status_from_ltp(trade, debug_logs=debug_logs)
                cp = float(status.get('current_price') or entry_price)
                max_h = float(status.get('max_high') or entry_price)
                min_l = float(status.get('min_low') or entry_price)
                hist_data_used = status.get('historical_data_used', False)
                lot_size_used = status.get('lot_size', 1)
                qty_used = status.get('effective_qty', 1)
                
                # Update trade with new max/min (persist for next check)
                trade['highest_price'] = max_h
                trade['lowest_price'] = min_l
                
                log_msg = f"[EOD] {symbol} option: entry={entry_price}, current={cp}, max_high={max_h}, min_low={min_l}, historical_data_used={hist_data_used}, lot_size={lot_size_used}, qty={qty_used}"
                logger.info(log_msg)
                print(log_msg)
                debug_logs.append(log_msg)
                
                # Add P&L calculation details if target/SL hit
                if status.get('status') in ['TARGET_HIT', 'STOP_LOSS_HIT']:
                    gross_pnl = status.get('gross_pnl', 0)
                    net_pnl = status.get('net_pnl', 0)
                    exit_price = status.get('exit_price', 0)
                    log_msg = f"[EOD] {symbol} P&L: exit_price={exit_price}, gross_pnl={gross_pnl}, net_pnl={net_pnl}, lot_size={lot_size_used}, qty={qty_used}"
                    logger.info(log_msg)
                    print(log_msg)
                    debug_logs.append(log_msg)
                
                log_msg = f"[EOD] {symbol} option status: {status.get('status')}, target={trade.get('target')}, stop_loss={trade.get('stop_loss')}, range_since_entry={min_l} to {max_h}"
                logger.info(log_msg)
                print(log_msg)
                debug_logs.append(log_msg)
                
                ohlc = {
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'entry_date': entry_date_str,
                    'open': cp, 'high': max_h, 'low': min_l, 'close': cp,
                    'volume': 0
                }
            else:
                log_msg = f"[EOD] Processing equity trade: {symbol}, entry_date={entry_date_str}, entry_price={trade.get('entry_price')}"
                logger.info(log_msg)
                print(log_msg)
                debug_logs.append(log_msg)
                
                hist_data = fetch_historical_ohlc(symbol, entry_date_str)
                if hist_data is None or hist_data.empty:
                    log_msg = f"[EOD] Could not fetch historical data for {symbol}, skipping"
                    logger.warning(log_msg)
                    print(log_msg)
                    continue
                
                latest = hist_data.iloc[-1]
                latest_date = hist_data.index[-1].strftime('%Y-%m-%d')
                first_date = hist_data.index[0].strftime('%Y-%m-%d')
                max_high = float(hist_data['High'].max())
                min_low = float(hist_data['Low'].min())
                current_price = float(latest['Close'])
                
                log_msg = f"[EOD] {symbol} OHLC summary: entry_date={entry_date_str}, data_range={first_date} to {latest_date}, max_high={max_high}, min_low={min_low}, current={current_price}"
                logger.info(log_msg)
                print(log_msg)
                debug_logs.append(log_msg)
                
                ohlc = {
                    'date': latest_date,
                    'entry_date': entry_date_str,
                    'first_date': first_date,
                    'open': float(latest['Open']),
                    'high': max_high,
                    'low': min_low,
                    'close': current_price,
                    'volume': int(latest['Volume'])
                }
                
                status = check_trade_status(
                    trade,
                    hist_data,
                    include_time_stop=include_time_stop,
                    time_stop_days=time_stop_days
                )
                
                log_msg = f"[EOD] {symbol} status: {status.get('status')}, target={trade.get('target')}, stop_loss={trade.get('stop_loss')}, max_high={max_high}, min_low={min_low}"
                logger.info(log_msg)
                print(log_msg)
                debug_logs.append(log_msg)
            
            # **NEW: Check trade health if still open**
            health_info = None
            if health_monitor and status['status'] == 'OPEN':
                try:
                    health_info = health_monitor.check_trade_health(trade)
                except Exception as e:
                    logger.warning(f"Health check failed for {symbol}: {e}")
            
            # Update trade with new max/min prices for options (persist across checks)
            if trade.get('instrument_type') == 'option':
                entry_price = float(trade.get('entry_price', 0))
                # Initialize if not exists
                if 'highest_price' not in trade or trade.get('highest_price') is None:
                    trade['highest_price'] = entry_price
                if 'lowest_price' not in trade or trade.get('lowest_price') is None:
                    trade['lowest_price'] = entry_price
                
                # Update with new max/min
                stored_max = float(trade.get('highest_price', entry_price))
                stored_min = float(trade.get('lowest_price', entry_price))
                trade['highest_price'] = max(max_h, stored_max, entry_price)
                trade['lowest_price'] = min(min_l, stored_min, entry_price)
                
                # Save updated trade data
                from webapp.api.paper_trading import save_trades
                all_trades_updated = load_trades(current_user.id)
                for i, t in enumerate(all_trades_updated):
                    if t['id'] == trade['id']:
                        all_trades_updated[i] = trade
                        break
                save_trades(current_user.id, all_trades_updated)
            
            # Add OHLC, status, and health to trade
            trade_result = {
                **trade,
                'ohlc': ohlc,
                'check_status': status,
                'health_info': health_info  # **NEW**
            }
            
            if status['status'] in ['TARGET_HIT', 'STOP_LOSS_HIT', 'TIME_STOP']:
                trades_to_close.append(trade_result)
            else:
                trades_still_open.append(trade_result)
                
                # **NEW: Track health warnings**
                if health_info and health_info.get('status') in ['WARNING', 'CRITICAL']:
                    health_warnings.append(trade_result)
        
        # Log this check
        log_eod_check(trades_to_close, trades_still_open)
        
        # Add summary to debug logs
        if not debug_logs:
            debug_logs.append(f"[EOD] No debug logs generated (possible issue)")
        debug_logs.append(f"[EOD] Summary: checked={len(open_trades)}, to_close={len(trades_to_close)}, still_open={len(trades_still_open)}")
        
        return JSONResponse({
            'success': True,
            'message': f'Checked {len(open_trades)} open trades',
            'timestamp': datetime.now().isoformat(),
            'trades_checked': len(open_trades),
            'trades_to_close': trades_to_close,
            'trades_still_open': trades_still_open,
            'health_warnings': health_warnings,  # **NEW**
            'debug_logs': debug_logs,  # Debug logs for troubleshooting
            'summary': {
                'total_checked': len(open_trades),
                'need_closing': len(trades_to_close),
                'still_open': len(trades_still_open),
                'targets_hit': len([t for t in trades_to_close if t['check_status']['status'] == 'TARGET_HIT']),
                'stop_losses_hit': len([t for t in trades_to_close if t['check_status']['status'] == 'STOP_LOSS_HIT']),
                'time_stops': len([t for t in trades_to_close if t['check_status']['status'] == 'TIME_STOP']),
                'health_warnings': len(health_warnings),  # **NEW**
                'health_critical': len([t for t in health_warnings if t.get('health_info', {}).get('status') == 'CRITICAL'])  # **NEW**
            }
        })
    
    except Exception as e:
        logger.error(f"Error running EOD check: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", summary="Get EOD check history")
async def get_eod_history(limit: int = 100):
    """
    Get historical EOD check logs
    """
    try:
        if not EOD_LOG_FILE.exists():
            return JSONResponse({
                'success': True,
                'history': [],
                'message': 'No history available yet'
            })
        
        # Read log file
        history = []
        with open(EOD_LOG_FILE, 'r') as f:
            lines = f.readlines()
            
            # Skip header
            if len(lines) > 1:
                # Get last N lines
                for line in lines[-limit:]:
                    parts = line.strip().split(',')
                    if len(parts) >= 12:
                        history.append({
                            'date': parts[0],
                            'time': parts[1],
                            'symbol': parts[2],
                            'entry_price': float(parts[3]),
                            'current_price': float(parts[4]),
                            'high': float(parts[5]),
                            'low': float(parts[6]),
                            'stop_loss': float(parts[7]),
                            'target': float(parts[8]),
                            'status': parts[9],
                            'days_held': int(parts[10]),
                            'pnl_pct': float(parts[11])
                        })
        
        return JSONResponse({
            'success': True,
            'history': list(reversed(history)),  # Most recent first
            'count': len(history)
        })
    
    except Exception as e:
        logger.error(f"Error reading EOD history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def log_eod_check(trades_to_close, trades_still_open):
    """Log EOD check to CSV"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create log file with headers if it doesn't exist
        if not EOD_LOG_FILE.exists():
            with open(EOD_LOG_FILE, 'w') as f:
                f.write("date,time,symbol,entry_price,current_price,high,low,stop_loss,target,status,days_held,pnl_pct\n")
        
        # Append checks
        with open(EOD_LOG_FILE, 'a') as f:
            timestamp = datetime.now()
            date_str = timestamp.strftime('%Y-%m-%d')
            time_str = timestamp.strftime('%H:%M:%S')

            def fmt_num(val, nd=2):
                try:
                    return f"{float(val):.{nd}f}"
                except Exception:
                    return ""
            
            # Log trades to close
            for trade in trades_to_close:
                status = trade['check_status']
                ohlc = trade['ohlc']
                f.write(f"{date_str},{time_str},")
                f.write(f"{trade['symbol']},")
                f.write(f"{fmt_num(trade.get('entry_price'))},")
                f.write(f"{fmt_num(ohlc.get('close'))},")
                f.write(f"{fmt_num(ohlc.get('high'))},")
                f.write(f"{fmt_num(ohlc.get('low'))},")
                f.write(f"{fmt_num(trade.get('stop_loss'))},")
                f.write(f"{fmt_num(trade.get('target'))},")
                f.write(f"{status['status']},")
                f.write(f"{int(status.get('days_held', 0))},")
                f.write(f"{fmt_num(status.get('pnl_pct'))}\n")
            
            # Log open trades
            for trade in trades_still_open:
                status = trade['check_status']
                ohlc = trade['ohlc']
                f.write(f"{date_str},{time_str},")
                f.write(f"{trade['symbol']},")
                f.write(f"{fmt_num(trade.get('entry_price'))},")
                f.write(f"{fmt_num(ohlc.get('close'))},")
                f.write(f"{fmt_num(ohlc.get('high'))},")
                f.write(f"{fmt_num(ohlc.get('low'))},")
                f.write(f"{fmt_num(trade.get('stop_loss'))},")
                f.write(f"{fmt_num(trade.get('target'))},")
                f.write(f"OPEN,")
                f.write(f"{int(status.get('days_held', 0))},")
                f.write(f"{fmt_num(status.get('pnl_pct'))}\n")
    
    except Exception as e:
        logger.error(f"Error logging EOD check: {e}")


@router.post("/auto-close", summary="Auto-close trades that hit SL/Target")
async def auto_close_trades(current_user: User = Depends(get_current_user), auth_token: str = None):
    """
    Automatically close trades that hit their SL or Target
    For live trades: Places SELL orders on Zerodha (requires auth_token)
    For paper trades: Closes in webapp database
    """
    try:
        # Run EOD check first (passing current_user)
        check_result = await run_eod_check(current_user)
        
        if not check_result:
            raise HTTPException(status_code=500, detail="Failed to run EOD check")
        
        result_data = json.loads(check_result.body.decode())
        
        if not result_data['success']:
            raise HTTPException(status_code=500, detail="EOD check failed")
        
        trades_to_close = result_data['trades_to_close']
        
        if not trades_to_close:
            return JSONResponse({
                'success': True,
                'message': 'No trades need closing',
                'closed_count': 0,
                'live_closed': 0,
                'paper_closed': 0
            })
        
        # Separate live and paper trades
        live_trades = [t for t in trades_to_close if t.get('is_live', False)]
        paper_trades = [t for t in trades_to_close if not t.get('is_live', False)]
        
        closed_count = 0
        live_closed_count = 0
        paper_closed_count = 0
        closed_trades = []
        failed_trades = []
        
        # Handle live trades (place SELL orders on Zerodha)
        if live_trades:
            if not auth_token:
                logger.warning("Live trades found but no auth token provided")
                for trade in live_trades:
                    failed_trades.append({
                        'symbol': trade['symbol'],
                        'reason': 'No auth token - cannot place Zerodha order'
                    })
            else:
                # Import order placement function
                import requests
                
                for trade_result in live_trades:
                    trade = trade_result
                    status = trade['check_status']
                    
                    try:
                        # Place SELL order on Zerodha
                        symbol = trade['symbol'].replace('.NS', '')
                        
                        order_data = {
                            'symbol': symbol,
                            'exchange': 'NSE',
                            'transaction_type': 'SELL',
                            'quantity': trade['shares'],
                            'order_type': 'MARKET',
                            'product': 'CNC',
                            'validity': 'DAY',
                            'notes': f"EOD Auto-exit: {status['exit_reason']}"
                        }
                        
                        # Call orders API
                        response = requests.post(
                            'http://localhost:8000/api/orders/place',
                            json=order_data,
                            headers={'Authorization': f'Bearer {auth_token}'},
                            timeout=15
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            if result.get('success'):
                                # Also close in webapp for tracking
                                from webapp.api.paper_trading import close_trade
                                await close_trade(
                                    trade['id'],
                                    exit_price=status['exit_price'],
                                    exit_reason=status['exit_reason'],
                                    notes=f"Zerodha Order: {result.get('zerodha_order_id')}. Auto-closed by EOD Monitor"
                                )
                                
                                closed_count += 1
                                live_closed_count += 1
                                closed_trades.append({
                                    'type': 'LIVE',
                                    'symbol': trade['symbol'],
                                    'exit_price': status['exit_price'],
                                    'pnl': status['net_pnl'],
                                    'reason': status['exit_reason'],
                                    'zerodha_order_id': result.get('zerodha_order_id')
                                })
                            else:
                                failed_trades.append({
                                    'symbol': trade['symbol'],
                                    'reason': result.get('message', 'Unknown error')
                                })
                        else:
                            failed_trades.append({
                                'symbol': trade['symbol'],
                                'reason': f'HTTP {response.status_code}'
                            })
                    
                    except Exception as e:
                        logger.error(f"Error closing live trade {trade['symbol']}: {e}")
                        failed_trades.append({
                            'symbol': trade['symbol'],
                            'reason': str(e)
                        })
        
        # Handle paper trades (close in webapp only)
        for trade_result in paper_trades:
            trade = trade_result
            status = trade['check_status']
            
            try:
                # Call the close endpoint from paper_trading
                from webapp.api.paper_trading import close_trade
                
                result = await close_trade(
                    trade['id'],
                    exit_price=status['exit_price'],
                    exit_reason=status['exit_reason'],
                    notes=f"Auto-closed by EOD Monitor: {status['status']}"
                )
                
                if result.status_code == 200:
                    closed_count += 1
                    paper_closed_count += 1
                    closed_trades.append({
                        'type': 'PAPER',
                        'symbol': trade['symbol'],
                        'exit_price': status['exit_price'],
                        'pnl': status['net_pnl'],
                        'reason': status['exit_reason']
                    })
                else:
                    failed_trades.append({
                        'symbol': trade['symbol'],
                        'reason': 'Failed to close in webapp'
                    })
            
            except Exception as e:
                logger.error(f"Error auto-closing {trade['symbol']}: {e}")
                failed_trades.append({
                    'symbol': trade['symbol'],
                    'reason': str(e)
                })
        
        return JSONResponse({
            'success': True,
            'message': f'Auto-closed {closed_count} trades (Live: {live_closed_count}, Paper: {paper_closed_count})',
            'closed_count': closed_count,
            'live_closed': live_closed_count,
            'paper_closed': paper_closed_count,
            'closed_trades': closed_trades,
            'failed_trades': failed_trades
        })
    
    except Exception as e:
        logger.error(f"Error in auto-close: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

