"""
API Credentials Models
Secure storage for AI providers and brokerage connections
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum
from sqlalchemy.sql import func
from database import Base
import enum


class ProviderType(enum.Enum):
    """Type of API provider"""
    AI_AGENT = "ai_agent"
    BROKERAGE = "brokerage"


class AIProvider(enum.Enum):
    """Supported AI providers"""
    GEMINI = "gemini"
    CLAUDE = "claude"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"


class BrokerageProvider(enum.Enum):
    """Supported brokerage providers"""
    ZERODHA = "zerodha"
    UPSTOX = "upstox"
    ANGELONE = "angelone"
    FYERS = "fyers"
    IIFL = "iifl"


class AIAgentCredential(Base):
    """
    Table for AI Agent API credentials
    Stores API keys for AI providers (Gemini, Claude, OpenAI, DeepSeek)
    """
    __tablename__ = "ai_agent_credentials"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    
    # Provider details
    provider = Column(String, nullable=False)  # gemini, claude, openai, deepseek
    model = Column(String, nullable=True)  # gemini-1.5-flash, claude-3-opus, gpt-4, etc.
    
    # Credentials (encrypted in production)
    api_key = Column(Text, nullable=False)  # Encrypted API key
    
    # Status
    is_enabled = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Default AI provider for this user
    
    # Usage tracking
    total_requests = Column(Integer, default=0)
    total_cost = Column(Integer, default=0)  # Cost in cents/paise
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Optional key expiration
    
    # Notes
    notes = Column(Text, nullable=True)  # User notes about this credential


class BrokerageCredential(Base):
    """
    Table for Brokerage API credentials
    Stores API credentials for brokers (Zerodha, Upstox, Angel One, etc.)
    """
    __tablename__ = "brokerage_credentials"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    
    # Provider details
    provider = Column(String, nullable=False)  # zerodha, upstox, angelone, fyers, iifl
    
    # Credentials (encrypted in production)
    api_key = Column(Text, nullable=False)  # Encrypted API key
    api_secret = Column(Text, nullable=True)  # Encrypted API secret (if required)
    client_id = Column(String, nullable=True)  # Client/User ID
    
    # Authentication tokens (encrypted, temporary)
    access_token = Column(Text, nullable=True)  # OAuth access token
    refresh_token = Column(Text, nullable=True)  # OAuth refresh token
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_enabled = Column(Boolean, default=True)
    is_connected = Column(Boolean, default=False)  # Connection status
    live_trading_enabled = Column(Boolean, default=False)  # Enable live orders
    
    # Usage tracking
    total_orders = Column(Integer, default=0)
    total_trades = Column(Integer, default=0)
    last_order_at = Column(DateTime(timezone=True), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Connection details
    user_name = Column(String, nullable=True)  # Broker account name
    user_email = Column(String, nullable=True)  # Broker account email
    account_type = Column(String, nullable=True)  # individual, corporate, etc.
    
    # Notes
    notes = Column(Text, nullable=True)  # User notes about this credential


class APIUsageLog(Base):
    """
    Log for API usage tracking
    Tracks every API call for both AI and brokerage
    """
    __tablename__ = "api_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    
    # API details
    provider_type = Column(String, nullable=False)  # ai_agent or brokerage
    provider_name = Column(String, nullable=False)  # gemini, zerodha, etc.
    credential_id = Column(Integer, nullable=False)  # Foreign key to credential table
    
    # Request details
    endpoint = Column(String, nullable=True)  # API endpoint called
    method = Column(String, nullable=True)  # GET, POST, etc.
    request_type = Column(String, nullable=True)  # analyze_trade, place_order, etc.
    
    # Response details
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)  # Response time in milliseconds
    success = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    
    # Cost tracking
    cost_amount = Column(Integer, nullable=True)  # Cost in cents/paise
    tokens_used = Column(Integer, nullable=True)  # For AI APIs
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)


class CredentialAuditLog(Base):
    """
    Audit log for credential changes
    Tracks when credentials are added, updated, or deleted
    """
    __tablename__ = "credential_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    
    # What changed
    provider_type = Column(String, nullable=False)  # ai_agent or brokerage
    provider_name = Column(String, nullable=False)
    credential_id = Column(Integer, nullable=False)
    
    # Action details
    action = Column(String, nullable=False)  # created, updated, deleted, enabled, disabled
    field_changed = Column(String, nullable=True)  # Which field was changed
    old_value = Column(Text, nullable=True)  # Old value (masked for sensitive fields)
    new_value = Column(Text, nullable=True)  # New value (masked for sensitive fields)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    notes = Column(Text, nullable=True)











