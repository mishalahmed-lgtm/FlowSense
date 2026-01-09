#!/usr/bin/env python3
"""Check how many devices have health data"""
from sqlalchemy.orm import Session
from database import SessionLocal
from models import DeviceHealthMetrics, Device

def check_health_devices():
    """Count devices with health data"""
    db: Session = SessionLocal()
    
    try:
        print(f"\n{'='*70}")
        print("DEVICE HEALTH DATA CHECK")
        print(f"{'='*70}\n")
        
        # Count total devices
        total_devices = db.query(Device).count()
        print(f"Total devices in system: {total_devices}")
        
        # Count devices with health metrics
        devices_with_health = db.query(DeviceHealthMetrics).count()
        print(f"Devices with health metrics: {devices_with_health}")
        
        # Count devices with recent health data (last seen in last 24 hours)
        from datetime import datetime, timezone, timedelta
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        
        recent_health = db.query(DeviceHealthMetrics).filter(
            DeviceHealthMetrics.last_seen_at >= yesterday
        ).count()
        
        print(f"Devices with health data in last 24h: {recent_health}")
        
        # Count online devices
        online_devices = db.query(DeviceHealthMetrics).filter(
            DeviceHealthMetrics.current_status == "online"
        ).count()
        
        print(f"Devices currently online: {online_devices}")
        
        # Count offline devices
        offline_devices = db.query(DeviceHealthMetrics).filter(
            DeviceHealthMetrics.current_status == "offline"
        ).count()
        
        print(f"Devices currently offline: {offline_devices}")
        
        # Get breakdown by status
        print(f"\n{'='*70}")
        print("BREAKDOWN BY STATUS")
        print(f"{'='*70}")
        
        statuses = db.query(DeviceHealthMetrics.current_status).distinct().all()
        for status_tuple in statuses:
            status = status_tuple[0] if status_tuple[0] else "unknown"
            count = db.query(DeviceHealthMetrics).filter(
                DeviceHealthMetrics.current_status == status_tuple[0]
            ).count()
            print(f"  {status}: {count}")
        
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"✅ Devices with health data: {devices_with_health}")
        print(f"   These will appear on the health page")
        print(f"   Online: {online_devices}, Offline: {offline_devices}")
        print(f"{'='*70}\n")
        
        return devices_with_health
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 0
    finally:
        db.close()

if __name__ == "__main__":
    check_health_devices()

