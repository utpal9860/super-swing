"""
Database schema for pattern detection and validation
"""
import sqlite3
from pathlib import Path
from typing import Optional
from config import DB_PATH
from utils.logger import setup_logger

logger = setup_logger("database")

def create_database():
    """Create database and all required tables"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Patterns table - stores detected patterns
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patterns (
            pattern_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            exchange TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            detection_date TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            confidence_score REAL,
            price_at_detection REAL,
            volume_at_detection INTEGER,
            pattern_start_date TEXT,
            pattern_end_date TEXT,
            chart_image_path TEXT,
            
            -- Technical context
            rsi_14 REAL,
            volume_ratio REAL,
            atr_14 REAL,
            distance_from_52w_high REAL,
            distance_from_52w_low REAL,
            
            -- Validation status
            validation_status TEXT DEFAULT 'PENDING',
            human_label TEXT,
            pattern_quality INTEGER,
            outcome TEXT,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            outcome_calculated_at TIMESTAMP
        )
    ''')
    
    # Pattern outcomes table - stores actual results
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pattern_outcomes (
            outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id TEXT NOT NULL,
            
            -- Entry/Exit details
            entry_date TEXT,
            entry_price REAL,
            exit_date TEXT,
            exit_price REAL,
            
            -- Performance metrics
            gain_loss_pct REAL,
            max_gain_pct REAL,
            max_loss_pct REAL,
            days_to_target INTEGER,
            days_to_stop INTEGER,
            actual_holding_days INTEGER,
            
            -- Exit reason
            exit_reason TEXT,
            target_hit BOOLEAN,
            stop_hit BOOLEAN,
            
            -- Risk metrics
            mae REAL,  -- Max Adverse Excursion
            mfe REAL,  -- Max Favorable Excursion
            risk_reward_ratio REAL,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (pattern_id) REFERENCES patterns(pattern_id)
        )
    ''')
    
    # Features table - stores engineered features
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pattern_features (
            feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id TEXT NOT NULL,
            
            -- Stock features
            sector TEXT,
            market_cap_category TEXT,
            avg_volume_20d INTEGER,
            delivery_percentage REAL,
            historical_volatility_30d REAL,
            
            -- Market features
            nifty_trend TEXT,
            nifty_rsi REAL,
            india_vix REAL,
            fii_dii_ratio REAL,
            advance_decline_ratio REAL,
            
            -- Pattern features
            pattern_duration_days INTEGER,
            pattern_height REAL,
            pattern_height_pct REAL,
            volume_trend TEXT,
            breakout_strength REAL,
            
            -- Temporal features
            day_of_week TEXT,
            is_earnings_season BOOLEAN,
            is_derivatives_expiry_week BOOLEAN,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (pattern_id) REFERENCES patterns(pattern_id)
        )
    ''')
    
    # Stock universe table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_universe (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            sector TEXT,
            industry TEXT,
            market_cap REAL,
            is_fno BOOLEAN DEFAULT 0,
            is_nifty_50 BOOLEAN DEFAULT 0,
            is_nifty_100 BOOLEAN DEFAULT 0,
            is_nifty_200 BOOLEAN DEFAULT 0,
            liquidity_score REAL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Model predictions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS model_predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            model_version TEXT,
            
            -- Predictions
            validity_probability REAL,
            success_probability REAL,
            expected_gain REAL,
            expected_holding_days INTEGER,
            risk_reward_estimate REAL,
            
            -- Ranking
            rank_score REAL,
            recommendation TEXT,
            
            prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (pattern_id) REFERENCES patterns(pattern_id)
        )
    ''')
    
    # Model performance tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS model_performance (
            performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            model_version TEXT NOT NULL,
            
            -- Metrics
            accuracy REAL,
            precision_score REAL,
            recall REAL,
            f1_score REAL,
            roc_auc REAL,
            
            -- Regression metrics (if applicable)
            mae REAL,
            rmse REAL,
            r2_score REAL,
            
            -- Dataset info
            train_size INTEGER,
            test_size INTEGER,
            evaluation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Trading signals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trading_signals (
            signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            
            -- Signal details
            signal_date TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            entry_price REAL,
            stop_loss REAL,
            target_price REAL,
            
            -- ML predictions
            success_probability REAL,
            expected_gain_pct REAL,
            risk_reward_ratio REAL,
            
            -- Position sizing
            suggested_position_size REAL,
            suggested_quantity INTEGER,
            
            -- Status
            status TEXT DEFAULT 'ACTIVE',
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (pattern_id) REFERENCES patterns(pattern_id)
        )
    ''')
    
    # Create indices for faster queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_patterns_ticker ON patterns(ticker)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_patterns_date ON patterns(detection_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_patterns_status ON patterns(validation_status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_outcomes_pattern ON pattern_outcomes(pattern_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_features_pattern ON pattern_features(pattern_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_date ON trading_signals(signal_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_status ON trading_signals(status)')
    
    conn.commit()
    conn.close()
    
    logger.info(f"Database created successfully at {DB_PATH}")

def get_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)

def insert_pattern(pattern_data: dict) -> bool:
    """
    Insert a detected pattern into database
    
    Args:
        pattern_data: Dictionary with pattern information
    
    Returns:
        True if successful
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        columns = ', '.join(pattern_data.keys())
        placeholders = ', '.join(['?' for _ in pattern_data])
        query = f'INSERT OR REPLACE INTO patterns ({columns}) VALUES ({placeholders})'
        
        cursor.execute(query, list(pattern_data.values()))
        conn.commit()
        conn.close()
        
        return True
    
    except Exception as e:
        logger.error(f"Error inserting pattern: {e}")
        return False

def update_pattern_validation(pattern_id: str, validation_data: dict) -> bool:
    """
    Update pattern validation status
    
    Args:
        pattern_id: Pattern ID
        validation_data: Dictionary with validation info
    
    Returns:
        True if successful
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        updates = ', '.join([f'{k} = ?' for k in validation_data.keys()])
        query = f'UPDATE patterns SET {updates} WHERE pattern_id = ?'
        
        values = list(validation_data.values()) + [pattern_id]
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        
        return True
    
    except Exception as e:
        logger.error(f"Error updating pattern validation: {e}")
        return False

def get_pending_patterns(limit: int = 100) -> list:
    """
    Get patterns pending review
    
    Args:
        limit: Maximum number of patterns to return
    
    Returns:
        List of pattern dictionaries
    """
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = '''
            SELECT * FROM patterns 
            WHERE validation_status = 'PENDING'
            ORDER BY detection_date DESC
            LIMIT ?
        '''
        
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        
        patterns = [dict(row) for row in rows]
        conn.close()
        
        return patterns
    
    except Exception as e:
        logger.error(f"Error fetching pending patterns: {e}")
        return []

def get_validated_patterns() -> list:
    """
    Get all validated patterns
    
    Returns:
        List of validated pattern dictionaries
    """
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = '''
            SELECT p.*, o.*
            FROM patterns p
            LEFT JOIN pattern_outcomes o ON p.pattern_id = o.pattern_id
            WHERE p.validation_status = 'VALID'
            ORDER BY p.detection_date DESC
        '''
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        patterns = [dict(row) for row in rows]
        conn.close()
        
        return patterns
    
    except Exception as e:
        logger.error(f"Error fetching validated patterns: {e}")
        return []

if __name__ == "__main__":
    create_database()
    print("Database schema created successfully!")

