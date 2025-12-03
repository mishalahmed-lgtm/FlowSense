"""Kafka producer for publishing raw telemetry data."""
import json
import logging
import time
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError
from config import settings
from error_handler import retry_handler, dead_letter_queue

logger = logging.getLogger(__name__)


class TelemetryProducer:
    """Kafka producer for raw telemetry data."""
    
    def __init__(self):
        """Initialize Kafka producer (lazy initialization)."""
        self.producer = None
        self._initialized = False
    
    def _ensure_producer(self):
        """Ensure Kafka producer is initialized."""
        if self._initialized and self.producer:
            return
        
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers.split(','),
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',  # Wait for all replicas to acknowledge
                retries=3,
                max_in_flight_requests_per_connection=1
            )
            self._initialized = True
            logger.info(f"Kafka producer initialized. Bootstrap servers: {settings.kafka_bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            self._initialized = False
            raise
    
    def publish_raw_telemetry(
        self,
        device_id: str,
        payload: Dict[str, Any],
        metadata: Dict[str, Any] = None,
        topic: Optional[str] = None,
    ) -> bool:
        """
        Publish raw telemetry data to Kafka raw_telemetry topic.
        Implements retry logic and dead letter queue for failed messages.
        
        Args:
            device_id: Unique device identifier
            payload: Raw telemetry payload from device
            metadata: Additional metadata (timestamp, source, etc.)
            
        Returns:
            True if published successfully, False otherwise
        """
        message = {
            "device_id": device_id,
            "payload": payload,
            "metadata": metadata or {},
            "timestamp": metadata.get("timestamp") if metadata else None
        }
        
        last_error = None
        
        # Retry loop
        for attempt in range(1, retry_handler.max_retries + 1):
            try:
                # Lazy initialization
                self._ensure_producer()
                
                # Use device_id as partition key for ordering per device
                target_topic = topic or settings.kafka_raw_telemetry_topic
                future = self.producer.send(
                    target_topic,
                    key=device_id,
                    value=message
                )
                
                # Wait for the message to be sent (with timeout)
                record_metadata = future.get(timeout=10)
                logger.info(
                    f"Published telemetry to Kafka. "
                    f"Topic: {record_metadata.topic}, "
                    f"Partition: {record_metadata.partition}, "
                    f"Offset: {record_metadata.offset}, "
                    f"Device: {device_id}"
                )
                return True
                
            except (KafkaError, Exception) as e:
                last_error = e
                
                # Check if we should retry
                if retry_handler.should_retry(e, attempt):
                    delay = retry_handler.get_retry_delay(attempt)
                    logger.warning(
                        f"Retry {attempt}/{retry_handler.max_retries} for device {device_id}: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    continue
                else:
                    # Non-retryable error or max retries reached
                    break
        
        # All retries exhausted - send to DLQ
        error_type = type(last_error).__name__ if last_error else "unknown_error"
        error_message = str(last_error) if last_error else "Failed to publish after retries"
        
        logger.error(
            f"Failed to publish telemetry after {retry_handler.max_retries} attempts. "
            f"Device: {device_id}, Error: {error_message}. Sending to DLQ."
        )
        
        # Publish to dead letter queue
        dead_letter_queue.publish_failed_message(
            device_id=device_id,
            payload=payload,
            metadata=metadata or {},
            error_type=error_type,
            error_message=error_message
        )
        
        return False
    
    def close(self):
        """Close the Kafka producer."""
        if self.producer:
            self.producer.close()
            logger.info("Kafka producer closed")


# Global producer instance (lazy initialization)
telemetry_producer = TelemetryProducer()

