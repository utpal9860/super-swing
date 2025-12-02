"""Analysis and filtering of trade results."""
import pandas as pd
import numpy as np
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


def filter_trades(trades_df, abs_threshold=10.0, min_pct=None, max_pct=None):
    """
    Filter trades based on percentage change thresholds.
    
    Args:
        trades_df: DataFrame with trade data
        abs_threshold: Filter trades where |pct_change| < abs_threshold
        min_pct: Minimum percentage change (optional)
        max_pct: Maximum percentage change (optional)
        
    Returns:
        pandas.DataFrame: Filtered trades
    """
    if trades_df.empty:
        return trades_df
    
    filtered = trades_df.copy()
    
    # Remove trades with missing pct_change (open trades)
    filtered = filtered.dropna(subset=['pct_change'])
    
    # Apply absolute threshold
    if abs_threshold is not None:
        filtered['abs_pct'] = filtered['pct_change'].abs()
        filtered = filtered[filtered['abs_pct'] < abs_threshold]
    
    # Apply min/max thresholds
    if min_pct is not None:
        filtered = filtered[filtered['pct_change'] >= min_pct]
    if max_pct is not None:
        filtered = filtered[filtered['pct_change'] <= max_pct]
    
    logger.info(f"Filtered to {len(filtered)} trades from {len(trades_df)}")
    return filtered


def compute_summary_stats(trades_df) -> Dict:
    """
    Compute summary statistics for trades.
    
    Args:
        trades_df: DataFrame with trade data
        
    Returns:
        dict: Summary statistics
    """
    if trades_df.empty:
        return {
            'total_trades': 0,
            'error': 'No trades found'
        }
    
    # Remove rows with missing pct_change
    valid_trades = trades_df.dropna(subset=['pct_change'])
    
    if len(valid_trades) == 0:
        return {
            'total_trades': len(trades_df),
            'completed_trades': 0,
            'error': 'No completed trades'
        }
    
    stats = {
        'total_trades': len(valid_trades),
        'total_symbols': trades_df['symbol'].nunique() if 'symbol' in trades_df.columns else 0,
        
        # Return statistics
        'mean_return': valid_trades['pct_change'].mean(),
        'median_return': valid_trades['pct_change'].median(),
        'std_return': valid_trades['pct_change'].std(),
        'min_return': valid_trades['pct_change'].min(),
        'max_return': valid_trades['pct_change'].max(),
        
        # Percentiles
        'q25_return': valid_trades['pct_change'].quantile(0.25),
        'q75_return': valid_trades['pct_change'].quantile(0.75),
        
        # Win/Loss
        'winning_trades': len(valid_trades[valid_trades['pct_change'] > 0]),
        'losing_trades': len(valid_trades[valid_trades['pct_change'] < 0]),
        'win_rate': (len(valid_trades[valid_trades['pct_change'] > 0]) / len(valid_trades)) * 100,
        
        # Holding period
        'mean_weeks_held': valid_trades['weeks_held'].mean() if 'weeks_held' in valid_trades.columns else None,
        'median_weeks_held': valid_trades['weeks_held'].median() if 'weeks_held' in valid_trades.columns else None,
        'min_weeks_held': valid_trades['weeks_held'].min() if 'weeks_held' in valid_trades.columns else None,
        'max_weeks_held': valid_trades['weeks_held'].max() if 'weeks_held' in valid_trades.columns else None,
    }
    
    return stats


def analyze_by_sector(trades_df) -> Dict:
    """
    Analyze trades grouped by sector.
    
    Args:
        trades_df: DataFrame with trade data (must have 'sector' column)
        
    Returns:
        dict: Sector-wise statistics
    """
    if 'sector' not in trades_df.columns or trades_df.empty:
        return {}
    
    sector_stats = {}
    
    for sector in trades_df['sector'].dropna().unique():
        sector_trades = trades_df[trades_df['sector'] == sector]
        valid_sector_trades = sector_trades.dropna(subset=['pct_change'])
        
        if len(valid_sector_trades) > 0:
            sector_stats[sector] = {
                'total_trades': len(valid_sector_trades),
                'mean_return': valid_sector_trades['pct_change'].mean(),
                'median_return': valid_sector_trades['pct_change'].median(),
                'win_rate': (len(valid_sector_trades[valid_sector_trades['pct_change'] > 0]) / 
                           len(valid_sector_trades)) * 100,
                'mean_weeks_held': valid_sector_trades['weeks_held'].mean() if 'weeks_held' in valid_sector_trades.columns else None,
            }
    
    return sector_stats


def threshold_analysis(trades_df, thresholds=[5, 10, 15, 20]) -> Dict:
    """
    Analyze how many trades fall within different percentage thresholds.
    
    Args:
        trades_df: DataFrame with trade data
        thresholds: List of percentage thresholds to analyze
        
    Returns:
        dict: Count and percentage for each threshold
    """
    if trades_df.empty:
        return {}
    
    valid_trades = trades_df.dropna(subset=['pct_change'])
    total = len(valid_trades)
    
    if total == 0:
        return {}
    
    threshold_stats = {}
    
    for threshold in sorted(thresholds):
        count = len(valid_trades[valid_trades['pct_change'].abs() < threshold])
        percentage = (count / total) * 100
        
        threshold_stats[f'within_{threshold}pct'] = {
            'count': count,
            'percentage': percentage
        }
    
    return threshold_stats


def get_top_performers(trades_df, top_n=10, by='pct_change', ascending=False):
    """
    Get top performing trades.
    
    Args:
        trades_df: DataFrame with trade data
        top_n: Number of top trades to return
        by: Column to sort by (default: 'pct_change')
        ascending: Sort order
        
    Returns:
        pandas.DataFrame: Top trades
    """
    if trades_df.empty:
        return trades_df
    
    valid_trades = trades_df.dropna(subset=[by])
    return valid_trades.sort_values(by=by, ascending=ascending).head(top_n)


def profit_loss_buckets(trades_df) -> Dict:
    """
    Analyze trades by profit/loss percentage buckets.
    
    Buckets:
    - Profits: 0-1%, 1-5%, 5-10%, 10%+
    - Losses: 0-1%, 1-5%, 5-10%, 10%+
    
    Args:
        trades_df: DataFrame with trade data
        
    Returns:
        dict: Bucket analysis with counts and percentages
    """
    if trades_df.empty:
        return {}
    
    valid_trades = trades_df.dropna(subset=['pct_change'])
    total = len(valid_trades)
    
    if total == 0:
        return {}
    
    # Separate profits and losses
    profits = valid_trades[valid_trades['pct_change'] > 0]
    losses = valid_trades[valid_trades['pct_change'] < 0]
    neutral = valid_trades[valid_trades['pct_change'] == 0]
    
    result = {
        'profit_buckets': {},
        'loss_buckets': {},
        'neutral': {
            'count': len(neutral),
            'percentage': (len(neutral) / total) * 100 if total > 0 else 0
        }
    }
    
    # Define profit buckets
    profit_ranges = [
        ('0-1%', 0, 1),
        ('1-5%', 1, 5),
        ('5-10%', 5, 10),
        ('10%+', 10, float('inf'))
    ]
    
    # Analyze profit buckets
    for label, min_pct, max_pct in profit_ranges:
        if max_pct == float('inf'):
            bucket_trades = profits[profits['pct_change'] >= min_pct]
        else:
            bucket_trades = profits[(profits['pct_change'] >= min_pct) & (profits['pct_change'] < max_pct)]
        
        count = len(bucket_trades)
        result['profit_buckets'][label] = {
            'count': count,
            'percentage_of_total': (count / total) * 100 if total > 0 else 0,
            'percentage_of_profits': (count / len(profits)) * 100 if len(profits) > 0 else 0
        }
    
    # Define loss buckets (using absolute values)
    loss_ranges = [
        ('0-1%', 0, 1),
        ('1-5%', 1, 5),
        ('5-10%', 5, 10),
        ('10%+', 10, float('inf'))
    ]
    
    # Analyze loss buckets
    losses_abs = losses.copy()
    losses_abs['pct_change_abs'] = losses_abs['pct_change'].abs()
    
    for label, min_pct, max_pct in loss_ranges:
        if max_pct == float('inf'):
            bucket_trades = losses_abs[losses_abs['pct_change_abs'] >= min_pct]
        else:
            bucket_trades = losses_abs[(losses_abs['pct_change_abs'] >= min_pct) & 
                                       (losses_abs['pct_change_abs'] < max_pct)]
        
        count = len(bucket_trades)
        result['loss_buckets'][label] = {
            'count': count,
            'percentage_of_total': (count / total) * 100 if total > 0 else 0,
            'percentage_of_losses': (count / len(losses)) * 100 if len(losses) > 0 else 0
        }
    
    # Add summary
    result['summary'] = {
        'total_trades': total,
        'total_profits': len(profits),
        'total_losses': len(losses),
        'total_neutral': len(neutral),
        'profit_percentage': (len(profits) / total) * 100 if total > 0 else 0,
        'loss_percentage': (len(losses) / total) * 100 if total > 0 else 0
    }
    
    logger.info(f"Bucket analysis: {len(profits)} profits, {len(losses)} losses, {len(neutral)} neutral")
    
    return result

