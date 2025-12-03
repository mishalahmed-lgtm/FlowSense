"""Metrics and monitoring for telemetry ingestion."""
import time
from collections import defaultdict
from typing import Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects metrics for telemetry ingestion pipeline.
    Tracks message counts, errors, device status, etc.
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        # Message counters
        self.messages_received = defaultdict(int)  # {device_id: count}
        self.messages_published = defaultdict(int)  # {device_id: count}
        self.messages_rejected = defaultdict(int)  # {device_id: count}
        
        # Error counters
        self.errors_by_type = defaultdict(int)  # {error_type: count}
        self.errors_by_device = defaultdict(int)  # {device_id: count}
        
        # Rate limiting
        self.rate_limit_hits = defaultdict(int)  # {device_id: count}
        
        # Authentication
        self.auth_failures = defaultdict(int)  # {device_id: count}
        
        # Timing
        self.processing_times = []  # List of processing durations
        
        # Device status
        self.device_last_seen = {}  # {device_id: timestamp}
        
        # Source tracking
        self.messages_by_source = defaultdict(int)  # {source: count}
        
        # Rule engine tracking
        self.rule_hits = defaultdict(int)
        self.rule_actions = defaultdict(int)
        self.rule_last_match = {}

        # Start time
        self.start_time = time.time()
    
    def record_message_received(self, device_id: str, source: str = "unknown"):
        """Record that a message was received."""
        self.messages_received[device_id] += 1
        self.messages_by_source[source] += 1
        self.device_last_seen[device_id] = time.time()
    
    def record_message_published(self, device_id: str):
        """Record that a message was successfully published to Kafka."""
        self.messages_published[device_id] += 1
    
    def record_message_rejected(self, device_id: str, reason: str):
        """Record that a message was rejected."""
        self.messages_rejected[device_id] += 1
        self.errors_by_type[reason] += 1
        logger.debug(f"Message rejected for device {device_id}: {reason}")
    
    def record_error(self, device_id: str, error_type: str):
        """Record an error."""
        self.errors_by_type[error_type] += 1
        self.errors_by_device[device_id] += 1
        logger.error(f"Error for device {device_id}: {error_type}")
    
    def record_rate_limit_hit(self, device_id: str):
        """Record a rate limit violation."""
        self.rate_limit_hits[device_id] += 1
    
    def record_auth_failure(self, device_id: str):
        """Record an authentication failure."""
        self.auth_failures[device_id] += 1
    
    def record_processing_time(self, duration_ms: float):
        """Record message processing time."""
        self.processing_times.append(duration_ms)
        # Keep only last 1000 processing times
        if len(self.processing_times) > 1000:
            self.processing_times = self.processing_times[-1000:]

    def record_rule_decision(self, device_id: str, rule_name: str, action_type: str, outcome: str):
        """Record rule engine activity."""
        self.rule_hits[device_id] += 1
        key = f"{action_type}:{outcome}"
        self.rule_actions[key] += 1
        self.rule_last_match[device_id] = {
            "rule": rule_name,
            "action": action_type,
            "outcome": outcome,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def get_stats(self) -> Dict:
        """Get overall statistics."""
        total_received = sum(self.messages_received.values())
        total_published = sum(self.messages_published.values())
        total_rejected = sum(self.messages_rejected.values())
        
        avg_processing_time = (
            sum(self.processing_times) / len(self.processing_times)
            if self.processing_times else 0
        )
        
        uptime_seconds = time.time() - self.start_time
        
        return {
            "uptime_seconds": int(uptime_seconds),
            "messages": {
                "total_received": total_received,
                "total_published": total_published,
                "total_rejected": total_rejected,
                "success_rate": (
                    total_published / total_received * 100
                    if total_received > 0 else 0
                )
            },
            "errors": {
                "total": sum(self.errors_by_type.values()),
                "by_type": dict(self.errors_by_type),
                "by_device": dict(self.errors_by_device)
            },
            "rate_limiting": {
                "total_hits": sum(self.rate_limit_hits.values()),
                "by_device": dict(self.rate_limit_hits)
            },
            "authentication": {
                "total_failures": sum(self.auth_failures.values()),
                "by_device": dict(self.auth_failures)
            },
            "processing": {
                "avg_time_ms": round(avg_processing_time, 2),
                "samples": len(self.processing_times)
            },
            "rules": {
                "matches": sum(self.rule_hits.values()),
                "actions": dict(self.rule_actions),
                "last_match": self.rule_last_match,
            },
            "sources": dict(self.messages_by_source),
            "active_devices": len(self.device_last_seen),
            "devices": {
                device_id: {
                    "received": self.messages_received.get(device_id, 0),
                    "published": self.messages_published.get(device_id, 0),
                    "rejected": self.messages_rejected.get(device_id, 0),
                    "last_seen": datetime.fromtimestamp(
                        self.device_last_seen.get(device_id, 0)
                    ).isoformat() if device_id in self.device_last_seen else None
                }
                for device_id in set(list(self.messages_received.keys()) + 
                                    list(self.messages_published.keys()) +
                                    list(self.device_last_seen.keys()))
            }
        }
    
    def get_device_stats(self, device_id: str) -> Optional[Dict]:
        """Get statistics for a specific device."""
        if device_id not in self.device_last_seen:
            return None
        
        return {
            "device_id": device_id,
            "messages_received": self.messages_received.get(device_id, 0),
            "messages_published": self.messages_published.get(device_id, 0),
            "messages_rejected": self.messages_rejected.get(device_id, 0),
            "errors": self.errors_by_device.get(device_id, 0),
            "rate_limit_hits": self.rate_limit_hits.get(device_id, 0),
            "auth_failures": self.auth_failures.get(device_id, 0),
            "last_seen": datetime.fromtimestamp(
                self.device_last_seen[device_id]
            ).isoformat()
        }


# Global metrics collector instance
metrics = MetricsCollector()

