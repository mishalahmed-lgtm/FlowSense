"""API endpoints for device health monitoring."""
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from database import get_db
from models import Device, DeviceHealthMetrics, DeviceHealthHistory, User, UserRole, TelemetryLatest
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
    """List health metrics for all devices (tenant-scoped for tenant admins)."""
    if current_user.role == UserRole.TENANT_ADMIN:
        # Tenant admin: only their tenant's devices
        if not current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant admin has no tenant assigned"
            )
        query = db.query(Device).filter(Device.tenant_id == current_user.tenant_id)
    else:
        # Admin: all devices
        query = db.query(Device)
    
    devices = query.filter(Device.is_active == True).all()
    
    results = []
    for device in devices:
        health = db.query(DeviceHealthMetrics).filter(
            DeviceHealthMetrics.device_id == device.id
        ).first()
        
        if not health:
            # Return default values if no health data yet
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
        
        # Apply status filter
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
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    
    # Tenant admin can only access their tenant's devices
    if current_user.role == UserRole.TENANT_ADMIN:
        if device.tenant_id != current_user.tenant_id:
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
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    
    # Tenant admin can only access their tenant's devices
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
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    
    # Tenant admin can only access their tenant's devices
    if current_user.role == UserRole.TENANT_ADMIN:
        if device.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to access this device"
            )
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get battery data from health history
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

