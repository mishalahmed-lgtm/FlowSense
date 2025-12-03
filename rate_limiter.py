"""Rate limiting for device telemetry ingestion."""
import time
from collections import defaultdict
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple rate limiter using token bucket algorithm.
    Tracks message counts per device within time windows.
    """
    
    def __init__(self, max_messages_per_minute: int = 60, max_messages_per_hour: int = 3600):
        """
        Initialize rate limiter.
        
        Args:
            max_messages_per_minute: Maximum messages allowed per device per minute
            max_messages_per_hour: Maximum messages allowed per device per hour
        """
        self.max_per_minute = max_messages_per_minute
        self.max_per_hour = max_messages_per_hour
        
        # Track message timestamps per device
        # Structure: {device_id: [list of timestamps]}
        self.message_history: Dict[str, list] = defaultdict(list)
        
        # Track rate limit violations
        self.violations: Dict[str, int] = defaultdict(int)
    
    def _cleanup_old_entries(self, device_id: str, current_time: float):
        """Remove timestamps older than 1 hour."""
        cutoff_time = current_time - 3600  # 1 hour ago
        self.message_history[device_id] = [
            ts for ts in self.message_history[device_id] if ts > cutoff_time
        ]
    
    def is_allowed(self, device_id: str) -> Tuple[bool, str]:
        """
        Check if device is allowed to send a message.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        current_time = time.time()
        
        # Cleanup old entries
        self._cleanup_old_entries(device_id, current_time)
        
        # Get recent message timestamps
        timestamps = self.message_history[device_id]
        
        # Check per-minute limit
        one_minute_ago = current_time - 60
        recent_messages = [ts for ts in timestamps if ts > one_minute_ago]
        
        if len(recent_messages) >= self.max_per_minute:
            self.violations[device_id] += 1
            logger.warning(
                f"Rate limit exceeded for device {device_id}: "
                f"{len(recent_messages)} messages in last minute (limit: {self.max_per_minute})"
            )
            return False, f"Rate limit exceeded: {len(recent_messages)} messages/minute (limit: {self.max_per_minute})"
        
        # Check per-hour limit
        if len(timestamps) >= self.max_per_hour:
            self.violations[device_id] += 1
            logger.warning(
                f"Rate limit exceeded for device {device_id}: "
                f"{len(timestamps)} messages in last hour (limit: {self.max_per_hour})"
            )
            return False, f"Rate limit exceeded: {len(timestamps)} messages/hour (limit: {self.max_per_hour})"
        
        # Allow message and record timestamp
        self.message_history[device_id].append(current_time)
        return True, "OK"
    
    def get_stats(self, device_id: str) -> Dict[str, int]:
        """Get rate limiting statistics for a device."""
        current_time = time.time()
        self._cleanup_old_entries(device_id, current_time)
        
        timestamps = self.message_history[device_id]
        one_minute_ago = current_time - 60
        recent_messages = [ts for ts in timestamps if ts > one_minute_ago]
        
        return {
            "messages_last_minute": len(recent_messages),
            "messages_last_hour": len(timestamps),
            "violations": self.violations.get(device_id, 0)
        }


# Global rate limiter instance
# Default: 60 messages/minute, 3600 messages/hour per device
rate_limiter = RateLimiter(
    max_messages_per_minute=60,
    max_messages_per_hour=3600
)

