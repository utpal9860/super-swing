"""
Position Sizing and Risk Management Utilities

Calculates proper position sizes based on:
- Account capital
- Risk percentage per trade
- Entry price and stop loss
- Risk:Reward ratio
"""

from typing import Dict, Optional


def calculate_position_size(
    capital: float,
    risk_pct: float,
    entry_price: float,
    stop_loss: float,
    min_shares: int = 1
) -> Optional[Dict]:
    """
    Calculate position size based on risk management rules.
    
    Args:
        capital: Total trading capital (e.g., ₹1,00,000)
        risk_pct: Risk percentage per trade (e.g., 2.0 for 2%)
        entry_price: Entry price per share
        stop_loss: Stop loss price per share
        min_shares: Minimum shares to buy (default: 1)
    
    Returns:
        Dict with position sizing details or None if invalid
    
    Example:
        >>> calculate_position_size(100000, 2.0, 2500, 2375)
        {
            'shares': 16,
            'position_value': 40000.0,
            'risk_amount': 2000.0,
            'risk_per_share': 125.0,
            'capital_allocation_pct': 40.0,
            'actual_risk_pct': 2.0
        }
    """
    # Validation
    if capital <= 0:
        return None
    if risk_pct <= 0 or risk_pct > 100:
        return None
    if entry_price <= 0:
        return None
    if stop_loss <= 0:
        return None
    if stop_loss >= entry_price:  # SL must be below entry for long positions
        return None
    
    # Calculate risk amount
    risk_amount = capital * (risk_pct / 100)
    
    # Calculate risk per share
    risk_per_share = abs(entry_price - stop_loss)
    
    # Calculate number of shares
    shares = int(risk_amount / risk_per_share)
    
    # Ensure minimum shares
    if shares < min_shares:
        shares = min_shares
    
    # Calculate position value
    position_value = shares * entry_price
    
    # Check if position exceeds capital
    if position_value > capital:
        # Reduce shares to fit capital
        shares = int(capital / entry_price)
        position_value = shares * entry_price
        # Recalculate actual risk
        actual_risk_amount = shares * risk_per_share
        actual_risk_pct = (actual_risk_amount / capital) * 100
    else:
        actual_risk_amount = risk_amount
        actual_risk_pct = risk_pct
    
    # Calculate capital allocation percentage
    capital_allocation_pct = (position_value / capital) * 100
    
    return {
        'shares': shares,
        'position_value': round(position_value, 2),
        'risk_amount': round(actual_risk_amount, 2),
        'risk_per_share': round(risk_per_share, 2),
        'capital_allocation_pct': round(capital_allocation_pct, 2),
        'actual_risk_pct': round(actual_risk_pct, 2)
    }


def calculate_risk_reward(
    entry_price: float,
    stop_loss: float,
    target: float
) -> Optional[Dict]:
    """
    Calculate risk:reward ratio.
    
    Args:
        entry_price: Entry price per share
        stop_loss: Stop loss price per share
        target: Target price per share
    
    Returns:
        Dict with risk:reward details or None if invalid
    
    Example:
        >>> calculate_risk_reward(2500, 2375, 2750)
        {
            'risk_amount': 125.0,
            'reward_amount': 250.0,
            'risk_reward_ratio': 2.0,
            'risk_pct': 5.0,
            'reward_pct': 10.0
        }
    """
    # Validation
    if entry_price <= 0 or stop_loss <= 0 or target <= 0:
        return None
    if stop_loss >= entry_price:
        return None
    if target <= entry_price:
        return None
    
    # Calculate risk and reward amounts
    risk_amount = abs(entry_price - stop_loss)
    reward_amount = abs(target - entry_price)
    
    # Calculate percentages
    risk_pct = (risk_amount / entry_price) * 100
    reward_pct = (reward_amount / entry_price) * 100
    
    # Calculate ratio
    risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
    
    return {
        'risk_amount': round(risk_amount, 2),
        'reward_amount': round(reward_amount, 2),
        'risk_reward_ratio': round(risk_reward_ratio, 2),
        'risk_pct': round(risk_pct, 2),
        'reward_pct': round(reward_pct, 2)
    }


def calculate_expected_value(
    risk_amount: float,
    reward_amount: float,
    win_rate: float
) -> Dict:
    """
    Calculate expected value of a trade based on win rate.
    
    Args:
        risk_amount: Amount at risk per trade
        reward_amount: Potential reward per trade
        win_rate: Win rate percentage (e.g., 60.0 for 60%)
    
    Returns:
        Dict with expected value details
    
    Example:
        >>> calculate_expected_value(2000, 4000, 58.0)
        {
            'expected_value': 480.0,
            'expected_return_pct': 24.0,
            'positive_expectancy': True
        }
    """
    # Convert win rate to decimal
    win_rate_decimal = win_rate / 100
    loss_rate_decimal = 1 - win_rate_decimal
    
    # Calculate expected value
    expected_value = (win_rate_decimal * reward_amount) - (loss_rate_decimal * risk_amount)
    
    # Calculate expected return percentage
    expected_return_pct = (expected_value / risk_amount) * 100 if risk_amount > 0 else 0
    
    return {
        'expected_value': round(expected_value, 2),
        'expected_return_pct': round(expected_return_pct, 2),
        'positive_expectancy': expected_value > 0
    }


def validate_position_size(
    position_value: float,
    capital: float,
    max_position_pct: float = 50.0
) -> Dict:
    """
    Validate if position size is within acceptable limits.
    
    Args:
        position_value: Total position value
        capital: Total trading capital
        max_position_pct: Maximum position size as % of capital
    
    Returns:
        Dict with validation results
    """
    position_pct = (position_value / capital) * 100
    
    is_valid = position_pct <= max_position_pct
    
    return {
        'is_valid': is_valid,
        'position_pct': round(position_pct, 2),
        'max_position_pct': max_position_pct,
        'warning': f'Position size ({position_pct:.1f}%) exceeds maximum ({max_position_pct}%)' if not is_valid else None
    }


def calculate_portfolio_heat(
    open_positions: list,
    capital: float
) -> Dict:
    """
    Calculate total portfolio risk (heat) from open positions.
    
    Args:
        open_positions: List of dicts with 'shares', 'entry_price', 'stop_loss'
        capital: Total trading capital
    
    Returns:
        Dict with portfolio heat metrics
    
    Example:
        >>> positions = [
        ...     {'shares': 10, 'entry_price': 2500, 'stop_loss': 2375},
        ...     {'shares': 20, 'entry_price': 1400, 'stop_loss': 1330}
        ... ]
        >>> calculate_portfolio_heat(positions, 100000)
        {
            'total_risk_amount': 2650.0,
            'portfolio_heat_pct': 2.65,
            'num_positions': 2,
            'avg_risk_per_position_pct': 1.325
        }
    """
    total_risk = 0
    
    for position in open_positions:
        shares = position.get('shares', 0)
        entry = position.get('entry_price', 0)
        sl = position.get('stop_loss', 0)
        
        if entry > 0 and sl > 0 and entry > sl:
            risk_per_share = entry - sl
            position_risk = shares * risk_per_share
            total_risk += position_risk
    
    portfolio_heat_pct = (total_risk / capital) * 100 if capital > 0 else 0
    num_positions = len(open_positions)
    avg_risk_per_position = portfolio_heat_pct / num_positions if num_positions > 0 else 0
    
    return {
        'total_risk_amount': round(total_risk, 2),
        'portfolio_heat_pct': round(portfolio_heat_pct, 2),
        'num_positions': num_positions,
        'avg_risk_per_position_pct': round(avg_risk_per_position, 2)
    }


# Example usage
if __name__ == "__main__":
    import sys
    # Fix encoding for Windows console
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    # Example 1: Calculate position size
    print("=== Position Sizing Example ===")
    capital = 100000  # Rs. 1 lakh
    risk_pct = 2.0    # Risk 2% per trade
    entry = 2500
    sl = 2375
    target = 2750
    
    pos_size = calculate_position_size(capital, risk_pct, entry, sl)
    print(f"Capital: Rs.{capital:,}")
    print(f"Risk: {risk_pct}% per trade")
    print(f"Entry: Rs.{entry}, SL: Rs.{sl}, Target: Rs.{target}")
    print(f"\nPosition Size:")
    print(f"  Shares to buy: {pos_size['shares']}")
    print(f"  Investment: Rs.{pos_size['position_value']:,.0f}")
    print(f"  Risk amount: Rs.{pos_size['risk_amount']:,.0f}")
    print(f"  Capital allocation: {pos_size['capital_allocation_pct']:.1f}%")
    
    # Example 2: Risk:Reward
    print("\n=== Risk:Reward Example ===")
    rr = calculate_risk_reward(entry, sl, target)
    print(f"Risk: Rs.{rr['risk_amount']} ({rr['risk_pct']}%)")
    print(f"Reward: Rs.{rr['reward_amount']} ({rr['reward_pct']}%)")
    print(f"R:R Ratio: 1:{rr['risk_reward_ratio']}")
    
    # Example 3: Expected Value
    print("\n=== Expected Value (58% Win Rate) ===")
    ev = calculate_expected_value(pos_size['risk_amount'], rr['reward_amount'] * pos_size['shares'], 58.0)
    print(f"Expected Value: Rs.{ev['expected_value']:,.0f}")
    print(f"Expected Return: {ev['expected_return_pct']:.1f}%")
    print(f"Positive Expectancy: {ev['positive_expectancy']}")

