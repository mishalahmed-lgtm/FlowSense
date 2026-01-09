#!/usr/bin/env python3
"""Check if telemetry data was received in the database"""
import sys
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Device, TelemetryLatest, TelemetryTimeseries, DeviceHealthMetrics
from datetime import datetime, timezone, timedelta

DEVICE_ID = "0101BDDDEA5E4D03"

def check_telemetry_in_db():
    """Check if telemetry data exists in the database for the device"""
    db: Session = SessionLocal()
    try:
        print(f"\n{'='*60}")
        print(f"Checking database for device: {DEVICE_ID}")
        print(f"{'='*60}\n")
        
        # Check if device exists
        device = db.query(Device).filter(Device.device_id == DEVICE_ID).first()
        if not device:
            print(f"❌ Device '{DEVICE_ID}' NOT FOUND in database")
            print("   The device may not have been created yet.")
            return False
        
        print(f"✅ Device found:")
        print(f"   - ID: {device.id}")
        print(f"   - Name: {device.name}")
        print(f"   - Tenant ID: {device.tenant_id}")
        print(f"   - Active: {device.is_active}")
        print(f"   - Created: {device.created_at}")
        print()
        
        # Check latest telemetry
        latest = db.query(TelemetryLatest).filter(TelemetryLatest.device_id == device.id).first()
        if not latest:
            print(f"❌ No telemetry data found in 'telemetry_latest' table")
            return False
        
        print(f"✅ Latest telemetry found:")
        print(f"   - Event Timestamp: {latest.event_timestamp}")
        print(f"   - Updated At: {latest.updated_at}")
        print(f"   - Data: {latest.data}")
        print()
        
        # Check how recent the data is
        if latest.updated_at:
            time_diff = datetime.now(timezone.utc) - latest.updated_at
            minutes_ago = time_diff.total_seconds() / 60
            print(f"   - Data is {minutes_ago:.1f} minutes old")
            if minutes_ago < 5:
                print(f"   ✅ Data is recent (less than 5 minutes old)")
            else:
                print(f"   ⚠️  Data is older than 5 minutes")
        print()
        
        # Check timeseries data (last hour)
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        timeseries_count = db.query(TelemetryTimeseries).filter(
            TelemetryTimeseries.device_id == device.id,
            TelemetryTimeseries.ts >= one_hour_ago
        ).count()
        
        print(f"📊 Timeseries data (last hour):")
        print(f"   - Records: {timeseries_count}")
        if timeseries_count > 0:
            print(f"   ✅ Timeseries data exists")
        else:
            print(f"   ⚠️  No timeseries data in the last hour")
        print()
        
        # Check device health metrics
        health = db.query(DeviceHealthMetrics).filter(DeviceHealthMetrics.device_id == device.id).first()
        if health:
            print(f"🏥 Device Health Metrics:")
            print(f"   - Status: {health.current_status}")
            print(f"   - Last Seen: {health.last_seen_at}")
            print(f"   - First Seen: {health.first_seen_at}")
            if health.last_battery_level:
                print(f"   - Battery Level: {health.last_battery_level}%")
            print()
        
        # Summary
        print(f"{'='*60}")
        print("SUMMARY:")
        print(f"   ✅ Device exists: Yes")
        print(f"   ✅ Latest telemetry: Yes")
        print(f"   {'✅' if timeseries_count > 0 else '⚠️ '} Timeseries data: {timeseries_count} records")
        print(f"{'='*60}\n")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking database: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = check_telemetry_in_db()
    sys.exit(0 if success else 1)

