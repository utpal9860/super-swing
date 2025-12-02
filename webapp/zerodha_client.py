"""
Zerodha Kite Connect API Client
Handles OAuth, token management, and API interactions
"""
from kiteconnect import KiteConnect
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class ZerodhaClient:
    """
    Wrapper for Zerodha Kite Connect API
    Handles authentication, token management, and API calls
    """
    
    def __init__(self, api_key: str, access_token: Optional[str] = None):
        """
        Initialize Zerodha client
        
        Args:
            api_key: Zerodha API key
            access_token: Optional access token (if already authenticated)
        """
        self.api_key = api_key
        self.kite = KiteConnect(api_key=api_key)
        
        if access_token:
            self.kite.set_access_token(access_token)
            self.access_token = access_token
        else:
            self.access_token = None
    
    def get_login_url(self) -> str:
        """
        Get the Zerodha login URL for OAuth flow
        
        Returns:
            Login URL string
        """
        return self.kite.login_url()
    
    def generate_session(self, request_token: str, api_secret: str) -> Dict[str, Any]:
        """
        Generate access token from request token (OAuth callback)
        
        Args:
            request_token: Request token from OAuth callback
            api_secret: Zerodha API secret
            
        Returns:
            Session data including access_token, user details
        """
        try:
            data = self.kite.generate_session(request_token, api_secret=api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            
            logger.info(f"Session generated successfully for user: {data.get('user_id')}")
            return data
        except Exception as e:
            logger.error(f"Session generation failed: {e}")
            raise
    
    def invalidate_session(self) -> bool:
        """
        Invalidate the current access token
        
        Returns:
            True if successful
        """
        try:
            self.kite.invalidate_access_token(self.access_token)
            self.access_token = None
            logger.info("Session invalidated successfully")
            return True
        except Exception as e:
            logger.error(f"Session invalidation failed: {e}")
            return False
    
    # =========================================================================
    # ORDER PLACEMENT
    # =========================================================================
    
    def place_order(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        product: str = "CNC",
        validity: str = "DAY",
        variety: str = "regular"
    ) -> Dict[str, Any]:
        """
        Place an order on Zerodha
        
        Args:
            symbol: Trading symbol (e.g., "RELIANCE")
            exchange: Exchange (NSE/BSE)
            transaction_type: BUY or SELL
            quantity: Number of shares
            order_type: MARKET, LIMIT, SL, SL-M
            price: Price for limit orders
            trigger_price: Trigger price for SL orders
            product: CNC/MIS/NRML
            validity: DAY/IOC
            variety: regular/amo/co/iceberg
            
        Returns:
            Order response dict with order_id
        """
        try:
            order_id = self.kite.place_order(
                variety=variety,
                exchange=exchange,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                product=product,
                order_type=order_type,
                price=price,
                trigger_price=trigger_price,
                validity=validity
            )
            
            logger.info(f"Order placed successfully: {order_id}")
            return {"order_id": order_id, "status": "success"}
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            raise
    
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        order_type: Optional[str] = None,
        validity: Optional[str] = None,
        variety: str = "regular"
    ) -> Dict[str, Any]:
        """
        Modify an existing order
        
        Args:
            order_id: Order ID to modify
            quantity: New quantity
            price: New price
            trigger_price: New trigger price
            order_type: New order type
            validity: New validity
            variety: Order variety
            
        Returns:
            Modification response dict
        """
        try:
            result = self.kite.modify_order(
                variety=variety,
                order_id=order_id,
                quantity=quantity,
                price=price,
                trigger_price=trigger_price,
                order_type=order_type,
                validity=validity
            )
            
            logger.info(f"Order modified successfully: {order_id}")
            return {"order_id": order_id, "status": "success"}
        except Exception as e:
            logger.error(f"Order modification failed: {e}")
            raise
    
    def cancel_order(self, order_id: str, variety: str = "regular") -> Dict[str, Any]:
        """
        Cancel an order
        
        Args:
            order_id: Order ID to cancel
            variety: Order variety
            
        Returns:
            Cancellation response dict
        """
        try:
            result = self.kite.cancel_order(variety=variety, order_id=order_id)
            logger.info(f"Order cancelled successfully: {order_id}")
            return {"order_id": order_id, "status": "cancelled"}
        except Exception as e:
            logger.error(f"Order cancellation failed: {e}")
            raise
    
    # =========================================================================
    # PORTFOLIO & POSITIONS
    # =========================================================================
    
    def get_holdings(self) -> List[Dict[str, Any]]:
        """
        Get user's portfolio holdings
        
        Returns:
            List of holdings with details
        """
        try:
            holdings = self.kite.holdings()
            logger.info(f"Fetched {len(holdings)} holdings")
            return holdings
        except Exception as e:
            logger.error(f"Failed to fetch holdings: {e}")
            raise
    
    def get_positions(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get user's current positions
        
        Returns:
            Dict with 'net' and 'day' positions
        """
        try:
            positions = self.kite.positions()
            logger.info(f"Fetched positions: {len(positions.get('net', []))} net, {len(positions.get('day', []))} day")
            return positions
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            raise
    
    def get_margins(self, segment: str = "equity") -> Dict[str, Any]:
        """
        Get account margins/balance
        
        Args:
            segment: equity/commodity
            
        Returns:
            Margin details dict
        """
        try:
            margins = self.kite.margins(segment)
            logger.info(f"Fetched margins for {segment}")
            return margins
        except Exception as e:
            logger.error(f"Failed to fetch margins: {e}")
            raise
    
    # =========================================================================
    # ORDER HISTORY
    # =========================================================================
    
    def get_orders(self) -> List[Dict[str, Any]]:
        """
        Get all orders for the day
        
        Returns:
            List of orders
        """
        try:
            orders = self.kite.orders()
            logger.info(f"Fetched {len(orders)} orders")
            return orders
        except Exception as e:
            logger.error(f"Failed to fetch orders: {e}")
            raise
    
    def get_order_history(self, order_id: str) -> List[Dict[str, Any]]:
        """
        Get history of a specific order
        
        Args:
            order_id: Order ID
            
        Returns:
            List of order status updates
        """
        try:
            history = self.kite.order_history(order_id)
            logger.info(f"Fetched history for order: {order_id}")
            return history
        except Exception as e:
            logger.error(f"Failed to fetch order history: {e}")
            raise
    
    def get_trades(self) -> List[Dict[str, Any]]:
        """
        Get all trades for the day
        
        Returns:
            List of executed trades
        """
        try:
            trades = self.kite.trades()
            logger.info(f"Fetched {len(trades)} trades")
            return trades
        except Exception as e:
            logger.error(f"Failed to fetch trades: {e}")
            raise
    
    # =========================================================================
    # MARKET DATA
    # =========================================================================
    
    def get_quote(self, instruments: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get real-time quotes for instruments
        
        Args:
            instruments: List of instrument tokens or symbols (e.g., ["NSE:RELIANCE"])
            
        Returns:
            Dict of quotes keyed by instrument
        """
        try:
            quotes = self.kite.quote(instruments)
            logger.info(f"Fetched quotes for {len(instruments)} instruments")
            return quotes
        except Exception as e:
            logger.error(f"Failed to fetch quotes: {e}")
            raise
    
    def get_ltp(self, instruments: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Get last traded price for instruments
        
        Args:
            instruments: List of instrument tokens or symbols
            
        Returns:
            Dict of LTPs keyed by instrument
        """
        try:
            ltps = self.kite.ltp(instruments)
            logger.info(f"Fetched LTP for {len(instruments)} instruments")
            return ltps
        except Exception as e:
            logger.error(f"Failed to fetch LTP: {e}")
            raise
    
    def get_instruments(self, exchange: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of all tradeable instruments
        
        Args:
            exchange: Optional exchange filter (NSE/BSE/NFO/etc.)
            
        Returns:
            List of instrument details
        """
        try:
            instruments = self.kite.instruments(exchange)
            logger.info(f"Fetched {len(instruments)} instruments for {exchange or 'all exchanges'}")
            return instruments
        except Exception as e:
            logger.error(f"Failed to fetch instruments: {e}")
            raise
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_profile(self) -> Dict[str, Any]:
        """
        Get user profile details
        
        Returns:
            User profile dict
        """
        try:
            profile = self.kite.profile()
            logger.info(f"Fetched profile for user: {profile.get('user_id')}")
            return profile
        except Exception as e:
            logger.error(f"Failed to fetch profile: {e}")
            raise
    
    def is_connected(self) -> bool:
        """
        Check if client is authenticated and connected
        
        Returns:
            True if connected, False otherwise
        """
        if not self.access_token:
            return False
        
        try:
            # Try to fetch profile as a connectivity check
            self.get_profile()
            return True
        except:
            return False


# Singleton instance management
_zerodha_clients: Dict[str, ZerodhaClient] = {}


def get_zerodha_client(user_id: str, api_key: str, access_token: Optional[str] = None) -> ZerodhaClient:
    """
    Get or create a Zerodha client for a user
    
    Args:
        user_id: User identifier
        api_key: Zerodha API key
        access_token: Optional access token
        
    Returns:
        ZerodhaClient instance
    """
    if user_id not in _zerodha_clients or access_token:
        _zerodha_clients[user_id] = ZerodhaClient(api_key, access_token)
    
    return _zerodha_clients[user_id]


def remove_zerodha_client(user_id: str) -> None:
    """
    Remove a user's Zerodha client from cache
    
    Args:
        user_id: User identifier
    """
    if user_id in _zerodha_clients:
        del _zerodha_clients[user_id]

