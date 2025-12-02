"""
Order Management Module
Handles order validation, placement, and tracking with risk management
"""
from typing import Dict, Optional, Tuple, Any
from datetime import datetime
import logging
from enum import Enum

logger = logging.getLogger(__name__)


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
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        product: str = "CNC",
        validity: str = "DAY"
    ) -> Dict[str, Any]:
        """
        Prepare order parameters for Zerodha API
        
        Args:
            symbol: Trading symbol
            exchange: Exchange (NSE/BSE)
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: Order type
            price: Price for limit orders
            trigger_price: Trigger price for SL orders
            product: Product type
            validity: Order validity
            
        Returns:
            Dict of order parameters
        """
        # Clean symbol (remove .NS suffix)
        clean_symbol = symbol.replace(".NS", "").strip().upper()
        
        params = {
            "symbol": clean_symbol,
            "exchange": exchange.upper(),
            "transaction_type": transaction_type.upper(),
            "quantity": quantity,
            "order_type": order_type.upper(),
            "product": product.upper(),
            "validity": validity.upper()
        }
        
        if price is not None:
            params["price"] = price
        
        if trigger_price is not None:
            params["trigger_price"] = trigger_price
        
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

