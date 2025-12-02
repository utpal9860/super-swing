-- Migration: Create API Credentials Tables
-- Date: 2025-10-29
-- Description: Separate tables for AI providers and brokerage connections

-- ====================================
-- Table 1: AI Agent Credentials
-- ====================================

CREATE TABLE IF NOT EXISTS ai_agent_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    
    -- Provider details
    provider VARCHAR(50) NOT NULL,  -- gemini, claude, openai, deepseek
    model VARCHAR(100),  -- gemini-1.5-flash, claude-3-opus, gpt-4, etc.
    
    -- Credentials (should be encrypted in production)
    api_key TEXT NOT NULL,
    
    -- Status
    is_enabled BOOLEAN DEFAULT 1,
    is_default BOOLEAN DEFAULT 0,  -- Default AI provider for this user
    
    -- Usage tracking
    total_requests INTEGER DEFAULT 0,
    total_cost INTEGER DEFAULT 0,  -- Cost in paise (₹0.01)
    last_used_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    expires_at TIMESTAMP,  -- Optional key expiration
    
    -- Notes
    notes TEXT,
    
    -- Indexes
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_user_provider UNIQUE (user_id, provider)
);

CREATE INDEX idx_ai_credentials_user ON ai_agent_credentials(user_id);
CREATE INDEX idx_ai_credentials_provider ON ai_agent_credentials(provider);
CREATE INDEX idx_ai_credentials_enabled ON ai_agent_credentials(is_enabled);


-- ====================================
-- Table 2: Brokerage Credentials
-- ====================================

CREATE TABLE IF NOT EXISTS brokerage_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    
    -- Provider details
    provider VARCHAR(50) NOT NULL,  -- zerodha, upstox, angelone, fyers, iifl
    
    -- Credentials (should be encrypted in production)
    api_key TEXT NOT NULL,
    api_secret TEXT,  -- Some brokers need secret
    client_id VARCHAR(100),  -- Client/User ID
    
    -- Authentication tokens (temporary, encrypted)
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,
    
    -- Status
    is_enabled BOOLEAN DEFAULT 1,
    is_connected BOOLEAN DEFAULT 0,
    live_trading_enabled BOOLEAN DEFAULT 0,
    
    -- Usage tracking
    total_orders INTEGER DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    last_order_at TIMESTAMP,
    last_synced_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    
    -- Connection details
    user_name VARCHAR(255),  -- Broker account name
    user_email VARCHAR(255),  -- Broker account email
    account_type VARCHAR(50),  -- individual, corporate
    
    -- Notes
    notes TEXT,
    
    -- Indexes
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_user_broker UNIQUE (user_id, provider)
);

CREATE INDEX idx_broker_credentials_user ON brokerage_credentials(user_id);
CREATE INDEX idx_broker_credentials_provider ON brokerage_credentials(provider);
CREATE INDEX idx_broker_credentials_enabled ON brokerage_credentials(is_enabled);


-- ====================================
-- Table 3: API Usage Logs
-- ====================================

CREATE TABLE IF NOT EXISTS api_usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    
    -- API details
    provider_type VARCHAR(20) NOT NULL,  -- ai_agent or brokerage
    provider_name VARCHAR(50) NOT NULL,  -- gemini, zerodha, etc.
    credential_id INTEGER NOT NULL,
    
    -- Request details
    endpoint VARCHAR(255),
    method VARCHAR(10),  -- GET, POST, PUT, DELETE
    request_type VARCHAR(100),  -- analyze_trade, place_order, etc.
    
    -- Response details
    status_code INTEGER,
    response_time_ms INTEGER,  -- Response time in milliseconds
    success BOOLEAN DEFAULT 0,
    error_message TEXT,
    
    -- Cost tracking
    cost_amount INTEGER,  -- Cost in paise
    tokens_used INTEGER,  -- For AI APIs
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_usage_logs_user ON api_usage_logs(user_id);
CREATE INDEX idx_usage_logs_provider ON api_usage_logs(provider_name);
CREATE INDEX idx_usage_logs_created ON api_usage_logs(created_at);
CREATE INDEX idx_usage_logs_success ON api_usage_logs(success);


-- ====================================
-- Table 4: Credential Audit Logs
-- ====================================

CREATE TABLE IF NOT EXISTS credential_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    
    -- What changed
    provider_type VARCHAR(20) NOT NULL,  -- ai_agent or brokerage
    provider_name VARCHAR(50) NOT NULL,
    credential_id INTEGER NOT NULL,
    
    -- Action details
    action VARCHAR(50) NOT NULL,  -- created, updated, deleted, enabled, disabled
    field_changed VARCHAR(100),
    old_value TEXT,  -- Masked for sensitive fields
    new_value TEXT,  -- Masked for sensitive fields
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    notes TEXT,
    
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_audit_logs_user ON credential_audit_logs(user_id);
CREATE INDEX idx_audit_logs_credential ON credential_audit_logs(credential_id);
CREATE INDEX idx_audit_logs_action ON credential_audit_logs(action);
CREATE INDEX idx_audit_logs_created ON credential_audit_logs(created_at);


-- ====================================
-- Migrate Existing Data (if any)
-- ====================================

-- Note: If you have existing AI config in localStorage or other tables,
-- you'll need to manually migrate it to these new tables.
-- This is intentionally left empty as data is currently in localStorage.


-- ====================================
-- Sample Data (for testing)
-- ====================================

-- Insert sample AI credentials (replace with actual encrypted keys)
-- INSERT INTO ai_agent_credentials (user_id, provider, model, api_key, is_enabled, is_default)
-- VALUES (1, 'gemini', 'gemini-1.5-flash', 'ENCRYPTED_KEY_HERE', 1, 1);

-- Insert sample brokerage credentials (replace with actual encrypted keys)
-- INSERT INTO brokerage_credentials (user_id, provider, api_key, api_secret, client_id, is_enabled)
-- VALUES (1, 'zerodha', 'ENCRYPTED_API_KEY', 'ENCRYPTED_SECRET', 'CLIENT123', 1);











