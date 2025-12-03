"""Admin API endpoints for device management."""

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from admin_auth import create_admin_token, require_admin
from config import settings
from database import get_db
from models import Device, DeviceType, ProvisioningKey, Tenant, DeviceRule, TelemetryLatest
from rule_engine import rule_engine
import json

router = APIRouter(prefix="/admin", tags=["admin"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int = Field(default=settings.admin_jwt_exp_minutes)


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


class DeviceRuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    priority: int = 100
    is_active: bool = True
    condition: Dict[str, Any]
    action: RuleAction


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


def _serialize_device(device: Device, *, is_live: Optional[bool] = None) -> DeviceResponse:
    provisioning = None
    if device.provisioning_key:
        provisioning = ProvisioningKeyResponse(
            key=device.provisioning_key.key,
            is_active=device.provisioning_key.is_active,
        )

    # If is_live is provided, prefer it over the raw DB flag so that the UI
    # reflects actual live telemetry rather than just a static boolean.
    effective_active = is_live if is_live is not None else device.is_active

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
        metadata=_serialize_metadata(device.device_metadata),
        provisioning_key=provisioning,
    )


@router.post("/login", response_model=TokenResponse, tags=["public"])
def admin_login(payload: LoginRequest):
    """Authenticate admin user and return JWT."""
    if (
        payload.email.lower() != settings.admin_email.lower()
        or payload.password != settings.admin_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_admin_token(settings.admin_email)
    return TokenResponse(access_token=token)


@router.get("/devices", response_model=List[DeviceResponse])
def list_devices(
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return all registered devices.

    The `is_active` flag in the response reflects *live* status based on
    recent telemetry, not just the static DB flag:
    - If the device has a `telemetry_latest` row updated in the last 90 seconds,
      it is marked Active.
    - Otherwise it is marked Inactive.
    """
    devices = db.query(Device).all()

    # Determine live status from latest telemetry timestamps
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=90)
    live_map: Dict[int, bool] = {}

    for device in devices:
        latest = (
            db.query(TelemetryLatest)
            .filter(TelemetryLatest.device_id == device.id)
            .first()
        )
        is_live = bool(latest and latest.updated_at and latest.updated_at >= cutoff)
        live_map[device.id] = is_live

    return [
        _serialize_device(device, is_live=live_map.get(device.id, False))
        for device in devices
    ]


@router.post("/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new device and optionally generate a provisioning key."""
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
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update an existing device."""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    if payload.name is not None:
        device.name = payload.name
    if payload.device_type_id is not None:
        device.device_type_id = payload.device_type_id
    if payload.tenant_id is not None:
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
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Remove a device."""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
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


@router.post("/devices/{device_id}/rotate-key", response_model=ProvisioningKeyResponse)
def rotate_provisioning_key(
    device_id: str,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate a new provisioning key for a device."""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
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
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return available device types."""
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
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return all rules configured for a device."""
    device = _get_device_or_404(device_id, db)
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
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a rule for a device."""
    device = _get_device_or_404(device_id, db)
    rule = DeviceRule(
        device_id=device.id,
        name=payload.name,
        description=payload.description,
        priority=payload.priority,
        is_active=payload.is_active,
        condition=payload.condition,
        action=payload.action.dict(exclude_none=True),
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
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update an existing rule."""
    device = _get_device_or_404(device_id, db)
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
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a rule from a device."""
    device = _get_device_or_404(device_id, db)
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


