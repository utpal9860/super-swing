"""
Authentication utilities for user management
"""
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from passlib.hash import bcrypt_sha256
from jose import JWTError, jwt
import secrets
import os

# Security configuration
# Use fixed secret from environment when available to keep tokens valid across restarts
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    import warnings
    warnings.warn(
        "JWT_SECRET_KEY not set in environment! Tokens will be invalid after server restart. "
        "Set JWT_SECRET_KEY in .env file for persistent authentication."
    )
    SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password hashing context
# Use bcrypt_sha256 to avoid bcrypt's 72-byte password limit while keeping bcrypt for legacy hashes
pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password
    
    Args:
        plain_password: The plain text password
        hashed_password: The hashed password to check against
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password for storing
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    # Explicitly use bcrypt_sha256 to avoid bcrypt's 72-byte limit
    return bcrypt_sha256.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Dictionary of data to encode in the token
        expires_delta: Optional expiration time delta
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT access token
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token data dict, or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_user_id() -> str:
    """
    Generate a unique user ID
    
    Returns:
        Random user ID string
    """
    return f"user_{secrets.token_urlsafe(16)}"


def generate_order_id() -> str:
    """
    Generate a unique order ID
    
    Returns:
        Random order ID string
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    random_part = secrets.token_urlsafe(8)
    return f"ORD_{timestamp}_{random_part}"

