"""Telemetry ingestion endpoints."""
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Dict, Any, Optional, Iterable
from datetime import datetime, timezone
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
from lorawan_handler import lorawan_handler

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
    Optional header: X-Access-Token: <access_token> (if device has access token configured)
    """
    start_time = time.time()
    
    try:
        # Verify access token (required)
        access_token = request.headers.get("X-Access-Token")
        from auth import verify_device_access_token
        if not verify_device_access_token(device, access_token):
            metrics.record_message_rejected(device.device_id, "invalid_access_token")
            metrics.record_auth_failure(device.device_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing access token. Provide X-Access-Token header."
            )
        
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
            # Fallback: Write directly to DB when Kafka fails (for Render deployment without Kafka)
            logger.warning(f"[HTTP] Kafka publish failed for {device.device_id}, using direct DB fallback")
            metrics.record_message_rejected(device.device_id, "kafka_publish_failed")
            
            try:
                from models import TelemetryLatest, DeviceHealthMetrics, TelemetryTimeseries
                from sqlalchemy import text
                
                event_ts = datetime.fromisoformat(metadata.get("timestamp", datetime.utcnow().isoformat()).replace('Z', '+00:00'))
                
                # Update telemetry_latest
                latest = db.query(TelemetryLatest).filter(TelemetryLatest.device_id == device.id).first()
                if latest:
                    latest.data = rule_result.payload
                    latest.event_timestamp = event_ts
                    latest.updated_at = datetime.now(timezone.utc)
                else:
                    latest = TelemetryLatest(
                        device_id=device.id,
                        data=rule_result.payload,
                        event_timestamp=event_ts,
                    )
                    db.add(latest)
                
                # Update health
                health = db.query(DeviceHealthMetrics).filter(DeviceHealthMetrics.device_id == device.id).first()
                if not health:
                    health = DeviceHealthMetrics(device_id=device.id)
                    db.add(health)
                
                now = datetime.now(timezone.utc)
                health.last_seen_at = now
                health.current_status = "online"
                health.calculated_at = now
                if not health.first_seen_at:
                    health.first_seen_at = now
                
                # Write to telemetry_timeseries for historical trends
                def _flatten_payload(payload_dict: Dict[str, Any], prefix: str = "") -> Iterable[Dict[str, Any]]:
                    """Flatten a telemetry payload into (key, value) pairs for time-series storage."""
                    for key, value in payload_dict.items():
                        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
                        if isinstance(value, (int, float)):
                            yield {"key": full_key, "value": float(value)}
                        elif isinstance(value, dict):
                            yield from _flatten_payload(value, full_key)
                
                for item in _flatten_payload(rule_result.payload):
                    ts_row = TelemetryTimeseries(
                        device_id=device.id,
                        ts=event_ts,
                        key=item["key"],
                        value=item["value"],
                    )
                    db.add(ts_row)
                
                db.commit()
                logger.info(f"[HTTP] ✓ Fallback: Direct DB write completed for device: {device.device_id}")
                
                return {
                    "status": "accepted",
                    "device_id": device.device_id,
                    "message": "Telemetry data received and stored (Kafka unavailable, using direct DB)"
                }
            except Exception as fallback_error:
                logger.error(f"[HTTP] ✗ Fallback DB write failed: {fallback_error}", exc_info=True)
                metrics.record_error(device.device_id, "fallback_db_failed")
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


@router.post("/lorawan/{device_id}", status_code=status.HTTP_202_ACCEPTED)
async def ingest_telemetry_lorawan(
    device_id: str,
    webhook_payload: Dict[str, Any],
    request: Request
):
    """
    LoRaWAN webhook endpoint for ingesting telemetry from LoRaWAN network servers.
    
    Supports webhooks from:
    - The Things Network (TTN)
    - ChirpStack
    - Other LoRaWAN network servers
    
    The webhook payload format varies by network server, but this handler
    supports common formats.
    """
    try:
        result = lorawan_handler.process_webhook(webhook_payload, device_id)
        
        if result["status"] == "accepted":
            return {
                "status": "accepted",
                "device_id": device_id,
                "message": "LoRaWAN telemetry processed"
            }
        elif result["status"] == "dropped":
            return {
                "status": "dropped",
                "device_id": device_id,
                "message": result.get("message", "Telemetry dropped")
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Failed to process LoRaWAN webhook")
            )
    except Exception as e:
        logger.error(f"Error processing LoRaWAN webhook: {e}", exc_info=True)
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

