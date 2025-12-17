"""GraphQL API endpoint for flexible data queries."""
import logging
from typing import List, Optional
from datetime import datetime, timedelta
import strawberry
from strawberry.fastapi import GraphQLRouter
from sqlalchemy.orm import Session

from admin_auth import get_current_user
from database import get_db
from models import Device, TelemetryLatest, TelemetryTimeseries, User, UserRole, Tenant, DeviceType

logger = logging.getLogger(__name__)


# GraphQL Types
@strawberry.type
class DeviceTypeGQL:
    """GraphQL representation of DeviceType."""
    id: int
    name: str
    protocol: str


@strawberry.type
class TenantGQL:
    """GraphQL representation of Tenant."""
    id: int
    name: str


@strawberry.type
class DeviceGQL:
    """GraphQL representation of Device."""
    id: int
    device_id: str
    name: Optional[str]
    device_type: DeviceTypeGQL
    tenant: TenantGQL
    is_active: bool
    metadata: str  # JSON as string


@strawberry.type
class TelemetryPoint:
    """Single telemetry data point."""
    timestamp: str
    key: str
    value: Optional[float]


@strawberry.type
class LatestTelemetry:
    """Latest telemetry snapshot for a device."""
    device_id: str
    data: str  # JSON as string
    event_timestamp: Optional[str]


@strawberry.type
class Query:
    """GraphQL query root."""
    
    @strawberry.field
    def devices(
        self,
        info: strawberry.Info,
        tenant_id: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> List[DeviceGQL]:
        """Query devices with optional filters."""
        # Get current user from context
        current_user: User = info.context.get("current_user")
        if not current_user:
            raise Exception("Authentication required")
        
        db: Session = info.context.get("db")
        
        # Build query
        query = db.query(Device)
        
        # Tenant filtering
        if current_user.role == UserRole.TENANT_ADMIN:
            query = query.filter(Device.tenant_id == current_user.tenant_id)
        elif tenant_id:
            query = query.filter(Device.tenant_id == tenant_id)
        
        if is_active is not None:
            query = query.filter(Device.is_active == is_active)
        
        devices = query.all()
        
        # Convert to GraphQL types
        result = []
        for device in devices:
            result.append(DeviceGQL(
                id=device.id,
                device_id=device.device_id,
                name=device.name,
                device_type=DeviceTypeGQL(
                    id=device.device_type.id,
                    name=device.device_type.name,
                    protocol=device.device_type.protocol
                ) if device.device_type else None,
                tenant=TenantGQL(
                    id=device.tenant.id,
                    name=device.tenant.name
                ) if device.tenant else None,
                is_active=device.is_active,
                metadata=str(device.metadata) if device.metadata else "{}"
            ))
        
        return result
    
    @strawberry.field
    def device(
        self,
        info: strawberry.Info,
        device_id: str
    ) -> Optional[DeviceGQL]:
        """Get a single device by device_id."""
        current_user: Optional[User] = info.context.get("current_user")
        if not current_user:
            raise Exception("Authentication required")
        
        db: Session = info.context.get("db")
        if not db:
            raise Exception("Database session not available")
        
        device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
        if not device:
            return None
        
        # Check tenant access
        if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
            raise Exception("Access denied")
        
        return DeviceGQL(
            id=device.id,
            device_id=device.device_id,
            name=device.name,
            device_type=DeviceTypeGQL(
                id=device.device_type.id,
                name=device.device_type.name,
                protocol=device.device_type.protocol
            ) if device.device_type else None,
            tenant=TenantGQL(
                id=device.tenant.id,
                name=device.tenant.name
            ) if device.tenant else None,
            is_active=device.is_active,
            metadata=str(device.metadata) if device.metadata else "{}"
        )
    
    @strawberry.field
    def latest_telemetry(
        self,
        info: strawberry.Info,
        device_id: str
    ) -> Optional[LatestTelemetry]:
        """Get latest telemetry for a device."""
        current_user: Optional[User] = info.context.get("current_user")
        if not current_user:
            raise Exception("Authentication required")
        
        db: Session = info.context.get("db")
        if not db:
            raise Exception("Database session not available")
        
        device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
        if not device:
            return None
        
        # Check tenant access
        if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
            raise Exception("Access denied")
        
        latest = (
            db.query(TelemetryLatest)
            .filter(TelemetryLatest.device_id == device.id)
            .one_or_none()
        )
        
        if not latest:
            return None
        
        return LatestTelemetry(
            device_id=device.device_id,
            data=str(latest.data) if latest.data else "{}",
            event_timestamp=latest.event_timestamp.isoformat() if latest.event_timestamp else None
        )
    
    @strawberry.field
    def telemetry_history(
        self,
        info: strawberry.Info,
        device_id: str,
        key: str,
        minutes: int = 60,
        limit: int = 100
    ) -> List[TelemetryPoint]:
        """Get telemetry history for a device and field key."""
        current_user: Optional[User] = info.context.get("current_user")
        if not current_user:
            raise Exception("Authentication required")
        
        db: Session = info.context.get("db")
        if not db:
            raise Exception("Database session not available")
        
        device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
        if not device:
            return []
        
        # Check tenant access
        if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
            raise Exception("Access denied")
        
        # Compute time window
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=minutes)
        
        rows = (
            db.query(TelemetryTimeseries)
            .filter(
                TelemetryTimeseries.device_id == device.id,
                TelemetryTimeseries.key == key,
                TelemetryTimeseries.ts >= cutoff,
            )
            .order_by(TelemetryTimeseries.ts.asc())
            .limit(limit)
            .all()
        )
        
        return [
            TelemetryPoint(
                timestamp=row.ts.isoformat(),
                key=row.key,
                value=row.value
            )
            for row in rows
        ]


# Create GraphQL schema
schema = strawberry.Schema(query=Query)


# Context dependency for GraphQL
async def get_graphql_context(
    request,
    db: Session = None,
    current_user: User = None
):
    """Create GraphQL context with database and user."""
    return {
        "request": request,
        "db": db,
        "current_user": current_user
    }


# Create GraphQL router with authentication
def create_graphql_router() -> GraphQLRouter:
    """Create GraphQL router with authentication middleware."""
    from fastapi import Request, Response
    
    async def get_context(request: Request, response: Response):
        """Get GraphQL context with authentication.
        
        FastAPI will inject Request and Response automatically.
        """
        from admin_auth import decode_token
        from database import SessionLocal
        
        auth_header = request.headers.get("Authorization", "")
        current_user = None
        db_session = SessionLocal()
        
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            try:
                payload = decode_token(token)
                current_user = db_session.query(User).filter(
                    User.id == payload.user_id,
                    User.is_active == True
                ).first()
            except Exception as e:
                logger.debug(f"GraphQL authentication failed: {e}")
        
        # Return context dict (strawberry expects this format)
        return {
            "request": request,
            "response": response,
            "db": db_session,
            "current_user": current_user
        }
    
    router = GraphQLRouter(
        schema=schema,
        context_getter=get_context
    )
    return router

