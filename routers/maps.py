"""Maps and geographic visualization endpoints."""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from admin_auth import get_current_user
from database import get_db
from models import Device, TelemetryLatest, User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maps", tags=["maps"])


class DeviceLocation(BaseModel):
    """Device location information for map visualization."""
    device_id: str
    device_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str  # active, inactive
    last_seen: Optional[str] = None
    latest_data: Optional[dict] = None


@router.get("/devices", response_model=List[DeviceLocation])
def get_devices_for_map(
    tenant_id: Optional[int] = Query(None, description="Filter by tenant ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all devices with location data for map visualization.
    
    Returns devices that have latitude/longitude in their telemetry data
    or device metadata, suitable for displaying on a map.
    """
    # Build query
    query = db.query(Device)
    
    # Tenant filtering
    if current_user.role == UserRole.TENANT_ADMIN:
        query = query.filter(Device.tenant_id == current_user.tenant_id)
    elif tenant_id:
        query = query.filter(Device.tenant_id == tenant_id)
    
    devices = query.all()
    
    result = []
    for device in devices:
        # Try to get location from latest telemetry
        latest = (
            db.query(TelemetryLatest)
            .filter(TelemetryLatest.device_id == device.id)
            .one_or_none()
        )
        
        latitude = None
        longitude = None
        latest_data = None
        
        if latest and latest.data:
            latest_data = latest.data
            # Check for location fields in various formats
            if isinstance(latest.data, dict):
                # Check nested location object
                if "location" in latest.data and isinstance(latest.data["location"], dict):
                    loc_obj = latest.data["location"]
                    latitude = loc_obj.get("latitude") or loc_obj.get("lat")
                    longitude = loc_obj.get("longitude") or loc_obj.get("lng") or loc_obj.get("lon")
                # Check top-level latitude/longitude
                elif "latitude" in latest.data:
                    latitude = latest.data.get("latitude")
                    longitude = latest.data.get("longitude")
                # Check top-level lat/lng/lon (alternative spelling)
                elif "lat" in latest.data:
                    latitude = latest.data.get("lat")
                    longitude = latest.data.get("lon") or latest.data.get("lng")
        
        # Determine status
        status = "inactive"
        last_seen = None
        if latest and latest.event_timestamp:
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            time_diff = (now - latest.event_timestamp).total_seconds()
            if time_diff < 600:  # Active if seen in last 10 minutes
                status = "active"
            last_seen = latest.event_timestamp.isoformat()
        
        result.append(DeviceLocation(
            device_id=device.device_id,
            device_name=device.name,
            latitude=latitude,
            longitude=longitude,
            status=status,
            last_seen=last_seen,
            latest_data=latest_data,
        ))
    
    return result


@router.get("/devices/{device_id}/location")
def get_device_location(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current location of a specific device."""
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
    
    # Get latest telemetry
    latest = (
        db.query(TelemetryLatest)
        .filter(TelemetryLatest.device_id == device.id)
        .one_or_none()
    )
    
    latitude = None
    longitude = None
    
    if latest and latest.data and isinstance(latest.data, dict):
        # Check nested location object
        if "location" in latest.data and isinstance(latest.data["location"], dict):
            loc_obj = latest.data["location"]
            latitude = loc_obj.get("latitude") or loc_obj.get("lat")
            longitude = loc_obj.get("longitude") or loc_obj.get("lng") or loc_obj.get("lon")
        # Check top-level latitude/longitude
        elif "latitude" in latest.data:
            latitude = latest.data.get("latitude")
            longitude = latest.data.get("longitude")
        # Check top-level lat/lng/lon (alternative spelling)
        elif "lat" in latest.data:
            latitude = latest.data.get("lat")
            longitude = latest.data.get("lon") or latest.data.get("lng")
    
    if latitude is None or longitude is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device location not available"
        )
    
    return {
        "device_id": device_id,
        "device_name": device.name,
        "latitude": latitude,
        "longitude": longitude,
        "timestamp": latest.event_timestamp.isoformat() if latest and latest.event_timestamp else None,
    }

