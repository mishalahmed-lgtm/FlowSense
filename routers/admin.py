"""Admin API endpoints for device management."""

import json
import logging
import math
import secrets
import requests
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import text, or_, func
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from admin_auth import create_access_token, require_admin, get_current_user, hash_password, verify_password
from config import settings
from database import get_db
from models import Device, DeviceType, ProvisioningKey, Tenant, DeviceRule, TelemetryLatest, DeviceDashboard, User, UserRole
from rule_engine import rule_engine
from influx_client import influx_service

router = APIRouter(prefix="/admin", tags=["admin"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int = Field(default=settings.admin_jwt_exp_minutes)
    user: Optional[Dict[str, Any]] = None


class DeviceMetadata(BaseModel):
    """Arbitrary per-device metadata stored as JSON."""

    http_settings: Optional[Dict[str, Any]] = None
    mqtt_settings: Optional[Dict[str, Any]] = None
    tcp_settings: Optional[Dict[str, Any]] = None
    extras: Optional[Dict[str, Any]] = None


class DeviceBase(BaseModel):
    device_id: str
    name: Optional[str] = None
    device_type_id: int
    tenant_id: int
    is_active: bool = True
    metadata: DeviceMetadata = DeviceMetadata()


class DeviceCreate(DeviceBase):
    auto_generate_key: bool = True


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    device_type_id: Optional[int] = None
    tenant_id: Optional[int] = None
    is_active: Optional[bool] = None
    metadata: Optional[DeviceMetadata] = None


class ProvisioningKeyResponse(BaseModel):
    key: str
    is_active: bool


class DeviceResponse(BaseModel):
    id: int
    device_id: str
    name: Optional[str]
    device_type: str
    device_type_id: int
    protocol: str
    tenant: str
    tenant_id: int
    is_active: bool
    metadata: DeviceMetadata
    provisioning_key: Optional[ProvisioningKeyResponse]
    has_dashboard: bool = False


class PaginatedDeviceResponse(BaseModel):
    """Response model for paginated device list."""
    devices: List[DeviceResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    total_active: Optional[int] = None  # Total active devices (based on DB flag)
    total_inactive: Optional[int] = None  # Total inactive devices (based on DB flag)


class DeviceTypeResponse(BaseModel):
    id: int
    name: str
    protocol: str
    description: Optional[str]
    schema_definition: Optional[Dict[str, Any]] = None


class RuleAction(BaseModel):
    type: str
    topic: Optional[str] = None
    reason: Optional[str] = None
    set: Optional[Dict[str, Any]] = None
    stop: Optional[bool] = True
    # New action types
    title: Optional[str] = None  # For alert action
    message: Optional[str] = None  # For alert action
    priority: Optional[str] = None  # For alert action
    command: Optional[Dict[str, Any]] = None  # For device_command action
    qos: Optional[int] = None  # For device_command action
    url: Optional[str] = None  # For webhook action
    method: Optional[str] = None  # For webhook action
    headers: Optional[Dict[str, Any]] = None  # For webhook action
    body: Optional[Dict[str, Any]] = None  # For webhook action


class DeviceRuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    priority: int = 100
    is_active: bool = True
    condition: Dict[str, Any]
    action: RuleAction
    rule_type: Optional[str] = "event"  # "event" or "scheduled"
    cron_schedule: Optional[str] = None  # Cron expression for scheduled rules


class DeviceRuleCreate(DeviceRuleBase):
    pass


class DeviceRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    condition: Optional[Dict[str, Any]] = None
    action: Optional[RuleAction] = None


class DeviceRuleResponse(DeviceRuleBase):
    id: int

    class Config:
        orm_mode = True


def _serialize_metadata(raw: Optional[str]) -> DeviceMetadata:
    if not raw:
        return DeviceMetadata()
    try:
        return DeviceMetadata(**json.loads(raw))
    except (json.JSONDecodeError, TypeError):
        return DeviceMetadata()


def _serialize_device(device: Device, *, is_live: Optional[bool] = None, has_dashboard: Optional[bool] = None) -> DeviceResponse:
    provisioning = None
    if device.provisioning_key:
        provisioning = ProvisioningKeyResponse(
            key=device.provisioning_key.key,
            is_active=device.provisioning_key.is_active,
        )

    # If is_live is provided, prefer it over the raw DB flag so that the UI
    # reflects actual live telemetry rather than just a static boolean.
    effective_active = is_live if is_live is not None else device.is_active
    
    # Check if device has a dashboard (if not provided, check the relationship)
    dashboard_exists = has_dashboard
    if dashboard_exists is None:
        dashboard_exists = (
            device.dashboard is not None 
            and device.dashboard.config 
            and len(device.dashboard.config.get("widgets", [])) > 0
        )
    
    # Parse device metadata - external_data will be included in metadata
    device_metadata = _serialize_metadata(device.device_metadata)

    return DeviceResponse(
        id=device.id,
        device_id=device.device_id,
        name=device.name,
        device_type=device.device_type.name if device.device_type else "Unknown",
        device_type_id=device.device_type_id,
        protocol=device.device_type.protocol if device.device_type else "Unknown",
        tenant=device.tenant.name if device.tenant else "Unknown",
        tenant_id=device.tenant_id,
        is_active=effective_active,
        metadata=device_metadata,
        provisioning_key=provisioning,
        has_dashboard=dashboard_exists,
    )


@router.post("/login", response_model=TokenResponse, tags=["public"])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return JWT."""
    # Find user by email
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    # Create token
    token = create_access_token(user)
    
    # Return token with user info
    user_info = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "tenant_id": user.tenant_id,
        "enabled_modules": user.enabled_modules or [],
    }
    
    return TokenResponse(access_token=token, user=user_info)


@router.get("/devices", response_model=PaginatedDeviceResponse)
def list_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=1000, description="Number of devices per page"),
    search: Optional[str] = Query(None, description="Search by device_id or name"),
    status: Optional[str] = Query(None, description="Filter by status: 'active' or 'inactive'"),
    protocol: Optional[str] = Query(None, description="Filter by protocol (e.g., 'HTTP', 'MQTT')"),
    include_counts: bool = Query(True, description="Include total_active and total_inactive counts (slower)"),
):
    """Return devices (filtered by tenant for tenant admins) with pagination."""
    from sqlalchemy import or_
    
    # SIMPLE QUERY - just get devices from DB
    query = db.query(Device)
    
    # Filter by tenant if user is tenant admin
    if current_user.role == UserRole.TENANT_ADMIN:
        query = query.filter(Device.tenant_id == current_user.tenant_id)
    
    # Server-side search filter
    if search:
        search_term = f"%{search.lower()}%"
        query = query.filter(
            or_(
                Device.device_id.ilike(search_term),
                Device.name.ilike(search_term)
            )
        )
    
    # Server-side protocol filter
    if protocol:
        query = query.join(DeviceType).filter(DeviceType.protocol.ilike(f"%{protocol}%"))
    
    # Simple count - just count IDs
    total_count = query.count()
    
    # Skip active/inactive counts for now - they're slow
    total_active_count = None
    total_inactive_count = None
    
    # Apply pagination and get devices
    offset = (page - 1) * limit
    devices = query.offset(offset).limit(limit).all()

    # Check live status from telemetry - device is online if it sent data in last 10 minutes
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=600)  # 10 minutes
    live_map: Dict[int, bool] = {}
    
    if devices:
        device_ids = [device.id for device in devices]
        # Batch query telemetry latest records
        latest_records = (
            db.query(TelemetryLatest.device_id, TelemetryLatest.updated_at)
            .filter(TelemetryLatest.device_id.in_(device_ids))
            .all()
        )
        latest_by_device_id = {record.device_id: record.updated_at for record in latest_records}
        
        for device in devices:
            updated_at = latest_by_device_id.get(device.id)
            is_live = bool(updated_at and updated_at >= cutoff)
            live_map[device.id] = is_live

    # Serialize devices with live status
    serialized_devices = [
        _serialize_device(device, is_live=live_map.get(device.id, False)) for device in devices
    ]
    
    # Apply server-side status filter if requested
    if status:
        is_active_filter = status.lower() == "active"
        serialized_devices = [d for d in serialized_devices if d.is_active == is_active_filter]
    
    # Return paginated response with metadata
    total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
    return PaginatedDeviceResponse(
        devices=serialized_devices,
        total=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages,
        total_active=total_active_count,
        total_inactive=total_inactive_count
    )


@router.post("/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new device and optionally generate a provisioning key."""
    # Tenant admins can only create devices for their tenant
    if current_user.role == UserRole.TENANT_ADMIN and payload.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create devices for your own tenant"
        )
    existing = db.query(Device).filter(Device.device_id == payload.device_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device ID already exists",
        )

    device = Device(
        device_id=payload.device_id,
        name=payload.name,
        device_type_id=payload.device_type_id,
        tenant_id=payload.tenant_id,
        is_active=payload.is_active,
        device_metadata=json.dumps(payload.metadata.dict()),
    )
    db.add(device)
    db.commit()
    db.refresh(device)

    if payload.auto_generate_key:
        _rotate_provisioning_key(device, db)
        db.refresh(device)

    return _serialize_device(device)


@router.put("/devices/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: str,
    payload: DeviceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing device."""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Tenant admins can only update their own devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update devices from your own tenant"
        )

    if payload.name is not None:
        device.name = payload.name
    if payload.device_type_id is not None:
        device.device_type_id = payload.device_type_id
    # Tenant admins cannot change tenant_id
    if payload.tenant_id is not None and current_user.role == UserRole.ADMIN:
        device.tenant_id = payload.tenant_id
    if payload.is_active is not None:
        device.is_active = payload.is_active
    if payload.metadata is not None:
        device.device_metadata = json.dumps(payload.metadata.dict())

    db.commit()
    db.refresh(device)
    return _serialize_device(device)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a device."""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Tenant admins can only delete their own devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete devices from your own tenant"
        )
    # Use raw SQL deletes to avoid ORM trying to NULL out foreign keys on related
    # rows (NOT NULL constraint on provisioning_keys.device_id).
    device_pk = device.id
    db.expunge(device)

    db.execute(
        text("DELETE FROM provisioning_keys WHERE device_id = :did"),
        {"did": device_pk},
    )
    db.execute(
        text("DELETE FROM device_rules WHERE device_id = :did"),
        {"did": device_pk},
    )
    db.execute(
        text("DELETE FROM telemetry_latest WHERE device_id = :did"),
        {"did": device_pk},
    )
    db.execute(
        text("DELETE FROM telemetry_timeseries WHERE device_id = :did"),
        {"did": device_pk},
    )
    db.execute(
        text("DELETE FROM devices WHERE id = :did"),
        {"did": device_pk},
    )
    db.commit()
    return None


@router.get("/devices/{device_id}/external-data")
def get_external_device_data(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    force_refresh: bool = Query(False, description="Force refresh from external API"),
):
    """Fetch device data from external API (SmartTive) and store in device_metadata.
    
    This endpoint:
    1. Fetches data from external API on-demand
    2. Stores it in device_metadata
    3. Tracks last_viewed_at for background sync
    4. Returns cached data if available and not forcing refresh
    """
    import requests
    import json
    from datetime import datetime, timezone
    
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Check tenant access
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to access this device",
        )
    
    # Check if we have cached data and it's recent (less than 1 hour old)
    device_metadata = {}
    if device.device_metadata:
        try:
            device_metadata = json.loads(device.device_metadata)
        except:
            device_metadata = {}
    
    external_data = device_metadata.get("external_data")
    last_synced = device_metadata.get("external_data_synced_at")
    
    # Return cached data if available and not forcing refresh
    if not force_refresh and external_data and last_synced:
        try:
            last_synced_dt = datetime.fromisoformat(last_synced.replace('Z', '+00:00'))
            age_seconds = (datetime.now(timezone.utc) - last_synced_dt).total_seconds()
            if age_seconds < 3600:  # Less than 1 hour old
                logger.info(f"Returning cached external data for device {device_id} (age: {age_seconds:.0f}s)")
                # Update last_viewed_at for background sync
                device_metadata["last_viewed_at"] = datetime.now(timezone.utc).isoformat()
                device.device_metadata = json.dumps(device_metadata)
                db.commit()
                return {"data": external_data, "cached": True, "synced_at": last_synced}
        except Exception as e:
            logger.warning(f"Error parsing cached data: {e}")
    
    # Fetch from external API
    if not settings.external_device_api_base_url or not settings.external_device_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="External device API not configured",
        )
    
    try:
        url = f"{settings.external_device_api_base_url}/device/{device_id.upper()}"
        headers = {"X-API-KEY": settings.external_device_api_key}
        
        logger.info(f"Fetching external data for device {device_id} from {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        external_data = response.json()
        
        # Store in device_metadata
        if not device_metadata:
            device_metadata = {}
        device_metadata["external_data"] = external_data
        device_metadata["external_data_synced_at"] = datetime.now(timezone.utc).isoformat()
        device_metadata["last_viewed_at"] = datetime.now(timezone.utc).isoformat()
        device.device_metadata = json.dumps(device_metadata)
        db.commit()
        
        logger.info(f"Successfully fetched and stored external data for device {device_id}")
        return {"data": external_data, "cached": False, "synced_at": device_metadata["external_data_synced_at"]}
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching external data for device {device_id}: {e}")
        # Return cached data if available, even if stale
        if external_data:
            logger.info(f"Returning stale cached data due to API error")
            return {"data": external_data, "cached": True, "synced_at": last_synced, "error": "API unavailable, using cached data"}
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch external device data: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching external data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing external device data: {str(e)}",
        )


@router.post("/devices/{device_id}/rotate-key", response_model=ProvisioningKeyResponse)
def rotate_provisioning_key(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a new provisioning key for a device."""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Tenant admins can only rotate keys for their own devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only rotate keys for devices from your own tenant"
        )

    key = _rotate_provisioning_key(device, db)
    db.refresh(device)
    return ProvisioningKeyResponse(key=key.key, is_active=key.is_active)


def _rotate_provisioning_key(device: Device, db: Session) -> ProvisioningKey:
    """Internal helper to upsert provisioning key."""
    existing = (
        db.query(ProvisioningKey).filter(ProvisioningKey.device_id == device.id).first()
    )
    new_key_value = secrets.token_urlsafe(32)
    if existing:
        existing.key = new_key_value
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    provisioning = ProvisioningKey(
        device_id=device.id,
        key=new_key_value,
        is_active=True,
    )
    db.add(provisioning)
    db.commit()
    db.refresh(provisioning)
    return provisioning


@router.get("/device-types", response_model=List[DeviceTypeResponse])
def list_device_types(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return available device types. Accessible to all authenticated users."""
    device_types = db.query(DeviceType).all()
    return [
        DeviceTypeResponse(
            id=dt.id,
            name=dt.name,
            protocol=dt.protocol,
            description=dt.description,
            schema_definition=_safe_load_json(dt.schema_definition),
        )
        for dt in device_types
    ]


class TenantResponse(BaseModel):
    id: int
    name: str


@router.get("/tenants", response_model=List[TenantResponse])
def list_tenants(
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return tenant names."""
    tenants = db.query(Tenant).all()
    return [TenantResponse(id=tenant.id, name=tenant.name) for tenant in tenants]


class InfluxStatusResponse(BaseModel):
    """High-level status of the InfluxDB time-series backend."""

    enabled: bool
    url: str
    org: str
    buckets: List[Dict[str, Any]] = []
    error: Optional[str] = None


class InfluxSampleItem(BaseModel):
    """Sample point from an InfluxDB bucket for admin/debugging."""

    bucket: str
    time: str
    measurement: str
    field: str
    device_id: Optional[str] = None
    value: Any


@router.get("/influx/status", response_model=InfluxStatusResponse)
def get_influx_status(
    _: str = Depends(require_admin),
):
    """Return InfluxDB status and bucket retention configuration.

    This lets admins verify that hot/warm/cold buckets are present and
    properly configured (30 days / 1 year / 5+ years).
    """
    status_data = influx_service.get_status()
    # Ensure all required keys exist for the response model
    if "error" not in status_data:
        status_data["error"] = None
    return InfluxStatusResponse(**status_data)


@router.get("/influx/sample", response_model=List[InfluxSampleItem])
def get_influx_sample(
    bucket: str = Query(..., description="Bucket name (e.g. 'iot_hot', 'iot_warm', 'iot_cold')"),
    limit: int = Query(5, ge=1, le=100, description="Number of points to return"),
    _: str = Depends(require_admin),
):
    """Return a small sample of recent telemetry points from a given bucket.

    Useful to confirm that data is flowing into hot/warm/cold tiers.
    """
    if not influx_service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="InfluxDB integration is disabled or not configured",
        )

    points = influx_service.get_bucket_sample(bucket=bucket, limit=limit)
    return [InfluxSampleItem(**p) for p in points]


def _get_device_or_404(device_id: str, db: Session) -> Device:
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found",
        )
    return device


def _serialize_rule(rule: DeviceRule) -> DeviceRuleResponse:
    return DeviceRuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        priority=rule.priority,
        is_active=rule.is_active,
        condition=rule.condition or {},
        action=rule.action or {},
    )


@router.get("/devices/{device_id}/rules", response_model=List[DeviceRuleResponse])
def list_device_rules(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all rules configured for a device."""
    device = _get_device_or_404(device_id, db)
    
    # Tenant admins can only view rules for their own devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view rules for devices from your own tenant"
        )
    
    rules = (
        db.query(DeviceRule)
        .filter(DeviceRule.device_id == device.id)
        .order_by(DeviceRule.priority.asc(), DeviceRule.id.asc())
        .all()
    )
    return [_serialize_rule(rule) for rule in rules]


@router.post(
    "/devices/{device_id}/rules",
    response_model=DeviceRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_device_rule(
    device_id: str,
    payload: DeviceRuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a rule for a device."""
    device = _get_device_or_404(device_id, db)
    
    # Tenant admins can only create rules for their own devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create rules for devices from your own tenant"
        )
    rule = DeviceRule(
        device_id=device.id,
        name=payload.name,
        description=payload.description,
        priority=payload.priority,
        is_active=payload.is_active,
        condition=payload.condition,
        action=payload.action.dict(exclude_none=True),
        rule_type=payload.rule_type or "event",
        cron_schedule=payload.cron_schedule,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    rule_engine.invalidate(device_id)
    return _serialize_rule(rule)


@router.put("/devices/{device_id}/rules/{rule_id}", response_model=DeviceRuleResponse)
def update_device_rule(
    device_id: str,
    rule_id: int,
    payload: DeviceRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing rule."""
    device = _get_device_or_404(device_id, db)
    
    # Tenant admins can only update rules for their own devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update rules for devices from your own tenant"
        )
    rule = (
        db.query(DeviceRule)
        .filter(DeviceRule.device_id == device.id, DeviceRule.id == rule_id)
        .first()
    )
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule {rule_id} not found for device {device_id}",
        )

    if payload.name is not None:
        rule.name = payload.name
    if payload.description is not None:
        rule.description = payload.description
    if payload.priority is not None:
        rule.priority = payload.priority
    if payload.is_active is not None:
        rule.is_active = payload.is_active
    if payload.condition is not None:
        rule.condition = payload.condition
    if payload.action is not None:
        rule.action = payload.action.dict(exclude_none=True)

    db.commit()
    db.refresh(rule)
    rule_engine.invalidate(device_id)
    return _serialize_rule(rule)


@router.delete("/devices/{device_id}/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device_rule(
    device_id: str,
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a rule from a device."""
    device = _get_device_or_404(device_id, db)
    
    # Tenant admins can only delete rules for their own devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete rules for devices from your own tenant"
        )
    
    rule = (
        db.query(DeviceRule)
        .filter(DeviceRule.device_id == device.id, DeviceRule.id == rule_id)
        .first()
    )
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule {rule_id} not found for device {device_id}",
        )

    db.delete(rule)
    db.commit()
    rule_engine.invalidate(device_id)
    return None


def _safe_load_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


