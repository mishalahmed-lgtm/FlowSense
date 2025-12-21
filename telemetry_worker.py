"""Background worker service that consumes telemetry from Kafka and persists it for dashboards.

This keeps ingestion (HTTP/MQTT/TCP) as a separate microservice and lets us
scale/read dashboards independently, following IoT best practices.
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
from typing import Any, Dict, Iterable

logger = logging.getLogger("telemetry_worker")
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)


KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
RAW_TELEMETRY_TOPIC = os.environ.get("KAFKA_RAW_TELEMETRY_TOPIC", "raw_telemetry")

SHUTDOWN = threading.Event()


from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from database import SessionLocal
from models import Device, TelemetryLatest, TelemetryTimeseries
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


def process_message(device_id: str, payload: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    """Persist latest and time-series telemetry for a single message."""
    event_ts = _parse_event_timestamp(metadata or {})
    
    # Record metrics (if available)
    try:
        from metrics import metrics
        source = metadata.get("source", "kafka") if metadata else "kafka"
        metrics.record_message_received(device_id, source=source)
    except Exception as e:
        logger.debug(f"Could not record metrics (non-critical): {e}")
    
    device_db_id = None
    tenant_db_id = None
    
    with db_session_scope() as db:
        device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
        if not device:
            logger.warning("Received telemetry for unknown device_id=%s", device_id)
            return
        
        # Store device info for alert processing
        device_db_id = device.id
        tenant_db_id = device.tenant_id
        
        # Upsert latest record
        latest = (
            db.query(TelemetryLatest)
            .filter(TelemetryLatest.device_id == device.id)
            .one_or_none()
        )
        if latest is None:
            latest = TelemetryLatest(
                device_id=device.id,
                data=payload,
                event_timestamp=event_ts,
            )
            db.add(latest)
        else:
            latest.data = payload
            latest.event_timestamp = event_ts
            # Explicitly update updated_at to ensure it's refreshed
            from datetime import datetime, timezone
            latest.updated_at = datetime.now(timezone.utc)
        
        # Append time-series points for numeric fields
        for item in _flatten_payload(payload):
            ts_row = TelemetryTimeseries(
                device_id=device.id,
                ts=event_ts,
                key=item["key"],
                value=item["value"],
            )
            db.add(ts_row)

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
    """Main loop: consume from Kafka and persist telemetry."""
    logger.info(
        "Starting telemetry worker: bootstrap=%s, topic=%s",
        KAFKA_BOOTSTRAP_SERVERS,
        RAW_TELEMETRY_TOPIC,
    )

    try:
        consumer = KafkaConsumer(
            RAW_TELEMETRY_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            enable_auto_commit=True,
            auto_offset_reset="latest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
    except NoBrokersAvailable as exc:
        logger.error("Kafka brokers not available: %s", exc)
        sys.exit(1)

    try:
        while not SHUTDOWN.is_set():
            records = consumer.poll(timeout_ms=1000)
            for partition_records in records.values():
                for msg in partition_records:
                    value = msg.value or {}
                    device_id = value.get("device_id")
                    payload = value.get("payload") or {}
                    metadata = value.get("metadata") or {}

                    if not device_id:
                        logger.warning("Skipping message without device_id: %s", value)
                        continue

                    try:
                        process_message(device_id, payload, metadata)
                    except Exception as exc:
                        logger.exception(
                            "Failed to persist telemetry for device_id=%s: %s",
                            device_id,
                            exc,
                        )
            # Avoid busy loop
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down worker.")
    finally:
        SHUTDOWN.set()
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


