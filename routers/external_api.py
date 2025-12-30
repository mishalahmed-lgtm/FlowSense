"""External API endpoints for integrations using API key authentication."""
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Security, status, Header
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
def create_or_update_device(
    payload: ExternalDeviceCreate,
    integration: ExternalIntegration = Depends(get_external_integration),
    db: Session = Depends(get_db),
):
    """Create or update a device (requires 'devices' permission)."""
    check_endpoint_permission(integration, "devices")
    user = get_user_from_integration(integration, db)
    
    if not user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be assigned to a tenant",
        )
    
    # Check if device already exists
    existing_device = db.query(Device).filter(Device.device_id == payload.device_id).first()
    
    # Determine device_type_id
    device_type_id = payload.device_type_id
    if not device_type_id and payload.device_type_name:
        device_type = db.query(DeviceType).filter(DeviceType.name == payload.device_type_name).first()
        if not device_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device type '{payload.device_type_name}' not found",
            )
        device_type_id = device_type.id
    
    if not device_type_id:
        # Default to first MQTT device type if available
        device_type = db.query(DeviceType).filter(DeviceType.protocol == "MQTT").first()
        if device_type:
            device_type_id = device_type.id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="device_type_id or device_type_name is required",
            )
    
    if existing_device:
        # Update existing device (only if it belongs to the same tenant)
        if existing_device.tenant_id != user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Device belongs to a different tenant",
            )
        
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
        # Create new device
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


@router.post("/data", status_code=status.HTTP_202_ACCEPTED)
def send_telemetry_data(
    payload: ExternalTelemetryPayload,
    integration: ExternalIntegration = Depends(get_external_integration),
    db: Session = Depends(get_db),
):
    """Send telemetry/payload data (requires 'data' permission)."""
    check_endpoint_permission(integration, "data")
    user = get_user_from_integration(integration, db)
    
    if not user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be assigned to a tenant",
        )
    
    # Get device
    device = db.query(Device).filter(
        Device.device_id == payload.device_id,
        Device.tenant_id == user.tenant_id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{payload.device_id}' not found in your tenant",
        )
    
    if not device.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device is not active",
        )
    
    # Prepare metadata
    timestamp = payload.timestamp or datetime.now(timezone.utc).isoformat()
    metadata = {
        "timestamp": timestamp,
        "source": "external_api",
        "device_type": device.device_type.name if device.device_type else None,
        "tenant_id": device.tenant_id,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "integration_id": integration.id,
    }
    
    # Publish to Kafka if available
    if TELEMETRY_AVAILABLE:
        try:
            # Evaluate rules if available
            rule_result = rule_engine.evaluate(
                device_id=device.device_id,
                payload=payload.data,
                metadata=metadata,
                source="external_api",
                device=device,
                db_session=db,
            )
            
            if rule_result.dropped:
                return {
                    "status": "dropped",
                    "device_id": device.device_id,
                    "message": "Telemetry dropped by rule engine",
                }
            
            # Publish to Kafka
            success = telemetry_producer.publish_raw_telemetry(
                device_id=device.device_id,
                payload=rule_result.payload,
                metadata=rule_result.metadata,
                topic=rule_result.target_topic,
            )
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Failed to process telemetry data",
                )
            
            logger.info(f"[External API] Telemetry published for device: {device.device_id}")
            
        except Exception as e:
            logger.error(f"Error publishing telemetry via external API: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process telemetry: {str(e)}",
            )
    else:
        # Fallback: just update TelemetryLatest table
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
    
    return {
        "status": "accepted",
        "device_id": device.device_id,
        "message": "Telemetry data received and processed",
    }


@router.post("/health", status_code=status.HTTP_200_OK)
def send_health_data(
    payload: ExternalHealthData,
    integration: ExternalIntegration = Depends(get_external_integration),
    db: Session = Depends(get_db),
):
    """Send health data for a device (requires 'health' permission)."""
    check_endpoint_permission(integration, "health")
    user = get_user_from_integration(integration, db)
    
    if not user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be assigned to a tenant",
        )
    
    # Get device
    device = db.query(Device).filter(
        Device.device_id == payload.device_id,
        Device.tenant_id == user.tenant_id
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{payload.device_id}' not found in your tenant",
        )
    
    # Get or create health metrics
    health = db.query(DeviceHealthMetrics).filter(
        DeviceHealthMetrics.device_id == device.id
    ).first()
    
    if not health:
        health = DeviceHealthMetrics(device_id=device.id)
        db.add(health)
    
    # Update health metrics
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
    
    # Set calculated_at timestamp
    health.calculated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(health)
    
    logger.info(f"[External API] Health data updated for device: {device.device_id}")
    
    return {
        "status": "success",
        "device_id": device.device_id,
        "message": "Health data updated",
    }

