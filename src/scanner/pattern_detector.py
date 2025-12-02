#!/usr/bin/env python3
"""
PATTERN DETECTION ENGINE FOR BTST TRADING
==========================================

Detects chart patterns for 1-3 day breakout trades:
- Bull Flag
- Ascending Triangle
- Narrow Range Breakout (NR4, NR7)
- Volume Surge Breakout
- Opening Range Breakout

Each pattern returns:
- Detection confidence (0-100)
- Entry price
- Stop loss
- Target 1 & 2
- Expected holding period
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def detect_bull_flag(df: pd.DataFrame, lookback: int = 20) -> Optional[Dict]:
    """
    Detect Bull Flag pattern
    
    Characteristics:
    - Strong upward move (pole): 5-15% gain in 3-5 days
    - Consolidation (flag): 2-5% range for 3-7 days
    - Decreasing volume during consolidation
    - Breakout above flag resistance with volume
    
    Returns pattern details or None
    """
    if len(df) < lookback:
        return None
    
    recent = df.tail(lookback).copy()
    recent = recent.reset_index(drop=True)
    
    # Look for the pole (strong move up)
    # Check last 10 days for a 5-15% rally
    for pole_start in range(0, len(recent) - 10):
        pole_end = pole_start + 5
        if pole_end >= len(recent):
            continue
        
        pole_gain = ((recent.loc[pole_end, 'Close'] - recent.loc[pole_start, 'Low']) / 
                     recent.loc[pole_start, 'Low']) * 100
        
        # Valid pole: 5-15% gain
        if pole_gain < 5 or pole_gain > 20:
            continue
        
        # Look for consolidation flag after pole
        flag_start = pole_end
        flag_end = min(flag_start + 7, len(recent) - 1)
        
        if flag_end - flag_start < 3:
            continue
        
        flag_data = recent.loc[flag_start:flag_end]
        flag_high = flag_data['High'].max()
        flag_low = flag_data['Low'].min()
        flag_range = ((flag_high - flag_low) / flag_low) * 100
        
        # Valid flag: 2-8% range
        if flag_range < 2 or flag_range > 8:
            continue
        
        # Check volume decrease during flag
        pole_avg_volume = recent.loc[pole_start:pole_end, 'Volume'].mean()
        flag_avg_volume = flag_data['Volume'].mean()
        
        if flag_avg_volume > pole_avg_volume * 0.8:  # Should be lower volume
            continue
        
        # Current price near flag resistance
        current_price = recent.iloc[-1]['Close']
        resistance = flag_high
        
        # Check if we're within 2% of breakout
        distance_to_breakout = ((resistance - current_price) / current_price) * 100
        
        if distance_to_breakout < -1 or distance_to_breakout > 3:
            continue
        
        # Calculate stops and targets
        stop_loss = flag_low * 0.985  # Just below flag low
        target_1 = resistance + (resistance - flag_low)  # Pole height projection
        target_2 = resistance + 1.5 * (resistance - flag_low)  # Extended target
        
        return {
            'pattern': 'Bull Flag',
            'confidence': 75,
            'pole_gain': pole_gain,
            'flag_range': flag_range,
            'resistance': resistance,
            'support': flag_low,
            'entry_price': resistance * 1.005,  # 0.5% above resistance
            'stop_loss': stop_loss,
            'target_1': target_1,
            'target_2': target_2,
            'risk_reward': (target_1 - resistance * 1.005) / (resistance * 1.005 - stop_loss),
            'holding_period': '1-3 days',
            'volume_trend': 'Decreasing (bullish)'
        }
    
    return None


def detect_ascending_triangle(df: pd.DataFrame, lookback: int = 20) -> Optional[Dict]:
    """
    Detect Ascending Triangle pattern
    
    Characteristics:
    - Horizontal resistance (price touches 2-3 times)
    - Rising support (higher lows)
    - Decreasing volume
    - Breakout above resistance with volume surge
    
    Returns pattern details or None
    """
    if len(df) < lookback:
        return None
    
    recent = df.tail(lookback).copy()
    recent = recent.reset_index(drop=True)
    
    # Identify resistance (horizontal line at highs)
    highs = recent['High'].values
    
    # Find potential resistance level (recurring high)
    resistance_candidates = []
    for i in range(len(recent) - 3):
        high = recent.loc[i, 'High']
        # Count how many times price touched this level (±1%)
        touches = sum(abs(h - high) / high < 0.01 for h in highs[i:])
        if touches >= 2:
            resistance_candidates.append((high, touches))
    
    if not resistance_candidates:
        return None
    
    # Take the most-touched resistance
    resistance = max(resistance_candidates, key=lambda x: x[1])[0]
    
    # Check for rising lows
    lows = recent['Low'].tail(10).values
    if len(lows) < 5:
        return None
    
    # Simple check: are lows trending up?
    low_trend = np.polyfit(range(len(lows)), lows, 1)[0]
    
    if low_trend <= 0:  # Not ascending
        return None
    
    # Find the lowest point in pattern for support
    support = recent.tail(10)['Low'].min()
    
    # Current price
    current_price = recent.iloc[-1]['Close']
    
    # Check if near breakout
    distance_to_breakout = ((resistance - current_price) / current_price) * 100
    
    if distance_to_breakout < -1 or distance_to_breakout > 3:
        return None
    
    # Calculate targets
    triangle_height = resistance - support
    stop_loss = support * 0.98
    target_1 = resistance + triangle_height
    target_2 = resistance + 1.5 * triangle_height
    
    return {
        'pattern': 'Ascending Triangle',
        'confidence': 70,
        'resistance': resistance,
        'support': support,
        'triangle_height': triangle_height,
        'entry_price': resistance * 1.005,
        'stop_loss': stop_loss,
        'target_1': target_1,
        'target_2': target_2,
        'risk_reward': (target_1 - resistance * 1.005) / (resistance * 1.005 - stop_loss),
        'holding_period': '1-3 days',
        'volume_trend': 'Decreasing (awaiting breakout)'
    }


def detect_narrow_range(df: pd.DataFrame) -> Optional[Dict]:
    """
    Detect Narrow Range (NR4, NR7) patterns
    
    NR4: Today's range is smallest of last 4 days
    NR7: Today's range is smallest of last 7 days
    
    Indicates contraction before expansion (breakout)
    
    Returns pattern details or None
    """
    if len(df) < 10:
        return None
    
    recent = df.tail(10).copy()
    recent['Range'] = recent['High'] - recent['Low']
    recent['Range_Pct'] = (recent['Range'] / recent['Low']) * 100
    
    today = recent.iloc[-1]
    today_range = today['Range_Pct']
    
    # Check NR7
    last_7_ranges = recent.tail(7)['Range_Pct'].values
    is_nr7 = today_range == min(last_7_ranges)
    
    # Check NR4
    last_4_ranges = recent.tail(4)['Range_Pct'].values
    is_nr4 = today_range == min(last_4_ranges)
    
    if not (is_nr4 or is_nr7):
        return None
    
    # Calculate average range for targets
    avg_range = recent.tail(10)['Range'].mean()
    avg_range_pct = recent.tail(10)['Range_Pct'].mean()
    
    current_price = today['Close']
    
    # For NR patterns, we expect breakout in either direction
    # For BTST, we look for bullish signals (covered by other confirmations)
    
    # Assume bullish breakout
    resistance = today['High']
    support = today['Low']
    
    entry_price = resistance * 1.003  # Just above today's high
    stop_loss = support * 0.995  # Just below today's low
    
    # Target based on average range expansion
    target_1 = entry_price + avg_range * 1.5
    target_2 = entry_price + avg_range * 2.5
    
    pattern_type = 'NR7' if is_nr7 else 'NR4'
    confidence = 80 if is_nr7 else 70
    
    return {
        'pattern': pattern_type,
        'confidence': confidence,
        'today_range_pct': today_range,
        'avg_range_pct': avg_range_pct,
        'contraction_ratio': today_range / avg_range_pct,
        'resistance': resistance,
        'support': support,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'target_1': target_1,
        'target_2': target_2,
        'risk_reward': (target_1 - entry_price) / (entry_price - stop_loss),
        'holding_period': '1-2 days',
        'volume_trend': 'Watch for surge on breakout'
    }


def detect_volume_breakout(df: pd.DataFrame, lookback: int = 20) -> Optional[Dict]:
    """
    Detect Volume Surge Breakout
    
    Characteristics:
    - Price near recent high
    - Volume 2X+ average
    - Strong close (in upper 25% of day's range)
    
    Returns pattern details or None
    """
    if len(df) < lookback:
        return None
    
    recent = df.tail(lookback).copy()
    today = recent.iloc[-1]
    
    # Calculate average volume (exclude today)
    avg_volume = recent.iloc[:-1]['Volume'].mean()
    today_volume = today['Volume']
    
    volume_ratio = today_volume / avg_volume
    
    # Need 2X+ volume
    if volume_ratio < 2.0:
        return None
    
    # Price should be near recent highs
    recent_high = recent.iloc[:-1]['High'].max()
    current_price = today['Close']
    
    distance_from_high = ((recent_high - current_price) / current_price) * 100
    
    # Should be within 3% of recent high
    if distance_from_high > 3:
        return None
    
    # Strong close check
    day_range = today['High'] - today['Low']
    if day_range == 0:
        return None
    
    close_position = (today['Close'] - today['Low']) / day_range
    
    # Close should be in upper 30% of range
    if close_position < 0.7:
        return None
    
    # Calculate stops and targets
    resistance = max(today['High'], recent_high)
    support = recent.tail(5)['Low'].min()
    
    entry_price = resistance * 1.003
    stop_loss = current_price * 0.985  # 1.5% stop
    
    # Conservative targets for volume breakout
    target_1 = entry_price * 1.025  # 2.5%
    target_2 = entry_price * 1.04   # 4%
    
    return {
        'pattern': 'Volume Breakout',
        'confidence': 85,
        'volume_ratio': volume_ratio,
        'close_position': close_position,
        'distance_from_high': distance_from_high,
        'resistance': resistance,
        'support': support,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'target_1': target_1,
        'target_2': target_2,
        'risk_reward': (target_1 - entry_price) / (entry_price - stop_loss),
        'holding_period': '1-2 days',
        'volume_trend': f'{volume_ratio:.1f}X average (STRONG!)'
    }


def detect_all_patterns(df: pd.DataFrame) -> list:
    """
    Run all pattern detectors and return all found patterns
    
    Returns list of pattern dictionaries, sorted by confidence
    """
    patterns = []
    
    # Try each pattern detector
    bull_flag = detect_bull_flag(df)
    if bull_flag:
        patterns.append(bull_flag)
    
    asc_triangle = detect_ascending_triangle(df)
    if asc_triangle:
        patterns.append(asc_triangle)
    
    narrow_range = detect_narrow_range(df)
    if narrow_range:
        patterns.append(narrow_range)
    
    volume_breakout = detect_volume_breakout(df)
    if volume_breakout:
        patterns.append(volume_breakout)
    
    # Sort by confidence
    patterns.sort(key=lambda x: x['confidence'], reverse=True)
    
    return patterns


def get_pattern_summary(df: pd.DataFrame) -> str:
    """
    Get a text summary of all detected patterns
    """
    patterns = detect_all_patterns(df)
    
    if not patterns:
        return "No patterns detected"
    
    summary = f"Found {len(patterns)} pattern(s):\n"
    for p in patterns:
        summary += f"  • {p['pattern']} (Confidence: {p['confidence']}%)\n"
        summary += f"    Entry: ₹{p['entry_price']:.2f}, SL: ₹{p['stop_loss']:.2f}, T1: ₹{p['target_1']:.2f}\n"
        summary += f"    Risk:Reward = 1:{p['risk_reward']:.2f}\n"
    
    return summary


