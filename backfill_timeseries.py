#!/usr/bin/env python3
"""
Backfill telemetry_timeseries table from devices_snapshot.

This script reads current telemetry from devices_snapshot and populates
the telemetry_timeseries table to enable historical trends without Kafka.
"""

import sys
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable

from database import SessionLocal
from models import Device, TelemetryTimeseries, DeviceSnapshot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def flatten_payload(payload: Dict[str, Any], prefix: str = "") -> Iterable[Dict[str, Any]]:
    """Flatten a telemetry payload into (key, value) pairs for time-series storage."""
    for key, value in payload.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, (int, float)):
            yield {"key": full_key, "value": float(value)}
        elif isinstance(value, dict):
            # Recurse into nested objects
            yield from flatten_payload(value, full_key)


def backfill_timeseries():
    """Backfill telemetry_timeseries from devices_snapshot."""
    db = SessionLocal()
    try:
        logger.info("Starting backfill of telemetry_timeseries...")
        
        # Get all devices with telemetry data
        snapshots = db.query(DeviceSnapshot).all()
        logger.info(f"Found {len(snapshots)} devices to process")
        
        total_inserted = 0
        devices_processed = 0
        
        for snapshot in snapshots:
            try:
                # Get device ID
                device = db.query(Device).filter(Device.device_id == snapshot.device_id).first()
                if not device:
                    logger.warning(f"Device not found for snapshot: {snapshot.device_id}")
                    continue
                
                payload = snapshot.payload or {}
                telemetry = payload.get("telemetry", {})
                data = telemetry.get("data", {})
                
                if not data:
                    continue
                
                # Get timestamp from telemetry or use current time
                timestamp_str = telemetry.get("timestamp")
                if timestamp_str:
                    try:
                        event_ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except:
                        event_ts = datetime.now(timezone.utc)
                else:
                    event_ts = datetime.now(timezone.utc)
                
                # Flatten and insert telemetry data
                for item in flatten_payload(data):
                    # Check if this exact record already exists
                    existing = db.query(TelemetryTimeseries).filter(
                        TelemetryTimeseries.device_id == device.id,
                        TelemetryTimeseries.key == item["key"],
                        TelemetryTimeseries.ts == event_ts
                    ).first()
                    
                    if not existing:
                        ts_row = TelemetryTimeseries(
                            device_id=device.id,
                            ts=event_ts,
                            key=item["key"],
                            value=item["value"],
                        )
                        db.add(ts_row)
                        total_inserted += 1
                
                devices_processed += 1
                
                # Commit every 100 devices
                if devices_processed % 100 == 0:
                    db.commit()
                    logger.info(f"Processed {devices_processed} devices, inserted {total_inserted} records")
            
            except Exception as e:
                logger.error(f"Error processing device {snapshot.device_id}: {e}")
                continue
        
        # Final commit
        db.commit()
        logger.info(f"✅ Backfill complete! Processed {devices_processed} devices, inserted {total_inserted} timeseries records")
        
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    backfill_timeseries()

