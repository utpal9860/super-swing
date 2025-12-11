"""
Order Management Module
Handles order validation, placement, and tracking with risk management
"""
from typing import Dict, Optional, Tuple, Any, List
from datetime import datetime
import logging
from enum import Enum

logger = logging.getLogger(__name__)

# BSE index symbols (for BFO exchange)
BSE_INDICES = {'SENSEX', 'BANKEX', 'SENSEX50'}


class OrderType(str, Enum):
    """Order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"  # Stop Loss
    SL_M = "SL-M"  # Stop Loss Market


class TransactionType(str, Enum):
    """Transaction types"""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    """Order status"""
    PENDING = "PENDING"
    PLACED = "PLACED"
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ProductType(str, Enum):
    """Product types"""
    CNC = "CNC"  # Cash and Carry (delivery)
    MIS = "MIS"  # Margin Intraday Square off
    NRML = "NRML"  # Normal (carry forward)


def is_option_symbol(symbol: str) -> bool:
    """
    Check if symbol is an option (ends with CE/PE)
    
    Args:
        symbol: Trading symbol
        
    Returns:
        True if option, False otherwise
    """
    symbol_upper = symbol.upper().replace(".NS", "").strip()
    return symbol_upper.endswith("CE") or symbol_upper.endswith("PE")


def get_option_exchange(symbol: str) -> str:
    """
    Get correct exchange for option (NFO/BFO)
    
    Args:
        symbol: Option symbol (e.g., "SENSEX11DEC84500CE")
        
    Returns:
        "BFO" for BSE indices, "NFO" for NSE indices/stocks
    """
    symbol_upper = symbol.upper().replace(".NS", "")
    
    # Check if it's a BSE index option
    for bse_index in BSE_INDICES:
        if symbol_upper.startswith(bse_index):
            return "BFO"
    
    # Default to NFO for NSE options
    return "NFO"


def get_stock_exchange(symbol: str, default_exchange: str = "NSE") -> str:
    """
    Get exchange for stock (NSE/BSE)
    
    Args:
        symbol: Stock symbol
        default_exchange: Default exchange if not specified
        
    Returns:
        Exchange name (NSE or BSE)
    """
    # For now, use default or check symbol prefix
    # Can be enhanced to check actual exchange from instrument list
    return default_exchange.upper()


def get_product_type_for_option() -> str:
    """
    Get product type for options (NRML for delivery)
    
    Returns:
        "NRML" - Normal product allows holding until expiry
    """
    return "NRML"


def get_product_type_for_stock() -> str:
    """
    Get product type for stocks (CNC for delivery)
    
    Returns:
        "CNC" - Cash and Carry for delivery
    """
    return "CNC"


def calculate_option_quantity(shares: int, lot_size: int) -> int:
    """
    Calculate order quantity for options (in lots)
    
    Args:
        shares: Number of shares/lots from trade
        lot_size: Lot size for the option
        
    Returns:
        Total quantity (shares × lot_size)
    """
    return shares * lot_size


def calculate_price_movement_pct(signal_price: float, current_price: float) -> float:
    """
    Calculate price movement percentage
    
    Args:
        signal_price: Original signal/requested price
        current_price: Current market price
        
    Returns:
        Price movement percentage (positive = moved up, negative = moved down)
    """
    if signal_price == 0:
        return 0.0
    return ((current_price - signal_price) / signal_price) * 100


def determine_order_strategy(
    signal_price: float,
    current_price: float,
    order_type: str = "LIMIT",
    price_tolerance_pct: float = 2.0,
    max_price_movement_pct: float = 5.0,
    target_price: Optional[float] = None,
    today_high: Optional[float] = None
) -> Dict[str, Any]:
    """
    Determine optimal order strategy based on price movement
    
    Pro Trader Strategy:
    - If price moved <2%: Use original price (LIMIT) - wait for pullback
    - If price moved 2-5%: Use adaptive price (LIMIT at midpoint or current)
    - If price moved >5%: Reject order (too risky)
    - If price already moved favorably (towards target) then came back: Reject (momentum lost)
    
    Args:
        signal_price: Original signal/requested price
        current_price: Current market price
        order_type: Requested order type
        price_tolerance_pct: Acceptable price movement (default 2%)
        max_price_movement_pct: Maximum acceptable movement (default 5%)
        target_price: Target price (to detect if price already moved favorably)
        today_high: Today's high price (to detect if price already moved up significantly)
        
    Returns:
        Dict with:
        - final_order_type: MARKET or LIMIT
        - final_price: Price to use (None for MARKET)
        - price_movement_pct: How much price moved
        - strategy: Strategy used
        - warning: Warning message if any
        - should_reject: True if order should be rejected
    """
    price_movement_pct = calculate_price_movement_pct(signal_price, current_price)
    abs_movement = abs(price_movement_pct)
    
    result = {
        "price_movement_pct": price_movement_pct,
        "signal_price": signal_price,
        "current_price": current_price,
        "should_reject": False,
        "warning": None,
        "strategy": None
    }
    
    # CRITICAL: Check if price already moved favorably (towards target) then came back
    # This prevents entering on falling price after momentum is lost
    if target_price and today_high:
        # Calculate how much price moved towards target from entry
        target_movement_pct = calculate_price_movement_pct(signal_price, target_price)
        high_movement_pct = calculate_price_movement_pct(signal_price, today_high)
        
        # If price moved significantly towards target (e.g., >30% of target movement)
        # and now it's back near entry, reject (momentum is lost)
        if target_movement_pct > 0:  # Target is above entry (BUY scenario)
            # If price reached >30% of the way to target, then came back
            favorable_movement_threshold = target_movement_pct * 0.3  # 30% of target movement
            
            if high_movement_pct > favorable_movement_threshold:
                # Price already moved favorably, check if it came back
                current_movement_from_high = calculate_price_movement_pct(today_high, current_price)
                
                # If price is now back near entry (within 2% of entry) after moving up
                if abs(price_movement_pct) < 2.0 and current_movement_from_high < -3.0:
                    result["should_reject"] = True
                    result["final_order_type"] = order_type
                    result["final_price"] = signal_price
                    result["strategy"] = "reject_momentum_lost"
                    result["warning"] = (
                        f"Price already moved up {high_movement_pct:+.2f}% (reached ₹{today_high:.2f}) "
                        f"towards target ₹{target_price:.2f}, but now back to ₹{current_price:.2f} "
                        f"(near entry ₹{signal_price:.2f}). Momentum lost - order rejected to prevent "
                        f"entering on falling price."
                    )
                    return result
    
    # Price moved too much - reject order
    if abs_movement > max_price_movement_pct:
        result["should_reject"] = True
        result["final_order_type"] = order_type
        result["final_price"] = signal_price
        result["strategy"] = "reject_high_movement"
        result["warning"] = (
            f"Price moved {price_movement_pct:+.2f}% (signal: ₹{signal_price:.2f}, "
            f"current: ₹{current_price:.2f}). "
            f"Movement exceeds maximum tolerance ({max_price_movement_pct}%). "
            f"Order rejected to prevent high-risk entry."
        )
        return result
    
    # Price moved moderately (2-5%) - use adaptive strategy
    if abs_movement > price_tolerance_pct:
        # Use midpoint between signal and current (compromise)
        midpoint_price = (signal_price + current_price) / 2
        
        # For BUY: If price moved up, use midpoint. If moved down, use current (better price)
        if price_movement_pct > 0:  # Price moved up
            final_price = midpoint_price
            strategy = "adaptive_midpoint"
            warning = (
                f"Price moved up {price_movement_pct:+.2f}% (signal: ₹{signal_price:.2f}, "
                f"current: ₹{current_price:.2f}). "
                f"Using adaptive LIMIT at ₹{final_price:.2f} (midpoint) to balance entry and risk."
            )
        else:  # Price moved down (better for BUY)
            final_price = current_price  # Use current (better price)
            strategy = "adaptive_current"
            warning = (
                f"Price moved down {abs_movement:.2f}% (signal: ₹{signal_price:.2f}, "
                f"current: ₹{current_price:.2f}). "
                f"Using LIMIT at current price ₹{final_price:.2f} (better entry)."
            )
        
        result["final_order_type"] = "LIMIT"
        result["final_price"] = final_price
        result["strategy"] = strategy
        result["warning"] = warning
        return result
    
    # Price moved minimally (<2%) - use original price (wait for pullback)
    result["final_order_type"] = "LIMIT"
    result["final_price"] = signal_price
    result["strategy"] = "original_price"
    if abs_movement > 0.1:  # Only warn if there's meaningful movement
        result["warning"] = (
            f"Price moved {price_movement_pct:+.2f}% (signal: ₹{signal_price:.2f}, "
            f"current: ₹{current_price:.2f}). "
            f"Using original LIMIT price ₹{signal_price:.2f} (waiting for pullback)."
        )
    
    return result


def extract_underlying_from_option_symbol(option_symbol: str) -> Optional[str]:
    """
    Extract underlying symbol from option symbol
    
    Args:
        option_symbol: Option symbol (e.g., "SENSEX11DEC84500CE", "PRESTIGE25DEC1680CE")
        
    Returns:
        Underlying symbol (e.g., "SENSEX", "PRESTIGE") or None if not found
    """
    import re
    
    symbol_upper = option_symbol.upper().replace(".NS", "").strip()
    
    # Check BSE indices first (longer names)
    for bse_index in sorted(BSE_INDICES, key=len, reverse=True):
        if symbol_upper.startswith(bse_index):
            return bse_index
    
    # Check NSE indices
    nse_indices = ['NIFTYNXT50', 'MIDCPNIFTY', 'FINNIFTY', 'BANKNIFTY', 'NIFTY']
    for nse_index in sorted(nse_indices, key=len, reverse=True):
        if symbol_upper.startswith(nse_index):
            return nse_index
    
    # For stock options, extract by removing date/strike/type patterns
    # Pattern: STOCKNAME + (YY|DD) + MON + STRIKE + (CE|PE)
    # Try to match stock name (letters only, before date pattern)
    match = re.match(r'^([A-Z]+?)(?:\d{2}[A-Z]{3}\d+[CP]E)', symbol_upper)
    if match:
        return match.group(1)
    
    # Fallback: try to extract just the letters before first digit
    match = re.match(r'^([A-Z]+)', symbol_upper)
    if match:
        return match.group(1)
    
    return None


class OrderValidator:
    """Validates orders against risk management rules"""
    
    @staticmethod
    def validate_symbol(symbol: str) -> Tuple[bool, str]:
        """
        Validate trading symbol
        
        Args:
            symbol: Symbol to validate
            
        Returns:
            (is_valid, error_message)
        """
        if not symbol:
            return False, "Symbol cannot be empty"
        
        # Remove .NS suffix if present
        clean_symbol = symbol.replace(".NS", "").strip().upper()
        
        if not clean_symbol:
            return False, "Invalid symbol format"
        
        if len(clean_symbol) > 20:
            return False, "Symbol too long"
        
        return True, ""
    
    @staticmethod
    def validate_quantity(quantity: int, min_qty: int = 1, max_qty: int = 10000) -> Tuple[bool, str]:
        """
        Validate order quantity
        
        Args:
            quantity: Quantity to validate
            min_qty: Minimum allowed quantity
            max_qty: Maximum allowed quantity
            
        Returns:
            (is_valid, error_message)
        """
        if quantity < min_qty:
            return False, f"Quantity must be at least {min_qty}"
        
        if quantity > max_qty:
            return False, f"Quantity cannot exceed {max_qty}"
        
        return True, ""
    
    @staticmethod
    def validate_price(price: Optional[float], order_type: str) -> Tuple[bool, str]:
        """
        Validate order price
        
        Args:
            price: Price to validate
            order_type: Type of order
            
        Returns:
            (is_valid, error_message)
        """
        if order_type in [OrderType.LIMIT, OrderType.SL]:
            if price is None or price <= 0:
                return False, f"{order_type} orders require a valid price"
        
        if price and price <= 0:
            return False, "Price must be positive"
        
        return True, ""
    
    @staticmethod
    def validate_order_value(
        quantity: int,
        price: float,
        max_order_value: float
    ) -> Tuple[bool, str]:
        """
        Validate total order value against limit
        
        Args:
            quantity: Order quantity
            price: Order price
            max_order_value: Maximum allowed order value
            
        Returns:
            (is_valid, error_message)
        """
        order_value = quantity * price
        
        if order_value > max_order_value:
            return False, f"Order value ₹{order_value:,.0f} exceeds maximum ₹{max_order_value:,.0f}"
        
        return True, ""
    
    @staticmethod
    def validate_stop_loss(
        transaction_type: str,
        entry_price: float,
        stop_loss: float,
        max_loss_pct: float = 10.0
    ) -> Tuple[bool, str]:
        """
        Validate stop loss price
        
        Args:
            transaction_type: BUY or SELL
            entry_price: Entry price
            stop_loss: Stop loss price
            max_loss_pct: Maximum allowed loss percentage
            
        Returns:
            (is_valid, error_message)
        """
        if transaction_type == TransactionType.BUY:
            if stop_loss >= entry_price:
                return False, "Stop loss must be below entry price for BUY orders"
            
            loss_pct = abs((stop_loss - entry_price) / entry_price * 100)
        else:  # SELL
            if stop_loss <= entry_price:
                return False, "Stop loss must be above entry price for SELL orders"
            
            loss_pct = abs((stop_loss - entry_price) / entry_price * 100)
        
        if loss_pct > max_loss_pct:
            return False, f"Stop loss {loss_pct:.1f}% exceeds maximum {max_loss_pct:.1f}%"
        
        return True, ""


class OrderManager:
    """Manages order placement and tracking"""
    
    def __init__(self, user_id: str, feature_flags: Dict[str, Any]):
        """
        Initialize order manager
        
        Args:
            user_id: User identifier
            feature_flags: User's feature flags and risk limits
        """
        self.user_id = user_id
        self.feature_flags = feature_flags
        self.validator = OrderValidator()
    
    def validate_order(
        self,
        symbol: str,
        transaction_type: str,
        quantity: int,
        price: Optional[float],
        order_type: str,
        stop_loss: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Validate an order before placement
        
        Args:
            symbol: Trading symbol
            transaction_type: BUY or SELL
            quantity: Order quantity
            price: Order price (required for LIMIT/SL orders)
            order_type: MARKET/LIMIT/SL/SL-M
            stop_loss: Optional stop loss price
            
        Returns:
            (is_valid, error_message)
        """
        # Validate symbol
        is_valid, error = self.validator.validate_symbol(symbol)
        if not is_valid:
            return False, error
        
        # Validate quantity
        is_valid, error = self.validator.validate_quantity(quantity)
        if not is_valid:
            return False, error
        
        # Validate price
        is_valid, error = self.validator.validate_price(price, order_type)
        if not is_valid:
            return False, error
        
        # Validate order value
        if price:
            max_order_value = self.feature_flags.get("max_order_value", 100000)
            is_valid, error = self.validator.validate_order_value(
                quantity, price, max_order_value
            )
            if not is_valid:
                return False, error
        
        # Validate stop loss
        if stop_loss and price:
            is_valid, error = self.validator.validate_stop_loss(
                transaction_type, price, stop_loss
            )
            if not is_valid:
                return False, error
        
        return True, ""
    
    def prepare_order_params(
        self,
        symbol: str,
        exchange: Optional[str] = None,
        transaction_type: str = "BUY",
        quantity: int = 1,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        product: Optional[str] = None,
        validity: str = "DAY",
        is_option: Optional[bool] = None,
        lot_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Prepare order parameters for Zerodha API
        
        Automatically detects if symbol is an option and sets correct exchange/product.
        
        Args:
            symbol: Trading symbol (e.g., "RELIANCE" or "SENSEX11DEC84500CE")
            exchange: Exchange (NSE/BSE/NFO/BFO) - auto-detected if None
            transaction_type: BUY or SELL
            quantity: Order quantity (for stocks) or shares (for options)
            order_type: Order type
            price: Price for limit orders
            trigger_price: Trigger price for SL orders
            product: Product type (CNC/NRML) - auto-selected if None
            validity: Order validity
            is_option: Whether symbol is an option (auto-detected if None)
            lot_size: Lot size for options (required if is_option=True)
            
        Returns:
            Dict of order parameters ready for Zerodha API
        """
        # Clean symbol (remove .NS suffix)
        clean_symbol = symbol.replace(".NS", "").strip().upper()
        
        # Auto-detect if option
        if is_option is None:
            is_option = is_option_symbol(clean_symbol)
        
        # Set exchange
        if exchange is None:
            if is_option:
                exchange = get_option_exchange(clean_symbol)
            else:
                exchange = get_stock_exchange(clean_symbol)
        else:
            exchange = exchange.upper()
        
        # Set product type
        if product is None:
            if is_option:
                product = get_product_type_for_option()
            else:
                product = get_product_type_for_stock()
        else:
            product = product.upper()
        
        # Calculate quantity for options
        if is_option and lot_size:
            final_quantity = calculate_option_quantity(quantity, lot_size)
            logger.info(f"Option quantity: {quantity} lots × {lot_size} = {final_quantity} contracts")
        else:
            final_quantity = quantity
        
        params = {
            "symbol": clean_symbol,
            "exchange": exchange,
            "transaction_type": transaction_type.upper(),
            "quantity": final_quantity,
            "order_type": order_type.upper(),
            "product": product,
            "validity": validity.upper()
        }
        
        if price is not None:
            params["price"] = price
        
        if trigger_price is not None:
            params["trigger_price"] = trigger_price
        
        logger.info(f"Prepared order params: symbol={clean_symbol}, exchange={exchange}, "
                   f"product={product}, quantity={final_quantity}, is_option={is_option}")
        
        return params
    
    def calculate_order_metrics(
        self,
        quantity: int,
        entry_price: float,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate order metrics (value, risk, reward, R:R ratio)
        
        Args:
            quantity: Order quantity
            entry_price: Entry price
            stop_loss: Stop loss price
            target: Target price
            
        Returns:
            Dict of metrics
        """
        order_value = quantity * entry_price
        
        metrics = {
            "order_value": order_value,
            "quantity": quantity,
            "entry_price": entry_price
        }
        
        if stop_loss:
            risk = abs(entry_price - stop_loss) * quantity
            risk_pct = abs(stop_loss - entry_price) / entry_price * 100
            metrics["risk"] = risk
            metrics["risk_pct"] = risk_pct
            metrics["stop_loss"] = stop_loss
        
        if target:
            reward = abs(target - entry_price) * quantity
            reward_pct = abs(target - entry_price) / entry_price * 100
            metrics["reward"] = reward
            metrics["reward_pct"] = reward_pct
            metrics["target"] = target
        
        if stop_loss and target:
            risk_amount = abs(entry_price - stop_loss)
            reward_amount = abs(target - entry_price)
            if risk_amount > 0:
                rr_ratio = reward_amount / risk_amount
                metrics["rr_ratio"] = rr_ratio
        
        return metrics
    
    def is_live_trading_enabled(self) -> bool:
        """
        Check if live trading is enabled for the user
        
        Returns:
            True if enabled, False otherwise
        """
        return self.feature_flags.get("live_trading_enabled", False)
    
    def can_place_order(self, order_value: float) -> Tuple[bool, str]:
        """
        Check if user can place an order based on limits
        
        Args:
            order_value: Total order value
            
        Returns:
            (can_place, reason)
        """
        # Check if live trading is enabled
        if not self.is_live_trading_enabled():
            return False, "Live trading is not enabled. Enable it in settings."
        
        # Check order value limit
        max_order_value = self.feature_flags.get("max_order_value", 100000)
        if order_value > max_order_value:
            return False, f"Order value ₹{order_value:,.0f} exceeds limit ₹{max_order_value:,.0f}"
        
        # TODO: Check daily order count limit (requires database query)
        # TODO: Check open positions limit (requires database query)
        
        return True, ""


def format_order_details(order_params: Dict[str, Any], metrics: Dict[str, float]) -> str:
    """
    Format order details for display/confirmation
    
    Args:
        order_params: Order parameters
        metrics: Order metrics
        
    Returns:
        Formatted string
    """
    details = f"""
Order Details:
--------------
Symbol: {order_params['symbol']} ({order_params['exchange']})
Type: {order_params['transaction_type']}
Quantity: {order_params['quantity']} shares
Price: ₹{metrics['entry_price']:.2f} ({order_params['order_type']})
Order Value: ₹{metrics['order_value']:,.2f}
"""
    
    if "stop_loss" in metrics:
        details += f"\nStop Loss: ₹{metrics['stop_loss']:.2f} (-{metrics['risk_pct']:.1f}%)"
        details += f"\nMax Risk: ₹{metrics['risk']:,.2f}"
    
    if "target" in metrics:
        details += f"\nTarget: ₹{metrics['target']:.2f} (+{metrics['reward_pct']:.1f}%)"
        details += f"\nPotential Reward: ₹{metrics['reward']:,.2f}"
    
    if "rr_ratio" in metrics:
        details += f"\nRisk:Reward Ratio: 1:{metrics['rr_ratio']:.2f}"
    
    return details

