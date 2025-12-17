"""WebSocket API for real-time data streaming."""
import json
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from admin_auth import get_current_user_from_token
from database import get_db
from models import Device, TelemetryLatest, User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time data streaming."""
    
    def __init__(self):
        # Map device_id -> Set[WebSocket]
        self.device_connections: Dict[str, Set[WebSocket]] = {}
        # Map WebSocket -> device_id
        self.connection_devices: Dict[WebSocket, str] = {}
        # Map WebSocket -> user_id
        self.connection_users: Dict[WebSocket, int] = {}
    
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
        
        logger.info(f"WebSocket disconnected: device={device_id}")
    
    async def broadcast_to_device(self, device_id: str, message: dict):
        """Broadcast a message to all clients subscribed to a device."""
        if device_id not in self.device_connections:
            return
        
        disconnected = set()
        for websocket in self.device_connections[device_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)
    
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
    db: Session = Depends(get_db),
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
    try:
        # Authenticate user from token
        user = get_current_user_from_token(token, db)
        if not user:
            await websocket.close(code=1008, reason="Authentication failed")
            return
        
        # Verify device exists and user has access
        device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
        if not device:
            await websocket.close(code=1008, reason="Device not found")
            return
        
        # Check tenant access
        if user.role == UserRole.TENANT_ADMIN and device.tenant_id != user.tenant_id:
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
        connection_manager.disconnect(websocket)


def broadcast_telemetry_update(device_id: str, data: dict, timestamp: str, db: Session):
    """Broadcast telemetry update to all connected WebSocket clients.
    
    This function should be called by the telemetry worker when new data arrives.
    """
    message = {
        "type": "telemetry",
        "device_id": device_id,
        "data": data,
        "timestamp": timestamp,
    }
    
    # Use asyncio to broadcast (this will be called from sync context)
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # If loop is already running, schedule the coroutine
        asyncio.create_task(connection_manager.broadcast_to_device(device_id, message))
    else:
        loop.run_until_complete(connection_manager.broadcast_to_device(device_id, message))

