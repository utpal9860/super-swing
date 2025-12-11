"""
Authentication API endpoints
Handles user registration, login, and session management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
import os

from webapp.database import get_db, User, FeatureFlags
from webapp.auth import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    decode_access_token,
    generate_user_id
)

router = APIRouter()
# Make bearer optional so we can bypass auth locally when enabled
security = HTTPBearer(auto_error=False)


# Request/Response Models
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class UserProfileResponse(BaseModel):
    username: str
    email: str
    full_name: Optional[str]
    created_at: datetime
    total_trades: int
    active_trades: int
    completed_trades: int



# Dependency to get current user from token
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
    request: Request = None
) -> User:
    """
    Get current authenticated user from JWT token
    
    Args:
        credentials: HTTP Authorization credentials
        db: Database session
        
    Returns:
        User object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    # Local bypass: if BYPASS_AUTH=true, return/create a local user without token
    bypass = os.environ.get("BYPASS_AUTH", "").lower() in ("1", "true", "yes")
    if bypass and not credentials:
        user = db.query(User).filter(User.username == "local").first()
        if not user:
            # Create a minimal local user
            user = User(
                id=generate_user_id(),
                username="local",
                email="local@example.com",
                password_hash="",
                full_name="Local User",
                is_active=True,
                is_admin=False
            )
            db.add(user)
            # Ensure default feature flags exist
            if not db.query(FeatureFlags).filter(FeatureFlags.user_id == user.id).first():
                flags = FeatureFlags(
                    user_id=user.id,
                    live_trading_enabled=False,
                    auto_order_placement=False,
                    max_order_value=100000.0,
                    max_daily_orders=10,
                    max_open_positions=5,
                    risk_per_trade_pct=2.0
                )
                db.add(flags)
            db.commit()
            db.refresh(user)
        return user

    # Static API key support (Authorization: Bearer <key> OR X-API-Key: <key>)
    service_api_key = os.environ.get("SERVICE_API_KEY") or os.environ.get("API_KEY")
    header_api_key = None
    try:
        header_api_key = request.headers.get("x-api-key") if request else None
    except Exception:
        header_api_key = None
    bearer_value = credentials.credentials if credentials else None
    if service_api_key and (header_api_key == service_api_key or bearer_value == service_api_key):
        user = db.query(User).filter(User.username == "service").first()
        if not user:
            user = User(
                id=generate_user_id(),
                username="service",
                email="service@example.com",
                password_hash="",
                full_name="Service API User",
                is_active=True,
                is_admin=False
            )
            db.add(user)
            if not db.query(FeatureFlags).filter(FeatureFlags.user_id == user.id).first():
                flags = FeatureFlags(
                    user_id=user.id,
                    live_trading_enabled=False,
                    auto_order_placement=False,
                    max_order_value=100000.0,
                    max_daily_orders=10,
                    max_open_positions=5,
                    risk_per_trade_pct=2.0
                )
                db.add(flags)
            db.commit()
            db.refresh(user)
        return user

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user
    
    Args:
        user_data: User registration data
        db: Database session
        
    Returns:
        Token and user data
        
    Raises:
        HTTPException: If username or email already exists
    """
    # Check if username exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user_id = generate_user_id()
    hashed_password = get_password_hash(user_data.password)
    
    new_user = User(
        id=user_id,
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        is_active=True,
        is_admin=False
    )
    
    db.add(new_user)
    
    # Create default feature flags
    default_flags = FeatureFlags(
        user_id=user_id,
        live_trading_enabled=False,  # Disabled by default
        auto_order_placement=False,
        max_order_value=100000.0,  # ₹1 lakh
        max_daily_orders=10,
        max_open_positions=5,
        risk_per_trade_pct=2.0
    )
    
    db.add(default_flags)
    db.commit()
    db.refresh(new_user)
    
    # Generate access token
    access_token = create_access_token(data={"sub": user_id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "is_active": new_user.is_active,
            "created_at": new_user.created_at
        }
    }


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Login user and return access token
    
    Args:
        credentials: User login credentials
        db: Database session
        
    Returns:
        Token and user data
        
    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by username
    user = db.query(User).filter(User.username == credentials.username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Generate access token
    access_token = create_access_token(data={"sub": user.id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "created_at": user.created_at
        }
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User data
    """
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at
    }


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout user (client should discard token)
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Success message
    """
    # In JWT, logout is handled client-side by discarding the token
    # Server-side, we could add token to blacklist if needed
    return {"message": "Logged out successfully"}


@router.get("/check")
async def check_auth(current_user: User = Depends(get_current_user)):
    """
    Check if user is authenticated (for frontend)
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Authentication status
    """
    return {
        "authenticated": True,
        "user_id": current_user.id,
        "username": current_user.username
    }


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete user profile with trade statistics
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        User profile with trade counts
    """
    # Import paper trading functions
    from webapp.api.paper_trading import load_trades
    
    try:
        # Load user's trades
        trades = load_trades(current_user.id)
        
        # Count trades by status
        total_trades = len(trades)
        active_trades = len([t for t in trades if t.get('status') == 'open'])
        completed_trades = len([t for t in trades if t.get('status') == 'closed'])
        
    except Exception as e:
        # If there's an error loading trades, return 0
        print(f"Error loading trades: {e}")
        total_trades = 0
        active_trades = 0
        completed_trades = 0
    
    return {
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "created_at": current_user.created_at,
        "total_trades": total_trades,
        "active_trades": active_trades,
        "completed_trades": completed_trades
    }


