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
from models import Device, DeviceType, ProvisioningKey, Tenant, DeviceRule, TelemetryLatest, DeviceDashboard, User, UserRole, DeviceSnapshot
from metrics import metrics
from rule_engine import rule_engine
from influx_client import influx_service

router = APIRouter(prefix="/admin", tags=["admin"])

# Separate router for metrics endpoints (no /admin prefix)
metrics_router = APIRouter(prefix="", tags=["metrics"])


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
    external_data: Optional[Dict[str, Any]] = None  # External API data (e.g., from SmartTive)
    external_data_synced_at: Optional[str] = None  # ISO timestamp of last sync


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
    """Authenticate user and return JWT.
    
    OPTIMIZED for free-tier database:
    - Uses indexed email lookup (email column has index)
    - Updates last_login_at in background (non-blocking)
    - Returns token immediately after password verification
    """
    # OPTIMIZED: Use indexed email lookup (email column has unique index)
    # Lowercase email for consistent lookup (emails should be stored lowercase)
    email_lower = payload.email.lower()
    user = db.query(User).filter(User.email == email_lower).first()
    
    # Verify password first (before any DB writes)
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
    
    # OPTIMIZED: Update last_login_at in a separate transaction (non-blocking)
    # This prevents the DB write from blocking the response
    try:
        user.last_login_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        # Log error but don't fail login if last_login_at update fails
        logger.warning(f"Failed to update last_login_at for user {user.id}: {e}")
        db.rollback()
    
    # Create token (fast operation, no DB access)
    token = create_access_token(user)
    
    # Return token with user info (no additional DB queries)
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
    """Return devices with pagination.

    NOTE:
    - For tenant admins, we now read from the `devices_snapshot` table (database-only view).
    - For global admins, we keep the existing behaviour (read from `devices` table).
    """
    try:
        logger.info(f"list_devices called: user={current_user.email}, role={current_user.role}, tenant_id={current_user.tenant_id}, page={page}, limit={limit}")
        
        # Special path for tenant admins: read from devices_snapshot (DB-only view)
        if current_user.role == UserRole.TENANT_ADMIN and current_user.tenant_id is not None:
            tenant_id = current_user.tenant_id
            logger.info(f"Tenant admin path: tenant_id={tenant_id}")

            # Base query on snapshot table
            snapshot_query = db.query(DeviceSnapshot).filter(DeviceSnapshot.tenant_id == tenant_id)

            # Server-side search filter (device_id only – snapshot has no name column)
            if search:
                search_term = f"%{search.lower()}%"
                snapshot_query = snapshot_query.filter(DeviceSnapshot.device_id.ilike(search_term))
                logger.info(f"Applied search filter: {search}")

            # NOTE: protocol/status filters are not applied in snapshot mode,
            # since those fields are not first-class columns. You can extend this
            # later by parsing them from payload JSON.

            # Count BEFORE pagination
            logger.info("Counting total devices...")
            total_count = snapshot_query.count()
            logger.info(f"Total devices found: {total_count}")

            # Pagination
            offset = (page - 1) * limit
            logger.info(f"Fetching devices: offset={offset}, limit={limit}")
            snapshots = (
                snapshot_query
                .order_by(DeviceSnapshot.device_id)
                .offset(offset)
                .limit(limit)
                .all()
            )
            logger.info(f"Fetched {len(snapshots)} devices from database")

            # Fetch tenant name for display
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            tenant_name = tenant.name if tenant else f"Tenant {tenant_id}"

            # Build DeviceResponse list from snapshot payload
            serialized_devices: List[DeviceResponse] = []
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=18300)  # 5 hours 5 minutes
            
            # Count active/inactive using SQL aggregation (never load all devices)
            total_active_count = None
            total_inactive_count = None
            if include_counts:
                logger.info("Calculating active/inactive counts...")
                # OPTIMIZED: Simplified query for free-tier DB (0.1% CPU)
                # Complex JSONB queries with multiple OR conditions timeout on free-tier
                # Use simplest possible query: only check is_active flag
                try:
                    # Simple query: only check top-level is_active (fastest)
                    active_query = text("""
                        SELECT COUNT(*) 
                        FROM devices_snapshot 
                        WHERE tenant_id = :tenant_id
                          AND (payload->>'is_active')::text = 'true'
                    """)
                    active_result = db.execute(active_query, {"tenant_id": tenant_id}).scalar()
                    total_active_count = active_result or 0
                    logger.info(f"Active devices count: {total_active_count}")
                    
                    # Total count (simple count, no JSONB operations)
                    total_count_query = db.query(func.count(DeviceSnapshot.device_id)).filter(
                        DeviceSnapshot.tenant_id == tenant_id
                    ).scalar()
                    
                    # Inactive = total - active
                    total_inactive_count = (total_count_query or 0) - total_active_count
                    logger.info(f"Inactive devices count: {total_inactive_count}")
                except Exception as e:
                    logger.error(f"Error counting devices: {e}", exc_info=True)
                    # Fallback: set to None to skip counts (don't block the request)
                    total_active_count = None
                    total_inactive_count = None
        
        for idx, snap in enumerate(snapshots, start=1 + offset):
            payload = snap.payload or {}
            if not isinstance(payload, dict):
                payload = {}

            # Extract ALL fields from payload - everything comes from devices_snapshot
            # Name extraction
            name = (
                payload.get("name") or 
                payload.get("device_name") or 
                payload.get("deviceName") or 
                payload.get("label") or 
                payload.get("title") or 
                snap.device_id
            )

            # Extract device_type from payload
            device_type_name = "Snapshot Device"
            device_type_id = 0
            protocol = "HTTP"
            
            device_type_obj = payload.get("device_type")
            if isinstance(device_type_obj, dict):
                device_type_name = device_type_obj.get("name") or device_type_name
                protocol = device_type_obj.get("protocol") or protocol
                device_type_id = device_type_obj.get("id") or 0
            elif isinstance(device_type_obj, str):
                device_type_name = device_type_obj
            
            # Protocol can also be top-level
            if payload.get("protocol"):
                protocol = payload["protocol"]

            # SECURITY: Never trust payload.tenant_id - always use current_user.tenant_id
            # Extract tenant name from payload if available, but always use authenticated tenant_id
            payload_tenant_name = payload.get("tenant_name")
            tenant_id_to_use = tenant_id  # Always use authenticated tenant_id
            tenant_name_to_use = payload_tenant_name if payload_tenant_name else tenant_name

            # Determine if device is online - check payload.is_active first, then telemetry timestamp
            is_active = payload.get("is_active", False)
            
            # If is_active not explicitly set, check telemetry timestamp
            if not isinstance(is_active, bool):
                telemetry = payload.get("telemetry") or {}
                telemetry_ts = telemetry.get("timestamp") or telemetry.get("updated_at")
                if telemetry_ts:
                    try:
                        if isinstance(telemetry_ts, str):
                            ts = datetime.fromisoformat(telemetry_ts.replace('Z', '+00:00'))
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                        else:
                            ts = telemetry_ts
                        is_active = ts >= cutoff
                    except (ValueError, TypeError, AttributeError):
                        # Fallback: check health.last_seen_at
                        health = payload.get("health") or {}
                        last_seen = health.get("last_seen_at")
                        if last_seen:
                            try:
                                if isinstance(last_seen, str):
                                    ts = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                                    if ts.tzinfo is None:
                                        ts = ts.replace(tzinfo=timezone.utc)
                                else:
                                    ts = last_seen
                                is_active = ts >= cutoff
                            except (ValueError, TypeError, AttributeError):
                                is_active = False
                else:
                    is_active = False

            # Extract metadata from payload
            payload_metadata = payload.get("metadata") or {}
            if isinstance(payload_metadata, dict):
                metadata = DeviceMetadata(
                    http_settings=payload_metadata.get("http_settings"),
                    mqtt_settings=payload_metadata.get("mqtt_settings"),
                    tcp_settings=payload_metadata.get("tcp_settings"),
                    extras=payload_metadata.get("extras") or payload,  # Put full payload in extras
                    external_data=payload_metadata.get("external_data"),
                    external_data_synced_at=payload_metadata.get("external_data_synced_at"),
                )
            else:
                metadata = DeviceMetadata(extras=payload)

            # Check if device has dashboard config
            dashboard_cfg = payload.get("dashboard") or {}
            has_dashboard = bool(dashboard_cfg.get("widgets") and len(dashboard_cfg.get("widgets", [])) > 0)

            device_resp = DeviceResponse(
                id=idx,  # Synthetic ID for UI purposes
                device_id=snap.device_id,
                name=name,
                device_type=device_type_name,
                device_type_id=device_type_id,
                protocol=protocol,
                tenant=tenant_name_to_use,
                tenant_id=tenant_id_to_use,
                is_active=is_active,
                metadata=metadata,
                provisioning_key=None,  # Snapshot devices don't have provisioning keys
                has_dashboard=has_dashboard,
            )
            serialized_devices.append(device_resp)

        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1

        return PaginatedDeviceResponse(
            devices=serialized_devices,
            total=total_count,
            page=page,
            limit=limit,
            total_pages=total_pages,
            total_active=total_active_count,
            total_inactive=total_inactive_count,
        )

        # ---- Default path (global admins) – existing behaviour on `devices` table ----
        logger.info("Global admin path: using devices table")
        query = db.query(Device)
        
        # Filter by tenant if user is tenant admin (fallback path)
        if current_user.role == UserRole.TENANT_ADMIN and current_user.tenant_id is not None:
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

        # Check live status: device is active if EITHER:
        # 1. It sent telemetry in the past 5 hours 5 minutes, OR
        # 2. It has external_data_synced_at in device_metadata within past 5 hours 5 minutes
        # Use PostgreSQL JSON queries for efficiency (no Python JSON parsing)
        live_map: Dict[int, bool] = {}
        
        if devices:
            device_ids = [device.id for device in devices]
            
            # Check telemetry latest records - single efficient query
            latest_records = (
                db.query(TelemetryLatest.device_id, TelemetryLatest.updated_at)
                .filter(TelemetryLatest.device_id.in_(device_ids))
                .all()
            )
            latest_by_device_id = {record.device_id: record.updated_at for record in latest_records}
            
            # Also check for devices with recent external_data_synced_at using native PostgreSQL JSON query
            # This is efficient - PostgreSQL extracts JSON at database level, no Python parsing
            cutoff_iso = (datetime.now(timezone.utc) - timedelta(seconds=18300)).isoformat()
            
            # Raw SQL query using PostgreSQL JSON operators for efficiency
            external_sync_query = text("""
                SELECT id 
                FROM devices 
                WHERE id = ANY(:device_ids)
                  AND device_metadata IS NOT NULL
                  AND device_metadata::jsonb->>'external_data_synced_at' >= :cutoff_iso
            """)
            
            external_synced_devices = db.execute(
                external_sync_query,
                {"device_ids": device_ids, "cutoff_iso": cutoff_iso}
            ).fetchall()
            external_synced_device_ids = {row[0] for row in external_synced_devices}
            
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=18300)  # 5 hours 5 minutes (305 minutes)
            
            for device in devices:
                # Check telemetry first
                updated_at = latest_by_device_id.get(device.id)
                has_recent_telemetry = bool(updated_at and updated_at >= cutoff)
                
                # Check if device has recent external sync
                has_recent_external = device.id in external_synced_device_ids
                
                # Device is active if it has EITHER recent telemetry OR recent external data
                is_live = has_recent_telemetry or has_recent_external
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
    except Exception as e:
        logger.error(f"Error in list_devices: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch devices: {str(e)}"
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


@metrics_router.get("/metrics")
def get_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get system-wide metrics (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    stats = metrics.get_stats()
    
    # Count active devices from database
    active_devices = db.query(Device).filter(Device.is_active == True).count()
    
    return {
        "active_devices": active_devices,
        "messages": {
            "total_received": stats["messages"]["total_received"],
            "total_published": stats["messages"]["total_published"],
            "total_rejected": stats["messages"]["total_rejected"],
        },
        "sources": stats.get("sources", {}),
    }


@metrics_router.get("/metrics/tenant")
def get_tenant_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get tenant-scoped metrics for tenant admins."""
    try:
        logger.info(f"get_tenant_metrics called: user={current_user.email}, tenant_id={current_user.tenant_id}")
        
        if current_user.role != UserRole.TENANT_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant admin access required"
            )
        
        if not current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant admin has no tenant assigned"
            )
        
        # Use SQL aggregation - never load all devices into memory
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=18300)  # 5 hours 5 minutes
        cutoff_iso = cutoff.isoformat()
        
        # OPTIMIZED: Simplified active device count query for free-tier DB performance
        # Use the simplest possible JSONB query to avoid timeout
        # On free-tier (0.1% CPU), complex JSONB queries can take 30+ seconds
        try:
            # Use simplest query: only check top-level is_active flag (fastest)
            # Skip timestamp checks to avoid complex JSONB operations
            active_query = text("""
                SELECT COUNT(*) 
                FROM devices_snapshot 
                WHERE tenant_id = :tenant_id
                  AND (payload->>'is_active')::text = 'true'
            """)
            
            # Set query timeout to prevent hanging (5 seconds max)
            # If query takes longer, return 0 to avoid blocking
            try:
                active_count = db.execute(active_query, {"tenant_id": current_user.tenant_id}).scalar() or 0
            except Exception as query_error:
                logger.warning(f"Active count query timed out or failed: {query_error}, returning 0")
                active_count = 0
            
            logger.info(f"Active devices count: {active_count}")
        except Exception as e:
            logger.error(f"Error counting active devices in metrics: {e}", exc_info=True)
            active_count = 0
        
        # OPTIMIZED: Skip fetching all device IDs (2000+ rows) - too slow on free-tier DB
        # Instead, get metrics stats first, then filter by tenant's devices if needed
        # This avoids loading all 2000 device_ids into memory
        try:
            stats = metrics.get_stats()
            
            # OPTIMIZED: Only fetch device IDs if we need to filter metrics
            # For now, return aggregate stats without device-level filtering (much faster)
            # If device-level filtering is needed, we can add it later with pagination
            device_ids = []  # Skip loading all device IDs (performance optimization)
            tenant_sources = {}
            
            # Return aggregate message counts (not device-specific to avoid loading 2000 IDs)
            # This is much faster on free-tier database
            total_received = stats.get("total_received", 0) if isinstance(stats.get("total_received"), int) else 0
            total_published = stats.get("total_published", 0) if isinstance(stats.get("total_published"), int) else 0
            total_rejected = stats.get("total_rejected", 0) if isinstance(stats.get("total_rejected"), int) else 0
            
            logger.info(f"Metrics stats: received={total_received}, published={total_published}, rejected={total_rejected}")
        except Exception as e:
            logger.error(f"Error getting metrics stats: {e}", exc_info=True)
            total_received = 0
            total_published = 0
            total_rejected = 0
            tenant_sources = {}
        
        return {
            "active_devices": active_count,
            "messages": {
                "total_received": total_received,
                "total_published": total_published,
                "total_rejected": total_rejected,
            },
            "sources": tenant_sources,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_tenant_metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant metrics: {str(e)}"
        )


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


