"""Metrics service - handles all metrics-related database queries sequentially."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from models import User, UserRole, DeviceSnapshot
from services.base_service import BaseService

logger = logging.getLogger(__name__)


class MetricsService(BaseService):
    """Service for metrics data access - all queries run sequentially."""
    
    def get_tenant_metrics(self, tenant_id: int) -> Dict[str, Any]:
        """Get metrics for a tenant admin.
        
        Sequential query execution:
        1. Count active devices
        2. Get in-memory message metrics (no DB query)
        3. Return aggregated metrics
        
        Args:
            tenant_id: Tenant ID to get metrics for
            
        Returns:
            Dictionary with active_devices, messages, sources
        """
        self._log_query("get_tenant_metrics", f"tenant_id={tenant_id}")
        
        # Query 1: Count active devices (SEQUENTIAL)
        self._log_query("count_active_devices", f"tenant_id={tenant_id}")
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=18300)  # 5 hours 5 minutes
        cutoff_iso = cutoff.isoformat()
        
        active_count = 0
        try:
            # Simple query: check is_active flag only (fastest)
            active_query = text("""
                SELECT COUNT(*) 
                FROM devices_snapshot 
                WHERE tenant_id = :tenant_id
                  AND (
                    (payload->>'is_active')::text IN ('true', 'True', 'TRUE')
                    OR (payload->>'is_active')::boolean = true
                  )
            """)
            active_count = self.db.execute(active_query, {"tenant_id": tenant_id}).scalar() or 0
            logger.info(f"Active devices count: {active_count}")
            
            # Fallback: if no devices are explicitly active, check for recent telemetry
            if active_count == 0:
                self._log_query("count_active_by_timestamp", "fallback to timestamp check")
                timestamp_query = text("""
                    SELECT COUNT(*)
                    FROM devices_snapshot
                    WHERE tenant_id = :tenant_id
                      AND (payload->'telemetry'->>'timestamp') IS NOT NULL
                      AND (payload->'telemetry'->>'timestamp')::timestamptz >= CAST(:cutoff AS timestamptz)
                """)
                try:
                    active_count = self.db.execute(
                        timestamp_query,
                        {"tenant_id": tenant_id, "cutoff": cutoff_iso}
                    ).scalar() or 0
                    logger.info(f"Active devices count (by timestamp): {active_count}")
                except Exception as e:
                    logger.error(f"Error counting active devices by timestamp: {e}")
                    self._handle_error(e)
                    active_count = 0
        except Exception as e:
            logger.error(f"Error counting active devices: {e}", exc_info=True)
            self._handle_error(e)
            active_count = 0
        
        # Query 2: Get in-memory message metrics (NO DB QUERY - from metrics module)
        self._log_query("get_in_memory_metrics", "fetching from metrics module")
        try:
            from metrics import metrics
            
            # Get tenant-specific metrics (in-memory, resets on restart)
            # Sum up all device metrics for this tenant
            # Note: metrics module doesn't have tenant-scoped methods, so we return 0 for now
            # In production, you'd need to track tenant_id per device in metrics
            total_received = sum(metrics.messages_received.values())
            total_published = sum(metrics.messages_published.values())
            total_rejected = sum(metrics.messages_rejected.values())
            
            # Get protocol distribution (global for now)
            tenant_sources = dict(metrics.messages_by_source)
        except Exception as e:
            logger.error(f"Error getting in-memory metrics: {e}")
            total_received = 0
            total_published = 0
            total_rejected = 0
            tenant_sources = {}
        
        return {
            "active_devices": active_count,
            "messages": {
                "total_received": total_received,
                "total_published": total_published,
                "total_rejected": total_rejected,
            },
            "sources": tenant_sources,
        }
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get metrics for global admin (all tenants).
        
        Sequential query execution:
        1. Get in-memory message metrics (no DB query)
        2. Return aggregated metrics
        
        Returns:
            Dictionary with active_devices, messages, sources
        """
        self._log_query("get_global_metrics", "fetching global metrics")
        
        try:
            from metrics import metrics
            
            # Global metrics (in-memory, resets on restart)
            total_received = sum(metrics.messages_received.values())
            total_published = sum(metrics.messages_published.values())
            total_rejected = sum(metrics.messages_rejected.values())
            
            # Get protocol distribution
            global_sources = dict(metrics.messages_by_source)
            
            # Active devices count (from in-memory metrics - devices that have sent messages)
            active_devices = len(metrics.device_last_seen)
        except Exception as e:
            logger.error(f"Error getting global metrics: {e}")
            total_received = 0
            total_published = 0
            total_rejected = 0
            global_sources = {}
            active_devices = 0
        
        return {
            "active_devices": active_devices,
            "messages": {
                "total_received": total_received,
                "total_published": total_published,
                "total_rejected": total_rejected,
            },
            "sources": global_sources,
        }

