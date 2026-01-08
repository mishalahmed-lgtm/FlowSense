"""Device service - handles all device-related database queries sequentially."""

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from sqlalchemy import text, func
from sqlalchemy.orm import Session

from models import (
    Device, DeviceSnapshot, DeviceType, Tenant, TelemetryLatest,
    User, UserRole
)
from services.base_service import BaseService

logger = logging.getLogger(__name__)


class DeviceService(BaseService):
    """Service for device data access - all queries run sequentially."""
    
    def get_devices_paginated(
        self,
        user: User,
        page: int = 1,
        limit: int = 50,
        search: Optional[str] = None,
        device_status: Optional[str] = None,
        protocol: Optional[str] = None,
        include_counts: bool = True,
    ) -> Dict[str, Any]:
        """Get devices with pagination - all queries run sequentially.
        
        Query execution order:
        1. Count total devices
        2. Fetch paginated devices
        3. Fetch tenant name
        4. Count active devices (if include_counts=True)
        5. Count inactive devices (if include_counts=True)
        
        Args:
            user: Current authenticated user
            page: Page number (1-indexed)
            limit: Number of devices per page
            search: Search term for device_id or name
            status: Filter by status ('active' or 'inactive')
            protocol: Filter by protocol
            include_counts: Whether to include active/inactive counts
            
        Returns:
            Dictionary with devices, total, page, limit, total_pages, total_active, total_inactive
        """
        self._log_query("get_devices_paginated", f"user={user.email}, page={page}, limit={limit}")
        
        # Determine if tenant admin or global admin
        if user.role == UserRole.TENANT_ADMIN and user.tenant_id is not None:
            return self._get_devices_tenant_admin(
                user, page, limit, search, device_status, protocol, include_counts
            )
        else:
            return self._get_devices_global_admin(
                user, page, limit, search, device_status, protocol, include_counts
            )
    
    def _get_devices_tenant_admin(
        self,
        user: User,
        page: int,
        limit: int,
        search: Optional[str],
        device_status: Optional[str],
        protocol: Optional[str],
        include_counts: bool,
    ) -> Dict[str, Any]:
        """Get devices for tenant admin from devices_snapshot table.
        
        Sequential query execution:
        1. Build base query
        2. Apply search filter (if provided)
        3. Count total devices
        4. Fetch paginated devices
        5. Fetch tenant name
        6. Count active/inactive (if include_counts=True)
        7. Transform payload to response format
        """
        tenant_id = user.tenant_id
        
        # Query 1: Build base query
        self._log_query("build_base_query", f"tenant_id={tenant_id}")
        snapshot_query = self.db.query(DeviceSnapshot).filter(
            DeviceSnapshot.tenant_id == tenant_id
        )
        
        # Query 2: Apply search filter
        if search:
            self._log_query("apply_search_filter", f"search={search}")
            search_term = f"%{search.lower()}%"
            snapshot_query = snapshot_query.filter(
                DeviceSnapshot.device_id.ilike(search_term)
            )
        
        # Query 3: Count total devices (SEQUENTIAL - wait for this to complete)
        self._log_query("count_total_devices", "counting total matching devices")
        total_count = snapshot_query.count()
        logger.info(f"Total devices found: {total_count}")
        
        # Query 4: Fetch paginated devices (SEQUENTIAL - after count completes)
        offset = (page - 1) * limit
        self._log_query("fetch_paginated_devices", f"offset={offset}, limit={limit}")
        snapshots = (
            snapshot_query
            .order_by(DeviceSnapshot.device_id)
            .offset(offset)
            .limit(limit)
            .all()
        )
        logger.info(f"Fetched {len(snapshots)} devices from database")
        
        # Query 5: Fetch tenant name (SEQUENTIAL)
        self._log_query("fetch_tenant_name", f"tenant_id={tenant_id}")
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        tenant_name = tenant.name if tenant else f"Tenant {tenant_id}"
        
        # Query 6 & 7: Count active/inactive (SEQUENTIAL - if requested)
        total_active_count = None
        total_inactive_count = None
        if include_counts:
            self._log_query("count_active_devices", "counting devices with is_active=true")
            try:
                active_query = text("""
                    SELECT COUNT(*) 
                    FROM devices_snapshot 
                    WHERE tenant_id = :tenant_id
                      AND (payload->>'is_active')::text = 'true'
                """)
                active_result = self.db.execute(active_query, {"tenant_id": tenant_id}).scalar()
                total_active_count = active_result or 0
                logger.info(f"Active devices count: {total_active_count}")
                
                # Query 7: Count total for inactive calculation
                self._log_query("count_total_for_inactive", "calculating inactive count")
                total_count_query = self.db.query(func.count(DeviceSnapshot.device_id)).filter(
                    DeviceSnapshot.tenant_id == tenant_id
                ).scalar()
                
                total_inactive_count = (total_count_query or 0) - total_active_count
                logger.info(f"Inactive devices count: {total_inactive_count}")
            except Exception as e:
                logger.error(f"Error counting devices: {e}", exc_info=True)
                total_active_count = None
                total_inactive_count = None
        
        # Transform snapshots to response format (no DB queries here)
        devices = self._transform_snapshots_to_devices(
            snapshots, tenant_id, tenant_name, offset
        )
        
        # Calculate pagination
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
        
        return {
            "devices": devices,
            "total": total_count,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "total_active": total_active_count,
            "total_inactive": total_inactive_count,
        }
    
    def _get_devices_global_admin(
        self,
        user: User,
        page: int,
        limit: int,
        search: Optional[str],
        device_status: Optional[str],
        protocol: Optional[str],
        include_counts: bool,
    ) -> Dict[str, Any]:
        """Get devices for global admin from devices table.
        
        Sequential query execution:
        1. Build base query with joins
        2. Apply filters (search, status, protocol)
        3. Count total devices
        4. Fetch paginated devices
        5. Fetch telemetry_latest for pagination window
        6. Count active/inactive (if include_counts=True)
        7. Transform to response format
        """
        # Query 1: Build base query with joins
        self._log_query("build_base_query_with_joins", "joining device_type and tenant")
        query = (
            self.db.query(Device)
            .join(DeviceType, Device.device_type_id == DeviceType.id, isouter=True)
            .join(Tenant, Device.tenant_id == Tenant.id, isouter=True)
        )
        
        # Query 2: Apply filters
        if search:
            self._log_query("apply_search_filter", f"search={search}")
            search_term = f"%{search}%"
            query = query.filter(
                (Device.device_id.ilike(search_term)) | (Device.name.ilike(search_term))
            )
        
        if protocol:
            self._log_query("apply_protocol_filter", f"protocol={protocol}")
            query = query.filter(DeviceType.protocol == protocol)
        
        # Query 3: Count total devices (SEQUENTIAL)
        self._log_query("count_total_devices", "counting total matching devices")
        total_count = query.count()
        logger.info(f"Total devices found: {total_count}")
        
        # Query 4: Fetch paginated devices (SEQUENTIAL)
        offset = (page - 1) * limit
        self._log_query("fetch_paginated_devices", f"offset={offset}, limit={limit}")
        devices = (
            query
            .order_by(Device.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        logger.info(f"Fetched {len(devices)} devices from database")
        
        # Query 5: Fetch telemetry_latest for this pagination window (SEQUENTIAL)
        if devices:
            device_ids = [d.id for d in devices]
            self._log_query("fetch_telemetry_latest", f"fetching for {len(device_ids)} devices")
            telemetry_map = self._fetch_telemetry_latest_map(device_ids)
        else:
            telemetry_map = {}
        
        # Query 6 & 7: Count active/inactive (SEQUENTIAL - if requested)
        total_active_count = None
        total_inactive_count = None
        if include_counts:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=18300)
            
            self._log_query("count_active_devices", "counting devices with recent telemetry")
            try:
                active_count_query = (
                    self.db.query(func.count(func.distinct(Device.id)))
                    .join(TelemetryLatest, Device.id == TelemetryLatest.device_id, isouter=True)
                    .filter(TelemetryLatest.updated_at >= cutoff)
                )
                total_active_count = active_count_query.scalar() or 0
                logger.info(f"Active devices count: {total_active_count}")
                
                self._log_query("calculate_inactive_count", "total - active")
                total_inactive_count = total_count - total_active_count
                logger.info(f"Inactive devices count: {total_inactive_count}")
            except Exception as e:
                logger.error(f"Error counting devices: {e}", exc_info=True)
                total_active_count = None
                total_inactive_count = None
        
        # Transform to response format (no DB queries)
        device_responses = self._transform_devices_to_response(
            devices, telemetry_map
        )
        
        # Apply status filter in Python (if needed)
        if device_status:
            if device_status == "active":
                device_responses = [d for d in device_responses if d.get("is_active")]
            elif device_status == "inactive":
                device_responses = [d for d in device_responses if not d.get("is_active")]
        
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
        
        return {
            "devices": device_responses,
            "total": total_count,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "total_active": total_active_count,
            "total_inactive": total_inactive_count,
        }
    
    def _fetch_telemetry_latest_map(self, device_ids: List[int]) -> Dict[int, Any]:
        """Fetch telemetry_latest for a list of device IDs (single query)."""
        telemetry_records = (
            self.db.query(TelemetryLatest.device_id, TelemetryLatest.updated_at)
            .filter(TelemetryLatest.device_id.in_(device_ids))
            .all()
        )
        return {rec[0]: rec[1] for rec in telemetry_records}
    
    def _transform_snapshots_to_devices(
        self,
        snapshots: List[DeviceSnapshot],
        tenant_id: int,
        tenant_name: str,
        offset: int,
    ) -> List[Dict[str, Any]]:
        """Transform DeviceSnapshot objects to device response format."""
        devices = []
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=18300)  # 5 hours 5 minutes
        
        for idx, snap in enumerate(snapshots, start=1 + offset):
            payload = snap.payload or {}
            if not isinstance(payload, dict):
                payload = {}
            
            # Extract fields from payload
            name = (
                payload.get("name") or 
                payload.get("device_name") or 
                payload.get("deviceName") or 
                payload.get("label") or 
                payload.get("title") or 
                snap.device_id
            )
            
            # Device type
            device_type_name = "Snapshot Device"
            device_type_id = 0
            protocol = "HTTP"
            
            device_type_obj = payload.get("device_type")
            if isinstance(device_type_obj, dict):
                device_type_name = device_type_obj.get("name") or device_type_name
                protocol = device_type_obj.get("protocol") or protocol
                device_type_id = device_type_obj.get("id") or 0
            elif isinstance(device_type_obj, str):
                device_type_name = device_type_obj
            
            if payload.get("protocol"):
                protocol = payload["protocol"]
            
            # Determine if device is active
            is_active = payload.get("is_active", False)
            
            # Metadata
            payload_metadata = payload.get("metadata") or {}
            if isinstance(payload_metadata, dict):
                metadata = {
                    "http_settings": payload_metadata.get("http_settings"),
                    "mqtt_settings": payload_metadata.get("mqtt_settings"),
                    "tcp_settings": payload_metadata.get("tcp_settings"),
                    "extras": payload_metadata.get("extras") or payload,
                    "external_data": payload_metadata.get("external_data"),
                    "external_data_synced_at": payload_metadata.get("external_data_synced_at"),
                }
            else:
                metadata = {"extras": payload}
            
            # Dashboard config
            dashboard_cfg = payload.get("dashboard") or {}
            has_dashboard = bool(dashboard_cfg.get("widgets") and len(dashboard_cfg.get("widgets", [])) > 0)
            
            devices.append({
                "id": idx,
                "device_id": snap.device_id,
                "name": name,
                "device_type": device_type_name,
                "device_type_id": device_type_id,
                "protocol": protocol,
                "tenant": tenant_name,
                "tenant_id": tenant_id,
                "is_active": is_active,
                "metadata": metadata,
                "provisioning_key": None,
                "has_dashboard": has_dashboard,
            })
        
        return devices
    
    def _transform_devices_to_response(
        self,
        devices: List[Device],
        telemetry_map: Dict[int, datetime],
    ) -> List[Dict[str, Any]]:
        """Transform Device objects to response format."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=18300)
        device_responses = []
        
        for device in devices:
            # Determine if device is active based on telemetry timestamp
            last_telemetry = telemetry_map.get(device.id)
            is_active = bool(last_telemetry and last_telemetry >= cutoff)
            
            device_responses.append({
                "id": device.id,
                "device_id": device.device_id,
                "name": device.name or device.device_id,
                "device_type": device.device_type.name if device.device_type else "Unknown",
                "device_type_id": device.device_type_id or 0,
                "protocol": device.device_type.protocol if device.device_type else "HTTP",
                "tenant": device.tenant.name if device.tenant else "Unknown",
                "tenant_id": device.tenant_id,
                "is_active": is_active,
                "metadata": device.metadata or {},
                "provisioning_key": None,
                "has_dashboard": False,  # Would need another query to check
            })
        
        return device_responses
    
    def get_device_by_id(self, device_id: str, user: User) -> Optional[Dict[str, Any]]:
        """Get a single device by device_id.
        
        Sequential query execution:
        1. Query device from devices_snapshot (tenant admin) or devices (global admin)
        2. Verify tenant access
        3. Return device data
        """
        self._log_query("get_device_by_id", f"device_id={device_id}, user={user.email}")
        
        if user.role == UserRole.TENANT_ADMIN and user.tenant_id is not None:
            # Query from snapshot
            snap = (
                self.db.query(DeviceSnapshot)
                .filter(
                    DeviceSnapshot.tenant_id == user.tenant_id,
                    DeviceSnapshot.device_id == device_id,
                )
                .one_or_none()
            )
            if not snap:
                return None
            
            # Transform to response
            devices = self._transform_snapshots_to_devices(
                [snap], user.tenant_id, "Tenant", 0
            )
            return devices[0] if devices else None
        else:
            # Query from devices table
            device = (
                self.db.query(Device)
                .filter(Device.device_id == device_id)
                .one_or_none()
            )
            if not device:
                return None
            
            # Fetch telemetry
            telemetry_map = self._fetch_telemetry_latest_map([device.id])
            
            # Transform to response
            devices = self._transform_devices_to_response([device], telemetry_map)
            return devices[0] if devices else None
    
    def get_device_health_summary(self, user: User) -> Dict[str, Any]:
        """Get device health summary (online/offline/unhealthy counts).
        
        Sequential query execution:
        1. Count online devices (last_seen < 5 hours ago)
        2. Count offline devices (last_seen > 5 hours ago)
        3. Count unhealthy devices (any health issues)
        
        Args:
            user: Current authenticated user
            
        Returns:
            Dictionary with online_count, offline_count, unhealthy_count
        """
        self._log_query("get_device_health_summary", f"user={user.email}")
        
        if user.role == UserRole.TENANT_ADMIN and user.tenant_id is not None:
            tenant_id = user.tenant_id
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=18300)  # 5 hours 5 minutes
            
            # Query 1: Count online devices
            self._log_query("count_online_devices", f"tenant_id={tenant_id}")
            online_query = text("""
                SELECT COUNT(*)
                FROM devices_snapshot
                WHERE tenant_id = :tenant_id
                  AND (
                    (payload->>'is_active')::text = 'true'
                    OR (payload->'telemetry'->>'timestamp')::timestamptz >= CAST(:cutoff AS timestamptz)
                  )
            """)
            online_count = self.db.execute(online_query, {"tenant_id": tenant_id, "cutoff": cutoff.isoformat()}).scalar() or 0
            
            # Query 2: Count total devices
            self._log_query("count_total_devices", f"tenant_id={tenant_id}")
            total_count = self.db.query(func.count(DeviceSnapshot.device_id)).filter(
                DeviceSnapshot.tenant_id == tenant_id
            ).scalar() or 0
            
            # Query 3: Count offline (total - online)
            offline_count = total_count - online_count
            
            # Query 4: Count unhealthy (devices with health issues)
            self._log_query("count_unhealthy_devices", f"tenant_id={tenant_id}")
            unhealthy_query = text("""
                SELECT COUNT(*)
                FROM devices_snapshot
                WHERE tenant_id = :tenant_id
                  AND (
                    (payload->'health'->>'status')::text IN ('error', 'warning', 'critical')
                    OR (payload->'health'->>'last_seen_at')::timestamptz < CAST(:cutoff AS timestamptz)
                  )
            """)
            unhealthy_count = self.db.execute(unhealthy_query, {"tenant_id": tenant_id, "cutoff": cutoff.isoformat()}).scalar() or 0
            
            return {
                "online_count": online_count,
                "offline_count": offline_count,
                "unhealthy_count": unhealthy_count,
                "total_count": total_count,
            }
        else:
            # Global admin path
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=18300)
            
            self._log_query("count_online_devices_global", "counting devices with recent telemetry")
            online_count = (
                self.db.query(func.count(func.distinct(Device.id)))
                .join(TelemetryLatest, Device.id == TelemetryLatest.device_id, isouter=True)
                .filter(TelemetryLatest.updated_at >= cutoff)
                .scalar() or 0
            )
            
            self._log_query("count_total_devices_global", "counting all devices")
            total_count = self.db.query(func.count(Device.id)).scalar() or 0
            
            offline_count = total_count - online_count
            
            self._log_query("count_unhealthy_devices_global", "counting unhealthy devices")
            unhealthy_count = (
                self.db.query(func.count(Device.id))
                .join(TelemetryLatest, Device.id == TelemetryLatest.device_id, isouter=True)
                .filter(TelemetryLatest.updated_at < cutoff)
                .scalar() or 0
            )
            
            return {
                "online_count": online_count,
                "offline_count": offline_count,
                "unhealthy_count": unhealthy_count,
                "total_count": total_count,
            }

