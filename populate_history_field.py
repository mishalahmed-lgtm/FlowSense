#!/usr/bin/env python3
"""
Populate devices_snapshot.payload.history from telemetry_timeseries.

For tenant admin users, the history API reads from payload.history field.
This script aggregates telemetry_timeseries data and stores it in the payload.
"""

import sys
import logging
import json
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import text
from database import SessionLocal
from models import DeviceSnapshot, TelemetryTimeseries, Device

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def populate_history():
    """Populate payload.history from telemetry_timeseries."""
    db = SessionLocal()
    try:
        logger.info("Populating devices_snapshot.payload.history from telemetry_timeseries...")
        
        # Get all devices with timeseries data
        snapshots = db.query(DeviceSnapshot).all()
        logger.info(f"Found {len(snapshots)} device snapshots")
        
        devices_updated = 0
        
        for snapshot in snapshots:
            try:
                # Get device
                device = db.query(Device).filter(Device.device_id == snapshot.device_id).first()
                if not device:
                    continue
                
                # Get all timeseries data for this device (last 1000 points)
                timeseries_data = db.query(TelemetryTimeseries).filter(
                    TelemetryTimeseries.device_id == device.id
                ).order_by(TelemetryTimeseries.ts.desc()).limit(1000).all()
                
                if not timeseries_data:
                    continue
                
                # Group by key
                history_by_key = defaultdict(list)
                for ts_row in timeseries_data:
                    history_by_key[ts_row.key].append({
                        "timestamp": ts_row.ts.isoformat(),
                        "value": ts_row.value
                    })
                
                # Sort each key's history by timestamp (oldest first)
                for key in history_by_key:
                    history_by_key[key] = sorted(
                        history_by_key[key], 
                        key=lambda x: x["timestamp"]
                    )
                
                # Update payload
                payload = snapshot.payload or {}
                payload["history"] = dict(history_by_key)
                
                # Update snapshot using raw SQL (JSON type compatibility)
                db.execute(
                    text("UPDATE devices_snapshot SET payload = :payload WHERE device_id = :device_id"),
                    {"payload": json.dumps(payload), "device_id": snapshot.device_id}
                )
                
                devices_updated += 1
                
                if devices_updated % 100 == 0:
                    db.commit()
                    logger.info(f"Updated {devices_updated} devices...")
            
            except Exception as e:
                logger.error(f"Error processing device {snapshot.device_id}: {e}")
                continue
        
        db.commit()
        logger.info(f"✅ Complete! Updated history for {devices_updated} devices")
        
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    populate_history()

