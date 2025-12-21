"""Async TCP ingestion server for raw telemetry data."""
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from config import settings
from database import SessionLocal
from models import ProvisioningKey, Device
from rate_limiter import rate_limiter
from metrics import metrics
from validators import telemetry_validator
from kafka_producer import telemetry_producer
from error_handler import dead_letter_queue
from parsers import DingtekDC41XParser, DingtekParseError
from rule_engine import rule_engine

logger = logging.getLogger(__name__)


class TCPIngestionServer:
    """Lightweight JSON-over-TCP ingestion server."""

    def __init__(self):
        self.host = settings.tcp_ingest_host
        self.port = settings.tcp_ingest_port
        self.read_timeout = settings.tcp_read_timeout_seconds
        self.server: Optional[asyncio.base_events.Server] = None
        self._serve_task: Optional[asyncio.Task] = None
        self._connection_semaphore = asyncio.Semaphore(settings.tcp_connection_limit)
        self.dingtek_parser = DingtekDC41XParser()

    async def start(self):
        """Start TCP server."""
        if self.server:
            logger.info("TCP ingestion server already running")
            return

        self.server = await asyncio.start_server(
            self._handle_client,
            host=self.host,
            port=self.port
        )
        self._serve_task = asyncio.create_task(self.server.serve_forever())
        sockets = self.server.sockets or []
        bound_addresses = ", ".join(
            f"{sock.getsockname()[0]}:{sock.getsockname()[1]}"
            for sock in sockets
        )
        logger.info("TCP ingestion server listening on %s", bound_addresses)

    async def stop(self):
        """Stop TCP server."""
        if not self.server:
            return

        logger.info("Stopping TCP ingestion server...")
        self.server.close()
        await self.server.wait_closed()

        if self._serve_task:
            self._serve_task.cancel()
            try:
                await self._serve_task
            except asyncio.CancelledError:
                pass

        self.server = None
        self._serve_task = None
        logger.info("TCP ingestion server stopped")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle inbound TCP connections."""
        peername = writer.get_extra_info("peername")
        remote_addr = f"{peername[0]}:{peername[1]}" if peername else "unknown"
        logger.debug("TCP client connected: %s", remote_addr)

        try:
            async with self._connection_semaphore:
                buffer = bytearray()
                while True:
                    try:
                        chunk = await asyncio.wait_for(reader.read(1024), timeout=self.read_timeout)
                    except asyncio.TimeoutError:
                        logger.debug("TCP read timeout from %s", remote_addr)
                        break

                    if not chunk:
                        while True:
                            frame = self._extract_frame(buffer)
                            if frame is None:
                                break
                            response = await self._process_frame(frame, remote_addr)
                            if response:
                                await self._send_response(writer, response)

                        if buffer:
                            frame = bytes(buffer)
                            buffer.clear()
                            response = await self._process_frame(frame, remote_addr)
                            if response:
                                await self._send_response(writer, response)
                        break

                    buffer.extend(chunk)

                    while True:
                        frame = self._extract_frame(buffer)
                        if frame is None:
                            break

                        response = await self._process_frame(frame, remote_addr)
                        if response:
                            await self._send_response(writer, response)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("TCP client handler error (%s): %s", remote_addr, exc, exc_info=True)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            logger.debug("TCP client disconnected: %s", remote_addr)

    def _extract_frame(self, buffer: bytearray, force_flush: bool = False) -> Optional[bytes]:
        """Extract a complete frame from the buffer."""
        if not buffer:
            return None

        # Dingtek binary frame (0x80 ... 0x81)
        if buffer[0] == self.dingtek_parser.PACKET_HEAD:
            try:
                tail_index = buffer.index(self.dingtek_parser.PACKET_TAIL, 1)
            except ValueError:
                return None if not force_flush else self._force_flush(buffer)
            frame = bytes(buffer[:tail_index + 1])
            del buffer[:tail_index + 1]
            return frame

        # JSON/newline-delimited frame
        newline_index = buffer.find(b"\n")
        if newline_index != -1:
            frame = bytes(buffer[:newline_index + 1])
            del buffer[:newline_index + 1]
            return frame

        # Prevent buffer growth if sender never terminates lines
        if force_flush or len(buffer) > 65535:
            return self._force_flush(buffer)

        return None

    @staticmethod
    def _force_flush(buffer: bytearray) -> Optional[bytes]:
        """Flush remaining bytes as a frame."""
        if not buffer:
            return None
        frame = bytes(buffer)
        buffer.clear()
        return frame

    async def _process_frame(self, data: bytes, remote_addr: str) -> Optional[Dict[str, Any]]:
        """Dispatch frame based on format."""
        if not data:
            return None

        logger.debug("TCP frame (%d bytes) from %s: %s", len(data), remote_addr, data[:16].hex().upper())

        if data[0] == self.dingtek_parser.PACKET_HEAD:
            return await asyncio.to_thread(self._process_dingtek_frame_sync, data, remote_addr)

        cleaned = data.strip()
        if not cleaned:
            return None

        return await self._process_json_frame(cleaned, remote_addr)

    async def _process_json_frame(self, data: bytes, remote_addr: str) -> Optional[Dict[str, Any]]:
        """Validate and route a single JSON message."""
        try:
            message = json.loads(data.decode("utf-8"))
        except UnicodeDecodeError:
            logger.warning(
                "Received non-UTF8 payload from %s (prefix=%s)",
                remote_addr,
                data[:16].hex().upper()
            )
            return {
                "status": "rejected",
                "message": "Payload must be UTF-8 encoded JSON",
                "error": "invalid_encoding"
            }
        except json.JSONDecodeError:
            logger.warning("Received invalid JSON payload from %s", remote_addr)
            metrics.record_error("unknown", "invalid_json")
            return {
                "status": "rejected",
                "message": "Invalid JSON payload",
                "error": "invalid_json"
            }

        if not isinstance(message, dict):
            return {
                "status": "rejected",
                "message": "Payload must be a JSON object",
                "error": "invalid_format"
            }

        return await asyncio.to_thread(self._process_json_message_sync, message, remote_addr)

    def _process_json_message_sync(self, message: Dict[str, Any], remote_addr: str) -> Dict[str, Any]:
        """Blocking processing logic executed in a worker thread."""
        start_time = time.time()

        device_id = message.get("device_id")
        device_key = message.get("device_key") or message.get("provisioning_key")
        payload = message.get("data") or message.get("payload")
        timestamp = message.get("timestamp")
        message_id = message.get("message_id")

        if not isinstance(payload, dict):
            payload = None

        if not device_id:
            metrics.record_error("unknown", "missing_device_id")
            return {
                "status": "rejected",
                "message": "device_id is required",
                "error": "missing_device_id"
            }

        metrics.record_message_received(device_id, source="tcp")

        if not device_key:
            metrics.record_message_rejected(device_id, "missing_device_key")
            metrics.record_auth_failure(device_id)
            return {
                "status": "rejected",
                "device_id": device_id,
                "message": "device_key (provisioning key) is required",
                "error": "missing_device_key"
            }

        if payload is None:
            metrics.record_message_rejected(device_id, "missing_payload")
            return {
                "status": "rejected",
                "device_id": device_id,
                "message": "data payload is required",
                "error": "missing_payload"
            }

        db = SessionLocal()
        device_type_name = None
        tenant_id = None
        try:
            provisioning_key: Optional[ProvisioningKey] = db.query(ProvisioningKey).filter(
                ProvisioningKey.key == device_key,
                ProvisioningKey.is_active == True  # noqa: E712
            ).first()

            if not provisioning_key:
                metrics.record_message_rejected(device_id, "invalid_device_key")
                metrics.record_auth_failure(device_id)
                return {
                    "status": "rejected",
                    "device_id": device_id,
                    "message": "Invalid or inactive provisioning key",
                    "error": "invalid_device_key"
                }

            device = provisioning_key.device
            if not device or not device.is_active:
                metrics.record_message_rejected(device_id, "inactive_device")
                metrics.record_auth_failure(device_id)
                return {
                    "status": "rejected",
                    "device_id": device_id,
                    "message": "Device is inactive or missing",
                    "error": "inactive_device"
                }

            if device.device_id != device_id:
                metrics.record_message_rejected(device_id, "device_key_mismatch")
                metrics.record_auth_failure(device_id)
                return {
                    "status": "rejected",
                    "device_id": device_id,
                    "message": "Provisioning key does not belong to device_id",
                    "error": "device_key_mismatch"
                }
            
            # Verify access token if configured
            provided_token = message.get("access_token") or message.get("token")
            from auth import verify_device_access_token
            if not verify_device_access_token(device, provided_token):
                metrics.record_message_rejected(device_id, "invalid_access_token")
                metrics.record_auth_failure(device_id)
                return {
                    "status": "rejected",
                    "device_id": device_id,
                    "message": "Invalid or missing access token",
                    "error": "invalid_access_token"
                }
            
            # Remove token from payload before processing (don't store it)
            if "access_token" in message:
                message.pop("access_token")
            if "token" in message:
                message.pop("token")

            if provisioning_key.expires_at and provisioning_key.expires_at < datetime.utcnow():
                metrics.record_message_rejected(device_id, "device_key_expired")
                metrics.record_auth_failure(device_id)
                return {
                    "status": "rejected",
                    "device_id": device_id,
                    "message": "Provisioning key has expired",
                    "error": "device_key_expired"
                }

            provisioning_key.last_used_at = datetime.utcnow()
            tenant_id = device.tenant_id
            device_type_name = device.device_type.name if device.device_type else None
            db.commit()

        except Exception as exc:
            db.rollback()
            metrics.record_error(device_id, "auth_lookup_failed")
            logger.error("Failed to verify provisioning key for %s: %s", device_id, exc)
            return {
                "status": "error",
                "device_id": device_id,
                "message": "Internal authentication error",
                "error": "auth_lookup_failed"
            }
        finally:
            db.close()

        # Rate limiting
        is_allowed, reason = rate_limiter.is_allowed(device_id)
        if not is_allowed:
            metrics.record_message_rejected(device_id, "rate_limit_exceeded")
            metrics.record_rate_limit_hit(device_id)
            return {
                "status": "rejected",
                "device_id": device_id,
                "message": reason,
                "error": "rate_limit_exceeded"
            }

        is_valid, validation_error = telemetry_validator.validate_payload(
            device_type_name,
            payload
        )

        if not is_valid:
            metrics.record_message_rejected(device_id, "validation_error")
            metrics.record_error(device_id, "validation_error")
            dead_letter_queue.publish_failed_message(
                device_id=device_id,
                payload=payload,
                metadata={"source": "tcp", "device_type": device_type_name},
                error_type="validation_error",
                error_message=validation_error or "Validation failed"
            )
            return {
                "status": "rejected",
                "device_id": device_id,
                "message": validation_error,
                "error": "validation_error"
            }

        metadata = {
            "timestamp": timestamp or datetime.utcnow().isoformat(),
            "source": "tcp",
            "remote_addr": remote_addr,
            "device_type": device_type_name,
            "tenant_id": tenant_id,
            "received_at": datetime.utcnow().isoformat()
        }

        extra_metadata = message.get("metadata")
        if isinstance(extra_metadata, dict):
            metadata.update(extra_metadata)

        rule_result = rule_engine.evaluate(
            device_id=device_id,
            payload=payload,
            metadata=metadata,
            source="tcp",
            device=device,
        )

        if rule_result.dropped:
            metrics.record_message_rejected(device_id, "rule_drop")
            return {
                "status": "dropped",
                "device_id": device_id,
                "message": rule_result.drop_reason or "Telemetry dropped by rule engine",
                "rule": rule_result.rule_name,
            }

        success = telemetry_producer.publish_raw_telemetry(
            device_id=device_id,
            payload=rule_result.payload,
            metadata=rule_result.metadata,
            topic=rule_result.target_topic,
        )

        processing_time_ms = (time.time() - start_time) * 1000
        metrics.record_processing_time(processing_time_ms)

        if not success:
            metrics.record_message_rejected(device_id, "kafka_publish_failed")
            metrics.record_error(device_id, "kafka_publish_failed")
            return {
                "status": "error",
                "device_id": device_id,
                "message": "Failed to enqueue telemetry",
                "error": "kafka_publish_failed"
            }

        metrics.record_message_published(device_id)

        return {
            "status": "accepted",
            "device_id": device_id,
            "message": "Telemetry accepted",
            "message_id": message_id,
            "source": "tcp"
        }

    def _process_dingtek_frame_sync(self, frame: bytes, remote_addr: str) -> Optional[Dict[str, Any]]:
        """Process Dingtek DC41X hexadecimal frames."""
        start_time = time.time()

        try:
            parsed = self.dingtek_parser.parse(frame)
        except DingtekParseError as exc:
            logger.warning("Failed to parse Dingtek frame: %s", exc)
            metrics.record_error("dingtek", "dingtek_parse_error")
            return {
                "status": "rejected",
                "message": "Invalid Dingtek frame",
                "error": "dingtek_parse_error"
            }

        device_id = parsed.device_id
        metrics.record_message_received(device_id, source="tcp")

        db = SessionLocal()
        device: Optional[Device] = None
        device_type_name: Optional[str] = None
        tenant_id: Optional[int] = None
        try:
            device = db.query(Device).filter(
                Device.device_id == device_id,
                Device.is_active == True  # noqa: E712
            ).first()
            if device:
                tenant_id = device.tenant_id
                device_type_name = device.device_type.name if device.device_type else None
        except Exception as exc:
            logger.error("Device lookup failed for %s: %s", device_id, exc)
            metrics.record_error(device_id, "device_lookup_failed")
        finally:
            db.close()

        if not device:
            metrics.record_message_rejected(device_id, "device_not_registered")
            metrics.record_auth_failure(device_id)
            return {
                "status": "rejected",
                "device_id": device_id,
                "message": "Device not registered or inactive",
                "error": "device_not_registered"
            }

        # Rate limiting
        is_allowed, reason = rate_limiter.is_allowed(device_id)
        if not is_allowed:
            metrics.record_message_rejected(device_id, "rate_limit_exceeded")
            metrics.record_rate_limit_hit(device_id)
            return {
                "status": "rejected",
                "device_id": device_id,
                "message": reason,
                "error": "rate_limit_exceeded"
            }

        telemetry = parsed.telemetry
        is_valid, validation_error = telemetry_validator.validate_payload(
            device_type_name,
            telemetry
        )

        if not is_valid:
            metrics.record_message_rejected(device_id, "validation_error")
            metrics.record_error(device_id, "validation_error")
            dead_letter_queue.publish_failed_message(
                device_id=device_id,
                payload=telemetry,
                metadata={
                    "source": "tcp",
                    "protocol": "dingtek_dc41x",
                    "raw_hex": parsed.raw_hex
                },
                error_type="validation_error",
                error_message=validation_error or "Validation failed"
            )
            return {
                "status": "rejected",
                "device_id": device_id,
                "message": validation_error,
                "error": "validation_error"
            }

        metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "source": "tcp",
            "protocol": "dingtek_dc41x",
            "report_type": parsed.report_type_label,
            "packet_size": parsed.packet_size,
            "forced_bit": parsed.forced_bit,
            "device_type": device_type_name,
            "tenant_id": tenant_id,
            "raw_hex": parsed.raw_hex,
            "remote_addr": remote_addr,
            "received_at": datetime.utcnow().isoformat()
        }

        rule_result = rule_engine.evaluate(
            device_id=device_id,
            payload=telemetry,
            metadata=metadata,
            source="tcp",
            device=device,
        )

        if rule_result.dropped:
            metrics.record_message_rejected(device_id, "rule_drop")
            return {
                "status": "dropped",
                "device_id": device_id,
                "message": rule_result.drop_reason or "Telemetry dropped by rule engine",
                "rule": rule_result.rule_name,
            }

        success = telemetry_producer.publish_raw_telemetry(
            device_id=device_id,
            payload=rule_result.payload,
            metadata=rule_result.metadata,
            topic=rule_result.target_topic,
        )

        processing_time_ms = (time.time() - start_time) * 1000
        metrics.record_processing_time(processing_time_ms)

        if not success:
            metrics.record_message_rejected(device_id, "kafka_publish_failed")
            metrics.record_error(device_id, "kafka_publish_failed")
            return {
                "status": "error",
                "device_id": device_id,
                "message": "Failed to enqueue telemetry",
                "error": "kafka_publish_failed"
            }

        metrics.record_message_published(device_id)

        return {
            "status": "accepted",
            "device_id": device_id,
            "message": "Telemetry accepted",
            "source": "tcp",
            "protocol": "dingtek_dc41x"
        }

    @staticmethod
    async def _send_response(writer: asyncio.StreamWriter, response: Dict[str, Any]):
        """Send JSON response to client."""
        try:
            writer.write(json.dumps(response).encode("utf-8") + b"\n")
            await writer.drain()
        except Exception as exc:
            logger.debug("Failed to send TCP response: %s", exc)


# Global TCP server instance
tcp_ingestion_server = TCPIngestionServer()


