# Telegram Monitoring Guide - Rate Limit Solutions

## Problem
Long polling causes rate limits and connection blocks from Telegram.

## Solution Implemented

### 1. **Rate Limiter** (`rate_limiter.py`)
- Tracks requests per minute (max 20)
- Implements exponential backoff
- Automatic cooldown periods
- Smart error detection

### 2. **Flood Protection**
- Catches `FloodWaitError` and `FloodError`
- Automatically waits the required time
- Adds buffer to prevent immediate re-triggering

### 3. **Health Monitoring**
- Background task checks connection every 60s
- Displays rate limiter stats
- Early warning for potential issues

### 4. **Graceful Error Handling**
- Consecutive error tracking
- Auto-restart after max errors
- Error classification (rate limit vs other)

### 5. **Connection Optimization**
- Uses event-driven model (not polling)
- `run_until_disconnected()` for efficiency
- Proper session management

## How It Works

```
Message arrives → Rate limiter checks → Process if OK → Record success
                                    ↓
                          Rate limited? → Wait → Retry
```

## Configuration

Edit `rate_limiter.py`:
```python
self.max_requests_per_minute = 20  # Conservative (Telegram limit ~30)
self.max_backoff = 300  # Max 5 min cooldown
```

Edit `orchestrator.py`:
```python
self.health_check_interval = 60  # Health check frequency
max_consecutive_errors = 5  # Restart threshold
```

## Running

```bash
python orchestrator.py
```

Output will show:
- `[OK]` - Successful operations
- `[THROTTLE]` - Waiting due to rate limit
- `[FLOOD WAIT]` - Telegram-imposed wait
- `[HEALTH CHECK]` - Periodic status updates

## Benefits

✅ **No more blocks** - Respects Telegram limits
✅ **Real-time data** - Still gets messages immediately
✅ **Self-healing** - Auto-recovers from errors
✅ **Long-term stable** - Can run 24/7
✅ **Transparent** - Shows what's happening

## Troubleshooting

**Still getting rate limited?**
- Lower `max_requests_per_minute` to 15
- Increase `health_check_interval` to 120
- Check you're not running multiple instances

**Messages delayed?**
- This is expected during cooldown periods
- Messages are queued by Telegram and delivered when available
- Better than getting blocked completely

**Want even more stability?**
- Run on a stable server (not laptop)
- Use a static IP
- Don't manually access the same account elsewhere

## Advanced: Multiple Channels

If monitoring multiple channels:
```python
# Use separate rate limiters per channel
rate_limiters = {
    'channel1': RateLimiter(),
    'channel2': RateLimiter()
}
```

## Monitoring Stats

The system logs:
- Requests per minute
- Messages collected
- Consecutive errors
- Cooldown status

Example output:
```
[HEALTH CHECK]
  Requests/min: 8/20
  Messages collected: 142
  Consecutive errors: 0
  Status: HEALTHY
```

