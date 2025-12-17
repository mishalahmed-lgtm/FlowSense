"""Service for sending MQTT commands to devices."""
import json
import logging
import paho.mqtt.client as mqtt
from typing import Dict, Any, Optional
from config import settings

logger = logging.getLogger(__name__)


class MQTTCommandService:
    """Service for publishing MQTT commands to devices."""
    
    def __init__(self):
        """Initialize MQTT command service."""
        self.client = mqtt.Client(client_id="iot-command-service")
        
        # Set credentials if provided
        if settings.mqtt_broker_username and settings.mqtt_broker_password:
            self.client.username_pw_set(
                settings.mqtt_broker_username,
                settings.mqtt_broker_password
            )
        
        self.is_connected = False
        self._connect()
    
    def _connect(self):
        """Connect to MQTT broker."""
        try:
            self.client.connect(
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
                keepalive=60
            )
            self.client.loop_start()
            self.is_connected = True
            logger.info(f"MQTT command service connected to {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")
        except Exception as e:
            logger.error(f"Failed to connect MQTT command service: {e}")
            self.is_connected = False
    
    def publish_command(
        self,
        device_id: str,
        command: Dict[str, Any],
        topic: Optional[str] = None,
        qos: int = 1
    ) -> bool:
        """Publish a command to a device via MQTT.
        
        Args:
            device_id: Device identifier
            command: Command payload (dict)
            topic: MQTT topic (default: devices/{device_id}/commands)
            qos: Quality of Service level (0, 1, or 2)
        
        Returns:
            True if published successfully, False otherwise
        """
        if not self.is_connected:
            logger.warning("MQTT command service not connected, attempting reconnect...")
            self._connect()
            if not self.is_connected:
                return False
        
        if not topic:
            topic = f"devices/{device_id}/commands"
        
        try:
            payload = json.dumps(command)
            result = self.client.publish(topic, payload, qos=qos)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published command to {topic} for device {device_id}")
                return True
            else:
                logger.error(f"Failed to publish command to {topic}: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Error publishing command to {topic}: {e}", exc_info=True)
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.is_connected:
            self.client.loop_stop()
            self.client.disconnect()
            self.is_connected = False
            logger.info("MQTT command service disconnected")


# Global instance
mqtt_command_service = MQTTCommandService()

