"""Alert service - handles all alert-related database queries sequentially."""

import logging
from typing import Dict, List, Any, Optional

from sqlalchemy.orm import Session

from models import Alert, AlertStatus, AlertPriority, User, UserRole
from services.base_service import BaseService

logger = logging.getLogger(__name__)


class AlertService(BaseService):
    """Service for alert data access - all queries run sequentially."""
    
    def get_alerts(
        self,
        user: User,
        device_id: Optional[int] = None,
        status: Optional[AlertStatus] = None,
        priority: Optional[AlertPriority] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get alerts with filtering.
        
        Sequential query execution:
        1. Build base query
        2. Apply tenant filter (if tenant admin)
        3. Apply device_id filter (if provided)
        4. Apply status filter (if provided)
        5. Apply priority filter (if provided)
        6. Fetch alerts with pagination
        7. Transform to response format
        
        Args:
            user: Current authenticated user
            device_id: Filter by device_id (optional)
            status: Filter by status (optional)
            priority: Filter by priority (optional)
            limit: Maximum number of alerts to return
            offset: Pagination offset
            
        Returns:
            List of alert dictionaries
        """
        self._log_query("get_alerts", f"user={user.email}, limit={limit}, offset={offset}")
        
        # Query 1: Build base query
        self._log_query("build_base_query", "starting alert query")
        query = self.db.query(Alert)
        
        # Query 2: Apply tenant filter (SEQUENTIAL)
        if user.role == UserRole.TENANT_ADMIN:
            self._log_query("apply_tenant_filter", f"tenant_id={user.tenant_id}")
            query = query.filter(Alert.tenant_id == user.tenant_id)
        
        # Query 3: Apply device_id filter (SEQUENTIAL)
        if device_id:
            self._log_query("apply_device_filter", f"device_id={device_id}")
            query = query.filter(Alert.device_id == device_id)
        
        # Query 4: Apply status filter (SEQUENTIAL)
        if status:
            self._log_query("apply_status_filter", f"status={status}")
            query = query.filter(Alert.status == status)
        
        # Query 5: Apply priority filter (SEQUENTIAL)
        if priority:
            self._log_query("apply_priority_filter", f"priority={priority}")
            query = query.filter(Alert.priority == priority)
        
        # Query 6: Fetch alerts (SEQUENTIAL)
        self._log_query("fetch_alerts", f"fetching with limit={limit}, offset={offset}")
        alerts = (
            query
            .order_by(Alert.triggered_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        logger.info(f"Fetched {len(alerts)} alerts")
        
        # Transform to response format (no DB queries)
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
                "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
                "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                "escalated": alert.escalated,
                "aggregated_count": alert.aggregated_count,
                "device_name": alert.device.name or alert.device.device_id if alert.device else None,
                "tenant_name": alert.tenant.name if alert.tenant else None,
            }
            result.append(alert_dict)
        
        return result
    
    def get_alert_by_id(self, alert_id: int, user: User) -> Optional[Dict[str, Any]]:
        """Get a single alert by ID.
        
        Sequential query execution:
        1. Query alert by ID
        2. Verify tenant access
        3. Return alert data
        
        Args:
            alert_id: Alert ID
            user: Current authenticated user
            
        Returns:
            Alert dictionary or None if not found
        """
        self._log_query("get_alert_by_id", f"alert_id={alert_id}, user={user.email}")
        
        # Query 1: Fetch alert
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return None
        
        # Query 2: Verify tenant access
        if user.role == UserRole.TENANT_ADMIN and alert.tenant_id != user.tenant_id:
            logger.warning(f"Tenant admin {user.email} tried to access alert from another tenant")
            return None
        
        # Transform to response format
        return {
            "id": alert.id,
            "rule_id": alert.rule_id,
            "device_id": alert.device_id,
            "tenant_id": alert.tenant_id,
            "title": alert.title,
            "message": alert.message,
            "priority": alert.priority.value if hasattr(alert.priority, 'value') else alert.priority,
            "status": alert.status.value if hasattr(alert.status, 'value') else alert.status,
            "trigger_data": alert.trigger_data,
            "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "escalated": alert.escalated,
            "aggregated_count": alert.aggregated_count,
            "device_name": alert.device.name or alert.device.device_id if alert.device else None,
            "tenant_name": alert.tenant.name if alert.tenant else None,
        }
    
    def get_recent_alerts(
        self,
        user: User,
        limit: int = 10,
        status: Optional[AlertStatus] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent alerts for dashboard.
        
        Sequential query execution:
        1. Build base query
        2. Apply tenant filter (if tenant admin)
        3. Apply status filter (if provided)
        4. Fetch recent alerts ordered by triggered_at DESC
        5. Transform to response format
        
        Args:
            user: Current authenticated user
            limit: Maximum number of alerts to return (default: 10)
            status: Filter by status (optional, default: None = all)
            
        Returns:
            List of alert dictionaries
        """
        self._log_query("get_recent_alerts", f"user={user.email}, limit={limit}, status={status}")
        
        # Query 1: Build base query
        query = self.db.query(Alert)
        
        # Query 2: Apply tenant filter
        if user.role == UserRole.TENANT_ADMIN:
            self._log_query("apply_tenant_filter", f"tenant_id={user.tenant_id}")
            query = query.filter(Alert.tenant_id == user.tenant_id)
        
        # Query 3: Apply status filter
        if status:
            self._log_query("apply_status_filter", f"status={status}")
            query = query.filter(Alert.status == status)
        
        # Query 4: Fetch recent alerts
        self._log_query("fetch_recent_alerts", f"fetching {limit} most recent alerts")
        alerts = (
            query
            .order_by(Alert.triggered_at.desc())
            .limit(limit)
            .all()
        )
        
        logger.info(f"Fetched {len(alerts)} recent alerts")
        
        # Transform to response format
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
                "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
                "device_name": alert.device.name or alert.device.device_id if alert.device else None,
            }
            result.append(alert_dict)
        
        return result

