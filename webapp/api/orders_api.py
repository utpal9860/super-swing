"""
Orders API endpoints
Handles live order placement, validation, and tracking
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from webapp.database import get_db, User, ZerodhaCredential, FeatureFlags, OrderLog
from webapp.api.auth_api import get_current_user
from webapp.zerodha_client import get_zerodha_client
from webapp.order_manager import OrderManager, format_order_details
from webapp.encryption import decrypt_api_key, decrypt_access_token
from webapp.auth import generate_order_id

router = APIRouter()


# Request/Response Models
class OrderRequest(BaseModel):
    symbol: str
    exchange: str = "NSE"
    transaction_type: str  # BUY/SELL
    quantity: int
    order_type: str  # MARKET/LIMIT/SL/SL-M
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    product: str = "CNC"
    validity: str = "DAY"
    stop_loss: Optional[float] = None
    target: Optional[float] = None


class OrderResponse(BaseModel):
    success: bool
    order_id: str
    message: str
    zerodha_order_id: Optional[str] = None


class OrderValidationResponse(BaseModel):
    is_valid: bool
    message: str
    order_details: Optional[dict] = None
    metrics: Optional[dict] = None


@router.post("/validate", response_model=OrderValidationResponse)
async def validate_order(
    order_data: OrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate an order before placement (preview mode)
    
    Args:
        order_data: Order parameters
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Validation result with order details
    """
    # Get feature flags
    flags = db.query(FeatureFlags).filter(
        FeatureFlags.user_id == current_user.id
    ).first()
    
    if not flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User feature flags not found"
        )
    
    # Create order manager
    manager = OrderManager(
        user_id=current_user.id,
        feature_flags={
            "live_trading_enabled": flags.live_trading_enabled,
            "max_order_value": flags.max_order_value,
            "max_daily_orders": flags.max_daily_orders,
            "risk_per_trade_pct": flags.risk_per_trade_pct
        }
    )
    
    # Validate order
    is_valid, error_msg = manager.validate_order(
        symbol=order_data.symbol,
        transaction_type=order_data.transaction_type,
        quantity=order_data.quantity,
        price=order_data.price,
        order_type=order_data.order_type,
        stop_loss=order_data.stop_loss
    )
    
    if not is_valid:
        return {
            "is_valid": False,
            "message": error_msg,
            "order_details": None,
            "metrics": None
        }
    
    # Prepare order parameters
    order_params = manager.prepare_order_params(
        symbol=order_data.symbol,
        exchange=order_data.exchange,
        transaction_type=order_data.transaction_type,
        quantity=order_data.quantity,
        order_type=order_data.order_type,
        price=order_data.price,
        trigger_price=order_data.trigger_price,
        product=order_data.product,
        validity=order_data.validity
    )
    
    # Calculate metrics
    metrics = manager.calculate_order_metrics(
        quantity=order_data.quantity,
        entry_price=order_data.price or 0,
        stop_loss=order_data.stop_loss,
        target=order_data.target
    )
    
    return {
        "is_valid": True,
        "message": "Order is valid and ready to place",
        "order_details": order_params,
        "metrics": metrics
    }


@router.post("/place", response_model=OrderResponse)
async def place_order(
    order_data: OrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Place a live order on Zerodha
    
    Args:
        order_data: Order parameters
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Order placement result
    """
    # Get feature flags
    flags = db.query(FeatureFlags).filter(
        FeatureFlags.user_id == current_user.id
    ).first()
    
    if not flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User feature flags not found"
        )
    
    # Check if live trading is enabled
    if not flags.live_trading_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Live trading is not enabled. Please enable it in settings."
        )
    
    # Get Zerodha credentials
    cred = db.query(ZerodhaCredential).filter(
        ZerodhaCredential.user_id == current_user.id
    ).first()
    
    if not cred or not cred.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zerodha account not connected. Please connect your account first."
        )
    
    # Create order manager
    manager = OrderManager(
        user_id=current_user.id,
        feature_flags={
            "live_trading_enabled": flags.live_trading_enabled,
            "max_order_value": flags.max_order_value,
            "max_daily_orders": flags.max_daily_orders,
            "risk_per_trade_pct": flags.risk_per_trade_pct
        }
    )
    
    # Validate order
    is_valid, error_msg = manager.validate_order(
        symbol=order_data.symbol,
        transaction_type=order_data.transaction_type,
        quantity=order_data.quantity,
        price=order_data.price,
        order_type=order_data.order_type,
        stop_loss=order_data.stop_loss
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Generate order ID
    order_id = generate_order_id()
    
    # Create order log (PENDING status)
    order_log = OrderLog(
        id=order_id,
        user_id=current_user.id,
        symbol=order_data.symbol,
        exchange=order_data.exchange,
        transaction_type=order_data.transaction_type,
        quantity=order_data.quantity,
        price=order_data.price,
        trigger_price=order_data.trigger_price,
        order_type=order_data.order_type,
        product=order_data.product,
        validity=order_data.validity,
        status="PENDING",
        created_at=datetime.utcnow()
    )
    
    db.add(order_log)
    db.commit()
    
    try:
        # Get Zerodha client
        api_key = decrypt_api_key(cred.api_key)
        access_token = decrypt_access_token(cred.access_token)
        client = get_zerodha_client(current_user.id, api_key, access_token)
        
        # Prepare order parameters
        order_params = manager.prepare_order_params(
            symbol=order_data.symbol,
            exchange=order_data.exchange,
            transaction_type=order_data.transaction_type,
            quantity=order_data.quantity,
            order_type=order_data.order_type,
            price=order_data.price,
            trigger_price=order_data.trigger_price,
            product=order_data.product,
            validity=order_data.validity
        )
        
        # Place order on Zerodha
        result = client.place_order(**order_params)
        
        # Update order log with success
        order_log.order_id = result.get("order_id")
        order_log.status = "PLACED"
        order_log.status_message = "Order placed successfully"
        order_log.placed_at = datetime.utcnow()
        order_log.zerodha_response = str(result)
        
        db.commit()
        
        return {
            "success": True,
            "order_id": order_id,
            "message": "Order placed successfully on Zerodha",
            "zerodha_order_id": result.get("order_id")
        }
        
    except Exception as e:
        # Update order log with error
        order_log.status = "REJECTED"
        order_log.error_message = str(e)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to place order: {str(e)}"
        )


@router.post("/place-bracket")
async def place_bracket_order(
    order_data: OrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Place a bracket order on Zerodha (BUY + SL + Target)
    
    This places 3 orders:
    1. Main BUY order
    2. Stop Loss (SL) order - triggers if price falls
    3. Target (LIMIT) order - triggers if price rises
    
    Args:
        order_data: Order parameters including SL and Target
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Order placement result with all 3 order IDs
    """
    # Get feature flags
    flags = db.query(FeatureFlags).filter(
        FeatureFlags.user_id == current_user.id
    ).first()
    
    if not flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User feature flags not found"
        )
    
    # Check if live trading is enabled
    if not flags.live_trading_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Live trading is not enabled. Please enable it in settings."
        )
    
    # Get Zerodha credentials
    cred = db.query(ZerodhaCredential).filter(
        ZerodhaCredential.user_id == current_user.id
    ).first()
    
    if not cred or not cred.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zerodha account not connected. Please connect your account first."
        )
    
    # Validate that SL and Target are provided
    if not order_data.stop_loss or not order_data.target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both stop_loss and target are required for bracket orders"
        )
    
    # Create order manager
    manager = OrderManager(
        user_id=current_user.id,
        feature_flags={
            "live_trading_enabled": flags.live_trading_enabled,
            "max_order_value": flags.max_order_value,
            "max_daily_orders": flags.max_daily_orders,
            "risk_per_trade_pct": flags.risk_per_trade_pct
        }
    )
    
    # Validate main order
    is_valid, error_msg = manager.validate_order(
        symbol=order_data.symbol,
        transaction_type=order_data.transaction_type,
        quantity=order_data.quantity,
        price=order_data.price,
        order_type=order_data.order_type,
        stop_loss=order_data.stop_loss
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Get Zerodha client
    api_key = decrypt_api_key(cred.api_key)
    access_token = decrypt_access_token(cred.access_token)
    client = get_zerodha_client(current_user.id, api_key, access_token)
    
    # Generate order IDs
    main_order_id = generate_order_id()
    sl_order_id = f"{main_order_id}_SL"
    target_order_id = f"{main_order_id}_TGT"
    
    try:
        # === 1. Place Main BUY Order ===
        main_order_params = manager.prepare_order_params(
            symbol=order_data.symbol,
            exchange=order_data.exchange,
            transaction_type=order_data.transaction_type,
            quantity=order_data.quantity,
            order_type=order_data.order_type,
            price=order_data.price,
            product=order_data.product,
            validity=order_data.validity
        )
        
        main_result = client.place_order(**main_order_params)
        zerodha_main_id = main_result.get("order_id")
        
        # Log main order
        main_log = OrderLog(
            id=main_order_id,
            user_id=current_user.id,
            symbol=order_data.symbol,
            exchange=order_data.exchange,
            transaction_type=order_data.transaction_type,
            quantity=order_data.quantity,
            price=order_data.price,
            order_type=order_data.order_type,
            product=order_data.product,
            validity=order_data.validity,
            status="PLACED",
            status_message="Main BUY order placed",
            order_id=zerodha_main_id,
            placed_at=datetime.utcnow(),
            zerodha_response=str(main_result),
            created_at=datetime.utcnow()
        )
        db.add(main_log)
        
        # === 2. Place Stop Loss Order ===
        sl_order_params = manager.prepare_order_params(
            symbol=order_data.symbol,
            exchange=order_data.exchange,
            transaction_type="SELL",  # SL is a sell order
            quantity=order_data.quantity,
            order_type="SL",  # Stop Loss order type
            price=order_data.stop_loss,
            trigger_price=order_data.stop_loss,  # Trigger when price hits SL
            product=order_data.product,
            validity="GTT"  # Good Till Triggered - stays active
        )
        
        try:
            sl_result = client.place_order(**sl_order_params)
            zerodha_sl_id = sl_result.get("order_id")
            
            # Log SL order
            sl_log = OrderLog(
                id=sl_order_id,
                user_id=current_user.id,
                symbol=order_data.symbol,
                exchange=order_data.exchange,
                transaction_type="SELL",
                quantity=order_data.quantity,
                price=order_data.stop_loss,
                trigger_price=order_data.stop_loss,
                order_type="SL",
                product=order_data.product,
                validity="GTT",
                status="PLACED",
                status_message="Stop Loss order placed",
                order_id=zerodha_sl_id,
                placed_at=datetime.utcnow(),
                zerodha_response=str(sl_result),
                created_at=datetime.utcnow()
            )
            db.add(sl_log)
        except Exception as e:
            # SL order failed, but main order is placed
            # Log the failure but don't fail the entire request
            sl_log = OrderLog(
                id=sl_order_id,
                user_id=current_user.id,
                symbol=order_data.symbol,
                exchange=order_data.exchange,
                transaction_type="SELL",
                quantity=order_data.quantity,
                price=order_data.stop_loss,
                order_type="SL",
                status="REJECTED",
                error_message=f"SL order failed: {str(e)}",
                created_at=datetime.utcnow()
            )
            db.add(sl_log)
            zerodha_sl_id = None
        
        # === 3. Place Target Order ===
        target_order_params = manager.prepare_order_params(
            symbol=order_data.symbol,
            exchange=order_data.exchange,
            transaction_type="SELL",  # Target is a sell order
            quantity=order_data.quantity,
            order_type="LIMIT",  # Limit order at target price
            price=order_data.target,
            product=order_data.product,
            validity="GTT"  # Good Till Triggered
        )
        
        try:
            target_result = client.place_order(**target_order_params)
            zerodha_target_id = target_result.get("order_id")
            
            # Log target order
            target_log = OrderLog(
                id=target_order_id,
                user_id=current_user.id,
                symbol=order_data.symbol,
                exchange=order_data.exchange,
                transaction_type="SELL",
                quantity=order_data.quantity,
                price=order_data.target,
                order_type="LIMIT",
                product=order_data.product,
                validity="GTT",
                status="PLACED",
                status_message="Target order placed",
                order_id=zerodha_target_id,
                placed_at=datetime.utcnow(),
                zerodha_response=str(target_result),
                created_at=datetime.utcnow()
            )
            db.add(target_log)
        except Exception as e:
            # Target order failed, but main order is placed
            target_log = OrderLog(
                id=target_order_id,
                user_id=current_user.id,
                symbol=order_data.symbol,
                exchange=order_data.exchange,
                transaction_type="SELL",
                quantity=order_data.quantity,
                price=order_data.target,
                order_type="LIMIT",
                status="REJECTED",
                error_message=f"Target order failed: {str(e)}",
                created_at=datetime.utcnow()
            )
            db.add(target_log)
            zerodha_target_id = None
        
        db.commit()
        
        return {
            "success": True,
            "message": "Bracket order placed successfully",
            "buy_order_id": zerodha_main_id,
            "sl_order_id": zerodha_sl_id,
            "target_order_id": zerodha_target_id,
            "internal_order_id": main_order_id
        }
        
    except Exception as e:
        # Main order failed
        main_log = OrderLog(
            id=main_order_id,
            user_id=current_user.id,
            symbol=order_data.symbol,
            exchange=order_data.exchange,
            transaction_type=order_data.transaction_type,
            quantity=order_data.quantity,
            price=order_data.price,
            order_type=order_data.order_type,
            product=order_data.product,
            validity=order_data.validity,
            status="REJECTED",
            error_message=str(e),
            created_at=datetime.utcnow()
        )
        db.add(main_log)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to place bracket order: {str(e)}"
        )


@router.get("/history")
async def get_order_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's order history
    
    Args:
        limit: Number of orders to fetch
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of orders
    """
    orders = db.query(OrderLog).filter(
        OrderLog.user_id == current_user.id
    ).order_by(OrderLog.created_at.desc()).limit(limit).all()
    
    return {
        "success": True,
        "orders": [
            {
                "id": order.id,
                "order_id": order.order_id,
                "symbol": order.symbol,
                "exchange": order.exchange,
                "transaction_type": order.transaction_type,
                "quantity": order.quantity,
                "price": order.price,
                "order_type": order.order_type,
                "status": order.status,
                "status_message": order.status_message,
                "error_message": order.error_message,
                "placed_at": order.placed_at,
                "created_at": order.created_at
            }
            for order in orders
        ]
    }


@router.get("/feature-flags")
async def get_feature_flags(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's feature flags and risk settings
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Feature flags
    """
    flags = db.query(FeatureFlags).filter(
        FeatureFlags.user_id == current_user.id
    ).first()
    
    if not flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature flags not found"
        )
    
    return {
        "live_trading_enabled": flags.live_trading_enabled,
        "auto_order_placement": flags.auto_order_placement,
        "max_order_value": flags.max_order_value,
        "max_daily_orders": flags.max_daily_orders,
        "max_open_positions": flags.max_open_positions,
        "risk_per_trade_pct": flags.risk_per_trade_pct,
        "email_notifications": flags.email_notifications,
        "order_notifications": flags.order_notifications
    }


class FeatureFlagsUpdate(BaseModel):
    live_trading_enabled: Optional[bool] = None
    max_order_value: Optional[float] = None
    max_daily_orders: Optional[int] = None
    risk_per_trade_pct: Optional[float] = None


@router.put("/feature-flags")
async def update_feature_flags(
    updates: FeatureFlagsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user's feature flags
    
    Args:
        updates: Fields to update
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Updated feature flags
    """
    flags = db.query(FeatureFlags).filter(
        FeatureFlags.user_id == current_user.id
    ).first()
    
    if not flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature flags not found"
        )
    
    # Update fields if provided
    if updates.live_trading_enabled is not None:
        flags.live_trading_enabled = updates.live_trading_enabled
    if updates.max_order_value is not None:
        flags.max_order_value = updates.max_order_value
    if updates.max_daily_orders is not None:
        flags.max_daily_orders = updates.max_daily_orders
    if updates.risk_per_trade_pct is not None:
        flags.risk_per_trade_pct = updates.risk_per_trade_pct
    
    flags.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "success": True,
        "message": "Feature flags updated successfully",
        "flags": {
            "live_trading_enabled": flags.live_trading_enabled,
            "max_order_value": flags.max_order_value,
            "max_daily_orders": flags.max_daily_orders,
            "risk_per_trade_pct": flags.risk_per_trade_pct
        }
    }

