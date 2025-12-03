"""Telemetry ingestion endpoints."""
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from database import get_db
from models import Device
from auth import get_device_from_key
from kafka_producer import telemetry_producer
from rate_limiter import rate_limiter
from metrics import metrics
from validators import telemetry_validator
from error_handler import dead_letter_queue
from rule_engine import rule_engine

logger = logging.getLogger(__name__)

router = APIRouter()


class TelemetryPayload(BaseModel):
    """Telemetry payload model."""
    data: Dict[str, Any]
    timestamp: Optional[str] = None


@router.post("/http", status_code=status.HTTP_202_ACCEPTED)
async def ingest_telemetry_http(
    payload: TelemetryPayload,
    request: Request,
    device: Device = Depends(get_device_from_key),
    db: Session = Depends(get_db)
):
    """
    HTTP endpoint for ingesting telemetry data from devices.
    
    Supports devices using HTTP protocol (LPG Meter via NB-IoT, LoRaVan, LTEM, GPS).
    
    Expected header: X-Device-Key: <provisioning_key>
    """
    start_time = time.time()
    
    try:
        # Record message received
        logger.info(f"[HTTP] Processing telemetry from device: {device.device_id}")
        metrics.record_message_received(device.device_id, source="http")
        
        # Check rate limiting
        is_allowed, reason = rate_limiter.is_allowed(device.device_id)
        if not is_allowed:
            metrics.record_message_rejected(device.device_id, "rate_limit_exceeded")
            metrics.record_rate_limit_hit(device.device_id)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {reason}"
            )
        
        # Validate payload against device type schema
        device_type_name = device.device_type.name if device.device_type else None
        is_valid, validation_error = telemetry_validator.validate_payload(
            device_type_name, payload.data
        )
        
        if not is_valid:
            metrics.record_message_rejected(device.device_id, "validation_error")
            metrics.record_error(device.device_id, "validation_error")
            dead_letter_queue.publish_failed_message(
                device_id=device.device_id,
                payload=payload.data,
                metadata={
                    "source": "http",
                    "device_type": device_type_name,
                    "tenant_id": device.tenant_id
                },
                error_type="validation_error",
                error_message=validation_error or "Unknown validation error"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payload validation failed: {validation_error}"
            )
        
        # Prepare metadata
        metadata = {
            "timestamp": payload.timestamp or datetime.utcnow().isoformat(),
            "source": "http",
            "device_type": device.device_type.name if device.device_type else None,
            "tenant_id": device.tenant_id,
            "received_at": datetime.utcnow().isoformat(),
            "client_ip": request.client.host if request.client else None
        }
        
        rule_result = rule_engine.evaluate(
            device_id=device.device_id,
            payload=payload.data,
            metadata=metadata,
            source="http",
            device=device,
            db_session=db,
        )

        if rule_result.dropped:
            metrics.record_message_rejected(device.device_id, "rule_drop")
            return {
                "status": "dropped",
                "device_id": device.device_id,
                "message": rule_result.drop_reason or "Telemetry dropped by rule engine",
            }

        # Publish to Kafka
        logger.info(f"[HTTP] Publishing to Kafka for device: {device.device_id}, topic: {rule_result.target_topic}")
        success = telemetry_producer.publish_raw_telemetry(
            device_id=device.device_id,
            payload=rule_result.payload,
            metadata=rule_result.metadata,
            topic=rule_result.target_topic,
        )
        logger.info(f"[HTTP] Kafka publish result for {device.device_id}: {success}")
        
        # Record processing time
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        metrics.record_processing_time(processing_time)
        
        if not success:
            metrics.record_message_rejected(device.device_id, "kafka_publish_failed")
            metrics.record_error(device.device_id, "kafka_publish_failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to process telemetry data. Please retry."
            )
        
        metrics.record_message_published(device.device_id)
        
        return {
            "status": "accepted",
            "device_id": device.device_id,
            "message": "Telemetry data received and queued for processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        metrics.record_error(device.device_id, "internal_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for telemetry service."""
    return {
        "status": "healthy",
        "service": "telemetry-ingestion"
    }

