"""Dashboard and telemetry read APIs.

These endpoints are read-only and optimized for UI dashboards, powered by the
telemetry-worker microservice that persists data from Kafka.
"""

from datetime import datetime, timedelta, date, timezone
from typing import Any, Dict, List, Optional
import logging
import statistics
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from admin_auth import require_admin, get_current_user
from database import get_db
from models import Device, DeviceDashboard, TelemetryLatest, TelemetryTimeseries, User, UserRole
from influx_client import influx_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

logger = logging.getLogger(__name__)


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
    "/activity",
)
def get_event_activity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return event activity (message count) over the last 24 hours.

    - For tenant admins: counts are scoped to their tenant's devices only.
    - For admins: counts cover all devices.
    - Buckets are 1-hour intervals over the last 24h.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    # Base query on TelemetryTimeseries joined to Device for tenant scoping
    bucket_expr = func.date_trunc("hour", TelemetryTimeseries.ts)

    query = (
        db.query(bucket_expr.label("bucket"), func.count().label("count"))
        .join(Device, Device.id == TelemetryTimeseries.device_id)
        .filter(TelemetryTimeseries.ts >= cutoff)
    )

    # Tenant admins only see their own tenant's activity
    if current_user.role == UserRole.TENANT_ADMIN and current_user.tenant_id:
        query = query.filter(Device.tenant_id == current_user.tenant_id)

    query = query.group_by(bucket_expr).order_by(bucket_expr)

    rows = query.all()
    bucket_map: Dict[datetime, int] = {row.bucket.replace(tzinfo=timezone.utc): row.count for row in rows}

    # Normalize to 24 hourly buckets, filling gaps with zeroes
    buckets: List[Dict[str, Any]] = []
    total_events = 0

    # Build from oldest -> newest
    for i in range(24):
        bucket_time = (now - timedelta(hours=23 - i)).replace(minute=0, second=0, microsecond=0)
        bucket_time = bucket_time.astimezone(timezone.utc)
        count = int(bucket_map.get(bucket_time, 0))
        total_events += count
        buckets.append(
            {
                "timestamp": bucket_time.isoformat(),
                "count": count,
            }
        )

    return {
        "total_events": total_events,
        "buckets": buckets,
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

    # Prefer InfluxDB time-series database when available for history queries
    points: List[Dict[str, Any]] = []
    if influx_service.enabled:
        try:
            points = influx_service.query_device_history(
                device_id=device.device_id,
                key=key,
                minutes=minutes,
                limit=500,
            )
        except Exception as exc:
            logger.warning(
                "Failed to query InfluxDB history for device_id=%s, key=%s: %s",
                device.device_id,
                key,
                exc,
            )

    # Fallback to PostgreSQL timeseries table if InfluxDB is disabled or returned no data
    if not points:
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


class FieldMetadata(BaseModel):
    """Metadata about a telemetry field for dynamic widget generation."""
    key: str
    display_name: str
    field_type: str  # "number", "boolean", "string", "object"
    unit: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    sample_value: Any = None


@router.get(
    "/devices/{device_id}/fields",
    response_model=List[FieldMetadata],
)
def get_device_fields(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Discover available telemetry fields for dynamic widget generation.
    
    Analyzes the latest telemetry payload and recent timeseries data to return
    metadata about each field, including suggested display names, data types,
    and value ranges. This enables dynamic widget creation without hardcoding
    field mappings for each device type.
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
    
    # Get latest telemetry to discover fields
    latest = (
        db.query(TelemetryLatest)
        .filter(TelemetryLatest.device_id == device.id)
        .one_or_none()
    )
    
    if not latest or not latest.data:
        return []
    
    # Recursively extract all fields from nested payload
    def extract_fields(obj: Any, prefix: str = "") -> List[Dict[str, Any]]:
        """Extract all fields from a nested dictionary."""
        fields = []
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                field_path = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, dict):
                    # Recurse into nested objects
                    fields.extend(extract_fields(value, field_path))
                elif isinstance(value, (int, float)):
                    fields.append({
                        "key": field_path,
                        "type": "number",
                        "sample_value": value
                    })
                elif isinstance(value, bool):
                    fields.append({
                        "key": field_path,
                        "type": "boolean",
                        "sample_value": value
                    })
                elif isinstance(value, str):
                    fields.append({
                        "key": field_path,
                        "type": "string",
                        "sample_value": value
                    })
        
        return fields
    
    discovered_fields = extract_fields(latest.data)
    
    # Get min/max values from timeseries for numeric fields
    field_metadata_list = []
    for field in discovered_fields:
        field_key = field["key"]
        field_type = field["type"]
        
        # Generate human-readable display name
        # Convert "battery.soc" -> "Battery SOC", "environment.temperature" -> "Environment Temperature"
        display_name = field_key.replace("_", " ").replace(".", " - ").title()
        
        # Try to detect common units from field names
        unit = None
        if "temp" in field_key.lower():
            unit = "°C"
        elif "humid" in field_key.lower():
            unit = "%"
        elif "voltage" in field_key.lower():
            unit = "V"
        elif "power" in field_key.lower() and "w" in field_key.lower():
            unit = "W"
        elif "soc" in field_key.lower() or "battery" in field_key.lower() and "level" not in field_key.lower():
            unit = "%"
        elif "pm25" in field_key.lower() or "pm10" in field_key.lower():
            unit = "μg/m³"
        elif "co2" in field_key.lower():
            unit = "ppm"
        
        # Get min/max from recent timeseries data (numeric fields only)
        min_val = None
        max_val = None
        if field_type == "number":
            stats = db.query(
                TelemetryTimeseries.value
            ).filter(
                TelemetryTimeseries.device_id == device.id,
                TelemetryTimeseries.key == field_key
            ).order_by(TelemetryTimeseries.ts.desc()).limit(100).all()
            
            if stats:
                values = [s[0] for s in stats if s[0] is not None]
                if values:
                    min_val = min(values)
                    max_val = max(values)
        
        field_metadata_list.append(FieldMetadata(
            key=field_key,
            display_name=display_name,
            field_type=field_type,
            unit=unit,
            min_value=min_val,
            max_value=max_val,
            sample_value=field["sample_value"]
        ))
    
    return field_metadata_list


