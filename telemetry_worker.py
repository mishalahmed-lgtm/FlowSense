"""Background worker service that consumes telemetry from Kafka and persists it for dashboards.

This keeps ingestion (HTTP/MQTT/TCP) as a separate microservice and lets us
scale/read dashboards independently, following IoT best practices.

OPTIMIZED FOR RENDER FREE TIER:
- Batch processing: ~200 messages per transaction
- Connection reuse: Single long-lived DB connection
- Memory efficient: Process in chunks, not all at once
"""

import json
import logging
import os
import signal
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

logger = logging.getLogger("telemetry_worker")
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)


KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
RAW_TELEMETRY_TOPIC = os.environ.get("KAFKA_RAW_TELEMETRY_TOPIC", "raw_telemetry")
BATCH_SIZE = int(os.environ.get("TELEMETRY_BATCH_SIZE", "200"))  # Process 200 messages per batch
BATCH_TIMEOUT_SECONDS = float(os.environ.get("TELEMETRY_BATCH_TIMEOUT", "2.0"))  # Or flush after 2 seconds

SHUTDOWN = threading.Event()


from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from database import SessionLocal
from models import Device, TelemetryLatest, TelemetryTimeseries, DeviceHealthMetrics
from alert_engine import alert_engine
from cep_engine import cep_engine
from influx_client import influx_service

# Import WebSocket broadcaster (with try/except to avoid circular imports)
try:
    from routers.websocket import broadcast_telemetry_update
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logger.warning("WebSocket broadcasting not available")


@contextmanager
def db_session_scope():
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _flatten_payload(payload: Dict[str, Any], prefix: str = "") -> Iterable[Dict[str, Any]]:
    """Flatten a telemetry payload into (key, value) pairs for time-series storage.

    Recursively walks the payload and emits numeric fields (ints/floats) using
    dotted-notation keys for nested structures, e.g.:
      {"battery": {"soc": 83}} -> key="battery.soc"
    """
    for key, value in payload.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, (int, float)):
            yield {"key": full_key, "value": float(value)}
        elif isinstance(value, dict):
            # Recurse into nested objects
            yield from _flatten_payload(value, full_key)


def _parse_event_timestamp(metadata: Dict[str, Any]) -> datetime:
    ts = metadata.get("timestamp") or metadata.get("received_at")
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        try:
            # Attempt to parse ISO 8601
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            pass
    return datetime.now(timezone.utc)


def process_message_batch(messages: List[Dict[str, Any]]) -> None:
    """Process a batch of telemetry messages in a single database transaction.
    
    This is CRITICAL for Render free tier performance:
    - Processes 200+ messages in one transaction
    - Reuses a single database connection
    - Reduces connection overhead from 2000+ to ~10 per batch cycle
    
    Args:
        messages: List of dicts with keys: device_id, payload, metadata
    """
    if not messages:
        return
    
    logger.info(f"Processing batch of {len(messages)} telemetry messages...")
    start_time = time.time()
    
    with db_session_scope() as db:
        # Step 1: Fetch all devices in batch (single query)
        device_ids = list({msg["device_id"] for msg in messages})
        devices = db.query(Device).filter(Device.device_id.in_(device_ids)).all()
        device_map = {d.device_id: d for d in devices}
        
        # Track unknown devices
        unknown_devices = [msg["device_id"] for msg in messages if msg["device_id"] not in device_map]
        if unknown_devices:
            logger.warning(f"Skipping {len(unknown_devices)} messages for unknown devices: {unknown_devices[:10]}")
        
        # Step 2: Fetch all existing telemetry_latest records (single query)
        device_db_ids = [d.id for d in devices]
        existing_latest = db.query(TelemetryLatest).filter(
            TelemetryLatest.device_id.in_(device_db_ids)
        ).all()
        latest_map = {tl.device_id: tl for tl in existing_latest}
        
        # Step 3: Fetch all existing health records (single query)
        existing_health = db.query(DeviceHealthMetrics).filter(
            DeviceHealthMetrics.device_id.in_(device_db_ids)
        ).all()
        health_map = {h.device_id: h for h in existing_health}
        
        # Step 4: Process each message and prepare bulk inserts
        telemetry_latest_to_add = []
        telemetry_timeseries_to_add = []
        health_to_add = []
        now = datetime.now(timezone.utc)
        
        for msg in messages:
            device_id_str = msg["device_id"]
            payload = msg["payload"]
            metadata = msg["metadata"]
            
            # Skip unknown devices
            if device_id_str not in device_map:
                continue
            
            device = device_map[device_id_str]
            event_ts = _parse_event_timestamp(metadata or {})
            
            # Record metrics (non-blocking)
            try:
                from metrics import metrics
                source = metadata.get("source", "kafka") if metadata else "kafka"
                metrics.record_message_received(device_id_str, source=source)
            except Exception as e:
                logger.debug(f"Could not record metrics (non-critical): {e}")
            
            # Upsert telemetry_latest (in-memory)
            if device.id in latest_map:
                latest = latest_map[device.id]
                latest.data = payload
                latest.event_timestamp = event_ts
                latest.updated_at = now
            else:
                latest = TelemetryLatest(
                    device_id=device.id,
                    data=payload,
                    event_timestamp=event_ts,
                    updated_at=now
                )
                telemetry_latest_to_add.append(latest)
                latest_map[device.id] = latest
            
            # Upsert device health (in-memory)
            if device.id in health_map:
                health = health_map[device.id]
            else:
                health = DeviceHealthMetrics(device_id=device.id)
                health_to_add.append(health)
                health_map[device.id] = health
            
            health.last_seen_at = now
            health.current_status = "online"
            health.calculated_at = now
            if not health.first_seen_at:
                health.first_seen_at = now
            
            # Prepare time-series inserts (bulk)
            for item in _flatten_payload(payload):
                ts_row = TelemetryTimeseries(
                    device_id=device.id,
                    ts=event_ts,
                    key=item["key"],
                    value=item["value"],
                )
                telemetry_timeseries_to_add.append(ts_row)
        
        # Step 5: Bulk insert new records
        if telemetry_latest_to_add:
            db.bulk_save_objects(telemetry_latest_to_add)
            logger.debug(f"Inserted {len(telemetry_latest_to_add)} new telemetry_latest records")
        
        if health_to_add:
            db.bulk_save_objects(health_to_add)
            logger.debug(f"Inserted {len(health_to_add)} new health records")
        
        if telemetry_timeseries_to_add:
            db.bulk_save_objects(telemetry_timeseries_to_add)
            logger.debug(f"Inserted {len(telemetry_timeseries_to_add)} timeseries points")
        
        # Commit happens in db_session_scope context manager
    
    duration = time.time() - start_time
    logger.info(f"✓ Batch of {len(messages)} messages processed in {duration:.2f}s ({len(messages)/duration:.1f} msg/s)")
    
    # Step 6: Post-processing (outside DB transaction) - Process alerts and InfluxDB asynchronously
    # This prevents blocking the main DB transaction
    for msg in messages:
        device_id_str = msg["device_id"]
        if device_id_str not in device_map:
            continue
        
        device = device_map[device_id_str]
        payload = msg["payload"]
        metadata = msg["metadata"]
        event_ts = _parse_event_timestamp(metadata or {})
        
        # Write to InfluxDB (non-blocking, best-effort)
        try:
            if influx_service.enabled:
                influx_service.write_telemetry(
                    device_id=device_id_str,
                    tenant_id=device.tenant_id,
                    payload=payload,
                    event_ts=event_ts,
                )
        except Exception as exc:
            logger.debug(f"Failed to write to InfluxDB for {device_id_str}: {exc}")
        
        # Process alert rules (best-effort)
        try:
            alert_engine.process_telemetry(
                device_id=device.id,
                tenant_id=device.tenant_id,
                payload=payload,
                metadata=metadata
            )
        except Exception as e:
            logger.debug(f"Error processing alerts for {device_id_str}: {e}")
        
        # CEP engine (best-effort)
        try:
            cep_engine.process_event(device_id_str, payload, metadata)
        except Exception as e:
            logger.debug(f"Error processing CEP for {device_id_str}: {e}")
        
        # WebSocket broadcast (best-effort)
        if WEBSOCKET_AVAILABLE:
            try:
                from database import SessionLocal as WS_DB
                ws_db = WS_DB()
                try:
                    broadcast_telemetry_update(
                        device_id=device_id_str,
                        data=payload,
                        timestamp=event_ts.isoformat() if event_ts else None,
                        db=ws_db,
                        tenant_id=device.tenant_id  # Pass tenant_id for dashboard subscriptions
                    )
                finally:
                    ws_db.close()
            except Exception as e:
                logger.debug(f"WebSocket broadcast error: {e}")
        
        # Record published metrics
        try:
            from metrics import metrics
            metrics.record_message_published(device_id_str)
        except Exception as e:
            logger.debug(f"Could not record published metrics: {e}")


def process_message(device_id: str, payload: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    """DEPRECATED: Use process_message_batch() instead for better performance.
    
    This function is kept for backward compatibility but should not be used in production.
    """
    logger.warning("process_message() called - use process_message_batch() instead for better performance")
    process_message_batch([{"device_id": device_id, "payload": payload, "metadata": metadata}])

    # Write numeric telemetry to InfluxDB time-series store (if enabled)
    try:
        if influx_service.enabled and device_db_id and tenant_db_id:
            influx_service.write_telemetry(
                device_id=device_id,
                tenant_id=tenant_db_id,
                payload=payload,
                event_ts=event_ts,
            )
    except Exception as exc:
        logger.warning(
            "Failed to write telemetry to InfluxDB for device_id=%s: %s",
            device_id,
            exc,
        )

    # Process alert rules (after committing telemetry, outside db session)
    if device_db_id and tenant_db_id:
        try:
            alert_engine.process_telemetry(
                device_id=device_db_id,
                tenant_id=tenant_db_id,
                payload=payload,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Error processing alerts for device {device_id}: {e}", exc_info=True)
    
    # Feed event to CEP engine for complex event processing
    try:
        cep_engine.process_event(device_id, payload, metadata)
    except Exception as e:
        logger.error(f"Error processing CEP event for device {device_id}: {e}", exc_info=True)
    
    # Broadcast to WebSocket clients (if available)
    if WEBSOCKET_AVAILABLE:
        try:
            from database import SessionLocal as WS_DB
            ws_db = WS_DB()
            try:
                broadcast_telemetry_update(
                    device_id=device_id,
                    data=payload,
                    timestamp=event_ts.isoformat() if event_ts else None,
                    db=ws_db
                )
            finally:
                ws_db.close()
        except Exception as e:
            logger.debug(f"WebSocket broadcast error (non-critical): {e}")
    
    # Record message as published/processed
    try:
        from metrics import metrics
        metrics.record_message_published(device_id)
    except Exception as e:
        logger.debug(f"Could not record published metrics (non-critical): {e}")


def run_worker() -> None:
    """Main loop: consume from Kafka and persist telemetry in batches.
    
    OPTIMIZED FOR RENDER FREE TIER:
    - Accumulates messages into batches of ~200
    - Processes each batch in a single DB transaction
    - Flushes batch after 2 seconds even if not full
    - Reuses single DB connection across all batches
    """
    logger.info(
        "Starting telemetry worker (BATCHED MODE): bootstrap=%s, topic=%s, batch_size=%d",
        KAFKA_BOOTSTRAP_SERVERS,
        RAW_TELEMETRY_TOPIC,
        BATCH_SIZE,
    )

    try:
        consumer = KafkaConsumer(
            RAW_TELEMETRY_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            enable_auto_commit=True,
            auto_offset_reset="latest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            max_poll_records=500,  # Fetch up to 500 messages per poll (for batching)
        )
    except NoBrokersAvailable as exc:
        logger.error("Kafka brokers not available: %s", exc)
        sys.exit(1)

    try:
        message_batch = []
        last_flush_time = time.time()
        
        while not SHUTDOWN.is_set():
            records = consumer.poll(timeout_ms=1000)
            
            # Accumulate messages into batch
            for partition_records in records.values():
                for msg in partition_records:
                    value = msg.value or {}
                    device_id = value.get("device_id")
                    payload = value.get("payload") or {}
                    metadata = value.get("metadata") or {}

                    if not device_id:
                        logger.warning("Skipping message without device_id: %s", value)
                        continue

                    message_batch.append({
                        "device_id": device_id,
                        "payload": payload,
                        "metadata": metadata
                    })
            
            # Flush batch if:
            # 1. Batch size reached, OR
            # 2. Timeout elapsed (don't wait forever for a full batch), OR
            # 3. Shutdown requested
            current_time = time.time()
            time_since_flush = current_time - last_flush_time
            should_flush = (
                len(message_batch) >= BATCH_SIZE or
                (len(message_batch) > 0 and time_since_flush >= BATCH_TIMEOUT_SECONDS) or
                (SHUTDOWN.is_set() and len(message_batch) > 0)
            )
            
            if should_flush:
                try:
                    process_message_batch(message_batch)
                    message_batch = []  # Clear batch
                    last_flush_time = time.time()
                except Exception as exc:
                    logger.exception(f"Failed to process batch of {len(message_batch)} messages: {exc}")
                    # Clear batch to avoid reprocessing same failed messages indefinitely
                    message_batch = []
                    last_flush_time = time.time()
            
            # Small sleep to avoid busy loop when no messages
            if not records:
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down worker.")
    finally:
        SHUTDOWN.set()
        
        # Flush any remaining messages
        if message_batch:
            try:
                logger.info(f"Flushing final batch of {len(message_batch)} messages...")
                process_message_batch(message_batch)
            except Exception as exc:
                logger.error(f"Failed to flush final batch: {exc}")
        
        try:
            consumer.close()
        except Exception:
            pass
        logger.info("Telemetry worker stopped.")


def _handle_signal(signum, frame):
    logger.info("Received signal %s, shutting down telemetry worker.", signum)
    SHUTDOWN.set()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    run_worker()


