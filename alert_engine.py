"""Alert engine for processing alerts from telemetry and rules."""
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from database import SessionLocal
from models import (
    Alert, AlertRule, AlertPriority, AlertStatus, Notification,
    Device, Tenant, User
)

logger = logging.getLogger(__name__)


class AlertEngine:
    """Engine for evaluating alert rules and creating alerts."""
    
    def __init__(self):
        """Initialize alert engine."""
        self._lock = threading.Lock()
        self._rule_cache: Dict[int, AlertRule] = {}
        self._aggregation_cache: Dict[str, List[datetime]] = {}  # rule_id+device_id -> timestamps
    
    def _get_alert_rules(self, device_id: int, tenant_id: int) -> List[AlertRule]:
        """Get active alert rules for a device/tenant."""
        db = SessionLocal()
        try:
            # Get device-specific rules
            device_rules = db.query(AlertRule).filter(
                AlertRule.device_id == device_id,
                AlertRule.is_active == True
            ).all()
            
            # Get tenant-specific rules
            tenant_rules = db.query(AlertRule).filter(
                AlertRule.tenant_id == tenant_id,
                AlertRule.device_id == None,
                AlertRule.is_active == True
            ).all()
            
            # Get global rules (no device_id, no tenant_id)
            global_rules = db.query(AlertRule).filter(
                AlertRule.device_id == None,
                AlertRule.tenant_id == None,
                AlertRule.is_active == True
            ).all()
            
            return list(device_rules) + list(tenant_rules) + list(global_rules)
        finally:
            db.close()
    
    def _evaluate_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate an alert rule condition against context data."""
        try:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")
            
            if not field or operator is None:
                return False
            
            # Get field value from context (supports nested paths like "payload.temperature")
            field_value = self._get_nested_value(context, field)
            
            if field_value is None:
                return False
            
            # Evaluate based on operator
            if operator == ">":
                return float(field_value) > float(value)
            elif operator == ">=":
                return float(field_value) >= float(value)
            elif operator == "<":
                return float(field_value) < float(value)
            elif operator == "<=":
                return float(field_value) <= float(value)
            elif operator == "==":
                return str(field_value) == str(value)
            elif operator == "!=":
                return str(field_value) != str(value)
            elif operator == "in":
                return str(field_value) in [str(v) for v in value] if isinstance(value, list) else False
            elif operator == "contains":
                return str(value) in str(field_value)
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}", exc_info=True)
            return False
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value from dict using dot notation."""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
    
    def _check_aggregation(self, rule_id: int, device_id: int, window_minutes: int, max_count: int) -> bool:
        """Check if alert should be throttled due to aggregation."""
        key = f"{rule_id}_{device_id}"
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=window_minutes)
        
        with self._lock:
            if key not in self._aggregation_cache:
                self._aggregation_cache[key] = []
            
            # Clean old entries
            self._aggregation_cache[key] = [
                ts for ts in self._aggregation_cache[key] if ts > cutoff
            ]
            
            # Check if we've exceeded the limit
            if len(self._aggregation_cache[key]) >= max_count:
                return False  # Throttled
            
            # Add this alert
            self._aggregation_cache[key].append(now)
            return True  # Allowed
    
    def _create_alert(
        self,
        rule: AlertRule,
        device_id: int,
        tenant_id: int,
        trigger_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[Alert]:
        """Create an alert instance."""
        db = SessionLocal()
        try:
            # Render title and message templates
            title = self._render_template(rule.title_template, context)
            message = self._render_template(rule.message_template or "", context) if rule.message_template else None
            
            # Check aggregation
            if rule.aggregation_enabled:
                if not self._check_aggregation(
                    rule.id, device_id,
                    rule.aggregation_window_minutes,
                    rule.max_alerts_per_window
                ):
                    logger.debug(f"Alert throttled due to aggregation: rule_id={rule.id}, device_id={device_id}")
                    return None
            
            # Create alert
            alert = Alert(
                rule_id=rule.id,
                device_id=device_id,
                tenant_id=tenant_id,
                title=title,
                message=message,
                priority=rule.priority,
                status=AlertStatus.OPEN,
                trigger_data=trigger_data,
                alert_metadata=context
            )
            
            db.add(alert)
            db.commit()
            db.refresh(alert)
            
            # Create notifications
            self._create_notifications(alert, rule, db)
            
            logger.info(f"Created alert: id={alert.id}, rule={rule.name}, device_id={device_id}, priority={rule.priority}")
            return alert
        except Exception as e:
            logger.error(f"Error creating alert: {e}", exc_info=True)
            db.rollback()
            return None
        finally:
            db.close()
    
    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """Render a simple template with context variables."""
        result = template
        # Simple variable substitution: {{field.path}}
        import re
        pattern = r'\{\{([^}]+)\}\}'
        
        def replace_var(match):
            var_path = match.group(1).strip()
            value = self._get_nested_value(context, var_path)
            return str(value) if value is not None else ""
        
        result = re.sub(pattern, replace_var, result)
        return result
    
    def _create_notifications(self, alert: Alert, rule: AlertRule, db: SessionLocal):
        """Create notification records for an alert."""
        # Get tenant users who should receive notifications
        users = db.query(User).filter(
            User.tenant_id == alert.tenant_id,
            User.is_active == True
        ).all()
        
        for user in users:
            # Email notifications
            if rule.notify_email and user.email:
                notification = Notification(
                    alert_id=alert.id,
                    channel="email",
                    recipient=user.email,
                    status="pending",
                    subject=alert.title,
                    body=alert.message or alert.title
                )
                db.add(notification)
            
            # SMS notifications (if phone number stored in user metadata)
            # Note: You'd need to add phone_number field to User model or store in metadata
            if rule.notify_sms:
                # Placeholder - implement when phone numbers are available
                pass
        
        # Webhook notifications
        if rule.notify_webhook and rule.webhook_url:
            notification = Notification(
                alert_id=alert.id,
                channel="webhook",
                recipient=rule.webhook_url,
                status="pending",
                body=json.dumps({
                    "alert_id": alert.id,
                    "title": alert.title,
                    "message": alert.message,
                    "priority": alert.priority.value,
                    "device_id": alert.device_id,
                    "triggered_at": alert.triggered_at.isoformat()
                })
            )
            db.add(notification)
        
        db.commit()
    
    def process_telemetry(
        self,
        device_id: int,
        tenant_id: int,
        payload: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> List[Alert]:
        """Process telemetry and evaluate alert rules."""
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if not device:
                return []
            
            # Get active alert rules
            rules = self._get_alert_rules(device_id, tenant_id)
            
            # Build context for condition evaluation
            context = {
                "payload": payload,
                "metadata": metadata,
                "device": {
                    "id": device.id,
                    "device_id": device.device_id,
                    "name": device.name,
                    "is_active": device.is_active
                }
            }
            
            created_alerts = []
            
            for rule in rules:
                try:
                    # Evaluate condition
                    if self._evaluate_condition(rule.condition, context):
                        # Condition met - create alert
                        alert = self._create_alert(
                            rule, device_id, tenant_id,
                            {"payload": payload, "metadata": metadata},
                            context
                        )
                        if alert:
                            created_alerts.append(alert)
                except Exception as e:
                    logger.error(f"Error evaluating rule {rule.id}: {e}", exc_info=True)
            
            return created_alerts
        finally:
            db.close()


# Global alert engine instance
alert_engine = AlertEngine()

