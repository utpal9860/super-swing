# Pattern Direction Guide

## How Bullish vs Bearish Patterns are Handled

### Pattern Detection

All candlestick patterns detected by TA-Lib include direction information:
- **Pattern Type Format**: `{PATTERN_NAME}_{DIRECTION}`
- **Example**: `CDLHAMMER_BULLISH`, `CDLHANGINGMAN_BEARISH`

The direction is determined by TA-Lib's pattern functions:
- Positive values (> 0) = BULLISH
- Negative values (< 0) = BEARISH

### Trade Setup Logic

#### BULLISH Patterns (LONG positions)
```
Entry:     Resistance × 1.002 (0.2% above resistance - breakout confirmation)
Stop Loss: Support × 0.98 (2% below support - protect from reversal)
Target:    Entry + Pattern Height (or use price prediction if higher)

Example:
- Current Price: ₹1000
- Support: ₹980
- Resistance: ₹1020
- Entry: ₹1022.04
- Stop Loss: ₹960.40
- Target: ₹1062.04 (minimum 3% gain)
- Risk:Reward = 1:1.5 or better
```

#### BEARISH Patterns (SHORT positions)
```
Entry:     Support × 0.998 (0.2% below support - breakdown confirmation)
Stop Loss: Resistance × 1.02 (2% above resistance - protect from reversal)
Target:    Entry - Pattern Height (or use price prediction if lower)

Example:
- Current Price: ₹1000
- Support: ₹980
- Resistance: ₹1020
- Entry: ₹978.04
- Stop Loss: ₹1040.40
- Target: ₹938.04 (minimum 3% drop)
- Risk:Reward = 1:1.5 or better
```

### Key Differences

| Aspect | BULLISH (LONG) | BEARISH (SHORT) |
|--------|----------------|-----------------|
| Entry | Above resistance | Below support |
| Stop Loss | Below support | Above resistance |
| Target | Above entry | Below entry |
| SL Position | Always < Entry | Always > Entry |
| Target Position | Always > Entry | Always < Entry |
| Profit Direction | Upward | Downward |

### Chart Visualization

- **Entry Line**: Blue (solid) - labeled as "LONG" or "SHORT"
- **Target Line**: Green (dashed) - profit target
- **Stop Loss Line**: Red (dashed) - loss protection

Both bullish and bearish patterns show:
- Target in green (profit direction)
- Stop Loss in red (loss direction)
- Percentage change relative to entry (can be positive or negative)

### Price Prediction Integration

The system uses StatsForecast predictions to refine targets:

**For BULLISH patterns**:
- If predicted price > entry → use as target
- Otherwise → use pattern height projection

**For BEARISH patterns**:
- If predicted price < entry → use as target
- Otherwise → use pattern height projection

### Sentiment Adjustment

**Bullish patterns with very bullish sentiment (>0.8)**:
- Extend target by 10% (more upside potential)

**Bearish patterns with very bearish sentiment (<-0.8)**:
- Extend target by 10% downward (more downside potential)

### Risk-Reward Calculation

```python
# Works for both directions
risk = abs(entry - stop_loss)
reward = abs(target - entry)
risk_reward_ratio = reward / risk
```

Minimum acceptable R:R ratios:
- STRONG_BUY/STRONG_SELL: 2.0:1
- BUY/SELL: 1.5:1
- WEAK_BUY/WEAK_SELL: 2.0:1 (compensate for lower confidence)

### Common Issues Fixed

❌ **Before**: All patterns treated as bullish
- SL always below entry
- Target always above entry
- Short signals impossible

✅ **After**: Direction-aware logic
- Bullish: Entry > SL, Target > Entry
- Bearish: Entry < SL, Target < Entry
- Both long and short signals supported

### Verification Checklist

When reviewing a signal, verify:

**For BULLISH patterns**:
- [ ] Pattern name ends with "_BULLISH"
- [ ] Entry > Stop Loss
- [ ] Target > Entry
- [ ] SL is below support
- [ ] Entry is near resistance

**For BEARISH patterns**:
- [ ] Pattern name ends with "_BEARISH"
- [ ] Entry < Stop Loss
- [ ] Target < Entry
- [ ] SL is above resistance
- [ ] Entry is near support

### Example Signals

#### Bullish Signal
```
Pattern: CDLMORNINGSTAR_BULLISH
Entry (LONG): ₹1022.00
Target: ₹1072.00 (+4.9%)
Stop Loss: ₹975.00 (-4.6%)
R:R: 2.1:1 ✓
```

#### Bearish Signal
```
Pattern: CDLEVENINGSTAR_BEARISH
Entry (SHORT): ₹978.00
Target: ₹928.00 (-5.1%)
Stop Loss: ₹1025.00 (+4.8%)
R:R: 2.2:1 ✓
```

---

**Last Updated**: November 3, 2025
**System Version**: Multi-Modal v2.0

