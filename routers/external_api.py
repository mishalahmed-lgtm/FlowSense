"""External API endpoints for integrations using API key authentication."""
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Security, status, Header, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import ExternalIntegration, User, Device, DeviceHealthMetrics, TelemetryLatest, DeviceType

logger = logging.getLogger(__name__)

# Try to import telemetry producer (may not be available in all contexts)
try:
    from kafka_producer import telemetry_producer
    from rule_engine import rule_engine
    TELEMETRY_AVAILABLE = True
except ImportError:
    TELEMETRY_AVAILABLE = False
    logger.warning("Telemetry producer not available, POST /external/data will be limited")

router = APIRouter(prefix="/external", tags=["external-api"])

# API Key header for external integrations
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_external_integration(
    api_key: Optional[str] = Security(api_key_header),
    db: Session = Depends(get_db),
) -> ExternalIntegration:
    """Verify API key and return the external integration."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header.",
        )
    
    integration = db.query(ExternalIntegration).filter(
        ExternalIntegration.api_key == api_key,
        ExternalIntegration.is_active == True,
    ).first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
        )
    
    # Update last_used_at
    integration.last_used_at = datetime.now(timezone.utc)
    db.commit()
    
    return integration


def check_endpoint_permission(integration: ExternalIntegration, endpoint: str):
    """Check if integration has permission to access the endpoint."""
    allowed = integration.allowed_endpoints or []
    if endpoint not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key does not have permission to access '{endpoint}' endpoint",
        )


def get_user_from_integration(integration: ExternalIntegration, db: Session) -> User:
    """Get the user associated with the integration."""
    user = db.query(User).filter(User.id == integration.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User associated with this API key is not active",
        )
    return user


# ============================================
# Response Models
# ============================================

class DeviceHealthResponse(BaseModel):
    device_id: str
    device_name: Optional[str]
    current_status: str
    last_seen_at: Optional[str]
    message_count_24h: int
    connectivity_score: Optional[float]
    last_battery_level: Optional[float]
    uptime_24h_percent: Optional[float]

    class Config:
        from_attributes = True


class DeviceResponse(BaseModel):
    id: int
    device_id: str
    name: Optional[str]
    device_type: Optional[str]
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class TelemetryDataResponse(BaseModel):
    device_id: str
    device_name: Optional[str]
    timestamp: str
    data: Dict[str, Any]

    class Config:
        from_attributes = True


# ============================================
# Request Models for POST endpoints
# ============================================

class ExternalDeviceCreate(BaseModel):
    """Request model for creating/updating devices via external API."""
    device_id: str = Field(..., description="Unique device identifier")
    name: Optional[str] = None
    device_type_name: Optional[str] = Field(None, description="Device type name (e.g., 'MQTT', 'HTTP')")
    device_type_id: Optional[int] = Field(None, description="Device type ID (alternative to device_type_name)")
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None


class ExternalTelemetryPayload(BaseModel):
    """Request model for sending telemetry data via external API."""
    device_id: str = Field(..., description="Device identifier")
    data: Dict[str, Any] = Field(..., description="Telemetry payload data")
    timestamp: Optional[str] = Field(None, description="ISO timestamp (defaults to now)")


class ExternalHealthData(BaseModel):
    """Request model for sending health data via external API."""
    device_id: str = Field(..., description="Device identifier")
    current_status: Optional[str] = Field(None, description="Status: online, offline, degraded")
    last_seen_at: Optional[str] = Field(None, description="ISO timestamp of last seen")
    message_count_24h: Optional[int] = None
    connectivity_score: Optional[float] = Field(None, ge=0, le=100)
    last_battery_level: Optional[float] = Field(None, ge=0, le=100)
    uptime_24h_percent: Optional[float] = Field(None, ge=0, le=100)


# ============================================
# External API Endpoints
# ============================================

@router.get("/health", response_model=List[DeviceHealthResponse])
def get_health_data(
    integration: ExternalIntegration = Depends(get_external_integration),
    db: Session = Depends(get_db),
    status_filter: Optional[str] = None,
):
    """Get health data for all devices in the tenant (requires 'health' permission)."""
    check_endpoint_permission(integration, "health")
    user = get_user_from_integration(integration, db)
    
    if not user.tenant_id:
        return []
    
    # Get all devices for the tenant
    devices = db.query(Device).filter(
        Device.tenant_id == user.tenant_id
    ).all()
    
    results = []
    for device in devices:
        health = db.query(DeviceHealthMetrics).filter(
            DeviceHealthMetrics.device_id == device.id
        ).first()
        
        if not health:
            health_data = {
                "device_id": device.device_id,
                "device_name": device.name or device.device_id,
                "current_status": "unknown",
                "last_seen_at": None,
                "message_count_24h": 0,
                "connectivity_score": None,
                "last_battery_level": None,
                "uptime_24h_percent": None,
            }
        else:
            health_data = {
                "device_id": device.device_id,
                "device_name": device.name or device.device_id,
                "current_status": health.current_status,
                "last_seen_at": health.last_seen_at.isoformat() if health.last_seen_at else None,
                "message_count_24h": health.message_count_24h,
                "connectivity_score": health.connectivity_score,
                "last_battery_level": health.last_battery_level,
                "uptime_24h_percent": health.uptime_24h_percent,
            }
        
        # Apply status filter
        if status_filter and health_data["current_status"] != status_filter:
            continue
        
        results.append(DeviceHealthResponse(**health_data))
    
    return results


@router.get("/devices", response_model=List[DeviceResponse])
def get_devices(
    integration: ExternalIntegration = Depends(get_external_integration),
    db: Session = Depends(get_db),
):
    """Get list of devices in the tenant (requires 'devices' permission)."""
    check_endpoint_permission(integration, "devices")
    user = get_user_from_integration(integration, db)
    
    if not user.tenant_id:
        return []
    
    devices = db.query(Device).filter(
        Device.tenant_id == user.tenant_id
    ).all()
    
    results = []
    for device in devices:
        device_type_name = device.device_type.name if device.device_type else None
        results.append(DeviceResponse(
            id=device.id,
            device_id=device.device_id,
            name=device.name,
            device_type=device_type_name,
            is_active=device.is_active,
            created_at=device.created_at.isoformat() if device.created_at else "",
        ))
    
    return results


@router.get("/data", response_model=List[TelemetryDataResponse])
def get_telemetry_data(
    integration: ExternalIntegration = Depends(get_external_integration),
    db: Session = Depends(get_db),
    device_id: Optional[str] = None,
    limit: int = 100,
):
    """Get latest telemetry data (requires 'data' permission)."""
    check_endpoint_permission(integration, "data")
    user = get_user_from_integration(integration, db)
    
    if not user.tenant_id:
        return []
    
    # Build query
    query = db.query(TelemetryLatest).join(Device).filter(
        Device.tenant_id == user.tenant_id
    )
    
    if device_id:
        query = query.filter(Device.device_id == device_id)
    
    # Get latest telemetry
    telemetry_records = query.order_by(
        TelemetryLatest.timestamp.desc()
    ).limit(limit).all()
    
    results = []
    for record in telemetry_records:
        device = db.query(Device).filter(Device.id == record.device_id).first()
        if not device:
            continue
        
        # Parse payload JSON
        import json
        try:
            payload_data = json.loads(record.payload) if isinstance(record.payload, str) else record.payload
        except:
            payload_data = {}
        
        results.append(TelemetryDataResponse(
            device_id=device.device_id,
            device_name=device.name or device.device_id,
            timestamp=record.timestamp.isoformat() if record.timestamp else "",
            data=payload_data,
        ))
    
    return results


@router.get("/data/{device_id}", response_model=TelemetryDataResponse)
def get_device_telemetry(
    device_id: str,
    integration: ExternalIntegration = Depends(get_external_integration),
    db: Session = Depends(get_db),
):
    """Get latest telemetry for a specific device (requires 'data' permission)."""
    check_endpoint_permission(integration, "data")
    user = get_user_from_integration(integration, db)
    
    if not user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Get device
    device = db.query(Device).filter(
        Device.device_id == device_id,
        Device.tenant_id == user.tenant_id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Get latest telemetry
    record = db.query(TelemetryLatest).filter(
        TelemetryLatest.device_id == device.id
    ).order_by(TelemetryLatest.timestamp.desc()).first()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No telemetry data found for this device",
        )
    
    # Parse payload JSON
    import json
    try:
        payload_data = json.loads(record.payload) if isinstance(record.payload, str) else record.payload
    except:
        payload_data = {}
    
    return TelemetryDataResponse(
        device_id=device.device_id,
        device_name=device.name or device.device_id,
        timestamp=record.timestamp.isoformat() if record.timestamp else "",
        data=payload_data,
    )


# ============================================
# POST Endpoints for External Systems to Send Data
# ============================================

@router.post("/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_device(
    payload: ExternalDeviceCreate,
    request: Request,
    integration: ExternalIntegration = Depends(get_external_integration),
    db: Session = Depends(get_db),
):
    """Create or update a device (requires 'devices' permission)."""
    # Log incoming payload for debugging
    logger.info(f"[External API] Received device payload: device_id={payload.device_id}, name={payload.name}, device_type_name={payload.device_type_name}, device_type_id={payload.device_type_id}, is_active={payload.is_active}, metadata={payload.metadata}")
    logger.info(f"[External API] Request path: {request.url.path}, Custom endpoint URLs: {integration.endpoint_urls}")
    
    check_endpoint_permission(integration, "devices")
    user = get_user_from_integration(integration, db)
    return await create_or_update_device_internal(payload, integration, user, db)


@router.post("/data", status_code=status.HTTP_202_ACCEPTED)
async def send_telemetry_data(
    payload: ExternalTelemetryPayload,
    request: Request,
    integration: ExternalIntegration = Depends(get_external_integration),
    db: Session = Depends(get_db),
):
    """Send telemetry/payload data (requires 'data' permission).
    
    This endpoint also supports custom endpoint URLs configured in the integration.
    If a custom URL is configured for 'data', external systems can POST to that path instead.
    Devices are automatically created if they don't exist when data is received.
    """
    logger.info(f"[External API] Received telemetry payload via /data: device_id={payload.device_id}, Request path: {request.url.path}, Custom endpoint URLs: {integration.endpoint_urls}")
    check_endpoint_permission(integration, "data")
    user = get_user_from_integration(integration, db)
    return await send_telemetry_data_internal(payload, integration, user, db)


@router.post("/health", status_code=status.HTTP_200_OK)
async def send_health_data(
    payload: ExternalHealthData,
    request: Request,
    integration: ExternalIntegration = Depends(get_external_integration),
    db: Session = Depends(get_db),
):
    """Send health data for a device (requires 'health' permission).
    
    This endpoint also supports custom endpoint URLs configured in the integration.
    If a custom URL is configured for 'health', external systems can POST to that path instead.
    """
    logger.info(f"[External API] Received health payload via /health: device_id={payload.device_id}, Request path: {request.url.path}, Custom endpoint URLs: {integration.endpoint_urls}")
    check_endpoint_permission(integration, "health")
    user = get_user_from_integration(integration, db)
    return await send_health_data_internal(payload, integration, user, db)


# ============================================
# Dynamic Routes for Custom Endpoint URLs
# ============================================

@router.api_route("/{path:path}", methods=["POST", "GET", "PUT", "DELETE"], include_in_schema=False)
async def handle_custom_endpoint(
    path: str,
    request: Request,
    integration: ExternalIntegration = Depends(get_external_integration),
    db: Session = Depends(get_db),
):
    """Catch-all handler for custom endpoint URLs configured in the integration.
    Only matches if the path matches a custom endpoint URL configured for this integration.
    """
    # Extract path from request
    full_path = request.url.path
    # Remove the /api/v1/external prefix to get the relative path
    base_path = "/api/v1/external"
    if full_path.startswith(base_path):
        relative_path = full_path[len(base_path):].strip('/')
    else:
        relative_path = path.strip('/')
    
    # Check if this is an installations endpoint first (before checking custom URLs)
    if "installations" in relative_path.lower():
        try:
            return await receive_installations(request, integration, db)
        except Exception as e:
            logger.error(f"Error handling installations endpoint: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    # Skip if no custom endpoints configured
    if not integration.endpoint_urls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint not found",
        )
    
    # Find matching custom endpoint by extracting path from custom URL
    matched_endpoint_type = None
    matched_custom_path = None
    
    for endpoint_type, custom_url in integration.endpoint_urls.items():
        if not custom_url:
            continue
        
        # Parse custom URL to extract path
        parsed = urlparse(custom_url)
        custom_path = parsed.path.strip('/')
        
        # Remove double slashes and normalize
        custom_path = custom_path.replace('//', '/')
        
        # Check if the request path matches the custom path
        # Flexible matching: exact match, ends with, or contains
        if custom_path:
            # Try exact match first
            if relative_path == custom_path or relative_path.endswith(custom_path) or custom_path in relative_path:
                matched_endpoint_type = endpoint_type
                matched_custom_path = custom_path
                logger.info(f"[External API] Matched custom endpoint: {endpoint_type} -> {custom_url} (custom path: {custom_path}, request path: {relative_path})")
                break
    
    if not matched_endpoint_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint not found. Requested path: {relative_path}, Configured custom endpoints: {list(integration.endpoint_urls.keys())}",
        )
    
    # Check permission
    check_endpoint_permission(integration, matched_endpoint_type)
    user = get_user_from_integration(integration, db)
    
    # Route to appropriate handler based on endpoint type
    try:
        body = await request.json() if request.method in ["POST", "PUT"] else {}
    except:
        body = {}
    
    if matched_endpoint_type == "devices":
        # Handle device creation/update
        try:
            payload = ExternalDeviceCreate(**body)
            return await create_or_update_device_internal(payload, integration, user, db)
        except Exception as e:
            logger.error(f"Error handling custom devices endpoint: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    elif matched_endpoint_type == "data":
        # Handle telemetry data
        try:
            payload = ExternalTelemetryPayload(**body)
            return await send_telemetry_data_internal(payload, integration, user, db)
        except Exception as e:
            logger.error(f"Error handling custom data endpoint: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    elif matched_endpoint_type == "health":
        # Handle health data
        try:
            payload = ExternalHealthData(**body)
            return await send_health_data_internal(payload, integration, user, db)
        except Exception as e:
            logger.error(f"Error handling custom health endpoint: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    # Check if this is an installations endpoint (custom URL might point to /api/installations)
    if "installations" in full_path.lower() or "installations" in relative_path.lower():
        # Route to installations handler
        try:
            return await receive_installations(request, integration, db)
        except Exception as e:
            logger.error(f"Error handling installations endpoint: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint handler not found")


# ============================================
# Installations Endpoint (for external API installations data)
# ============================================

@router.post("/installations", status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.api_route("/api/installations", methods=["POST", "GET"], status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def receive_installations(
    request: Request,
    integration: ExternalIntegration = Depends(get_external_integration),
    db: Session = Depends(get_db),
):
    """Receive installations data from external API and auto-create devices.
    
    Accepts data in format:
    [
        {
            "id": "123",
            "deviceId": "A1B2C3D4E5F6G7H8",
            "amanah": "Tabuk",
            "createdAt": "2025-01-10"
        }
    ]
    
    Devices are automatically created with HTTP protocol since data comes via HTTP.
    """
    # Check for "installations", "devices", or "data" permission
    # (installations creates devices, and installations are a type of data)
    # Make check case-insensitive
    allowed_raw = integration.allowed_endpoints or []
    # Handle both list and string formats
    if isinstance(allowed_raw, str):
        import json
        try:
            allowed_raw = json.loads(allowed_raw)
        except:
            allowed_raw = [allowed_raw]
    
    allowed = [ep.lower() if isinstance(ep, str) else str(ep).lower() for ep in allowed_raw]
    
    logger.info(f"Installations endpoint check - Integration ID: {integration.id}, Raw allowed_endpoints: {allowed_raw}, Normalized: {allowed}, Type: {type(allowed_raw)}")
    
    if "installations" not in allowed and "devices" not in allowed and "data" not in allowed:
        logger.error(f"Permission denied for installations endpoint. Integration ID: {integration.id}, Allowed endpoints (raw): {allowed_raw}, Allowed endpoints (normalized): {allowed}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API key does not have permission to access 'installations', 'devices', or 'data' endpoint. Allowed endpoints: {allowed_raw}",
        )
    
    user = get_user_from_integration(integration, db)
    
    if not user.tenant_id:
        logger.error(f"User {user.email} (ID: {user.id}) does not have a tenant_id assigned")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be assigned to a tenant",
        )
    
    try:
        # Parse request body - can be array directly or wrapped
        # Handle GET requests (external API might send GET to fetch, but we'll process as POST)
        if request.method == "GET":
            # For GET, we might receive query params or empty body
            body = {}
        else:
            try:
                body = await request.json()
            except:
                body = {}
        
        # Handle both array format and object with installations array
        installations_list = []
        if isinstance(body, list):
            installations_list = body
        elif isinstance(body, dict):
            if "installations" in body:
                installations_list = body["installations"]
            else:
                # Single installation object
                installations_list = [body]
        
        if not installations_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No installations data provided"
            )
        
        # Get HTTP device type - prefer generic "HTTP" type over specific ones
        http_device_type = db.query(DeviceType).filter(
            DeviceType.protocol == "HTTP",
            DeviceType.name == "HTTP"
        ).first()
        
        # If generic HTTP not found, get any HTTP device type
        if not http_device_type:
            http_device_type = db.query(DeviceType).filter(
                DeviceType.protocol == "HTTP"
            ).order_by(DeviceType.id).first()
        
        # Fallback to generic MQTT if HTTP not found
        if not http_device_type:
            http_device_type = db.query(DeviceType).filter(
                DeviceType.protocol == "MQTT",
                DeviceType.name == "MQTT"
            ).first()
        
        if not http_device_type:
            # Last resort: any MQTT device type
            http_device_type = db.query(DeviceType).filter(
                DeviceType.protocol == "MQTT"
            ).first()
        
        if not http_device_type:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No HTTP or MQTT device type found in system"
            )
        
        created_devices = []
        updated_devices = []
        errors = []
        
        for item in installations_list:
            try:
                # Parse installation item
                if isinstance(item, dict):
                    device_id = item.get("deviceId") or item.get("device_id")
                    installation_id = item.get("id")
                    amanah = item.get("amanah")
                    created_at = item.get("createdAt") or item.get("created_at")
                    
                    if not device_id:
                        errors.append(f"Missing deviceId in item: {item}")
                        continue
                    
                    # Check if device already exists
                    existing_device = db.query(Device).filter(
                        Device.device_id == device_id,
                        Device.tenant_id == user.tenant_id
                    ).first()
                    
                    # Prepare device name
                    # Use installation_id if it exists and is different from device_id (and not too long)
                    # Otherwise, use a shortened version of device_id
                    device_name = device_id
                    if installation_id and installation_id != device_id:
                        # Check if installation_id looks like a short identifier (not a long hex string)
                        # If it's short (less than 20 chars) and not the same as device_id, use it
                        if len(installation_id) < 20:
                            device_name = f"Installation {installation_id}"
                        else:
                            # installation_id is too long, might be the same as device_id
                            # Use first 8 chars of device_id for readability
                            device_name = f"Installation {device_id[:8]}"
                    elif installation_id and installation_id == device_id:
                        # installation_id is the same as device_id, use shortened version
                        device_name = f"Installation {device_id[:8]}"
                    else:
                        # No installation_id, use shortened device_id
                        device_name = f"Installation {device_id[:8]}"
                    
                    # Prepare metadata
                    device_metadata = {
                        "installation_id": installation_id,
                        "source": "external_installations_api",
                    }
                    if amanah:
                        device_metadata["amanah"] = amanah
                    if created_at:
                        device_metadata["created_at"] = created_at
                    
                    if existing_device:
                        # Update existing device
                        if not existing_device.name or existing_device.name == existing_device.device_id:
                            existing_device.name = device_name
                        existing_device.is_active = True
                        # Merge metadata
                        existing_metadata = {}
                        if existing_device.device_metadata:
                            try:
                                existing_metadata = json.loads(existing_device.device_metadata)
                            except:
                                pass
                        existing_metadata.update(device_metadata)
                        existing_device.device_metadata = json.dumps(existing_metadata)
                        db.commit()
                        db.refresh(existing_device)
                        updated_devices.append(device_id)
                        logger.info(f"[External API] Updated device from installations: {device_id}")
                    else:
                        # Create new device
                        device = Device(
                            device_id=device_id,
                            name=device_name,
                            device_type_id=http_device_type.id,
                            tenant_id=user.tenant_id,
                            is_active=True,
                            device_metadata=json.dumps(device_metadata),
                        )
                        db.add(device)
                        db.commit()
                        db.refresh(device)
                        created_devices.append(device_id)
                        logger.info(f"[External API] Created device from installations: {device_id} (name: {device_name}, tenant: {user.tenant_id})")
                else:
                    errors.append(f"Invalid item format: {item}")
            except Exception as e:
                logger.error(f"Error processing installation item {item}: {e}", exc_info=True)
                errors.append(f"Error processing item: {str(e)}")
        
        return {
            "status": "success",
            "created": len(created_devices),
            "updated": len(updated_devices),
            "errors": len(errors),
            "created_devices": created_devices,
            "updated_devices": updated_devices,
            "error_details": errors if errors else None,
        }
    
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    except Exception as e:
        logger.error(f"Error processing installations data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process installations: {str(e)}"
        )


# Internal handler functions (extracted from route handlers)
async def create_or_update_device_internal(
    payload: ExternalDeviceCreate,
    integration: ExternalIntegration,
    user: User,
    db: Session,
):
    """Internal function to create/update device."""
    if not user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User must be assigned to a tenant")
    
    existing_device = db.query(Device).filter(Device.device_id == payload.device_id).first()
    
    device_type_id = payload.device_type_id
    if not device_type_id and payload.device_type_name:
        device_type = db.query(DeviceType).filter(DeviceType.name == payload.device_type_name).first()
        if not device_type:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Device type '{payload.device_type_name}' not found")
        device_type_id = device_type.id
    
    if not device_type_id:
        device_type = db.query(DeviceType).filter(DeviceType.protocol == "MQTT").first()
        if device_type:
            device_type_id = device_type.id
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="device_type_id or device_type_name is required")
    
    if existing_device:
        if existing_device.tenant_id != user.tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device belongs to a different tenant")
        
        if payload.name is not None:
            existing_device.name = payload.name
        if device_type_id is not None:
            existing_device.device_type_id = device_type_id
        if payload.is_active is not None:
            existing_device.is_active = payload.is_active
        if payload.metadata is not None:
            existing_device.device_metadata = json.dumps(payload.metadata) if payload.metadata else None
        
        db.commit()
        db.refresh(existing_device)
        device_type_name = existing_device.device_type.name if existing_device.device_type else None
        return DeviceResponse(
            id=existing_device.id,
            device_id=existing_device.device_id,
            name=existing_device.name,
            device_type=device_type_name,
            is_active=existing_device.is_active,
            created_at=existing_device.created_at.isoformat() if existing_device.created_at else "",
        )
    else:
        device = Device(
            device_id=payload.device_id,
            name=payload.name,
            device_type_id=device_type_id,
            tenant_id=user.tenant_id,
            is_active=payload.is_active,
            device_metadata=json.dumps(payload.metadata) if payload.metadata else None,
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        device_type_name = device.device_type.name if device.device_type else None
        return DeviceResponse(
            id=device.id,
            device_id=device.device_id,
            name=device.name,
            device_type=device_type_name,
            is_active=device.is_active,
            created_at=device.created_at.isoformat() if device.created_at else "",
        )


async def send_telemetry_data_internal(
    payload: ExternalTelemetryPayload,
    integration: ExternalIntegration,
    user: User,
    db: Session,
):
    """Internal function to send telemetry data. Auto-creates device if it doesn't exist."""
    if not user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User must be assigned to a tenant")
    
    device = db.query(Device).filter(Device.device_id == payload.device_id, Device.tenant_id == user.tenant_id).first()
    
    # Auto-create device if it doesn't exist
    if not device:
        logger.info(f"[External API] Device '{payload.device_id}' not found, auto-creating for tenant {user.tenant_id}")
        
        # Try to extract device name and type from payload data
        device_name = payload.device_id  # Default to device_id
        device_type_name = None
        
        # Try to extract name from payload data
        if isinstance(payload.data, dict):
            # Common field names for device name
            for name_field in ['name', 'device_name', 'deviceName', 'device_name', 'label', 'title']:
                if name_field in payload.data:
                    device_name = str(payload.data[name_field])
                    break
            
            # Try to extract device type from payload
            for type_field in ['device_type', 'deviceType', 'type', 'device_type_name']:
                if type_field in payload.data:
                    device_type_name = str(payload.data[type_field])
                    break
        
        # Get or create device type
        device_type_id = None
        if device_type_name:
            device_type = db.query(DeviceType).filter(DeviceType.name == device_type_name).first()
            if device_type:
                device_type_id = device_type.id
        
        # Default to MQTT device type if not found
        if not device_type_id:
            device_type = db.query(DeviceType).filter(DeviceType.protocol == "MQTT").first()
            if device_type:
                device_type_id = device_type.id
            else:
                # Fallback to first available device type
                device_type = db.query(DeviceType).first()
                if device_type:
                    device_type_id = device_type.id
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="No device types available in the system"
                    )
        
        # Extract location from payload if available
        device_metadata = {}
        if isinstance(payload.data, dict):
            # Check for location fields (common patterns)
            if 'latitude' in payload.data and 'longitude' in payload.data:
                device_metadata['latitude'] = payload.data['latitude']
                device_metadata['longitude'] = payload.data['longitude']
            elif 'location' in payload.data and isinstance(payload.data['location'], dict):
                loc = payload.data['location']
                if 'latitude' in loc and 'longitude' in loc:
                    device_metadata['latitude'] = loc['latitude']
                    device_metadata['longitude'] = loc['longitude']
            elif 'lat' in payload.data and 'lng' in payload.data:
                device_metadata['latitude'] = payload.data['lat']
                device_metadata['longitude'] = payload.data['lng']
            elif 'lat' in payload.data and 'lon' in payload.data:
                device_metadata['latitude'] = payload.data['lat']
                device_metadata['longitude'] = payload.data['lon']
        
        # Create the device
        device = Device(
            device_id=payload.device_id,
            name=device_name,
            device_type_id=device_type_id,
            tenant_id=user.tenant_id,
            is_active=True,  # Auto-activate devices created from external data
            device_metadata=json.dumps(device_metadata) if device_metadata else None,
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        logger.info(f"[External API] Auto-created device: {device.device_id} (name: {device_name}, type_id: {device_type_id})")
    
    if not device.is_active:
        # Auto-activate inactive devices when receiving data
        logger.info(f"[External API] Activating device: {device.device_id}")
        device.is_active = True
        db.commit()
        db.refresh(device)
    
    timestamp = payload.timestamp or datetime.now(timezone.utc).isoformat()
    metadata = {
        "timestamp": timestamp,
        "source": "external_api",
        "device_type": device.device_type.name if device.device_type else None,
        "tenant_id": device.tenant_id,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "integration_id": integration.id,
    }
    
    if TELEMETRY_AVAILABLE:
        try:
            rule_result = rule_engine.evaluate(
                device_id=device.device_id,
                payload=payload.data,
                metadata=metadata,
                source="external_api",
                device=device,
                db_session=db,
            )
            
            if rule_result.dropped:
                return {"status": "dropped", "device_id": device.device_id, "message": "Telemetry dropped by rule engine"}
            
            success = telemetry_producer.publish_raw_telemetry(
                device_id=device.device_id,
                payload=rule_result.payload,
                metadata=rule_result.metadata,
                topic=rule_result.target_topic,
            )
            
            if not success:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to process telemetry data")
            
            logger.info(f"[External API] Telemetry published for device: {device.device_id}")
        except Exception as e:
            logger.error(f"Error publishing telemetry via external API: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to process telemetry: {str(e)}")
    else:
        from models import TelemetryLatest
        latest = db.query(TelemetryLatest).filter(TelemetryLatest.device_id == device.id).first()
        if latest:
            latest.payload = json.dumps(payload.data)
            latest.timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if timestamp else datetime.now(timezone.utc)
        else:
            latest = TelemetryLatest(
                device_id=device.id,
                payload=json.dumps(payload.data),
                timestamp=datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if timestamp else datetime.now(timezone.utc),
            )
            db.add(latest)
        db.commit()
        logger.info(f"[External API] Telemetry stored (Kafka unavailable) for device: {device.device_id}")
    
    return {"status": "accepted", "device_id": device.device_id, "message": "Telemetry data received and processed"}


async def send_health_data_internal(
    payload: ExternalHealthData,
    integration: ExternalIntegration,
    user: User,
    db: Session,
):
    """Internal function to send health data."""
    if not user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User must be assigned to a tenant")
    
    device = db.query(Device).filter(Device.device_id == payload.device_id, Device.tenant_id == user.tenant_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{payload.device_id}' not found in your tenant")
    
    health = db.query(DeviceHealthMetrics).filter(DeviceHealthMetrics.device_id == device.id).first()
    if not health:
        health = DeviceHealthMetrics(device_id=device.id)
        db.add(health)
    
    if payload.current_status:
        health.current_status = payload.current_status
    if payload.last_seen_at:
        try:
            health.last_seen_at = datetime.fromisoformat(payload.last_seen_at.replace('Z', '+00:00'))
        except:
            health.last_seen_at = datetime.now(timezone.utc)
    if payload.message_count_24h is not None:
        health.message_count_24h = payload.message_count_24h
    if payload.connectivity_score is not None:
        health.connectivity_score = payload.connectivity_score
    if payload.last_battery_level is not None:
        health.last_battery_level = payload.last_battery_level
    if payload.uptime_24h_percent is not None:
        health.uptime_24h_percent = payload.uptime_24h_percent
    
    health.calculated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(health)
    
    logger.info(f"[External API] Health data updated for device: {device.device_id}")
    return {"status": "success", "device_id": device.device_id, "message": "Health data updated"}

