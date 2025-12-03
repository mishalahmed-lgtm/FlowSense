"""Error handling and retry logic for telemetry ingestion."""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from kafka import KafkaProducer
from kafka.errors import KafkaError
from config import settings

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """
    Dead Letter Queue (DLQ) for messages that fail processing.
    Publishes failed messages to a Kafka topic for later analysis/reprocessing.
    """
    
    def __init__(self, dlq_topic: str = "dlq_telemetry"):
        """
        Initialize DLQ.
        
        Args:
            dlq_topic: Kafka topic name for dead letter queue
        """
        self.dlq_topic = dlq_topic
        self.producer: Optional[KafkaProducer] = None
    
    def _get_producer(self) -> KafkaProducer:
        """Get or create Kafka producer for DLQ."""
        if self.producer is None:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=settings.kafka_bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    retries=3,
                    acks="all"
                )
                logger.info(f"DLQ producer initialized for topic: {self.dlq_topic}")
            except Exception as e:
                logger.error(f"Failed to initialize DLQ producer: {e}")
                raise
        return self.producer
    
    def publish_failed_message(
        self,
        device_id: str,
        payload: Dict[str, Any],
        metadata: Dict[str, Any],
        error_type: str,
        error_message: str
    ) -> bool:
        """
        Publish a failed message to the dead letter queue.
        
        Args:
            device_id: Device identifier
            payload: Original message payload
            metadata: Original message metadata
            error_type: Type of error (e.g., "validation_error", "kafka_error")
            error_message: Error message
            
        Returns:
            True if published successfully, False otherwise
        """
        try:
            producer = self._get_producer()
            
            dlq_message = {
                "device_id": device_id,
                "original_payload": payload,
                "original_metadata": metadata,
                "error": {
                    "type": error_type,
                    "message": error_message,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "dlq_timestamp": datetime.utcnow().isoformat()
            }
            
            future = producer.send(self.dlq_topic, dlq_message)
            future.get(timeout=5)  # Wait for confirmation
            logger.info(
                f"Published failed message to DLQ: device={device_id}, "
                f"error_type={error_type}"
            )
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to publish to DLQ: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error publishing to DLQ: {e}")
            return False
    
    def close(self):
        """Close the DLQ producer."""
        if self.producer:
            self.producer.close()
            self.producer = None
            logger.info("DLQ producer closed")


class RetryHandler:
    """
    Handles retries for transient failures.
    """
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize retry handler.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """
        Determine if an error should be retried.
        
        Args:
            error: The exception that occurred
            attempt: Current attempt number (1-indexed)
            
        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.max_retries:
            return False
        
        # Retry on transient errors
        retryable_errors = (
            KafkaError,
            ConnectionError,
            TimeoutError
        )
        
        if isinstance(error, retryable_errors):
            return True
        
        # Check error message for transient indicators
        error_str = str(error).lower()
        transient_indicators = [
            "timeout",
            "connection",
            "network",
            "temporary",
            "retry"
        ]
        
        return any(indicator in error_str for indicator in transient_indicators)
    
    def get_retry_delay(self, attempt: int) -> float:
        """
        Get delay before next retry (exponential backoff).
        
        Args:
            attempt: Current attempt number
            
        Returns:
            Delay in seconds
        """
        return self.retry_delay * (2 ** (attempt - 1))  # Exponential backoff


# Global instances
dead_letter_queue = DeadLetterQueue()
retry_handler = RetryHandler(max_retries=3, retry_delay=1.0)

