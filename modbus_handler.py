"""Modbus TCP/IP ingestion handler."""
import logging
import json
import struct
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from database import SessionLocal
from models import Device
from kafka_producer import telemetry_producer
from metrics import metrics
from rule_engine import rule_engine
from alert_engine import alert_engine

logger = logging.getLogger(__name__)


class ModbusTCPHandler:
    """Handler for Modbus TCP/IP protocol ingestion."""
    
    # Modbus TCP/IP constants
    MBAP_HEADER_LENGTH = 7
    MODBUS_TCP_PORT = 502
    
    def __init__(self):
        """Initialize Modbus TCP handler."""
        self.server: Optional[asyncio.Server] = None
        self._running = False
    
    async def start(self, host: str = "0.0.0.0", port: int = 5020):
        """Start Modbus TCP server."""
        if self._running:
            logger.warning("Modbus TCP server already running")
            return
        
        self.server = await asyncio.start_server(
            self._handle_client,
            host=host,
            port=port
        )
        self._running = True
        logger.info(f"Modbus TCP server listening on {host}:{port}")
    
    async def stop(self):
        """Stop Modbus TCP server."""
        if not self._running:
            return
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        self._running = False
        logger.info("Modbus TCP server stopped")
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle Modbus TCP client connection."""
        peername = writer.get_extra_info("peername")
        remote_addr = f"{peername[0]}:{peername[1]}" if peername else "unknown"
        logger.debug(f"Modbus TCP client connected: {remote_addr}")
        
        try:
            while True:
                # Read MBAP header (7 bytes)
                header = await reader.read(self.MBAP_HEADER_LENGTH)
                if len(header) < self.MBAP_HEADER_LENGTH:
                    break
                
                # Parse MBAP header
                transaction_id, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
                
                # Read remaining PDU
                pdu_length = length - 1  # Subtract unit_id byte
                pdu = await reader.read(pdu_length)
                if len(pdu) < pdu_length:
                    break
                
                # Process Modbus request
                response = await self._process_modbus_request(
                    transaction_id, unit_id, pdu, remote_addr
                )
                
                # Send response
                if response:
                    writer.write(response)
                    await writer.drain()
        except Exception as e:
            logger.error(f"Error handling Modbus TCP client {remote_addr}: {e}", exc_info=True)
        finally:
            writer.close()
            await writer.wait_closed()
            logger.debug(f"Modbus TCP client disconnected: {remote_addr}")
    
    async def _process_modbus_request(
        self, transaction_id: int, unit_id: int, pdu: bytes, remote_addr: str
    ) -> Optional[bytes]:
        """Process Modbus request and return response."""
        if len(pdu) < 1:
            return None
        
        function_code = pdu[0]
        
        # Handle Read Holding Registers (0x03)
        if function_code == 0x03:
            return await self._handle_read_holding_registers(
                transaction_id, unit_id, pdu, remote_addr
            )
        # Handle Read Input Registers (0x04)
        elif function_code == 0x04:
            return await self._handle_read_input_registers(
                transaction_id, unit_id, pdu, remote_addr
            )
        # Handle Read Coils (0x01)
        elif function_code == 0x01:
            return await self._handle_read_coils(
                transaction_id, unit_id, pdu, remote_addr
            )
        # Handle Read Discrete Inputs (0x02)
        elif function_code == 0x02:
            return await self._handle_read_discrete_inputs(
                transaction_id, unit_id, pdu, remote_addr
            )
        else:
            # Unsupported function code
            logger.warning(f"Unsupported Modbus function code: {function_code}")
            return self._create_error_response(transaction_id, unit_id, function_code, 0x01)
    
    async def _handle_read_holding_registers(
        self, transaction_id: int, unit_id: int, pdu: bytes, remote_addr: str
    ) -> bytes:
        """Handle Read Holding Registers request."""
        if len(pdu) < 5:
            return self._create_error_response(transaction_id, unit_id, 0x03, 0x01)
        
        start_address = struct.unpack(">H", pdu[1:3])[0]
        quantity = struct.unpack(">H", pdu[3:5])[0]
        
        # Map unit_id to device_id (you may need to configure this mapping)
        device_id = await self._get_device_from_unit_id(unit_id)
        if not device_id:
            return self._create_error_response(transaction_id, unit_id, 0x03, 0x0B)
        
        # For ingestion, we treat Modbus reads as telemetry data
        # In a real system, you'd read actual register values from the device
        # For now, we'll create a telemetry payload from the request
        telemetry_data = {
            "modbus_unit_id": unit_id,
            "start_address": start_address,
            "quantity": quantity,
            "function_code": "read_holding_registers",
        }
        
        metadata = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "modbus_tcp",
            "remote_addr": remote_addr,
            "transaction_id": transaction_id,
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
        except Exception as e:
            logger.error(f"Error publishing Modbus telemetry: {e}")
        
        # Return dummy response (in production, read actual register values)
        byte_count = quantity * 2
        response_pdu = struct.pack(">BB", 0x03, byte_count) + b"\x00" * byte_count
        return self._create_response(transaction_id, unit_id, response_pdu)
    
    async def _handle_read_input_registers(
        self, transaction_id: int, unit_id: int, pdu: bytes, remote_addr: str
    ) -> bytes:
        """Handle Read Input Registers request."""
        # Similar to holding registers
        return await self._handle_read_holding_registers(transaction_id, unit_id, pdu, remote_addr)
    
    async def _handle_read_coils(
        self, transaction_id: int, unit_id: int, pdu: bytes, remote_addr: str
    ) -> bytes:
        """Handle Read Coils request."""
        if len(pdu) < 5:
            return self._create_error_response(transaction_id, unit_id, 0x01, 0x01)
        
        start_address = struct.unpack(">H", pdu[1:3])[0]
        quantity = struct.unpack(">H", pdu[3:5])[0]
        
        device_id = await self._get_device_from_unit_id(unit_id)
        if device_id:
            telemetry_data = {
                "modbus_unit_id": unit_id,
                "start_address": start_address,
                "quantity": quantity,
                "function_code": "read_coils",
            }
            
            metadata = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "modbus_tcp",
                "remote_addr": remote_addr,
            }
            
            try:
                telemetry_producer.publish_raw_telemetry(
                    device_id=device_id,
                    payload=telemetry_data,
                    metadata=metadata,
                    topic="raw_telemetry",
                )
            except Exception as e:
                logger.error(f"Error publishing Modbus telemetry: {e}")
        
        # Return dummy response
        byte_count = (quantity + 7) // 8
        response_pdu = struct.pack(">BB", 0x01, byte_count) + b"\x00" * byte_count
        return self._create_response(transaction_id, unit_id, response_pdu)
    
    async def _handle_read_discrete_inputs(
        self, transaction_id: int, unit_id: int, pdu: bytes, remote_addr: str
    ) -> bytes:
        """Handle Read Discrete Inputs request."""
        # Similar to coils
        return await self._handle_read_coils(transaction_id, unit_id, pdu, remote_addr)
    
    async def _get_device_from_unit_id(self, unit_id: int) -> Optional[str]:
        """Map Modbus unit_id to device_id."""
        # In production, you'd have a mapping table or use device metadata
        # For now, we'll try to find a device with matching metadata
        db = SessionLocal()
        try:
            # Try to find device with modbus_unit_id in metadata
            devices = db.query(Device).filter(Device.is_active == True).all()
            for device in devices:
                if device.device_metadata:
                    try:
                        metadata = json.loads(device.device_metadata) if isinstance(device.device_metadata, str) else device.device_metadata
                        if metadata.get("modbus_unit_id") == unit_id:
                            return device.device_id
                    except:
                        pass
            return None
        finally:
            db.close()
    
    def _create_response(self, transaction_id: int, unit_id: int, pdu: bytes) -> bytes:
        """Create Modbus TCP response with MBAP header."""
        length = len(pdu) + 1  # +1 for unit_id
        mbap = struct.pack(">HHHB", transaction_id, 0x0000, length, unit_id)
        return mbap + pdu
    
    def _create_error_response(self, transaction_id: int, unit_id: int, function_code: int, exception_code: int) -> bytes:
        """Create Modbus error response."""
        error_pdu = struct.pack(">BB", function_code | 0x80, exception_code)
        return self._create_response(transaction_id, unit_id, error_pdu)


# Global Modbus TCP handler instance
modbus_handler = ModbusTCPHandler()

