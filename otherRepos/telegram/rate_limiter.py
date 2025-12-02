"""
Rate limiting and backoff management for Telegram
"""
import asyncio
import time
from datetime import datetime, timedelta


class RateLimiter:
    """Manages rate limiting and exponential backoff"""
    
    def __init__(self):
        self.request_times = []
        self.max_requests_per_minute = 20  # Conservative limit
        self.cooldown_until = None
        self.consecutive_errors = 0
        self.backoff_seconds = 1
        self.max_backoff = 300  # 5 minutes max backoff
    
    def can_make_request(self):
        """Check if we can make a request"""
        # Check if in cooldown
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            remaining = (self.cooldown_until - datetime.now()).total_seconds()
            return False, remaining
        
        # Clean old request times (older than 1 minute)
        now = time.time()
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        # Check rate limit
        if len(self.request_times) >= self.max_requests_per_minute:
            wait_time = 60 - (now - self.request_times[0])
            return False, wait_time
        
        return True, 0
    
    def record_request(self):
        """Record a successful request"""
        self.request_times.append(time.time())
        self.consecutive_errors = 0
        self.backoff_seconds = 1  # Reset backoff on success
    
    def record_error(self, is_rate_limit=False):
        """Record an error and calculate backoff"""
        self.consecutive_errors += 1
        
        if is_rate_limit:
            # For rate limit errors, use longer backoff
            self.backoff_seconds = min(self.backoff_seconds * 2, self.max_backoff)
            self.cooldown_until = datetime.now() + timedelta(seconds=self.backoff_seconds)
            print(f"[RATE LIMIT] Backing off for {self.backoff_seconds}s")
        else:
            # For other errors, use shorter backoff
            self.backoff_seconds = min(self.consecutive_errors * 2, 30)
        
        return self.backoff_seconds
    
    async def wait_if_needed(self):
        """Wait if rate limited"""
        can_proceed, wait_time = self.can_make_request()
        
        if not can_proceed:
            print(f"[THROTTLE] Waiting {wait_time:.1f}s before next request...")
            await asyncio.sleep(wait_time + 1)  # Add 1 second buffer
            return True
        
        return False
    
    def get_stats(self):
        """Get rate limiter statistics"""
        now = time.time()
        recent_requests = [t for t in self.request_times if now - t < 60]
        
        stats = {
            'requests_last_minute': len(recent_requests),
            'consecutive_errors': self.consecutive_errors,
            'current_backoff': self.backoff_seconds,
            'in_cooldown': self.cooldown_until and datetime.now() < self.cooldown_until
        }
        
        return stats

