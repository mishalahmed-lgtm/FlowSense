"""Dashboard service - handles all dashboard-related database queries sequentially."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import (
    Device, DeviceSnapshot, TelemetryLatest, TelemetryTimeseries,
    User, UserRole
)
from services.base_service import BaseService

logger = logging.getLogger(__name__)


class DashboardService(BaseService):
    """Service for dashboard data access - all queries run sequentially."""
    
    def get_device_latest_telemetry(
        self,
        device_id: str,
        user: User,
    ) -> Dict[str, Any]:
        """Get latest telemetry for a device.
        
        Sequential query execution:
        1. Query device from devices_snapshot (tenant admin) or devices (global admin)
        2. Verify tenant access
        3. Query latest telemetry
        4. Return telemetry data
        
        Args:
            device_id: Device identifier
            user: Current authenticated user
            
        Returns:
            Dictionary with device_id, data, event_timestamp
        """
        self._log_query("get_device_latest_telemetry", f"device_id={device_id}, user={user.email}")
        
        # Tenant admin path - use snapshot table
        if user.role == UserRole.TENANT_ADMIN and user.tenant_id is not None:
            self._log_query("query_device_snapshot", f"tenant_id={user.tenant_id}")
            snap = (
                self.db.query(DeviceSnapshot)
                .filter(
                    DeviceSnapshot.tenant_id == user.tenant_id,
                    DeviceSnapshot.device_id == device_id,
                )
                .one_or_none()
            )
            if snap:
                payload = snap.payload or {}
                telemetry = payload.get("telemetry") or {}
                data = telemetry.get("data") or {}
                event_ts = telemetry.get("timestamp") or telemetry.get("updated_at")
                return {
                    "device_id": device_id,
                    "data": data,
                    "event_timestamp": event_ts,
                }
            
            return {
                "device_id": device_id,
                "data": {},
                "event_timestamp": None,
            }
        
        # Global admin path - use devices + telemetry_latest
        self._log_query("query_device", f"device_id={device_id}")
        device = self.db.query(Device).filter(Device.device_id == device_id).one_or_none()
        if not device:
            return {
                "device_id": device_id,
                "data": {},
                "event_timestamp": None,
            }
        
        # Verify tenant access
        if user.role == UserRole.TENANT_ADMIN and device.tenant_id != user.tenant_id:
            logger.warning(f"Tenant admin {user.email} tried to access device from another tenant")
            return {
                "device_id": device_id,
                "data": {},
                "event_timestamp": None,
            }
        
        # Query latest telemetry
        self._log_query("query_telemetry_latest", f"device.id={device.id}")
        latest = (
            self.db.query(TelemetryLatest)
            .filter(TelemetryLatest.device_id == device.id)
            .one_or_none()
        )
        if not latest:
            return {
                "device_id": device.device_id,
                "data": {},
                "event_timestamp": None,
            }
        
        return {
            "device_id": device.device_id,
            "data": latest.data or {},
            "event_timestamp": latest.event_timestamp.isoformat() if latest.event_timestamp else None,
        }
    
    def get_event_activity(
        self,
        user: User,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Get event activity (message count) over the last N hours.
        
        Sequential query execution:
        1. Determine if tenant admin or global admin
        2. Query telemetry timeseries grouped by hour
        3. Build hourly buckets
        4. Return activity data
        
        Args:
            user: Current authenticated user
            hours: Number of hours to query (default: 24)
            
        Returns:
            Dictionary with total_events, buckets
        """
        self._log_query("get_event_activity", f"user={user.email}, hours={hours}")
        
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours)
        
        # Tenant admin path: return empty activity (snapshot data doesn't have time-series)
        if user.role == UserRole.TENANT_ADMIN and user.tenant_id:
            self._log_query("tenant_admin_activity", "returning empty buckets for snapshot mode")
            
            buckets: List[Dict[str, Any]] = []
            for i in range(hours):
                bucket_time = (now - timedelta(hours=hours - 1 - i)).replace(
                    minute=0, second=0, microsecond=0
                )
                bucket_time = bucket_time.astimezone(timezone.utc)
                buckets.append({
                    "timestamp": bucket_time.isoformat(),
                    "count": 0,
                })
            
            return {
                "total_events": 0,
                "buckets": buckets,
            }
        
        # Global admin path: query telemetry timeseries
        self._log_query("query_telemetry_timeseries", f"cutoff={cutoff.isoformat()}")
        bucket_expr = func.date_trunc("hour", TelemetryTimeseries.ts)
        
        rows = (
            self.db.query(
                bucket_expr.label("bucket"),
                func.count(TelemetryTimeseries.id).label("count"),
            )
            .filter(TelemetryTimeseries.ts >= cutoff)
            .group_by("bucket")
            .order_by("bucket")
            .all()
        )
        
        # Build bucket map
        bucket_map = {}
        total_events = 0
        for row in rows:
            bucket_time = row.bucket.replace(tzinfo=timezone.utc)
            count = row.count or 0
            bucket_map[bucket_time.isoformat()] = count
            total_events += count
        
        # Fill in missing buckets with 0
        buckets: List[Dict[str, Any]] = []
        for i in range(hours):
            bucket_time = (now - timedelta(hours=hours - 1 - i)).replace(
                minute=0, second=0, microsecond=0
            )
            bucket_time = bucket_time.astimezone(timezone.utc)
            bucket_key = bucket_time.isoformat()
            buckets.append({
                "timestamp": bucket_key,
                "count": bucket_map.get(bucket_key, 0),
            })
        
        return {
            "total_events": total_events,
            "buckets": buckets,
        }
    
    def get_initial_dashboard_state(self, user: User) -> Dict[str, Any]:
        """Get initial dashboard state (for first load).
        
        Sequential query execution:
        1. Get metrics (active_devices, messages)
        2. Get event activity (24h buckets)
        3. Get device list (first page, 50 devices)
        4. Return all data
        
        This is called ONCE on dashboard load, then WebSocket takes over.
        
        Args:
            user: Current authenticated user
            
        Returns:
            Dictionary with metrics, activity, devices
        """
        self._log_query("get_initial_dashboard_state", f"user={user.email}")
        
        # Step 1: Get metrics (SEQUENTIAL)
        from services.metrics_service import MetricsService
        metrics_service = MetricsService(self.db)
        
        if user.role == UserRole.TENANT_ADMIN and user.tenant_id:
            metrics = metrics_service.get_tenant_metrics(user.tenant_id)
        else:
            # Global admin - use in-memory metrics
            from metrics import metrics as metrics_collector
            stats = metrics_collector.get_stats()
            metrics = {
                "active_devices": stats.get("active_devices", 0),
                "messages": stats.get("messages", {
                    "total_received": 0,
                    "total_published": 0,
                    "total_rejected": 0,
                }),
                "sources": stats.get("sources", {}),
            }
        
        # Step 2: Get event activity (SEQUENTIAL - after metrics completes)
        activity = self.get_event_activity(user, hours=24)
        
        # Step 3: Get device list (SEQUENTIAL - after activity completes)
        from services.device_service import DeviceService
        device_service = DeviceService(self.db)
        
        devices_data = device_service.get_devices_paginated(
            user=user,
            page=1,
            limit=50,
            include_counts=False,  # We already have active count from metrics
        )
        
        return {
            "metrics": metrics,
            "activity": activity,
            "devices": devices_data["devices"],
            "total_devices": devices_data["total"],
        }

