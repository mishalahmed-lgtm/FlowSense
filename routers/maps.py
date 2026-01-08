"""Maps and geographic visualization endpoints."""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from admin_auth import get_current_user
from database import get_db
from models import Device, TelemetryLatest, User, UserRole, DeviceSnapshot

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
    from datetime import datetime, timedelta, timezone
    
    result = []
    
    # Tenant admin path: use JSONB queries to extract location in SQL (never load all devices)
    if current_user.role == UserRole.TENANT_ADMIN and current_user.tenant_id:
        from sqlalchemy import text
        
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=600)  # 10 minutes
        cutoff_iso = cutoff.isoformat()
        
        # Use PostgreSQL JSONB to extract location directly in SQL - only get devices with location
        location_query = text("""
            SELECT 
                device_id,
                payload->>'name' as name,
                COALESCE(
                    (payload->'telemetry'->'data'->'location'->>'latitude')::float,
                    (payload->'telemetry'->'data'->'location'->>'lat')::float,
                    (payload->'telemetry'->'data'->>'latitude')::float,
                    (payload->'telemetry'->'data'->>'lat')::float
                ) as latitude,
                COALESCE(
                    (payload->'telemetry'->'data'->'location'->>'longitude')::float,
                    (payload->'telemetry'->'data'->'location'->>'lng')::float,
                    (payload->'telemetry'->'data'->'location'->>'lon')::float,
                    (payload->'telemetry'->'data'->>'longitude')::float,
                    (payload->'telemetry'->'data'->>'lng')::float,
                    (payload->'telemetry'->'data'->>'lon')::float
                ) as longitude,
                COALESCE(
                    (payload->'telemetry'->>'timestamp'),
                    (payload->'telemetry'->>'updated_at'),
                    (payload->'health'->>'last_seen_at')
                ) as last_seen_str,
                payload->'telemetry'->'data' as telemetry_data
            FROM devices_snapshot
            WHERE tenant_id = :tenant_id
              AND (
                (payload->'telemetry'->'data'->'location'->>'latitude') IS NOT NULL
                OR (payload->'telemetry'->'data'->'location'->>'lat') IS NOT NULL
                OR (payload->'telemetry'->'data'->>'latitude') IS NOT NULL
                OR (payload->'telemetry'->'data'->>'lat') IS NOT NULL
              )
              AND (
                (payload->'telemetry'->'data'->'location'->>'longitude') IS NOT NULL
                OR (payload->'telemetry'->'data'->'location'->>'lng') IS NOT NULL
                OR (payload->'telemetry'->'data'->'location'->>'lon') IS NOT NULL
                OR (payload->'telemetry'->'data'->>'longitude') IS NOT NULL
                OR (payload->'telemetry'->'data'->>'lng') IS NOT NULL
                OR (payload->'telemetry'->'data'->>'lon') IS NOT NULL
              )
        """)
        
        rows = db.execute(location_query, {"tenant_id": current_user.tenant_id}).fetchall()
        
        for row in rows:
            device_id, name, latitude, longitude, last_seen_str, telemetry_data = row
            
            if latitude is None or longitude is None:
                continue
            
            # Determine status from timestamp
            status = "inactive"
            last_seen = None
            if last_seen_str:
                try:
                    if isinstance(last_seen_str, str):
                        ts = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    else:
                        ts = last_seen_str
                    
                    time_diff = (now - ts).total_seconds()
                    if time_diff < 600:  # Active if seen in last 10 minutes
                        status = "active"
                    last_seen = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
                except (ValueError, TypeError, AttributeError):
                    pass
            
            result.append(DeviceLocation(
                device_id=device_id,
                device_name=name or device_id,
                latitude=float(latitude),
                longitude=float(longitude),
                status=status,
                last_seen=last_seen,
                latest_data=telemetry_data if isinstance(telemetry_data, dict) else {},
            ))
    else:
        # Admin path: original behaviour
        query = db.query(Device)
    
    # Tenant filtering
    if current_user.role == UserRole.TENANT_ADMIN:
        query = query.filter(Device.tenant_id == current_user.tenant_id)
    elif tenant_id:
        query = query.filter(Device.tenant_id == tenant_id)
    
    devices = query.all()
    
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
        
            # Skip if no location
            if latitude is None or longitude is None:
                continue
            
        # Determine status
        status = "inactive"
        last_seen = None
        if latest and latest.event_timestamp:
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
    
    # Tenant admin path: read from devices_snapshot
    if current_user.role == UserRole.TENANT_ADMIN and current_user.tenant_id:
        snap = (
            db.query(DeviceSnapshot)
            .filter(
                DeviceSnapshot.tenant_id == current_user.tenant_id,
                DeviceSnapshot.device_id == device_id,
            )
            .one_or_none()
        )
        
        if not snap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found",
            )
        
        payload = snap.payload or {}
        telemetry = payload.get("telemetry") or {}
        telemetry_data = telemetry.get("data") or {}
        
        latitude = None
        longitude = None
        
        if isinstance(telemetry_data, dict):
            # Check nested location object
            if "location" in telemetry_data and isinstance(telemetry_data["location"], dict):
                loc_obj = telemetry_data["location"]
                latitude = loc_obj.get("latitude") or loc_obj.get("lat")
                longitude = loc_obj.get("longitude") or loc_obj.get("lng") or loc_obj.get("lon")
            # Check top-level latitude/longitude
            elif "latitude" in telemetry_data:
                latitude = telemetry_data.get("latitude")
                longitude = telemetry_data.get("longitude")
            # Check top-level lat/lng/lon
            elif "lat" in telemetry_data:
                latitude = telemetry_data.get("lat")
                longitude = telemetry_data.get("lon") or telemetry_data.get("lng")
        
        if latitude is None or longitude is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device location not available"
            )
        
        name = payload.get("name") or snap.device_id
        telemetry_ts = telemetry.get("timestamp") or telemetry.get("updated_at")
        
        return {
            "device_id": device_id,
            "device_name": name,
            "latitude": latitude,
            "longitude": longitude,
            "timestamp": telemetry_ts,
        }
    
    # Admin path: original behaviour
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

