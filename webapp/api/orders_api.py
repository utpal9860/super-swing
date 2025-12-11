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
from webapp.order_manager import (
    OrderManager, 
    format_order_details,
    is_option_symbol,
    get_option_exchange,
    get_product_type_for_option,
    calculate_option_quantity,
    extract_underlying_from_option_symbol,
    determine_order_strategy
)
from webapp.encryption import decrypt_api_key, decrypt_access_token
from webapp.auth import generate_order_id
from webapp.utils.options import get_option_lot_size

router = APIRouter()


# Request/Response Models
class OrderRequest(BaseModel):
    symbol: str
    exchange: str = "NSE"
    transaction_type: str  # BUY/SELL
    quantity: int
    order_type: str = "LIMIT"  # MARKET/LIMIT/SL/SL-M (default LIMIT for breakout orders)
    price: Optional[float] = None  # Entry price (can be above/below market for breakout)
    trigger_price: Optional[float] = None
    product: str = "CNC"
    validity: str = "DAY"
    stop_loss: Optional[float] = None  # If provided with target, creates bracket order (fire-and-forget)
    target: Optional[float] = None  # If provided with stop_loss, creates bracket order (fire-and-forget)
    use_bracket_order: bool = True  # Auto-use bracket order if SL and Target provided
    signal_price: Optional[float] = None  # Original signal price (for price movement detection)
    price_tolerance_pct: float = 2.0  # Acceptable price movement % (default 2%)
    max_price_movement_pct: float = 5.0  # Maximum acceptable movement % (default 5%, rejects if exceeded)
    trailing_enabled: bool = False  # Enable trailing stop loss
    trailing_distance: float = 3.0  # Trailing distance % (default 3%)


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
        
        # Detect if this is an option
        is_option = is_option_symbol(order_data.symbol)
        
        # For options: resolve symbol and get lot size
        resolved_symbol = order_data.symbol
        lot_size = None
        
        if is_option:
            # Extract underlying symbol from option symbol
            underlying_symbol = extract_underlying_from_option_symbol(order_data.symbol)
            
            # Get lot size for underlying symbol
            if underlying_symbol:
                try:
                    lot_size = get_option_lot_size(underlying_symbol)
                    logger.info(f"Extracted underlying: {underlying_symbol}, lot size: {lot_size}")
                except Exception as e:
                    logger.warning(f"Could not get lot size for {underlying_symbol}: {e}")
                    lot_size = 1
            else:
                logger.warning(f"Could not extract underlying symbol from {order_data.symbol}")
                lot_size = 1
            
            # Note: Symbol resolution would happen here if we have strike/expiry
            # For now, we'll use the symbol as-is and let Zerodha validate it
            # In production, you'd call: resolved_symbol = client.resolve_option_symbol(...)
        
        # =====================================================================
        # ADAPTIVE ORDER STRATEGY: Handle price movement and time delays
        # =====================================================================
        
        # Get current market price to compare with signal price
        current_price = None
        signal_price = order_data.signal_price or order_data.price
        
        # Get today's high price to detect if price already moved favorably
        today_high = None
        current_price = None
        
        if signal_price and order_data.order_type == "LIMIT":
            try:
                # Determine exchange for instrument token
                # For options, exchange is already set (NFO/BFO)
                # For stocks, use provided exchange or default to NSE
                exchange_for_token = order_data.exchange
                if not is_option and not exchange_for_token:
                    exchange_for_token = "NSE"
                
                # Construct instrument token
                instrument_token = f"{exchange_for_token}:{resolved_symbol}"
                
                # Get current price and today's high from Zerodha
                # Try quote first (has more data including high/low)
                try:
                    quotes = client.get_quote([instrument_token])
                    if instrument_token in quotes:
                        quote_data = quotes[instrument_token]
                        if isinstance(quote_data, dict):
                            # Zerodha quote format has 'ohlc' with 'high', 'low', 'last_price'
                            ohlc = quote_data.get('ohlc', {})
                            current_price = ohlc.get('last_price') or quote_data.get('last_price')
                            today_high = ohlc.get('high') or quote_data.get('day_high') or quote_data.get('high')
                except:
                    # Fallback to LTP if quote fails
                    pass
                
                # Fallback to LTP if quote didn't work
                if current_price is None:
                    ltps = client.get_ltp([instrument_token])
                    if instrument_token in ltps:
                        ltp_data = ltps[instrument_token]
                        if isinstance(ltp_data, dict):
                            current_price = ltp_data.get('last_price')
                        else:
                            current_price = float(ltp_data) if ltp_data else None
                
                if current_price:
                    logger.info(f"Current price for {resolved_symbol}: ₹{current_price:.2f} (signal: ₹{signal_price:.2f})")
                    if today_high:
                        logger.info(f"Today's high for {resolved_symbol}: ₹{today_high:.2f}")
                else:
                    logger.warning(f"Could not get current price for {instrument_token}")
            except Exception as e:
                logger.warning(f"Could not fetch current price: {e}. Will use signal price.")
                import traceback
                logger.debug(f"Price fetch error traceback: {traceback.format_exc()}")
                current_price = None
                today_high = None
        
        # Determine optimal order strategy based on price movement
        final_order_type = order_data.order_type
        final_price = order_data.price
        order_warning = None
        should_reject = False
        
        if current_price and signal_price and order_data.order_type == "LIMIT":
            strategy_result = determine_order_strategy(
                signal_price=signal_price,
                current_price=current_price,
                order_type=order_data.order_type,
                price_tolerance_pct=order_data.price_tolerance_pct,
                max_price_movement_pct=order_data.max_price_movement_pct,
                target_price=order_data.target,  # Pass target to detect momentum loss
                today_high=today_high  # Pass today's high to detect if price already moved up
            )
            
            final_order_type = strategy_result["final_order_type"]
            final_price = strategy_result["final_price"]
            order_warning = strategy_result["warning"]
            should_reject = strategy_result["should_reject"]
            
            logger.info(f"Order strategy: {strategy_result['strategy']} - "
                       f"Price movement: {strategy_result['price_movement_pct']:+.2f}%, "
                       f"Final order type: {final_order_type}, Final price: {final_price}")
            
            if order_warning:
                logger.warning(order_warning)
            
            # Reject order if price moved too much
            if should_reject:
                order_log.status = "REJECTED"
                order_log.error_message = order_warning
                order_log.status_message = "Order rejected due to excessive price movement"
                db.commit()
                
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=order_warning
                )
        
        # =====================================================================
        # BRACKET ORDER PLACEMENT
        # =====================================================================
        
        # Check if this should be a bracket order (fire-and-forget with SL and Target)
        use_bracket_order = order_data.stop_loss is not None and order_data.target is not None
        
        if use_bracket_order:
            # FIRE-AND-FORGET: Use bracket order (entry + SL + target all at once)
            # This automatically places all 3 orders and manages exits
            logger.info(f"Placing bracket order (fire-and-forget) for {resolved_symbol} with SL={order_data.stop_loss}, Target={order_data.target}")
            
            # Prepare order parameters (using adaptive strategy)
            order_params = manager.prepare_order_params(
                symbol=resolved_symbol,
                exchange=order_data.exchange,
                transaction_type=order_data.transaction_type,
                quantity=order_data.quantity,
                order_type=final_order_type,  # Use adaptive order type
                price=final_price,  # Use adaptive price
                trigger_price=order_data.trigger_price,
                product=order_data.product,
                validity=order_data.validity,
                is_option=is_option,
                lot_size=lot_size
            )
            
            # Add bracket order parameters
            order_params["variety"] = "bo"  # Bracket order
            order_params["squareoff"] = order_data.target  # Target price
            order_params["stoploss"] = order_data.stop_loss  # Stop loss price
            
            # Place bracket order (all 3 orders placed together)
            result = client.place_order(**order_params)
            
            logger.info(f"Bracket order placed: {result.get('order_id')} - Entry + SL + Target all active")
        else:
            # Regular order (no auto-exit) - using adaptive strategy
            order_params = manager.prepare_order_params(
                symbol=resolved_symbol,
                exchange=order_data.exchange,  # Will be auto-corrected if None
                transaction_type=order_data.transaction_type,
                quantity=order_data.quantity,
                order_type=final_order_type,  # Use adaptive order type
                price=final_price,  # Use adaptive price
                trigger_price=order_data.trigger_price,
                product=order_data.product,  # Will be auto-set to NRML for options if None
                validity=order_data.validity,
                is_option=is_option,
                lot_size=lot_size
            )
            
            # Place regular order
            result = client.place_order(**order_params)
        
        # Update order log with success
        order_log.order_id = result.get("order_id")
        order_log.status = "PLACED"
        order_log.status_message = "Order placed successfully"
        order_log.placed_at = datetime.utcnow()
        order_log.zerodha_response = str(result)
        
        db.commit()
        
        # =====================================================================
        # AUTO-CREATE TRADE ENTRY FOR LIVE ORDERS
        # =====================================================================
        trade_created = None
        try:
            from webapp.api.paper_trading import load_trades, save_trades
            from webapp.utils.options import get_option_lot_size
            from webapp.order_manager import is_option_symbol, extract_underlying_from_option_symbol
            
            # Determine if this is an option
            is_option_trade = is_option_symbol(resolved_symbol)
            
            # Get lot size for options
            lot_size_val = 1
            if is_option_trade:
                underlying = extract_underlying_from_option_symbol(resolved_symbol)
                if underlying:
                    try:
                        lot_size_val = get_option_lot_size(underlying)
                    except:
                        lot_size_val = 1
            
            # Calculate effective quantity
            effective_qty = order_data.quantity
            if is_option_trade:
                effective_qty = order_data.quantity * lot_size_val
            
            # Create trade entry
            trade_id = f"TRADE_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            trade_entry = {
                "id": trade_id,
                "symbol": resolved_symbol.replace('.NS', '') + '.NS' if not is_option_trade else resolved_symbol.split()[0] + '.NS',
                "entry_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "entry_price": float(final_price) if final_price else float(signal_price) if signal_price else float(order_data.price) if order_data.price else 0.0,
                "shares": order_data.quantity,
                "stop_loss": float(order_data.stop_loss) if order_data.stop_loss else 0.0,
                "target": float(order_data.target) if order_data.target else 0.0,
                "position_value": (float(final_price) if final_price else float(signal_price) if signal_price else float(order_data.price) if order_data.price else 0.0) * effective_qty,
                "status": "open",
                "brokerage": 20.0,
                "user_id": current_user.id,
                "is_live": True,  # Mark as live trade
                "zerodha_buy_order_id": result.get("order_id"),  # Store buy order ID
                "zerodha_sl_order_id": None,  # Will be set when SL order is placed (if separate)
                "zerodha_target_order_id": None,  # Will be set when target order is placed (if separate)
                "trailing_enabled": order_data.trailing_enabled,
                "trailing_distance": order_data.trailing_distance,
                "highest_price": float(final_price) if final_price else float(signal_price) if signal_price else float(order_data.price) if order_data.price else 0.0,
                "initial_sl": float(order_data.stop_loss) if order_data.stop_loss else None,
                "sl_updates_count": 0,
                "last_sl_update": None,
                "last_price_check": None,
                "instrument_type": "option" if is_option_trade else None,
                "option_symbol": resolved_symbol if is_option_trade else None,
                "option_type": None,  # Will be extracted from symbol if needed
                "option_strike": None,  # Will be extracted from symbol if needed
                "option_expiry_month": None,  # Will be extracted from symbol if needed
                "lot_size": lot_size_val if is_option_trade else None,
                "notes": f"Auto-created from live order {result.get('order_id')}. Order type: {final_order_type}, Strategy: {strategy_result.get('strategy') if strategy_result else 'N/A'}"
            }
            
            # For bracket orders, note that SL and Target are managed by Zerodha
            if use_bracket_order:
                trade_entry["notes"] += f" | Bracket order: SL and Target managed by Zerodha"
                trade_entry["zerodha_sl_order_id"] = f"{result.get('order_id')}_SL"  # Bracket order SL
                trade_entry["zerodha_target_order_id"] = f"{result.get('order_id')}_TGT"  # Bracket order Target
            
            # Load existing trades
            trades = load_trades(current_user.id)
            trades.append(trade_entry)
            save_trades(current_user.id, trades)
            
            trade_created = trade_entry
            logger.info(f"✅ Auto-created trade {trade_id} for live order {result.get('order_id')}")
            
        except Exception as e:
            logger.warning(f"Could not auto-create trade entry: {e}. Order placed successfully but trade not linked.")
            import traceback
            logger.debug(traceback.format_exc())
        
        response_data = {
            "success": True,
            "order_id": order_id,
            "message": "Order placed successfully on Zerodha",
            "zerodha_order_id": result.get("order_id"),
            "order_strategy": {
                "final_order_type": final_order_type,
                "final_price": final_price,
                "signal_price": signal_price,
                "current_price": current_price
            },
            "trade_created": trade_created is not None,
            "trade_id": trade_created.get("id") if trade_created else None
        }
        
        if order_warning:
            response_data["warning"] = order_warning
        
        if use_bracket_order:
            response_data["message"] = "Bracket order placed successfully (fire-and-forget with auto SL and Target)"
            response_data["order_type"] = "bracket"
            response_data["stop_loss"] = order_data.stop_loss
            response_data["target"] = order_data.target
            response_data["note"] = "Entry, SL, and Target orders are all active. When entry fills, SL and Target become active. When either hits, the other is automatically cancelled."
        
        return response_data
        
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

