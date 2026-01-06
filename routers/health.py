"""API endpoints for device health monitoring."""
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from database import get_db
from models import Device, DeviceHealthMetrics, DeviceHealthHistory, User, UserRole, TelemetryLatest, DeviceSnapshot
from admin_auth import get_current_user, require_module

router = APIRouter()


class DeviceHealthResponse(BaseModel):
    """Device health metrics response."""
    device_id: int
    device_name: str
    device_identifier: str
    current_status: str
    last_seen_at: Optional[str]
    first_seen_at: Optional[str]
    
    # Connectivity
    message_count_24h: int
    message_count_7d: int
    avg_message_interval_seconds: Optional[float]
    connectivity_score: Optional[float]
    
    # Battery
    last_battery_level: Optional[float]
    battery_trend: Optional[str]
    estimated_battery_days_remaining: Optional[int]
    
    # Uptime
    uptime_24h_percent: Optional[float]
    uptime_7d_percent: Optional[float]
    uptime_30d_percent: Optional[float]
    
    calculated_at: Optional[str]
    
    class Config:
        from_attributes = True


class DeviceHealthHistoryResponse(BaseModel):
    """Device health history snapshot."""
    snapshot_at: str
    status: str
    battery_level: Optional[float]
    message_count_1h: int
    avg_message_interval_seconds: Optional[float]
    uptime_24h_percent: Optional[float]
    connectivity_score: Optional[float]
    
    class Config:
        from_attributes = True


@router.get("/devices/health", response_model=List[DeviceHealthResponse])
def list_device_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: online, offline, degraded"),
):
    """List health metrics for all devices.

    For tenant admins:
    - Read health from devices_snapshot.payload.health (database-only snapshot)
    - Battery and status come from payload.health

    For admins:
    - Use existing DeviceHealthMetrics as before
    """
    # Tenant admin path: use snapshot table
    if current_user.role == UserRole.TENANT_ADMIN:
        if not current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant admin has no tenant assigned"
            )

        # Only return unhealthy/offline devices (limit 100) - don't load all devices
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=18300)  # 5 hours 5 minutes
        cutoff_iso = cutoff.isoformat()
        
        # Query only devices that are offline or have issues (limit to 100 for performance)
        # Use JSONB queries to filter in SQL instead of loading all devices
        from sqlalchemy import text
        
        # Get offline devices: payload.is_active != true AND telemetry timestamp < cutoff
        # Handle both boolean and string values in JSONB
        offline_query = text("""
            SELECT device_id, payload
            FROM devices_snapshot
            WHERE tenant_id = :tenant_id
              AND (
                (payload->>'is_active')::text NOT IN ('true', 'True', 'TRUE')
                AND (payload->'is_active' != 'true'::jsonb OR payload->'is_active' IS NULL)
                OR (payload->'telemetry'->>'timestamp')::timestamptz < :cutoff::timestamptz
                OR (payload->'telemetry'->>'updated_at')::timestamptz < :cutoff::timestamptz
                OR (payload->'health'->>'last_seen_at')::timestamptz < :cutoff::timestamptz
                OR (payload->'telemetry'->>'timestamp') IS NULL
              )
            ORDER BY created_at DESC
            LIMIT 100
        """)
        
        offline_rows = db.execute(offline_query, {"tenant_id": current_user.tenant_id, "cutoff": cutoff_iso}).fetchall()
        
        # If status_filter is 'online', get online devices instead
        if status_filter == "online":
            online_query = text("""
                SELECT device_id, payload
                FROM devices_snapshot
                WHERE tenant_id = :tenant_id
                  AND (
                    (payload->>'is_active')::text IN ('true', 'True', 'TRUE')
                    OR payload->'is_active' = 'true'::jsonb
                    OR (payload->'telemetry'->>'timestamp')::timestamptz >= :cutoff::timestamptz
                    OR (payload->'telemetry'->>'updated_at')::timestamptz >= :cutoff::timestamptz
                    OR (payload->'health'->>'last_seen_at')::timestamptz >= :cutoff::timestamptz
                  )
                ORDER BY created_at DESC
                LIMIT 100
            """)
            rows = db.execute(online_query, {"tenant_id": current_user.tenant_id, "cutoff": cutoff_iso}).fetchall()
        elif status_filter:
            # Filtered by status - use offline query and filter in Python (small result set)
            rows = offline_rows
        else:
            # No filter - return offline devices (most important to show)
            rows = offline_rows

        results: List[DeviceHealthResponse] = []
        for idx, (device_id, payload_json) in enumerate(rows, start=1):
            # Parse payload JSON
            import json
            if isinstance(payload_json, dict):
                payload = payload_json
            else:
                try:
                    payload = json.loads(payload_json) if isinstance(payload_json, str) else payload_json or {}
                except (json.JSONDecodeError, TypeError):
                    payload = {}
            
            # payload already parsed above
            health = payload.get("health") or {}
            telemetry = payload.get("telemetry") or {}

            # Status
            current_status = health.get("status")
            if not current_status:
                current_status = "offline" if telemetry else "unknown"

            # Last seen: prefer health.last_seen_at, then telemetry timestamps
            last_seen_at = (
                health.get("last_seen_at")
                or telemetry.get("timestamp")
                or telemetry.get("updated_at")
            )

            # Battery: prefer health.battery.level, then telemetry.data.battery
            battery_level = None
            if isinstance(health.get("battery"), dict):
                battery_level = health["battery"].get("level")
            if battery_level is None and isinstance(telemetry.get("data"), dict):
                battery_level = telemetry["data"].get("battery")

            # Extract uptime percentages from health payload
            uptime_24h = health.get("uptime_24h_percent")
            uptime_7d = health.get("uptime_7d_percent")
            uptime_30d = health.get("uptime_30d_percent")
            
            # Extract connectivity score
            connectivity_score = health.get("connectivity_score")
            
            # Extract message counts if available
            message_count_24h = health.get("message_count_24h", 0)
            message_count_7d = health.get("message_count_7d", 0)
            avg_message_interval_seconds = health.get("avg_message_interval_seconds")
            
            # Extract battery trend and estimated days remaining
            battery_trend = None
            estimated_battery_days_remaining = None
            if isinstance(health.get("battery"), dict):
                battery_trend = health["battery"].get("trend")
                estimated_battery_days_remaining = health["battery"].get("estimated_days_remaining")

            # Apply status filter
            if status_filter and current_status != status_filter:
                continue

            # Build response (synthetic device_id for UI)
            results.append(
                DeviceHealthResponse(
                    device_id=idx,
                    device_name=payload.get("name") or device_id,
                    device_identifier=device_id,
                    current_status=current_status,
                    last_seen_at=last_seen_at,
                    first_seen_at=health.get("first_seen_at"),
                    message_count_24h=message_count_24h,
                    message_count_7d=message_count_7d,
                    avg_message_interval_seconds=avg_message_interval_seconds,
                    connectivity_score=connectivity_score,
                    last_battery_level=battery_level,
                    battery_trend=battery_trend,
                    estimated_battery_days_remaining=estimated_battery_days_remaining,
                    uptime_24h_percent=uptime_24h,
                    uptime_7d_percent=uptime_7d,
                    uptime_30d_percent=uptime_30d,
                    calculated_at=health.get("calculated_at"),
                )
            )

        return results

    # Admin path: original behaviour
    if current_user.role == UserRole.TENANT_ADMIN:
        # Should not reach here, but keep tenant filter as safety
        query = db.query(Device).filter(Device.tenant_id == current_user.tenant_id)
    else:
        query = db.query(Device)

    devices = query.all()
    results = []
    for device in devices:
        health = db.query(DeviceHealthMetrics).filter(
            DeviceHealthMetrics.device_id == device.id
        ).first()

        if not health:
            health_data = {
                "device_id": device.id,
                "device_name": device.name or device.device_id,
                "device_identifier": device.device_id,
                "current_status": "unknown",
                "last_seen_at": None,
                "first_seen_at": None,
                "message_count_24h": 0,
                "message_count_7d": 0,
                "avg_message_interval_seconds": None,
                "connectivity_score": None,
                "last_battery_level": None,
                "battery_trend": None,
                "estimated_battery_days_remaining": None,
                "uptime_24h_percent": None,
                "uptime_7d_percent": None,
                "uptime_30d_percent": None,
                "calculated_at": None,
            }
        else:
            health_data = {
                "device_id": device.id,
                "device_name": device.name or device.device_id,
                "device_identifier": device.device_id,
                "current_status": health.current_status,
                "last_seen_at": health.last_seen_at.isoformat() if health.last_seen_at else None,
                "first_seen_at": health.first_seen_at.isoformat() if health.first_seen_at else None,
                "message_count_24h": health.message_count_24h,
                "message_count_7d": health.message_count_7d,
                "avg_message_interval_seconds": health.avg_message_interval_seconds,
                "connectivity_score": health.connectivity_score,
                "last_battery_level": health.last_battery_level,
                "battery_trend": health.battery_trend,
                "estimated_battery_days_remaining": health.estimated_battery_days_remaining,
                "uptime_24h_percent": health.uptime_24h_percent,
                "uptime_7d_percent": health.uptime_7d_percent,
                "uptime_30d_percent": health.uptime_30d_percent,
                "calculated_at": health.calculated_at.isoformat() if health.calculated_at else None,
            }

        if status_filter and health_data["current_status"] != status_filter:
            continue

        results.append(DeviceHealthResponse(**health_data))

    return results


@router.get("/devices/{device_id}/health", response_model=DeviceHealthResponse)
def get_device_health(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed health metrics for a specific device."""

    # Tenant admin path: use devices_snapshot payload
    if current_user.role == UserRole.TENANT_ADMIN and current_user.tenant_id:
        snap = (
            db.query(DeviceSnapshot)
            .filter(
                DeviceSnapshot.tenant_id == current_user.tenant_id,
                DeviceSnapshot.device_id == str(device_id) if isinstance(device_id, str) else device_id,
            )
            .one_or_none()
        )
        # device_id here is numeric (path param), but snapshot uses string device_id; allow either
        if not snap:
            snap = (
                db.query(DeviceSnapshot)
                .filter(
                    DeviceSnapshot.tenant_id == current_user.tenant_id,
                    DeviceSnapshot.device_id == str(device_id),
                )
                .one_or_none()
            )
        if snap:
            payload = snap.payload or {}
            health = payload.get("health") or {}
            telemetry = payload.get("telemetry") or {}
            
            current_status = health.get("status")
            if not current_status:
                current_status = "offline" if telemetry else "unknown"
            
            last_seen_at = (
                health.get("last_seen_at")
                or telemetry.get("timestamp")
                or telemetry.get("updated_at")
            )
            
            battery_level = None
            if isinstance(health.get("battery"), dict):
                battery_level = health["battery"].get("level")
            if battery_level is None and isinstance(telemetry.get("data"), dict):
                battery_level = telemetry["data"].get("battery")
            
            # Extract all health metrics from payload
            uptime_24h = health.get("uptime_24h_percent")
            uptime_7d = health.get("uptime_7d_percent")
            uptime_30d = health.get("uptime_30d_percent")
            connectivity_score = health.get("connectivity_score")
            message_count_24h = health.get("message_count_24h", 0)
            message_count_7d = health.get("message_count_7d", 0)
            avg_message_interval_seconds = health.get("avg_message_interval_seconds")
            battery_trend = None
            estimated_battery_days_remaining = None
            if isinstance(health.get("battery"), dict):
                battery_trend = health["battery"].get("trend")
                estimated_battery_days_remaining = health["battery"].get("estimated_days_remaining")

            return DeviceHealthResponse(
                device_id=0,
                device_name=payload.get("name") or snap.device_id,
                device_identifier=snap.device_id,
                current_status=current_status,
                last_seen_at=last_seen_at,
                first_seen_at=health.get("first_seen_at"),
                message_count_24h=message_count_24h,
                message_count_7d=message_count_7d,
                avg_message_interval_seconds=avg_message_interval_seconds,
                connectivity_score=connectivity_score,
                last_battery_level=battery_level,
                battery_trend=battery_trend,
                estimated_battery_days_remaining=estimated_battery_days_remaining,
                uptime_24h_percent=uptime_24h,
                uptime_7d_percent=uptime_7d,
                uptime_30d_percent=uptime_30d,
                calculated_at=health.get("calculated_at"),
            )

    # Admin path: original behaviour
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to access this device"
        )
    
    health = db.query(DeviceHealthMetrics).filter(
        DeviceHealthMetrics.device_id == device_id
    ).first()
    
    if not health:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Health metrics not yet calculated for this device"
        )
    
    return DeviceHealthResponse(
        device_id=device.id,
        device_name=device.name or device.device_id,
        device_identifier=device.device_id,
        current_status=health.current_status,
        last_seen_at=health.last_seen_at.isoformat() if health.last_seen_at else None,
        first_seen_at=health.first_seen_at.isoformat() if health.first_seen_at else None,
        message_count_24h=health.message_count_24h,
        message_count_7d=health.message_count_7d,
        avg_message_interval_seconds=health.avg_message_interval_seconds,
        connectivity_score=health.connectivity_score,
        last_battery_level=health.last_battery_level,
        battery_trend=health.battery_trend,
        estimated_battery_days_remaining=health.estimated_battery_days_remaining,
        uptime_24h_percent=health.uptime_24h_percent,
        uptime_7d_percent=health.uptime_7d_percent,
        uptime_30d_percent=health.uptime_30d_percent,
        calculated_at=health.calculated_at.isoformat() if health.calculated_at else None,
    )


@router.get("/devices/{device_id}/health/history", response_model=List[DeviceHealthHistoryResponse])
def get_device_health_history(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    hours: int = Query(24, ge=1, le=720, description="Lookback window in hours (max 30 days)"),
):
    """Get historical health snapshots for a device."""

    # Tenant admin path: read from devices_snapshot.payload.health.history if present
    if current_user.role == UserRole.TENANT_ADMIN and current_user.tenant_id:
        snap = (
            db.query(DeviceSnapshot)
            .filter(
                DeviceSnapshot.tenant_id == current_user.tenant_id,
                DeviceSnapshot.device_id == str(device_id) if isinstance(device_id, str) else device_id,
            )
            .one_or_none()
        )
        if not snap:
            snap = (
                db.query(DeviceSnapshot)
                .filter(
                    DeviceSnapshot.tenant_id == current_user.tenant_id,
                    DeviceSnapshot.device_id == str(device_id),
                )
                .one_or_none()
            )
        if snap:
            payload = snap.payload or {}
            health = payload.get("health") or {}
            history_arr = health.get("history") or []  # list of snapshots
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            filtered = []
            for h in history_arr:
                ts = h.get("timestamp") or h.get("snapshot_at")
                if ts:
                    try:
                        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if ts_dt < cutoff:
                            continue
                    except Exception:
                        pass
                filtered.append(h)

            return [
                DeviceHealthHistoryResponse(
                    snapshot_at=h.get("timestamp") or h.get("snapshot_at") or "",
                    status=h.get("status") or "unknown",
                    battery_level=(h.get("battery") or {}).get("level"),
                    message_count_1h=h.get("message_count_1h") or 0,
                    avg_message_interval_seconds=h.get("avg_message_interval_seconds"),
                    uptime_24h_percent=h.get("uptime_24h_percent"),
                    connectivity_score=h.get("connectivity_score"),
                )
                for h in filtered
            ]

    # Admin path: original behaviour
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    
    if current_user.role == UserRole.TENANT_ADMIN:
        if device.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to access this device"
            )
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    history = db.query(DeviceHealthHistory).filter(
        DeviceHealthHistory.device_id == device_id,
        DeviceHealthHistory.snapshot_at >= cutoff
    ).order_by(DeviceHealthHistory.snapshot_at.desc()).all()
    
    return [
        DeviceHealthHistoryResponse(
            snapshot_at=h.snapshot_at.isoformat(),
            status=h.status,
            battery_level=h.battery_level,
            message_count_1h=h.message_count_1h,
            avg_message_interval_seconds=h.avg_message_interval_seconds,
            uptime_24h_percent=h.uptime_24h_percent,
            connectivity_score=h.connectivity_score,
        )
        for h in history
    ]


@router.get("/devices/{device_id}/health/battery-trend", response_model=dict)
def get_device_battery_trend(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=30, description="Lookback window in days"),
):
    """Get battery level trend over time."""

    # Tenant admin path: use devices_snapshot.payload.health.history battery levels
    if current_user.role == UserRole.TENANT_ADMIN and current_user.tenant_id:
        snap = (
            db.query(DeviceSnapshot)
            .filter(
                DeviceSnapshot.tenant_id == current_user.tenant_id,
                DeviceSnapshot.device_id == str(device_id) if isinstance(device_id, str) else device_id,
            )
            .one_or_none()
        )
        if not snap:
            snap = (
                db.query(DeviceSnapshot)
                .filter(
                    DeviceSnapshot.tenant_id == current_user.tenant_id,
                    DeviceSnapshot.device_id == str(device_id),
                )
                .one_or_none()
            )
        if snap:
            payload = snap.payload or {}
            health = payload.get("health") or {}
            history_arr = health.get("history") or []

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            data_points = []
            for h in history_arr:
                ts = h.get("timestamp") or h.get("snapshot_at")
                if not ts:
                    continue
                try:
                    ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if ts_dt < cutoff:
                        continue
                except Exception:
                    pass
                battery_level = None
                if isinstance(h.get("battery"), dict):
                    battery_level = h["battery"].get("level")
                if battery_level is not None:
                    data_points.append({
                        "timestamp": ts,
                        "battery_level": battery_level
                    })

            trend = "stable"
            if len(data_points) > 1:
                first = data_points[0]["battery_level"]
                last = data_points[-1]["battery_level"]
                if last > first:
                    trend = "increasing"
                elif last < first:
                    trend = "decreasing"

            return {
                "device_id": snap.device_id,
                "device_name": payload.get("name") or snap.device_id,
                "data_points": data_points,
                "trend": trend,
            }

    # Admin path: original behaviour
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    
    if current_user.role == UserRole.TENANT_ADMIN:
        if device.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to access this device"
            )
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    history = db.query(DeviceHealthHistory).filter(
        DeviceHealthHistory.device_id == device_id,
        DeviceHealthHistory.snapshot_at >= cutoff,
        DeviceHealthHistory.battery_level.isnot(None)
    ).order_by(DeviceHealthHistory.snapshot_at.asc()).all()
    
    return {
        "device_id": device_id,
        "device_name": device.name or device.device_id,
        "data_points": [
            {
                "timestamp": h.snapshot_at.isoformat(),
                "battery_level": h.battery_level,
            }
            for h in history
        ],
        "trend": "increasing" if len(history) > 1 and history[-1].battery_level > history[0].battery_level else "decreasing" if len(history) > 1 and history[-1].battery_level < history[0].battery_level else "stable"
    }

