"""DALI (Digital Addressable Lighting Interface) ingestion handler."""
import logging
import json
import asyncio
import struct
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from database import SessionLocal
from models import Device
from kafka_producer import telemetry_producer
from metrics import metrics

logger = logging.getLogger(__name__)


class DALIHandler:
    """Handler for DALI protocol ingestion (typically over TCP or serial)."""
    
    def __init__(self):
        """Initialize DALI handler."""
        self.server: Optional[asyncio.Server] = None
        self._running = False
    
    async def start(self, host: str = "0.0.0.0", port: int = 6001):
        """Start DALI TCP server."""
        if self._running:
            logger.warning("DALI server already running")
            return
        
        self.server = await asyncio.start_server(
            self._handle_client,
            host=host,
            port=port
        )
        self._running = True
        logger.info(f"DALI server listening on {host}:{port}")
    
    async def stop(self):
        """Stop DALI server."""
        if not self._running:
            return
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        self._running = False
        logger.info("DALI server stopped")
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle DALI client connection."""
        peername = writer.get_extra_info("peername")
        remote_addr = f"{peername[0]}:{peername[1]}" if peername else "unknown"
        logger.debug(f"DALI client connected: {remote_addr}")
        
        try:
            while True:
                # DALI frames are typically 2 bytes (address + command)
                # But we'll support variable length for flexibility
                data = await reader.read(1024)
                if not data:
                    break
                
                # Process DALI frame
                await self._process_dali_frame(data, remote_addr)
                
                # Send acknowledgment
                writer.write(b"OK\n")
                await writer.drain()
        except Exception as e:
            logger.error(f"Error handling DALI client {remote_addr}: {e}", exc_info=True)
        finally:
            writer.close()
            await writer.wait_closed()
            logger.debug(f"DALI client disconnected: {remote_addr}")
    
    async def _process_dali_frame(self, frame: bytes, remote_addr: str):
        """Process DALI frame and extract telemetry."""
        if len(frame) < 2:
            return
        
        # Parse DALI frame
        # Format: [address (8 bits)] [command (8 bits)] [optional data...]
        address = frame[0]
        command = frame[1] if len(frame) > 1 else 0
        
        # Extract device_id from address or remote_addr mapping
        device_id = await self._get_device_from_dali_address(address, remote_addr)
        if not device_id:
            logger.warning(f"DALI: No device found for address {address} from {remote_addr}")
            return
        
        # Build telemetry payload
        telemetry_data = {
            "dali_address": address,
            "dali_command": command,
            "raw_frame": frame.hex().upper(),
        }
        
        # If frame has additional data, try to parse it
        if len(frame) > 2:
            telemetry_data["data_bytes"] = [b for b in frame[2:]]
        
        metadata = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "dali",
            "remote_addr": remote_addr,
        }
        
        # Publish to Kafka
        try:
            telemetry_producer.publish_raw_telemetry(
                device_id=device_id,
                payload=telemetry_data,
                metadata=metadata,
                topic="raw_telemetry",
            )
            metrics.record_message_published(device_id)
            logger.debug(f"DALI: Published telemetry for device {device_id}")
        except Exception as e:
            logger.error(f"Error publishing DALI telemetry: {e}")
    
    async def _get_device_from_dali_address(self, address: int, remote_addr: str) -> Optional[str]:
        """Map DALI address to device_id."""
        db = SessionLocal()
        try:
            # Try to find device with dali_address in metadata
            devices = db.query(Device).filter(Device.is_active == True).all()
            for device in devices:
                if device.device_metadata:
                    try:
                        metadata = json.loads(device.device_metadata) if isinstance(device.device_metadata, str) else device.device_metadata
                        if metadata.get("dali_address") == address:
                            return device.device_id
                    except:
                        pass
            
            # Fallback: try to match by remote_addr or use address as device_id
            # In production, you'd have a proper mapping table
            return None
        finally:
            db.close()


# Global DALI handler instance
dali_handler = DALIHandler()

