"""Tests for signal detection and pairing."""
import pytest
import pandas as pd
import numpy as np
from scanner.signal_detector import find_buy_sell_pairs


def create_signal_data():
    """Create test data with known buy/sell signals."""
    dates = pd.date_range('2023-01-01', periods=20, freq='W')
    
    # Create a pattern: downtrend → uptrend → downtrend
    # -1, -1, -1, 1, 1, 1, 1, -1, -1, -1, 1, 1, 1, -1, -1, 1, 1, 1, 1, 1
    st_dir = [-1, -1, -1, 1, 1, 1, 1, -1, -1, -1, 1, 1, 1, -1, -1, 1, 1, 1, 1, 1]
    
    close_prices = [100, 98, 96, 95, 100, 105, 110, 108, 105, 102, 103, 108, 112, 110, 107, 108, 112, 115, 118, 120]
    
    df = pd.DataFrame({
        'Date': dates,
        'Close': close_prices,
        'ST_dir': st_dir,
        'Open': close_prices,
        'High': [p + 2 for p in close_prices],
        'Low': [p - 2 for p in close_prices],
        'Volume': [1000000] * 20
    })
    
    return df


def test_find_buy_sell_pairs_basic():
    """Test basic buy/sell pair detection."""
    df = create_signal_data()
    
    trades = find_buy_sell_pairs(df, 'TEST')
    
    # Should find multiple trades
    assert len(trades) > 0
    
    # Each trade should have required fields
    for trade in trades:
        assert 'symbol' in trade
        assert 'buy_date' in trade
        assert 'buy_price' in trade
        assert 'sell_date' in trade
        assert 'sell_price' in trade
        assert 'pct_change' in trade
        assert 'weeks_held' in trade


def test_buy_sell_sequence():
    """Test that buys and sells alternate correctly."""
    df = create_signal_data()
    
    trades = find_buy_sell_pairs(df, 'TEST', include_open=False)
    
    # All trades should have both buy and sell
    for trade in trades:
        assert trade['buy_date'] is not None
        assert trade['sell_date'] is not None
        assert trade['buy_date'] < trade['sell_date']


def test_percentage_calculation():
    """Test that percentage change is calculated correctly."""
    df = create_signal_data()
    
    trades = find_buy_sell_pairs(df, 'TEST')
    
    for trade in trades:
        if trade['pct_change'] is not None:
            expected_pct = ((trade['sell_price'] - trade['buy_price']) / trade['buy_price']) * 100
            assert abs(trade['pct_change'] - expected_pct) < 0.01


def test_open_trade_handling():
    """Test handling of open trades at data end."""
    # Create data that ends in an uptrend (open buy)
    dates = pd.date_range('2023-01-01', periods=10, freq='W')
    st_dir = [-1, -1, 1, 1, 1, 1, 1, 1, 1, 1]  # Buy signal at index 2, no sell
    close_prices = [100, 98, 95, 100, 105, 110, 115, 120, 125, 130]
    
    df = pd.DataFrame({
        'Date': dates,
        'Close': close_prices,
        'ST_dir': st_dir,
        'Open': close_prices,
        'High': [p + 2 for p in close_prices],
        'Low': [p - 2 for p in close_prices],
        'Volume': [1000000] * 10
    })
    
    # Without include_open
    trades_no_open = find_buy_sell_pairs(df, 'TEST', include_open=False)
    
    # With include_open
    trades_with_open = find_buy_sell_pairs(df, 'TEST', include_open=True)
    
    # With include_open should have more trades
    assert len(trades_with_open) >= len(trades_no_open)
    
    # Last trade in with_open should have None sell_date
    if len(trades_with_open) > 0:
        last_trade = trades_with_open[-1]
        if last_trade['sell_date'] is None:
            assert last_trade['pct_change'] is None


def test_no_signals():
    """Test with data that has no signals."""
    dates = pd.date_range('2023-01-01', periods=10, freq='W')
    
    # All downtrend, no buy signals
    df = pd.DataFrame({
        'Date': dates,
        'Close': range(100, 110),
        'ST_dir': [-1] * 10,
        'Open': range(100, 110),
        'High': range(102, 112),
        'Low': range(98, 108),
        'Volume': [1000000] * 10
    })
    
    trades = find_buy_sell_pairs(df, 'TEST')
    
    # Should return empty list
    assert len(trades) == 0


def test_multiple_complete_cycles():
    """Test detection of multiple complete buy→sell cycles."""
    dates = pd.date_range('2023-01-01', periods=30, freq='W')
    
    # Create multiple cycles: down→up→down→up→down→up→down
    st_dir = (
        [-1] * 3 +  # Down
        [1] * 4 +   # Up (buy at index 3)
        [-1] * 4 +  # Down (sell at index 7)
        [1] * 5 +   # Up (buy at index 11)
        [-1] * 4 +  # Down (sell at index 16)
        [1] * 6 +   # Up (buy at index 20)
        [-1] * 4    # Down (sell at index 26)
    )
    
    close_prices = list(range(100, 130))
    
    df = pd.DataFrame({
        'Date': dates,
        'Close': close_prices,
        'ST_dir': st_dir,
        'Open': close_prices,
        'High': [p + 2 for p in close_prices],
        'Low': [p - 2 for p in close_prices],
        'Volume': [1000000] * 30
    })
    
    trades = find_buy_sell_pairs(df, 'TEST', include_open=False)
    
    # Should find 3 complete cycles
    assert len(trades) == 3

