"""Dashboard and telemetry read APIs.

These endpoints are read-only and optimized for UI dashboards, powered by the
telemetry-worker microservice that persists data from Kafka.
"""

from datetime import datetime, timedelta, date, timezone
from typing import Any, Dict, List, Optional
import statistics
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from admin_auth import require_admin, get_current_user
from database import get_db
from models import Device, DeviceDashboard, TelemetryLatest, TelemetryTimeseries, User, UserRole

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/devices/{device_id}/latest",
    response_model=Dict[str, Any],
)
def get_device_latest_telemetry(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return latest telemetry snapshot for a device."""
    device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Tenant admins can only access their own tenant's devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access devices from your own tenant"
        )

    latest = (
        db.query(TelemetryLatest)
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


@router.get(
    "/devices/{device_id}/history",
)
def get_device_history(
    device_id: str,
    key: str = Query(..., description="Telemetry field key, e.g. 'level'"),
    minutes: int = Query(60, ge=1, le=24 * 60, description="Lookback window in minutes"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return simple time-series history for a given device and key."""
    device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Tenant admins can only access their own tenant's devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access devices from your own tenant"
        )

    # Compute time window
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=minutes)

    rows = (
        db.query(TelemetryTimeseries)
        .filter(
            TelemetryTimeseries.device_id == device.id,
            TelemetryTimeseries.key == key,
            TelemetryTimeseries.ts >= cutoff,
        )
        .order_by(TelemetryTimeseries.ts.asc())
        .limit(500)
        .all()
    )

    points = [
        {"ts": row.ts.isoformat(), "value": row.value}
        for row in rows
    ]

    return {
        "device_id": device.device_id,
        "key": key,
        "points": points,
    }


@router.get(
    "/devices/{device_id}/dashboard",
)
def get_device_dashboard(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return dashboard configuration merged with latest telemetry."""
    device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Tenant admins can only access their own tenant's devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access devices from your own tenant"
        )

    dashboard = (
        db.query(DeviceDashboard)
        .filter(DeviceDashboard.device_id == device.id)
        .one_or_none()
    )

    # Start with empty dashboard - user builds it from widget library
    config = dashboard.config if dashboard else {"widgets": [], "layout": []}

    latest = (
        db.query(TelemetryLatest)
        .filter(TelemetryLatest.device_id == device.id)
        .one_or_none()
    )

    latest_payload = latest.data if latest else {}
    event_ts = latest.event_timestamp.isoformat() if latest and latest.event_timestamp else None

    return {
        "device_id": device.device_id,
        "config": config,
        "latest": {
            "data": latest_payload,
            "event_timestamp": event_ts,
        },
    }


@router.post(
    "/devices/{device_id}/dashboard",
)
def upsert_device_dashboard(
    device_id: str,
    body: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update dashboard configuration for a device."""
    device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Tenant admins can only access their own tenant's devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access devices from your own tenant"
        )

    config = body.get("config")
    if not isinstance(config, dict) or "widgets" not in config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid dashboard config payload",
        )

    dashboard = (
        db.query(DeviceDashboard)
        .filter(DeviceDashboard.device_id == device.id)
        .one_or_none()
    )
    if dashboard is None:
        dashboard = DeviceDashboard(device_id=device.id, config=config)
        db.add(dashboard)
    else:
        dashboard.config = config

    db.commit()

    return {"status": "ok"}


class ReadingItem(BaseModel):
    timestamp: str
    key: str
    value: Optional[float]
    is_anomaly: bool = False
    anomaly_reason: Optional[str] = None


@router.get(
    "/devices/{device_id}/readings",
    response_model=List[ReadingItem],
)
def get_device_readings(
    device_id: str,
    key: Optional[str] = Query(None, description="Filter by telemetry field key"),
    limit: int = Query(10, ge=1, le=1000, description="Maximum number of readings to return"),
    current_user: User = Depends(get_current_user),
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    detect_anomalies: bool = Query(True, description="Enable anomaly detection"),
    db: Session = Depends(get_db),
):
    """Return device readings (timeseries data) with optional filtering and anomaly detection.
    
    Returns the last N readings, optionally filtered by field key and date range.
    Anomaly detection uses statistical methods (Z-score) to identify outliers.
    """
    device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Tenant admins can only access their own tenant's devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access devices from your own tenant"
        )

    # Build query
    query = db.query(TelemetryTimeseries).filter(
        TelemetryTimeseries.device_id == device.id
    )
    
    if key:
        query = query.filter(TelemetryTimeseries.key == key)
    
    if from_date:
        from_dt = datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
        query = query.filter(TelemetryTimeseries.ts >= from_dt)
    
    if to_date:
        to_dt = datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)
        # Make it end of day
        to_dt = to_dt + timedelta(days=1)
        query = query.filter(TelemetryTimeseries.ts < to_dt)
    
    # Order by timestamp descending (most recent first)
    rows = query.order_by(TelemetryTimeseries.ts.desc()).limit(limit).all()
    
    # Convert to response format
    readings = [
        ReadingItem(
            timestamp=row.ts.isoformat(),
            key=row.key,
            value=row.value,
            is_anomaly=False,
            anomaly_reason=None,
        )
        for row in rows
    ]
    
    # Anomaly detection if enabled
    if detect_anomalies and readings:
        # Group readings by key for anomaly detection
        readings_by_key = defaultdict(list)
        for reading in readings:
            readings_by_key[reading.key].append(reading)
        
        # Detect anomalies per key
        for key, key_readings in readings_by_key.items():
            # Only detect anomalies for numeric values
            numeric_values = [r.value for r in key_readings if r.value is not None]
            if len(numeric_values) < 3:
                continue  # Need at least 3 values for statistical analysis
            
            # Calculate mean and standard deviation
            mean_val = statistics.mean(numeric_values)
            if len(numeric_values) > 1:
                std_val = statistics.stdev(numeric_values)
            else:
                std_val = 0
            
            # Mark anomalies (Z-score > 2 or < -2)
            threshold = 2.0
            for reading in key_readings:
                if reading.value is not None and std_val > 0:
                    z_score = abs((reading.value - mean_val) / std_val)
                    if z_score > threshold:
                        reading.is_anomaly = True
                        reading.anomaly_reason = f"Z-score: {z_score:.2f} (mean: {mean_val:.2f}, std: {std_val:.2f})"
    
    # Reverse to show oldest first (chronological order)
    readings.reverse()
    
    return readings


