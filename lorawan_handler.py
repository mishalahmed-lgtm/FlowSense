"""LoRaWAN ingestion handler - processes webhooks from LoRaWAN network servers."""
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from database import SessionLocal
from models import Device, TelemetryLatest
from kafka_producer import telemetry_producer
from metrics import metrics
from rule_engine import rule_engine
from alert_engine import alert_engine

logger = logging.getLogger(__name__)


class LoRaWANHandler:
    """Handler for LoRaWAN webhook ingestion from network servers (TTN, ChirpStack, etc.)."""
    
    def process_webhook(self, webhook_payload: Dict[str, Any], device_id: str) -> Dict[str, Any]:
        """
        Process LoRaWAN webhook payload from network server.
        
        Common webhook formats:
        - TTN (The Things Network): https://www.thethingsnetwork.org/docs/applications/mqtt/api/
        - ChirpStack: https://www.chirpstack.io/application-server/integrations/webhook/
        
        Args:
            webhook_payload: Raw webhook JSON from LoRaWAN network server
            device_id: Device identifier (DevEUI or device_id from webhook)
            
        Returns:
            Response dict with status and message
        """
        db = SessionLocal()
        try:
            # Find device by device_id
            device = db.query(Device).filter(Device.device_id == device_id).first()
            if not device:
                logger.warning(f"LoRaWAN: Device {device_id} not found")
                return {"status": "error", "message": f"Device {device_id} not found"}
            
            # Extract telemetry data from webhook
            # Different network servers have different formats
            telemetry_data = self._extract_telemetry(webhook_payload)
            
            if not telemetry_data:
                logger.warning(f"LoRaWAN: Could not extract telemetry from webhook for {device_id}")
                return {"status": "error", "message": "Could not extract telemetry data"}
            
            # Extract metadata
            metadata = self._extract_metadata(webhook_payload)
            
            # Record metrics
            metrics.record_message_received(device_id, source="lorawan")
            
            # Process with rule engine
            class DeviceInfo:
                def __init__(self, device):
                    self.device_id = device.device_id
                    self.id = device.id
                    self.tenant_id = device.tenant_id
                    self.device_type = device.device_type
            
            device_obj = DeviceInfo(device)
            rule_result = rule_engine.evaluate(
                device_id=device.device_id,
                payload=telemetry_data,
                metadata=metadata,
                source="lorawan",
                device=device_obj,
            )
            
            if rule_result.dropped:
                metrics.record_message_rejected(device_id, "rule_drop")
                return {"status": "dropped", "message": rule_result.drop_reason}
            
            # Publish to Kafka
            success = telemetry_producer.publish_raw_telemetry(
                device_id=device_id,
                payload=rule_result.payload,
                metadata=rule_result.metadata,
                topic=rule_result.target_topic,
            )
            
            if success:
                metrics.record_message_published(device_id)
                # Process alerts
                try:
                    alert_engine.process_telemetry(
                        device_id=device.id,
                        tenant_id=device.tenant_id,
                        payload=rule_result.payload,
                        metadata=rule_result.metadata
                    )
                except Exception as e:
                    logger.error(f"Error processing alerts for LoRaWAN device {device_id}: {e}")
                
                return {"status": "accepted", "message": "Telemetry processed"}
            else:
                metrics.record_message_rejected(device_id, "kafka_publish_failed")
                return {"status": "error", "message": "Failed to publish to Kafka"}
                
        except Exception as e:
            logger.error(f"Error processing LoRaWAN webhook for {device_id}: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
        finally:
            db.close()
    
    def _extract_telemetry(self, webhook: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract telemetry data from various LoRaWAN webhook formats."""
        # Try TTN format
        if "uplink_message" in webhook:
            uplink = webhook["uplink_message"]
            # Decode payload (base64)
            if "decoded_payload" in uplink:
                return uplink["decoded_payload"]
            # Or use raw payload if available
            if "frm_payload" in uplink:
                # Base64 encoded, would need decoding
                return {"raw_payload": uplink["frm_payload"]}
        
        # Try ChirpStack format
        if "data" in webhook:
            data = webhook["data"]
            if isinstance(data, dict):
                return data
            elif isinstance(data, str):
                # Try to parse as JSON
                try:
                    return json.loads(data)
                except:
                    return {"raw_data": data}
        
        # Try generic format
        if "payload" in webhook:
            return webhook["payload"]
        
        # Try "object" field (common in some formats)
        if "object" in webhook:
            return webhook["object"]
        
        return None
    
    def _extract_metadata(self, webhook: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from LoRaWAN webhook."""
        metadata = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "lorawan",
        }
        
        # Extract timestamp
        if "received_at" in webhook:
            metadata["received_at"] = webhook["received_at"]
        if "uplink_message" in webhook and "received_at" in webhook["uplink_message"]:
            metadata["received_at"] = webhook["uplink_message"]["received_at"]
        
        # Extract gateway info
        if "uplink_message" in webhook and "rx_metadata" in webhook["uplink_message"]:
            rx_meta = webhook["uplink_message"]["rx_metadata"]
            if rx_meta and len(rx_meta) > 0:
                gateway = rx_meta[0]
                metadata["gateway_id"] = gateway.get("gateway_ids", {}).get("gateway_id")
                metadata["rssi"] = gateway.get("rssi")
                metadata["snr"] = gateway.get("snr")
        
        # Extract frequency and data rate
        if "uplink_message" in webhook:
            uplink = webhook["uplink_message"]
            if "settings" in uplink:
                settings = uplink["settings"]
                metadata["frequency"] = settings.get("frequency")
                metadata["data_rate"] = settings.get("data_rate")
        
        return metadata


# Global LoRaWAN handler instance
lorawan_handler = LoRaWANHandler()

