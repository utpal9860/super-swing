"""
Database configuration and models for SuperTrend Trading Platform
"""
from sqlalchemy import create_engine, Column, String, Boolean, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from pathlib import Path

# Get absolute path to database file (always in webapp/data/)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "trading_platform.db"

# Database URL - SQLite for simplicity
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

# Create engine
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# Models
class User(Base):
    """User model for authentication"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    
    # Relationships
    zerodha_cred = relationship("ZerodhaCredential", back_populates="user", uselist=False)
    feature_flags = relationship("FeatureFlags", back_populates="user", uselist=False)
    order_logs = relationship("OrderLog", back_populates="user")


class ZerodhaCredential(Base):
    """Zerodha API credentials (encrypted)"""
    __tablename__ = "zerodha_credentials"
    
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    api_key = Column(String, nullable=False)  # Encrypted
    api_secret = Column(String)  # Encrypted (optional, can be server-side only)
    access_token = Column(String)  # Encrypted, expires daily
    request_token = Column(String)  # Temporary, for OAuth flow
    token_expires_at = Column(DateTime)
    is_connected = Column(Boolean, default=False)
    last_connected_at = Column(DateTime)
    zerodha_user_id = Column(String)  # Zerodha's user ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="zerodha_cred")


class FeatureFlags(Base):
    """Feature flags and risk management settings per user"""
    __tablename__ = "feature_flags"
    
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    
    # Trading flags
    live_trading_enabled = Column(Boolean, default=False)
    auto_order_placement = Column(Boolean, default=False)
    
    # Risk management
    max_order_value = Column(Float, default=100000.0)  # ₹1 lakh max per order
    max_daily_orders = Column(Integer, default=10)
    max_open_positions = Column(Integer, default=5)
    risk_per_trade_pct = Column(Float, default=2.0)  # 2% of capital
    
    # Notifications
    email_notifications = Column(Boolean, default=True)
    order_notifications = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="feature_flags")


class OrderLog(Base):
    """Log of all order attempts and executions"""
    __tablename__ = "order_logs"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Order details
    order_id = Column(String)  # Zerodha order ID (if placed)
    symbol = Column(String, nullable=False)
    exchange = Column(String, default="NSE")
    transaction_type = Column(String, nullable=False)  # BUY/SELL
    quantity = Column(Integer, nullable=False)
    price = Column(Float)
    trigger_price = Column(Float)
    order_type = Column(String, nullable=False)  # MARKET/LIMIT/SL/SL-M
    product = Column(String, default="CNC")  # CNC/MIS/NRML
    validity = Column(String, default="DAY")
    
    # Status tracking
    status = Column(String, nullable=False)  # PENDING/PLACED/COMPLETE/REJECTED/CANCELLED
    status_message = Column(Text)
    error_message = Column(Text)
    
    # Trading details
    filled_quantity = Column(Integer, default=0)
    average_price = Column(Float)
    
    # Metadata
    placed_at = Column(DateTime)
    completed_at = Column(DateTime)
    zerodha_response = Column(Text)  # JSON response from Zerodha
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="order_logs")


def get_db():
    """Dependency for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables"""
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("[OK] Database initialized successfully")


if __name__ == "__main__":
    # Initialize database when run directly
    init_db()

