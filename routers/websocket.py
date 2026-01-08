"""WebSocket API for real-time data streaming."""
import json
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from admin_auth import get_current_user_from_token
from models import Device, TelemetryLatest, User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time data streaming."""
    
    def __init__(self):
        # Map device_id -> Set[WebSocket] (single device subscriptions)
        self.device_connections: Dict[str, Set[WebSocket]] = {}
        # Map WebSocket -> device_id (for single device subscriptions)
        self.connection_devices: Dict[WebSocket, str] = {}
        # Map WebSocket -> user_id
        self.connection_users: Dict[WebSocket, int] = {}
        # Map tenant_id -> Set[WebSocket] for dashboard subscriptions
        self.dashboard_connections: Dict[int, Set[WebSocket]] = {}
        # Map WebSocket -> tenant_id (for dashboard subscriptions)
        self.dashboard_tenants: Dict[WebSocket, int] = {}
    
    async def connect(self, websocket: WebSocket, device_id: str, user_id: int):
        """Connect a WebSocket client to a device stream."""
        await websocket.accept()
        
        if device_id not in self.device_connections:
            self.device_connections[device_id] = set()
        
        self.device_connections[device_id].add(websocket)
        self.connection_devices[websocket] = device_id
        self.connection_users[websocket] = user_id
        
        logger.info(f"WebSocket connected: device={device_id}, user={user_id}, total={len(self.device_connections[device_id])}")
    
    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket client."""
        device_id = self.connection_devices.pop(websocket, None)
        self.connection_users.pop(websocket, None)
        
        if device_id and device_id in self.device_connections:
            self.device_connections[device_id].discard(websocket)
            if not self.device_connections[device_id]:
                del self.device_connections[device_id]
        
        # Also remove from dashboard connections
        tenant_id = self.dashboard_tenants.pop(websocket, None)
        if tenant_id and tenant_id in self.dashboard_connections:
            self.dashboard_connections[tenant_id].discard(websocket)
            if not self.dashboard_connections[tenant_id]:
                del self.dashboard_connections[tenant_id]
        
        logger.info(f"WebSocket disconnected: device={device_id}")
    
    async def broadcast_to_device(self, device_id: str, message: dict):
        """Broadcast a message to all clients subscribed to a device."""
        disconnected = set()
        
        # Broadcast to single-device subscriptions
        if device_id in self.device_connections:
            for websocket in self.device_connections[device_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send to WebSocket: {e}")
                    disconnected.add(websocket)
        
        # Note: Dashboard broadcasts are handled by broadcast_to_dashboard() method
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)
    
    async def broadcast_to_dashboard(self, tenant_id: int, message: dict):
        """Broadcast a message to all clients subscribed to a tenant's dashboard."""
        if tenant_id not in self.dashboard_connections:
            logger.debug(f"No dashboard connections for tenant {tenant_id}")
            return
        
        count = len(self.dashboard_connections[tenant_id])
        logger.info(f"Broadcasting to {count} dashboard connections for tenant {tenant_id}: {message.get('type', 'unknown')}")
        
        disconnected = set()
        sent_count = 0
        for websocket in self.dashboard_connections[tenant_id]:
            try:
                await websocket.send_json(message)
                sent_count += 1
                logger.debug(f"✓ Sent {message.get('type')} to dashboard WebSocket for tenant {tenant_id} (device: {message.get('device_id', 'unknown')})")
            except Exception as e:
                logger.warning(f"✗ Failed to send to dashboard WebSocket for tenant {tenant_id}: {e}", exc_info=True)
                disconnected.add(websocket)
        
        logger.info(f"Successfully sent {message.get('type')} to {sent_count}/{count} dashboard connections for tenant {tenant_id}")
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)
    
    async def connect_dashboard(self, websocket: WebSocket, tenant_id: int, user_id: int):
        """Connect a WebSocket client to dashboard stream (all tenant devices)."""
        await websocket.accept()
        
        # Handle None tenant_id (global admin)
        if tenant_id is None:
            tenant_id = -1  # Use -1 for global admin
        
        if tenant_id not in self.dashboard_connections:
            self.dashboard_connections[tenant_id] = set()
        
        self.dashboard_connections[tenant_id].add(websocket)
        self.dashboard_tenants[websocket] = tenant_id
        self.connection_users[websocket] = user_id
        
        logger.info(f"Dashboard WebSocket connected: tenant_id={tenant_id}, user={user_id}, total={len(self.dashboard_connections[tenant_id])}")
    
    def get_subscribed_devices(self) -> Set[str]:
        """Get all device IDs that have active subscriptions."""
        return set(self.device_connections.keys())


# Global connection manager
connection_manager = ConnectionManager()


@router.websocket("/devices/{device_id}/stream")
async def websocket_device_stream(
    websocket: WebSocket,
    device_id: str,
    token: str = Query(..., description="JWT authentication token"),
):
    """WebSocket endpoint for real-time device telemetry streaming.
    
    Clients connect to this endpoint to receive real-time updates whenever
    new telemetry data arrives for the specified device.
    
    Messages are sent as JSON:
    {
        "type": "telemetry",
        "device_id": "DEVICE-001",
        "data": {...},
        "timestamp": "2024-01-01T12:00:00Z"
    }
    """
    # Create database session manually (WebSocket can't use Depends)
    from database import SessionLocal
    db = SessionLocal()
    
    try:
        # Authenticate user from token
        user = get_current_user_from_token(token, db)
        if not user:
            db.close()  # Close DB before returning
            await websocket.close(code=1008, reason="Authentication failed")
            return
        
        # Verify device exists and user has access
        device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
        if not device:
            db.close()  # Close DB before returning
            await websocket.close(code=1008, reason="Device not found")
            return
        
        # Check tenant access
        if user.role == UserRole.TENANT_ADMIN and device.tenant_id != user.tenant_id:
            db.close()  # Close DB before returning
            await websocket.close(code=1008, reason="Access denied")
            return
        
        # Connect WebSocket
        await connection_manager.connect(websocket, device_id, user.id)
        
        # Send initial latest telemetry
        latest = (
            db.query(TelemetryLatest)
            .filter(TelemetryLatest.device_id == device.id)
            .one_or_none()
        )
        
        if latest:
            await websocket.send_json({
                "type": "telemetry",
                "device_id": device_id,
                "data": latest.data or {},
                "timestamp": latest.event_timestamp.isoformat() if latest.event_timestamp else None,
            })
        
        # Close DB session after initial data - we don't need it during the WebSocket lifecycle
        db.close()
        db = None
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for client messages (ping/pong or commands)
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle ping
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
        
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}", exc_info=True)
    finally:
        if db:
            db.close()
        connection_manager.disconnect(websocket)


async def broadcast_telemetry_update_async(device_id: str, tenant_id: int, data: dict, timestamp: str = None):
    """Async version of broadcast_telemetry_update for use in async contexts."""
    message = {
        "type": "telemetry_update",
        "device_id": device_id,
        "data": data,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }
    
    # Broadcast to individual device subscribers
    await connection_manager.broadcast_to_device(device_id, message)
    # Broadcast to dashboard subscribers for the tenant
    if tenant_id:
        await connection_manager.broadcast_to_dashboard(tenant_id, message)


def broadcast_telemetry_update(device_id: str, tenant_id: int, data: dict, timestamp: str = None):
    """Broadcast telemetry update to all connected WebSocket clients (device and dashboard).
    
    This function should be called by the telemetry worker or external API when new data arrives.
    
    Args:
        device_id: Device identifier
        tenant_id: Tenant ID for dashboard-level broadcasts
        data: Telemetry data payload
        timestamp: ISO timestamp string (optional)
    """
    message = {
        "type": "telemetry_update",
        "device_id": device_id,
        "data": data,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }
    
    # Use asyncio to broadcast (this will be called from sync context)
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    async def _do_broadcast():
        # Broadcast to individual device subscribers
        await connection_manager.broadcast_to_device(device_id, message)
        # Broadcast to dashboard subscribers for the tenant
        if tenant_id:
            await connection_manager.broadcast_to_dashboard(tenant_id, message)
    
    if loop.is_running():
        # If loop is already running, schedule the coroutine
        asyncio.create_task(_do_broadcast())
    else:
        # If loop is not running, we need to run it
        try:
            loop.run_until_complete(_do_broadcast())
        except RuntimeError:
            # If we can't run, create a new loop and run in background thread
            import threading
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                new_loop.run_until_complete(_do_broadcast())
                new_loop.close()
            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()


@router.websocket("/dashboard/stream")
async def websocket_dashboard_stream(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token"),
):
    """WebSocket endpoint for dashboard-level real-time streaming (all tenant devices).
    
    This endpoint subscribes to ALL devices for the authenticated user's tenant.
    Perfect for dashboard pages that need to show live updates for multiple devices.
    
    Message format:
    {
        "type": "telemetry",
        "device_id": "DEVICE-001",
        "data": {...},
        "timestamp": "2024-01-01T12:00:00Z"
    }
    
    Initial state message:
    {
        "type": "initial_state",
        "metrics": {...},
        "devices": [...],
        "activity": {...}
    }
    """
    # Create database session manually (WebSocket can't use Depends)
    from database import SessionLocal
    db = SessionLocal()
    
    try:
        # Authenticate user from token
        try:
            user = get_current_user_from_token(token, db)
        except Exception as e:
            logger.error(f"Auth error in WebSocket: {e}", exc_info=True)
            db.rollback()
            db.close()
            await websocket.close(code=1008, reason="Authentication failed")
            return
        
        if not user:
            db.rollback()
            db.close()
            await websocket.close(code=1008, reason="Authentication failed")
            return
        
        # Determine tenant_id
        tenant_id = user.tenant_id if user.role == UserRole.TENANT_ADMIN else None
        
        # Connect dashboard WebSocket (accepts the connection)
        await connection_manager.connect_dashboard(websocket, tenant_id, user.id)
        
        # Send initial state (from database via service layer)
        try:
            from services import DashboardService
            dashboard_service = DashboardService(db)
            initial_state = dashboard_service.get_initial_dashboard_state(user)
            
            await websocket.send_json({
                "type": "initial_state",
                "metrics": initial_state.get("metrics", {}),
                "activity": initial_state.get("activity", {}),
                "total_devices": initial_state.get("total_devices", 0),
            })
            logger.info(f"✓ Sent initial state to dashboard WebSocket: tenant_id={tenant_id}")
        except Exception as e:
            logger.error(f"✗ Error sending initial state: {e}", exc_info=True)
            # Don't rollback here - the error is already handled in service layer
            # Send empty initial state if service fails so frontend doesn't hang
            try:
                await websocket.send_json({
                    "type": "initial_state",
                    "metrics": {"active_devices": 0, "messages": {"total_received": 0, "total_published": 0, "total_rejected": 0}, "sources": {}},
                    "activity": {"total_events": 0, "buckets": []},
                    "total_devices": 0,
                })
                logger.info("✓ Sent fallback empty initial state")
            except Exception as fallback_error:
                logger.error(f"✗ Failed to send fallback initial state: {fallback_error}")
                # Close the WebSocket if we can't even send the fallback
                await websocket.close(code=1011, reason="Failed to initialize")
                return
        
        # Close DB session after initial state - we don't need it during the WebSocket lifecycle
        db.close()
        db = None
        
        # Send a ping immediately to confirm connection is alive
        await websocket.send_json({"type": "ping"})
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for client messages with timeout
                import asyncio
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)
                
                # Handle ping
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    break
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
        
    except Exception as e:
        logger.error(f"Dashboard WebSocket connection error: {e}", exc_info=True)
        if db:
            try:
                db.rollback()
            except:
                pass
    finally:
        if db:
            db.close()
        connection_manager.disconnect(websocket)

