"""Metrics service - handles all metrics-related database queries sequentially."""

import logging
from datetime import datetime, timezone
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
        
        active_count = 0
        try:
            # Simple query: check is_active flag only (fastest)
            active_query = text("""
                SELECT COUNT(*) 
                FROM devices_snapshot 
                WHERE tenant_id = :tenant_id
                  AND (payload->>'is_active')::text IN ('true', 'True', 'TRUE')
            """)
            active_count = self.db.execute(active_query, {"tenant_id": tenant_id}).scalar() or 0
            logger.info(f"Active devices count: {active_count}")
        except Exception as e:
            logger.error(f"Error counting active devices: {e}", exc_info=True)
            self._handle_error(e)
            active_count = 0
        
        # Query 2: Count devices with telemetry data (messages received)
        self._log_query("count_messages_received", f"tenant_id={tenant_id}")
        messages_received = 0
        try:
            messages_query = text("""
                SELECT COUNT(*) 
                FROM devices_snapshot 
                WHERE tenant_id = :tenant_id
                  AND payload->'telemetry' IS NOT NULL
                  AND payload->'telemetry'->'data' IS NOT NULL
            """)
            messages_received = self.db.execute(messages_query, {"tenant_id": tenant_id}).scalar() or 0
            logger.info(f"Messages received (devices with telemetry): {messages_received}")
        except Exception as e:
            logger.error(f"Error counting messages received: {e}", exc_info=True)
            self._handle_error(e)
            messages_received = 0
        
        # Query 3: Get protocol distribution
        self._log_query("get_protocol_distribution", f"tenant_id={tenant_id}")
        tenant_sources = {}
        try:
            protocol_query = text("""
                SELECT 
                    COALESCE(payload->'device_type'->>'protocol', 'HTTP') as protocol,
                    COUNT(*) as count
                FROM devices_snapshot 
                WHERE tenant_id = :tenant_id
                GROUP BY payload->'device_type'->>'protocol'
            """)
            protocol_rows = self.db.execute(protocol_query, {"tenant_id": tenant_id}).fetchall()
            for row in protocol_rows:
                protocol = row[0] or "HTTP"
                count = row[1] or 0
                tenant_sources[protocol] = count
            logger.info(f"Protocol distribution: {tenant_sources}")
        except Exception as e:
            logger.error(f"Error getting protocol distribution: {e}", exc_info=True)
            self._handle_error(e)
            tenant_sources = {}
        
        # Messages published and rejected are in-memory only (from metrics module)
        # These reset on server restart and only increment with live telemetry
        total_published = 0
        total_rejected = 0
        try:
            from metrics import metrics
            total_published = sum(metrics.messages_published.values())
            total_rejected = sum(metrics.messages_rejected.values())
        except Exception as e:
            logger.debug(f"Error getting in-memory metrics: {e}")
            total_published = 0
            total_rejected = 0
        
        return {
            "active_devices": active_count,
            "messages": {
                "total_received": messages_received,  # Count of devices with telemetry data
                "total_published": total_published,     # In-memory (resets on restart)
                "total_rejected": total_rejected,       # In-memory (resets on restart)
            },
            "sources": tenant_sources,  # Protocol distribution from devices_snapshot
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

