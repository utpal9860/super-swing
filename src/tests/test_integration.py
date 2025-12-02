"""Integration tests for complete pipeline."""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from scanner.indicators import supertrend
from scanner.signal_detector import detect_signals_for_symbol, find_buy_sell_pairs
from scanner.analyser import filter_trades, compute_summary_stats, threshold_analysis


def create_realistic_data(n=100, seed=42):
    """Create realistic synthetic stock data."""
    np.random.seed(seed)
    dates = pd.date_range('2022-01-01', periods=n, freq='W')
    
    # Generate price with trend and noise
    trend = np.linspace(100, 150, n)
    noise = np.cumsum(np.random.randn(n) * 3)
    close_prices = trend + noise
    
    # Ensure positive prices
    close_prices = np.maximum(close_prices, 50)
    
    df = pd.DataFrame({
        'Date': dates,
        'Open': close_prices + np.random.randn(n) * 0.5,
        'High': close_prices + np.abs(np.random.randn(n) * 2),
        'Low': close_prices - np.abs(np.random.randn(n) * 2),
        'Close': close_prices,
        'Volume': np.random.randint(1000000, 10000000, n)
    })
    
    return df


def test_full_pipeline():
    """Test complete analysis pipeline."""
    df = create_realistic_data(100)
    
    # Step 1: Compute SuperTrend
    df_st = supertrend(df, atr_period=10, multiplier=3.0)
    
    assert 'ST' in df_st.columns
    assert 'ST_dir' in df_st.columns
    
    # Step 2: Find trades
    trades = find_buy_sell_pairs(df_st, 'TEST.NS')
    
    assert isinstance(trades, list)
    
    # Step 3: Convert to DataFrame
    if trades:
        trades_df = pd.DataFrame(trades)
        
        # Step 4: Compute statistics
        stats = compute_summary_stats(trades_df)
        
        assert 'total_trades' in stats
        assert 'mean_return' in stats
        assert 'win_rate' in stats
        
        # Step 5: Filter trades
        filtered = filter_trades(trades_df, abs_threshold=10.0)
        
        # Filtered should have <= original
        assert len(filtered) <= len(trades_df)


def test_detect_signals_wrapper():
    """Test the complete detect_signals_for_symbol wrapper."""
    df = create_realistic_data(100)
    
    df_st, trades = detect_signals_for_symbol('TEST', df, atr_period=10, multiplier=3.0)
    
    # Check that both outputs are correct
    assert 'ST' in df_st.columns
    assert 'ST_dir' in df_st.columns
    assert isinstance(trades, list)


def test_threshold_analysis_integration():
    """Test threshold analysis with real pipeline."""
    df = create_realistic_data(150)
    
    df_st, trades = detect_signals_for_symbol('TEST', df, atr_period=10, multiplier=3.0)
    
    if trades:
        trades_df = pd.DataFrame(trades)
        
        # Run threshold analysis
        threshold_stats = threshold_analysis(trades_df, thresholds=[5, 10, 15, 20])
        
        # Should have entries for each threshold
        assert 'within_5pct' in threshold_stats
        assert 'within_10pct' in threshold_stats
        
        # Percentages should be between 0 and 100
        for key, value in threshold_stats.items():
            assert 0 <= value['percentage'] <= 100


def test_multiple_symbols_integration():
    """Test processing multiple symbols."""
    symbols = ['SYM1', 'SYM2', 'SYM3']
    all_trades = []
    
    for symbol in symbols:
        df = create_realistic_data(100, seed=hash(symbol) % 10000)
        df_st, trades = detect_signals_for_symbol(symbol, df, atr_period=10, multiplier=3.0)
        all_trades.extend(trades)
    
    if all_trades:
        trades_df = pd.DataFrame(all_trades)
        
        # Should have trades from multiple symbols
        unique_symbols = trades_df['symbol'].nunique()
        assert unique_symbols > 1
        
        # Compute combined statistics
        stats = compute_summary_stats(trades_df)
        
        assert stats['total_trades'] > 0
        assert stats['total_symbols'] > 1


def test_edge_case_insufficient_data():
    """Test with insufficient data."""
    # Very short dataset
    df = create_realistic_data(5)
    
    # Should not crash, but may not produce valid results
    df_st = supertrend(df, atr_period=10, multiplier=3.0)
    
    # Most values will be NaN
    assert df_st['ST'].isna().sum() > 0


def test_edge_case_all_nan():
    """Test handling of data with NaN values."""
    df = create_realistic_data(50)
    
    # Introduce some NaN values
    df.loc[10:15, 'Close'] = np.nan
    
    # Should handle NaN gracefully
    df_st = supertrend(df, atr_period=10, multiplier=3.0)
    
    # Should still produce some valid values
    assert df_st['ST'].notna().sum() > 0

