"""Tests for indicator calculations."""
import pytest
import pandas as pd
import numpy as np
from scanner.indicators import atr, supertrend


def create_test_data(n=100):
    """Create synthetic OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=n, freq='W')
    
    close_prices = 100 + np.cumsum(np.random.randn(n) * 2)
    high_prices = close_prices + np.abs(np.random.randn(n) * 1)
    low_prices = close_prices - np.abs(np.random.randn(n) * 1)
    open_prices = close_prices + np.random.randn(n) * 0.5
    volume = np.random.randint(1000000, 10000000, n)
    
    df = pd.DataFrame({
        'Date': dates,
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volume
    })
    
    return df


def test_atr_basic():
    """Test ATR calculation."""
    df = create_test_data(50)
    
    atr_values = atr(df, period=10)
    
    # ATR should be NaN for first period-1 values
    assert pd.isna(atr_values.iloc[0])
    
    # ATR should be positive
    assert (atr_values.dropna() > 0).all()
    
    # ATR length should match dataframe
    assert len(atr_values) == len(df)


def test_supertrend_basic():
    """Test SuperTrend calculation."""
    df = create_test_data(100)
    
    df_st = supertrend(df, atr_period=10, multiplier=3.0)
    
    # Check that required columns exist
    assert 'ST' in df_st.columns
    assert 'ST_dir' in df_st.columns
    assert 'ATR' in df_st.columns
    
    # Check that ST_dir is either 1 or -1 (where not NaN)
    valid_dirs = df_st['ST_dir'].dropna()
    assert set(valid_dirs.unique()).issubset({-1, 1})
    
    # Check that ST values are positive
    assert (df_st['ST'].dropna() > 0).all()


def test_supertrend_trend_change():
    """Test that SuperTrend detects trend changes."""
    # Create data with clear trend change
    dates = pd.date_range('2023-01-01', periods=50, freq='W')
    
    # Uptrend first 25 weeks, then downtrend
    close_prices = np.concatenate([
        np.linspace(100, 150, 25),  # Uptrend
        np.linspace(150, 100, 25)   # Downtrend
    ])
    
    df = pd.DataFrame({
        'Date': dates,
        'Open': close_prices - 1,
        'High': close_prices + 2,
        'Low': close_prices - 2,
        'Close': close_prices,
        'Volume': [1000000] * 50
    })
    
    df_st = supertrend(df, atr_period=10, multiplier=3.0)
    
    # There should be at least one trend change
    dir_changes = (df_st['ST_dir'].diff() != 0).sum()
    assert dir_changes > 0
    
    # Both directions should appear
    assert -1 in df_st['ST_dir'].values
    assert 1 in df_st['ST_dir'].values


def test_supertrend_different_parameters():
    """Test SuperTrend with different parameters."""
    df = create_test_data(100)
    
    df_st1 = supertrend(df, atr_period=7, multiplier=2.0)
    df_st2 = supertrend(df, atr_period=14, multiplier=4.0)
    
    # Different parameters should give different results
    assert not df_st1['ST'].equals(df_st2['ST'])
    
    # But structure should be the same
    assert len(df_st1) == len(df_st2)
    assert set(df_st1.columns) == set(df_st2.columns)

