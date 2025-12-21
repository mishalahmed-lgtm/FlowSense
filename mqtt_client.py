"""MQTT client for receiving telemetry from valve controllers and other MQTT devices."""
import json
import logging
import time
from typing import Callable, Dict, Any, Optional
import paho.mqtt.client as mqtt
from config import settings
from kafka_producer import telemetry_producer
from datetime import datetime
from database import SessionLocal
from models import Device
from rate_limiter import rate_limiter
from metrics import metrics
from validators import telemetry_validator
from error_handler import dead_letter_queue
from rule_engine import rule_engine

logger = logging.getLogger(__name__)


class MQTTTelemetryHandler:
    """MQTT client for ingesting telemetry from MQTT devices."""
    
    def __init__(self):
        """Initialize MQTT client."""
        self.client = mqtt.Client(client_id="iot-ingestion-gateway")
        
        # Set credentials if provided
        if settings.mqtt_broker_username and settings.mqtt_broker_password:
            self.client.username_pw_set(
                settings.mqtt_broker_username,
                settings.mqtt_broker_password
            )
        
        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        self.is_connected = False
    
    def _verify_device(self, device_id: str):
        """
        Verify that a device exists and is active in the database.
        
        Args:
            device_id: The device identifier from the MQTT topic
            
        Returns:
            Tuple of (device_id, device_type_name, device_db_id, tenant_id) if valid, None otherwise
        """
        from sqlalchemy.orm import joinedload
        db = SessionLocal()
        try:
            device = db.query(Device).options(
                joinedload(Device.device_type)
            ).filter(
                Device.device_id == device_id,
                Device.is_active == True
            ).first()
            if device:
                device_type_name = device.device_type.name if device.device_type else None
                tenant_id = device.tenant_id
                # Return tuple to avoid session issues
                return (device.device_id, device_type_name, device.id, tenant_id)
            return None
        except Exception as e:
            logger.error(f"Error verifying device {device_id}: {e}")
            return None
        finally:
            db.close()
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when MQTT client connects."""
        if rc == 0:
            self.is_connected = True
            logger.info(f"Connected to MQTT broker at {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")
            
            # Subscribe to all device telemetry topics
            # Format: devices/{device_id}/telemetry or device/{device_id}/telemetry
            client.subscribe("devices/+/telemetry", qos=1)
            client.subscribe("devices/+/status", qos=1)
            client.subscribe("device/+/telemetry", qos=1)  # Also support singular "device" prefix
            client.subscribe("device/+/status", qos=1)
            logger.info("Subscribed to MQTT topics: devices/+/telemetry, devices/+/status, device/+/telemetry, device/+/status")
        else:
            logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
            self.is_connected = False
    
    def _on_message(self, client, userdata, msg):
        """Callback when MQTT message is received."""
        start_time = time.time()
        device_id = None
        
        try:
            topic_parts = msg.topic.split('/')
            if len(topic_parts) < 2:
                logger.warning(f"Invalid MQTT topic format: {msg.topic}")
                metrics.record_error("unknown", "invalid_topic_format")
                return
            
            device_id = topic_parts[1]
            message_type = topic_parts[2] if len(topic_parts) > 2 else "telemetry"
            
            # Record message received
            metrics.record_message_received(device_id, source="mqtt")
            
            # Step 1: Verify device exists and is active
            device_info = self._verify_device(device_id)
            if not device_info:
                logger.warning(
                    f"Rejected MQTT message from unauthorized/inactive device: {device_id} "
                    f"(topic: {msg.topic})"
                )
                metrics.record_message_rejected(device_id, "unauthorized_device")
                metrics.record_auth_failure(device_id)
                return  # Reject message from unknown/inactive device
            
            verified_device_id, device_type_name, device_db_id, tenant_id = device_info
            
            # Step 2: Check rate limiting
            is_allowed, reason = rate_limiter.is_allowed(device_id)
            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for device {device_id}: {reason} "
                    f"(topic: {msg.topic})"
                )
                metrics.record_message_rejected(device_id, "rate_limit_exceeded")
                metrics.record_rate_limit_hit(device_id)
                return  # Reject message due to rate limiting
            
            # Parse payload
            try:
                payload = json.loads(msg.payload.decode('utf-8'))
                
                # Verify access token if configured (after parsing payload)
                provided_token = payload.get("access_token") or payload.get("token")
                db = SessionLocal()
                try:
                    device = db.query(Device).filter(Device.id == device_db_id).first()
                    if device:
                        from auth import verify_device_access_token
                        if not verify_device_access_token(device, provided_token):
                            logger.warning(
                                f"Rejected MQTT message from device {device_id}: invalid access token "
                                f"(topic: {msg.topic})"
                            )
                            metrics.record_message_rejected(device_id, "invalid_access_token")
                            metrics.record_auth_failure(device_id)
                            return
                finally:
                    db.close()
                
                # Remove token from payload before processing (don't store it)
                if "access_token" in payload:
                    payload.pop("access_token")
                if "token" in payload:
                    payload.pop("token")
                    
            except json.JSONDecodeError:
                error_msg = "Invalid JSON payload"
                logger.warning(f"{error_msg} from device {device_id}")
                metrics.record_message_rejected(device_id, "invalid_json")
                metrics.record_error(device_id, "invalid_json")
                dead_letter_queue.publish_failed_message(
                    device_id=device_id,
                    payload={"raw": msg.payload.decode('utf-8')},
                    metadata={"topic": msg.topic},
                    error_type="invalid_json",
                    error_message=error_msg
                )
                return
            
            # Step 3: Validate payload against device type schema
            is_valid, validation_error = telemetry_validator.validate_payload(
                device_type_name, payload
            )
            
            if not is_valid:
                error_msg = f"Payload validation failed: {validation_error}"
                logger.warning(f"{error_msg} for device {device_id}")
                metrics.record_message_rejected(device_id, "validation_error")
                metrics.record_error(device_id, "validation_error")
                dead_letter_queue.publish_failed_message(
                    device_id=device_id,
                    payload=payload,
                    metadata={"topic": msg.topic, "device_type": device_type_name},
                    error_type="validation_error",
                    error_message=validation_error or "Unknown validation error"
                )
                return
            
            # Create metadata
            metadata = {
                "timestamp": datetime.utcnow().isoformat(),
                "source": "mqtt",
                "topic": msg.topic,
                "qos": msg.qos,
                "message_type": message_type,
                "device_type": device_type_name,
                "tenant_id": tenant_id
            }
            
            # Evaluate rules before publishing
            # Create a simple device-like object for rule engine
            class DeviceInfo:
                def __init__(self, device_id, device_type_name, device_db_id, tenant_id):
                    self.device_id = device_id
                    self.id = device_db_id
                    self.tenant_id = tenant_id
                    self.device_type = type('obj', (object,), {'name': device_type_name})() if device_type_name else None
            
            device_obj = DeviceInfo(verified_device_id, device_type_name, device_db_id, tenant_id)
            rule_result = rule_engine.evaluate(
                device_id=device_id,
                payload=payload,
                metadata=metadata,
                source="mqtt",
                device=device_obj,
            )

            if rule_result.dropped:
                metrics.record_message_rejected(device_id, "rule_drop")
                logger.info(
                    "Rule '%s' dropped MQTT telemetry for %s (%s)",
                    rule_result.rule_name,
                    device_id,
                    rule_result.drop_reason,
                )
                return

            payload = rule_result.payload
            metadata = rule_result.metadata
            target_topic = rule_result.target_topic

            # Publish to Kafka
            success = telemetry_producer.publish_raw_telemetry(
                device_id=device_id,
                payload=payload,
                metadata=metadata,
                topic=target_topic,
            )
            
            # Record processing time
            processing_time = (time.time() - start_time) * 1000  # Convert to ms
            metrics.record_processing_time(processing_time)
            
            if success:
                metrics.record_message_published(device_id)
                logger.debug(f"Processed MQTT message from device {device_id} on topic {msg.topic}")
            else:
                metrics.record_message_rejected(device_id, "kafka_publish_failed")
                metrics.record_error(device_id, "kafka_publish_failed")
                logger.warning(f"Failed to publish MQTT message from device {device_id} to Kafka")
                    
        except Exception as e:
            if device_id:
                metrics.record_error(device_id, "processing_error")
            logger.error(f"Error processing MQTT message: {e}", exc_info=True)
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when MQTT client disconnects."""
        self.is_connected = False
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection. Return code: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def connect(self):
        """Connect to MQTT broker."""
        try:
            logger.info(f"Connecting to MQTT broker at {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")
            self.client.connect(
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
                keepalive=60
            )
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.is_connected:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Disconnected from MQTT broker")


# Global MQTT handler instance
mqtt_handler = MQTTTelemetryHandler()

