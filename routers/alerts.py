"""Alert management API endpoints."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pydantic import BaseModel, Field

from admin_auth import get_current_user, require_admin
from database import get_db
from models import (
    Alert, AlertRule, AlertPriority, AlertStatus, Notification, AlertAuditLog,
    Device, Tenant, User, UserRole
)
from notification_service import notification_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


# Pydantic models
class AlertRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    device_id: Optional[int] = None
    tenant_id: Optional[int] = None
    condition: Dict[str, Any]
    priority: AlertPriority = AlertPriority.MEDIUM
    title_template: str
    message_template: Optional[str] = None
    notify_email: bool = True
    notify_sms: bool = False
    notify_webhook: bool = False
    webhook_url: Optional[str] = None
    escalation_enabled: bool = False
    escalation_delay_minutes: int = 30
    escalation_priority: Optional[AlertPriority] = None
    aggregation_enabled: bool = True
    aggregation_window_minutes: int = 5
    max_alerts_per_window: int = 10
    is_active: bool = True


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    condition: Optional[Dict[str, Any]] = None
    priority: Optional[AlertPriority] = None
    title_template: Optional[str] = None
    message_template: Optional[str] = None
    notify_email: Optional[bool] = None
    notify_sms: Optional[bool] = None
    notify_webhook: Optional[bool] = None
    webhook_url: Optional[str] = None
    escalation_enabled: Optional[bool] = None
    escalation_delay_minutes: Optional[int] = None
    escalation_priority: Optional[AlertPriority] = None
    aggregation_enabled: Optional[bool] = None
    aggregation_window_minutes: Optional[int] = None
    max_alerts_per_window: Optional[int] = None
    is_active: Optional[bool] = None


class AlertRuleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    device_id: Optional[int]
    tenant_id: Optional[int]
    condition: Dict[str, Any]
    priority: AlertPriority
    title_template: str
    message_template: Optional[str]
    notify_email: bool
    notify_sms: bool
    notify_webhook: bool
    webhook_url: Optional[str]
    escalation_enabled: bool
    aggregation_enabled: bool
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    rule_id: Optional[int]
    device_id: int
    tenant_id: int
    title: str
    message: Optional[str]
    priority: AlertPriority
    status: AlertStatus
    trigger_data: Optional[Dict[str, Any]]
    triggered_at: datetime
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]
    escalated: bool
    aggregated_count: int
    device_name: Optional[str] = None
    tenant_name: Optional[str] = None
    
    class Config:
        from_attributes = True


# Alert Rules Management
@router.get("/rules", response_model=List[AlertRuleResponse])
def list_alert_rules(
    device_id: Optional[int] = Query(None),
    tenant_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List alert rules."""
    query = db.query(AlertRule)
    
    # Tenant admins can only see rules for their tenant
    if current_user.role == UserRole.TENANT_ADMIN:
        query = query.filter(
            or_(
                AlertRule.tenant_id == current_user.tenant_id,
                AlertRule.tenant_id == None  # Global rules
            )
        )
    
    if device_id:
        query = query.filter(AlertRule.device_id == device_id)
    if tenant_id:
        query = query.filter(AlertRule.tenant_id == tenant_id)
    
    rules = query.order_by(AlertRule.priority.desc(), AlertRule.created_at.desc()).all()
    return rules


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
def create_alert_rule(
    rule_data: AlertRuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new alert rule."""
    # Tenant admins can only create rules for their tenant
    if current_user.role == UserRole.TENANT_ADMIN:
        if rule_data.tenant_id and rule_data.tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=403, detail="Cannot create rules for other tenants")
        rule_data.tenant_id = current_user.tenant_id
    
    # Validate device/tenant
    if rule_data.device_id:
        device = db.query(Device).filter(Device.id == rule_data.device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=403, detail="Cannot create rules for devices in other tenants")
    
    rule = AlertRule(**rule_data.dict())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
def update_alert_rule(
    rule_id: int,
    rule_data: AlertRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    # Tenant admins can only update their tenant's rules
    if current_user.role == UserRole.TENANT_ADMIN:
        if rule.tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=403, detail="Cannot update rules for other tenants")
    
    # Update fields
    update_data = rule_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    # Tenant admins can only delete their tenant's rules
    if current_user.role == UserRole.TENANT_ADMIN:
        if rule.tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=403, detail="Cannot delete rules for other tenants")
    
    db.delete(rule)
    db.commit()


# Alert Management
@router.get("", response_model=List[AlertResponse])
def list_alerts(
    device_id: Optional[int] = Query(None),
    status: Optional[AlertStatus] = Query(None),
    priority: Optional[AlertPriority] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List alerts."""
    query = db.query(Alert)
    
    # Tenant admins can only see alerts for their tenant
    if current_user.role == UserRole.TENANT_ADMIN:
        query = query.filter(Alert.tenant_id == current_user.tenant_id)
    
    if device_id:
        query = query.filter(Alert.device_id == device_id)
    if status:
        query = query.filter(Alert.status == status)
    if priority:
        query = query.filter(Alert.priority == priority)
    
    alerts = query.options(
        # Load related data
    ).order_by(Alert.triggered_at.desc()).offset(offset).limit(limit).all()
    
    # Add device/tenant names
    result = []
    for alert in alerts:
        alert_dict = {
            "id": alert.id,
            "rule_id": alert.rule_id,
            "device_id": alert.device_id,
            "tenant_id": alert.tenant_id,
            "title": alert.title,
            "message": alert.message,
            "priority": alert.priority.value if hasattr(alert.priority, 'value') else alert.priority,
            "status": alert.status.value if hasattr(alert.status, 'value') else alert.status,
            "trigger_data": alert.trigger_data,
            "triggered_at": alert.triggered_at,
            "acknowledged_at": alert.acknowledged_at,
            "resolved_at": alert.resolved_at,
            "escalated": alert.escalated,
            "aggregated_count": alert.aggregated_count,
            "device_name": alert.device.name or alert.device.device_id if alert.device else None,
            "tenant_name": alert.tenant.name if alert.tenant else None,
        }
        result.append(AlertResponse(**alert_dict))
    
    return result


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Tenant admins can only see alerts for their tenant
    if current_user.role == UserRole.TENANT_ADMIN and alert.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Cannot access alerts from other tenants")
    
    alert_dict = {
        "id": alert.id,
        "rule_id": alert.rule_id,
        "device_id": alert.device_id,
        "tenant_id": alert.tenant_id,
        "title": alert.title,
        "message": alert.message,
        "priority": alert.priority.value if hasattr(alert.priority, 'value') else alert.priority,
        "status": alert.status.value if hasattr(alert.status, 'value') else alert.status,
        "trigger_data": alert.trigger_data,
        "triggered_at": alert.triggered_at,
        "acknowledged_at": alert.acknowledged_at,
        "resolved_at": alert.resolved_at,
        "escalated": alert.escalated,
        "aggregated_count": alert.aggregated_count,
        "device_name": alert.device.name or alert.device.device_id if alert.device else None,
        "tenant_name": alert.tenant.name if alert.tenant else None,
    }
    
    return AlertResponse(**alert_dict)


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acknowledge an alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Tenant admins can only acknowledge alerts for their tenant
    if current_user.role == UserRole.TENANT_ADMIN and alert.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Cannot acknowledge alerts from other tenants")
    
    if alert.status != AlertStatus.OPEN:
        raise HTTPException(status_code=400, detail="Alert is not open")
    
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = current_user.id
    
    # Create audit log
    audit_log = AlertAuditLog(
        alert_id=alert.id,
        user_id=current_user.id,
        action="acknowledged"
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(alert)
    
    alert_dict = {
        "id": alert.id,
        "rule_id": alert.rule_id,
        "device_id": alert.device_id,
        "tenant_id": alert.tenant_id,
        "title": alert.title,
        "message": alert.message,
        "priority": alert.priority.value if hasattr(alert.priority, 'value') else alert.priority,
        "status": alert.status.value if hasattr(alert.status, 'value') else alert.status,
        "trigger_data": alert.trigger_data,
        "triggered_at": alert.triggered_at,
        "acknowledged_at": alert.acknowledged_at,
        "resolved_at": alert.resolved_at,
        "escalated": alert.escalated,
        "aggregated_count": alert.aggregated_count,
        "device_name": alert.device.name or alert.device.device_id if alert.device else None,
        "tenant_name": alert.tenant.name if alert.tenant else None,
    }
    
    return AlertResponse(**alert_dict)


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve an alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Tenant admins can only resolve alerts for their tenant
    if current_user.role == UserRole.TENANT_ADMIN and alert.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Cannot resolve alerts from other tenants")
    
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = current_user.id
    
    # Create audit log
    audit_log = AlertAuditLog(
        alert_id=alert.id,
        user_id=current_user.id,
        action="resolved"
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(alert)
    
    alert_dict = {
        "id": alert.id,
        "rule_id": alert.rule_id,
        "device_id": alert.device_id,
        "tenant_id": alert.tenant_id,
        "title": alert.title,
        "message": alert.message,
        "priority": alert.priority.value if hasattr(alert.priority, 'value') else alert.priority,
        "status": alert.status.value if hasattr(alert.status, 'value') else alert.status,
        "trigger_data": alert.trigger_data,
        "triggered_at": alert.triggered_at,
        "acknowledged_at": alert.acknowledged_at,
        "resolved_at": alert.resolved_at,
        "escalated": alert.escalated,
        "aggregated_count": alert.aggregated_count,
        "device_name": alert.device.name or alert.device.device_id if alert.device else None,
        "tenant_name": alert.tenant.name if alert.tenant else None,
    }
    
    return AlertResponse(**alert_dict)


@router.post("/{alert_id}/close", response_model=AlertResponse)
def close_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Close an alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Tenant admins can only close alerts for their tenant
    if current_user.role == UserRole.TENANT_ADMIN and alert.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Cannot close alerts from other tenants")
    
    alert.status = AlertStatus.CLOSED
    alert.closed_at = datetime.now(timezone.utc)
    alert.closed_by = current_user.id
    
    # Create audit log
    audit_log = AlertAuditLog(
        alert_id=alert.id,
        user_id=current_user.id,
        action="closed"
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(alert)
    
    alert_dict = {
        "id": alert.id,
        "rule_id": alert.rule_id,
        "device_id": alert.device_id,
        "tenant_id": alert.tenant_id,
        "title": alert.title,
        "message": alert.message,
        "priority": alert.priority.value if hasattr(alert.priority, 'value') else alert.priority,
        "status": alert.status.value if hasattr(alert.status, 'value') else alert.status,
        "trigger_data": alert.trigger_data,
        "triggered_at": alert.triggered_at,
        "acknowledged_at": alert.acknowledged_at,
        "resolved_at": alert.resolved_at,
        "escalated": alert.escalated,
        "aggregated_count": alert.aggregated_count,
        "device_name": alert.device.name or alert.device.device_id if alert.device else None,
        "tenant_name": alert.tenant.name if alert.tenant else None,
    }
    
    return AlertResponse(**alert_dict)


@router.get("/{alert_id}/notifications")
def get_alert_notifications(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get notifications for an alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Tenant admins can only see notifications for their tenant's alerts
    if current_user.role == UserRole.TENANT_ADMIN and alert.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Cannot access notifications from other tenants")
    
    notifications = db.query(Notification).filter(Notification.alert_id == alert_id).order_by(Notification.created_at.desc()).all()
    
    # Serialize notifications
    result = []
    for notif in notifications:
        result.append({
            "id": notif.id,
            "alert_id": notif.alert_id,
            "channel": notif.channel,
            "recipient": notif.recipient,
            "status": notif.status,
            "sent_at": notif.sent_at.isoformat() if notif.sent_at else None,
            "error_message": notif.error_message,
            "retry_count": notif.retry_count,
            "subject": notif.subject,
            "body": notif.body,
            "created_at": notif.created_at.isoformat() if notif.created_at else None,
        })
    
    return result


@router.get("/{alert_id}/audit")
def get_alert_audit(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get audit log for an alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Tenant admins can only see audit logs for their tenant's alerts
    if current_user.role == UserRole.TENANT_ADMIN and alert.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Cannot access audit logs from other tenants")
    
    audit_logs = db.query(AlertAuditLog).filter(
        AlertAuditLog.alert_id == alert_id
    ).order_by(AlertAuditLog.created_at.desc()).all()
    
    return audit_logs


@router.post("/notifications/process")
def process_pending_notifications(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually trigger processing of pending notifications (admin only)."""
    notification_service.process_pending_notifications()
    return {"status": "ok", "message": "Processing pending notifications"}

