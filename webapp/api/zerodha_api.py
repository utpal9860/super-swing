"""
Zerodha Integration API endpoints
Handles Zerodha account connection, OAuth, and portfolio sync
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from webapp.database import get_db, User, ZerodhaCredential, FeatureFlags
from webapp.api.auth_api import get_current_user
from webapp.zerodha_client import ZerodhaClient, get_zerodha_client, remove_zerodha_client
from webapp.encryption import encrypt_api_key, decrypt_api_key, encrypt_access_token, decrypt_access_token

router = APIRouter()


# Request/Response Models
class ZerodhaConnect(BaseModel):
    api_key: str
    api_secret: Optional[str] = None  # Optional, can be server-side only


class ZerodhaStatus(BaseModel):
    is_connected: bool
    has_credentials: bool
    last_connected_at: Optional[datetime]
    zerodha_user_id: Optional[str]
    token_expires_at: Optional[datetime]
    needs_reauth: bool


@router.post("/connect")
async def connect_zerodha(
    data: ZerodhaConnect,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Save Zerodha API credentials and get login URL
    
    Args:
        data: API key and secret
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Login URL for OAuth flow
    """
    # Encrypt credentials
    encrypted_api_key = encrypt_api_key(data.api_key)
    encrypted_api_secret = encrypt_api_key(data.api_secret) if data.api_secret else None
    
    # Check if credentials already exist
    existing_cred = db.query(ZerodhaCredential).filter(
        ZerodhaCredential.user_id == current_user.id
    ).first()
    
    if existing_cred:
        # Update existing
        existing_cred.api_key = encrypted_api_key
        if encrypted_api_secret:
            existing_cred.api_secret = encrypted_api_secret
        existing_cred.updated_at = datetime.utcnow()
    else:
        # Create new
        new_cred = ZerodhaCredential(
            user_id=current_user.id,
            api_key=encrypted_api_key,
            api_secret=encrypted_api_secret,
            is_connected=False
        )
        db.add(new_cred)
    
    db.commit()
    
    # Generate login URL
    client = ZerodhaClient(api_key=data.api_key)
    login_url = client.get_login_url()
    
    return {
        "success": True,
        "message": "API credentials saved. Please login to Zerodha.",
        "login_url": login_url
    }


@router.get("/oauth-callback")
async def zerodha_oauth_callback(
    request_token: str = Query(...),
    status: str = Query(...),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Handle OAuth callback from Zerodha
    
    This endpoint is called by Zerodha after user login, so it doesn't require
    authentication. We use the state parameter (user_id) to identify the user.
    
    Args:
        request_token: Request token from Zerodha
        status: Status from Zerodha
        state: User ID passed in login URL
        db: Database session
        
    Returns:
        Redirect to profile page or error page
    """
    if status != "success":
        return RedirectResponse(url="/profile?zerodha_error=auth_failed")
    
    # Get user_id from state parameter or find the most recent credential entry
    if state:
        user_id = state
    else:
        # Fallback: get the most recently updated credential (assuming user just added it)
        recent_cred = db.query(ZerodhaCredential).order_by(
            ZerodhaCredential.updated_at.desc()
        ).first()
        
        if not recent_cred:
            return RedirectResponse(url="/profile?zerodha_error=no_credentials")
        
        user_id = recent_cred.user_id
    
    # Get user's credentials
    cred = db.query(ZerodhaCredential).filter(
        ZerodhaCredential.user_id == user_id
    ).first()
    
    if not cred:
        return RedirectResponse(url="/profile?zerodha_error=credentials_not_found")
    
    # Decrypt credentials
    api_key = decrypt_api_key(cred.api_key)
    api_secret = decrypt_api_key(cred.api_secret) if cred.api_secret else None
    
    if not api_secret:
        return RedirectResponse(url="/profile?zerodha_error=no_api_secret")
    
    # Generate session
    try:
        client = ZerodhaClient(api_key=api_key)
        session_data = client.generate_session(request_token, api_secret)
        
        # Save access token and session info
        cred.access_token = encrypt_access_token(session_data["access_token"])
        cred.request_token = request_token
        cred.token_expires_at = datetime.utcnow() + timedelta(days=1)  # Tokens expire daily
        cred.is_connected = True
        cred.last_connected_at = datetime.utcnow()
        cred.zerodha_user_id = session_data.get("user_id")
        
        db.commit()
        
        # Redirect to profile page with success
        return RedirectResponse(url="/profile?zerodha_connected=true")
        
    except Exception as e:
        import logging
        logging.error(f"Zerodha session generation failed: {str(e)}")
        return RedirectResponse(url=f"/profile?zerodha_error=session_failed&message={str(e)}")


@router.post("/disconnect")
async def disconnect_zerodha(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disconnect Zerodha account
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success message
    """
    cred = db.query(ZerodhaCredential).filter(
        ZerodhaCredential.user_id == current_user.id
    ).first()
    
    if not cred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zerodha credentials not found"
        )
    
    # Invalidate session if connected
    if cred.is_connected and cred.access_token:
        try:
            api_key = decrypt_api_key(cred.api_key)
            access_token = decrypt_access_token(cred.access_token)
            client = ZerodhaClient(api_key=api_key, access_token=access_token)
            client.invalidate_session()
        except:
            pass  # Ignore errors during invalidation
    
    # Remove from cache
    remove_zerodha_client(current_user.id)
    
    # Delete credentials
    db.delete(cred)
    db.commit()
    
    return {
        "success": True,
        "message": "Zerodha account disconnected successfully"
    }


@router.get("/status", response_model=ZerodhaStatus)
async def get_zerodha_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get Zerodha connection status
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Connection status
    """
    cred = db.query(ZerodhaCredential).filter(
        ZerodhaCredential.user_id == current_user.id
    ).first()
    
    if not cred:
        return {
            "is_connected": False,
            "has_credentials": False,
            "last_connected_at": None,
            "zerodha_user_id": None,
            "token_expires_at": None,
            "needs_reauth": False
        }
    
    # Check if token needs refresh
    needs_reauth = False
    if cred.token_expires_at:
        needs_reauth = datetime.utcnow() >= cred.token_expires_at
    
    return {
        "is_connected": cred.is_connected and not needs_reauth,
        "has_credentials": True,
        "last_connected_at": cred.last_connected_at,
        "zerodha_user_id": cred.zerodha_user_id,
        "token_expires_at": cred.token_expires_at,
        "needs_reauth": needs_reauth
    }


@router.get("/holdings")
async def get_holdings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get portfolio holdings from Zerodha
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of holdings
    """
    # Get credentials
    cred = db.query(ZerodhaCredential).filter(
        ZerodhaCredential.user_id == current_user.id
    ).first()
    
    if not cred or not cred.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zerodha account not connected"
        )
    
    # Get client
    api_key = decrypt_api_key(cred.api_key)
    access_token = decrypt_access_token(cred.access_token)
    client = get_zerodha_client(current_user.id, api_key, access_token)
    
    try:
        holdings = client.get_holdings()
        return {"success": True, "holdings": holdings}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch holdings: {str(e)}"
        )


@router.get("/positions")
async def get_positions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current positions from Zerodha
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Positions data
    """
    # Get credentials
    cred = db.query(ZerodhaCredential).filter(
        ZerodhaCredential.user_id == current_user.id
    ).first()
    
    if not cred or not cred.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zerodha account not connected"
        )
    
    # Get client
    api_key = decrypt_api_key(cred.api_key)
    access_token = decrypt_access_token(cred.access_token)
    client = get_zerodha_client(current_user.id, api_key, access_token)
    
    try:
        positions = client.get_positions()
        return {"success": True, "positions": positions}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch positions: {str(e)}"
        )


@router.get("/margins")
async def get_margins(
    segment: str = Query("equity"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get account margins/balance from Zerodha
    
    Args:
        segment: equity or commodity
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Margin/balance data
    """
    # Get credentials
    cred = db.query(ZerodhaCredential).filter(
        ZerodhaCredential.user_id == current_user.id
    ).first()
    
    if not cred or not cred.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zerodha account not connected"
        )
    
    # Get client
    api_key = decrypt_api_key(cred.api_key)
    access_token = decrypt_access_token(cred.access_token)
    client = get_zerodha_client(current_user.id, api_key, access_token)
    
    try:
        margins = client.get_margins(segment)
        return {"success": True, "margins": margins}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch margins: {str(e)}"
        )

