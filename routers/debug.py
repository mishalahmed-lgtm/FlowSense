"""Debug endpoints for testing ExternalAPISyncService."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from admin_auth import get_current_user, require_admin
from models import User, Device, ExternalIntegration
from external_api_sync_service import external_api_sync_service
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/sync-service/status")
def get_sync_service_status():
    """Get status of ExternalAPISyncService. Public endpoint for debugging - no auth required."""
    status = external_api_sync_service.get_sync_status()
    return {
        "service_running": external_api_sync_service.is_running(),
        **status
    }


@router.post("/sync-service/test-one-device")
async def test_sync_one_device(
    device_id: str,
    db: Session = Depends(get_db),
):
    """Test syncing one device manually (for debugging)."""
    from config import settings
    import asyncio
    import aiohttp
    from datetime import datetime, timezone, timedelta
    import random
    import string
    
    # Get API config
    installations_api = getattr(settings, 'installations_api_url', None) or "https://flooddemo-qr2x.onrender.com/api/installations"
    smarttive_api_base = settings.external_device_api_base_url or "https://op1.smarttive.com/device/{}"
    smarttive_api_key = settings.external_device_api_key or "M2nJ5vKt8QwR3pLxT0yZ7aDbU1sH6cYe"
    
    # Get integration API key
    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.is_active == True
    ).first()
    flowsense_api_key = integration.api_key if integration else None
    
    if not flowsense_api_key:
        raise HTTPException(status_code=400, detail="No active integration API key found")
    
    # Get FlowSense URL
    import os
    flowsense_url = (
        settings.api_base_url or 
        os.getenv("API_BASE_URL") or 
        os.getenv("RENDER_EXTERNAL_URL") or
        "https://flowsense-772d.onrender.com"
    )
    
    # Helper functions (same as service)
    def now():
        return datetime.now(timezone.utc).isoformat() + "Z"
    
    def rand_float(a, b, r=2):
        return round(random.uniform(a, b), r)
    
    def rand_int(a, b):
        return random.randint(a, b)
    
    def random_history(value, points=3, spread=1.0):
        base = datetime.now(timezone.utc)
        return [
            {
                "timestamp": (base - timedelta(minutes=15 * i)).isoformat() + "Z",
                "value": round(value + random.uniform(-spread, spread), 2)
            }
            for i in reversed(range(points))
        ]
    
    def flatten_dict(d, parent="", out=None):
        if out is None:
            out = {}
        for k, v in d.items():
            key = f"{parent}.{k}" if parent else k
            if isinstance(v, dict):
                flatten_dict(v, key, out)
            else:
                out[key] = v
        return out
    
    # Fetch installations to find this device
    async with aiohttp.ClientSession() as session:
        async with session.get(installations_api, timeout=aiohttp.ClientTimeout(total=30)) as r:
            if r.status != 200:
                raise HTTPException(status_code=500, detail=f"Failed to fetch installations: HTTP {r.status}")
            installations_data = await r.json()
    
    # Handle different response formats
    if isinstance(installations_data, list):
        installations = installations_data
    elif isinstance(installations_data, dict):
        installations = installations_data.get('data', installations_data.get('installations', []))
    else:
        installations = []
    
    # Find the installation for this device
    install = None
    for inst in installations:
        if (inst.get("deviceId") or inst.get("device_id")) == device_id:
            install = inst
            break
    
    if not install:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found in installations")
    
    # Fetch telemetry
    url = smarttive_api_base.format(device_id.upper())
    headers = {"X-API-KEY": smarttive_api_key}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                telemetry = {}
            else:
                data = await r.json()
                telemetry = flatten_dict(data)
    
    # Build device data (same logic as service)
    def extract_location(install):
        loc = install.get("LocationCoordinates") or {}
        if isinstance(loc, dict) and loc.get("latitude") and loc.get("longitude"):
            return loc.get("latitude"), loc.get("longitude")
        if isinstance(loc, list) and len(loc) == 2:
            return loc[0], loc[1]
        if install.get("userLatitude") and install.get("userLongitude"):
            return install.get("userLatitude"), install.get("userLongitude")
        return None, None
    
    lat, lng = extract_location(install)
    
    if not telemetry:
        device_data = {
            "device_id": device_id,
            "name": install.get("deviceName") or install.get("name") or device_id,
            "device_type": {"id": 1, "name": "HTTP Device", "protocol": "HTTP"},
            "is_active": False,
            "metadata": {
                "installation_id": install.get("installationId"),
                "source": "external_installations_api",
                "no_telemetry": True
            }
        }
    else:
        level = telemetry.get("level", rand_float(20, 90))
        temperature = telemetry.get("temperature", rand_float(15, 40))
        battery = telemetry.get("battery", rand_int(40, 100))
        pressure = telemetry.get("pressure", rand_float(1.5, 2.5))
        dis_cm = telemetry.get("dis_cm", rand_float(10, 80))
        
        device_data = {
            "device_id": device_id,
            "name": install.get("deviceName") or install.get("name") or device_id,
            "device_type": {
                "id": 1,
                "name": "HTTP Device",
                "protocol": "HTTP",
                "description": "HTTP telemetry device"
            },
            "tenant_id": 2,
            "tenant_name": "Flowsense",
            "is_active": True,
            "is_provisioned": True,
            "location": {
                "latitude": lat,
                "longitude": lng,
                "address": None,
                "accuracy": rand_float(5, 25) if lat else None,
                "source": "gps" if lat else None,
                "updated_at": now()
            } if lat and lng else {},
            "telemetry": {
                "timestamp": now(),
                "updated_at": now(),
                "data": telemetry or {
                    "level": level,
                    "temperature": temperature,
                    "pressure": pressure,
                    "battery": battery,
                    "dis_cm": dis_cm
                }
            },
            "history": {
                "level": random_history(level),
                "temperature": random_history(temperature),
                "battery": random_history(battery),
                "pressure": random_history(pressure),
                "dis_cm": random_history(dis_cm)
            },
            "fields": [
                {"key": "level", "display_name": "Level", "field_type": "number", "unit": "%", "sample_value": level},
                {"key": "temperature", "display_name": "Temperature", "field_type": "number", "unit": "°C", "sample_value": temperature},
                {"key": "battery", "display_name": "Battery", "field_type": "number", "unit": "%", "sample_value": battery},
                {"key": "pressure", "display_name": "Pressure", "field_type": "number", "unit": "bar", "sample_value": pressure},
                {"key": "dis_cm", "display_name": "Dis Cm", "field_type": "number", "unit": "cm", "sample_value": dis_cm}
            ],
            "dashboard": {
                "widgets": [
                    {"id": "level-gauge", "type": "gauge", "field": "level"},
                    {"id": "temp-thermo", "type": "thermometer", "field": "temperature"},
                    {"id": "battery", "type": "battery", "field": "battery"}
                ],
                "layout": "grid"
            },
            "health": {
                "status": "online",
                "last_seen_at": now(),
                "battery": {
                    "level": battery,
                    "trend": "stable"
                }
            },
            "metadata": {
                "installation_id": install.get("installationId"),
                "source": "external_installations_api"
            },
            "created_at": now(),
            "updated_at": now()
        }
    
    # Return the device data structure (for inspection)
    return {
        "device_id": device_id,
        "has_telemetry": len(telemetry) > 0,
        "telemetry_fields": len(telemetry),
        "device_data_structure": {
            "keys": list(device_data.keys()),
            "is_active": device_data.get("is_active"),
            "has_location": bool(device_data.get("location")),
            "has_telemetry": bool(device_data.get("telemetry")),
            "has_history": bool(device_data.get("history")),
            "has_fields": bool(device_data.get("fields")),
            "has_dashboard": bool(device_data.get("dashboard")),
            "has_health": bool(device_data.get("health")),
        },
        "sample_data": {
            "location": device_data.get("location"),
            "telemetry_keys": list(device_data.get("telemetry", {}).get("data", {}).keys())[:10] if device_data.get("telemetry") else [],
            "history_keys": list(device_data.get("history", {}).keys())[:5] if device_data.get("history") else [],
            "fields_count": len(device_data.get("fields", [])),
            "dashboard_widgets": len(device_data.get("dashboard", {}).get("widgets", [])),
            "health_status": device_data.get("health", {}).get("status") if device_data.get("health") else None,
        },
        "full_payload": device_data  # Full payload for inspection
    }


@router.get("/sync-service/test-format")
def test_output_format():
    """Test if the output format matches expected structure."""
    from datetime import datetime, timezone, timedelta
    import random
    
    # Generate sample device data (same format as service)
    def now():
        return datetime.now(timezone.utc).isoformat() + "Z"
    
    def random_history(value, points=3):
        base = datetime.now(timezone.utc)
        return [
            {
                "timestamp": (base - timedelta(minutes=15 * i)).isoformat() + "Z",
                "value": round(value + random.uniform(-1, 1), 2)
            }
            for i in reversed(range(points))
        ]
    
    sample_device = {
        "device_id": "TEST_DEVICE_123",
        "name": "Test Device",
        "device_type": {
            "id": 1,
            "name": "HTTP Device",
            "protocol": "HTTP",
            "description": "HTTP telemetry device"
        },
        "tenant_id": 2,
        "tenant_name": "Flowsense",
        "is_active": True,
        "is_provisioned": True,
        "location": {
            "latitude": 24.7136,
            "longitude": 46.6753,
            "source": "gps",
            "updated_at": now()
        },
        "telemetry": {
            "timestamp": now(),
            "updated_at": now(),
            "data": {
                "level": 75.5,
                "temperature": 25.3,
                "battery": 85,
                "pressure": 2.1,
                "dis_cm": 45.2
            }
        },
        "history": {
            "level": random_history(75.5),
            "temperature": random_history(25.3),
            "battery": random_history(85),
            "pressure": random_history(2.1),
            "dis_cm": random_history(45.2)
        },
        "fields": [
            {"key": "level", "display_name": "Level", "field_type": "number", "unit": "%", "sample_value": 75.5},
            {"key": "temperature", "display_name": "Temperature", "field_type": "number", "unit": "°C", "sample_value": 25.3},
            {"key": "battery", "display_name": "Battery", "field_type": "number", "unit": "%", "sample_value": 85},
            {"key": "pressure", "display_name": "Pressure", "field_type": "number", "unit": "bar", "sample_value": 2.1},
            {"key": "dis_cm", "display_name": "Dis Cm", "field_type": "number", "unit": "cm", "sample_value": 45.2}
        ],
        "dashboard": {
            "widgets": [
                {"id": "level-gauge", "type": "gauge", "field": "level"},
                {"id": "temp-thermo", "type": "thermometer", "field": "temperature"},
                {"id": "battery", "type": "battery", "field": "battery"}
            ],
            "layout": "grid"
        },
        "health": {
            "status": "online",
            "last_seen_at": now(),
            "battery": {
                "level": 85,
                "trend": "stable"
            }
        },
        "metadata": {
            "installation_id": "INST_123",
            "source": "external_installations_api"
        },
        "created_at": now(),
        "updated_at": now()
    }
    
    # Validate structure
    required_keys = [
        "device_id", "name", "device_type", "is_active",
        "location", "telemetry", "history", "fields",
        "dashboard", "health", "metadata"
    ]
    
    missing_keys = [key for key in required_keys if key not in sample_device]
    
    validation = {
        "format_valid": len(missing_keys) == 0,
        "missing_keys": missing_keys,
        "structure": {
            "has_location": bool(sample_device.get("location")),
            "has_telemetry": bool(sample_device.get("telemetry")),
            "has_history": bool(sample_device.get("history")),
            "has_fields": bool(sample_device.get("fields")),
            "has_dashboard": bool(sample_device.get("dashboard")),
            "has_health": bool(sample_device.get("health")),
        },
        "telemetry_structure": {
            "has_data": bool(sample_device.get("telemetry", {}).get("data")),
            "has_timestamp": bool(sample_device.get("telemetry", {}).get("timestamp")),
            "data_fields": list(sample_device.get("telemetry", {}).get("data", {}).keys()),
        },
        "history_structure": {
            "fields": list(sample_device.get("history", {}).keys()),
            "sample_points": len(sample_device.get("history", {}).get("level", [])),
        },
        "dashboard_structure": {
            "has_widgets": bool(sample_device.get("dashboard", {}).get("widgets")),
            "widget_count": len(sample_device.get("dashboard", {}).get("widgets", [])),
            "widget_types": [w.get("type") for w in sample_device.get("dashboard", {}).get("widgets", [])],
        },
        "sample_device": sample_device
    }
    
    return validation

