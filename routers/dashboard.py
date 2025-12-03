"""Dashboard and telemetry read APIs.

These endpoints are read-only and optimized for UI dashboards, powered by the
telemetry-worker microservice that persists data from Kafka.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from admin_auth import require_admin
from database import get_db
from models import Device, DeviceDashboard, TelemetryLatest, TelemetryTimeseries

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/devices/{device_id}/latest",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_admin)],
)
def get_device_latest_telemetry(
    device_id: str,
    db: Session = Depends(get_db),
):
    """Return latest telemetry snapshot for a device."""
    device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
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
    dependencies=[Depends(require_admin)],
)
def get_device_history(
    device_id: str,
    key: str = Query(..., description="Telemetry field key, e.g. 'level'"),
    minutes: int = Query(60, ge=1, le=24 * 60, description="Lookback window in minutes"),
    db: Session = Depends(get_db),
):
    """Return simple time-series history for a given device and key."""
    device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
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
    dependencies=[Depends(require_admin)],
)
def get_device_dashboard(
    device_id: str,
    db: Session = Depends(get_db),
):
    """Return dashboard configuration merged with latest telemetry."""
    device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
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
    dependencies=[Depends(require_admin)],
)
def upsert_device_dashboard(
    device_id: str,
    body: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """Create or update dashboard configuration for a device."""
    device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
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


