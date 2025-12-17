"""Service for calculating and maintaining device health metrics."""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import SessionLocal
from models import (
    Device, DeviceHealthMetrics, DeviceHealthHistory, TelemetryLatest, TelemetryTimeseries
)

logger = logging.getLogger(__name__)


class HealthMonitoringService:
    """Service that calculates device health metrics from telemetry data."""
    
    def __init__(self):
        """Initialize health monitoring service."""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def start(self):
        """Start the health monitoring service."""
        if self._running:
            logger.warning("Health monitoring service is already running")
            return
        
        self._running = True
        
        # Start background worker thread
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info("Health monitoring service started")
    
    def stop(self):
        """Stop the health monitoring service."""
        if not self._running:
            return
        
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("Health monitoring service stopped")
    
    def _worker_loop(self):
        """Background worker loop that calculates health metrics."""
        while self._running:
            try:
                self._calculate_all_device_health()
                time.sleep(300)  # Run every 5 minutes
            except Exception as e:
                logger.error(f"Error in health monitoring worker loop: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute on error
    
    def _calculate_all_device_health(self):
        """Calculate health metrics for all active devices."""
        db = SessionLocal()
        try:
            devices = db.query(Device).filter(Device.is_active == True).all()
            logger.debug(f"Calculating health metrics for {len(devices)} devices")
            
            for device in devices:
                try:
                    self._calculate_device_health(device.id, db)
                except Exception as e:
                    logger.error(f"Error calculating health for device {device.device_id}: {e}", exc_info=True)
            
            db.commit()
        except Exception as e:
            logger.error(f"Error in _calculate_all_device_health: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    def _calculate_device_health(self, device_id: int, db: Session):
        """Calculate health metrics for a single device."""
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            return
        
        # Get latest telemetry
        latest = db.query(TelemetryLatest).filter(TelemetryLatest.device_id == device_id).first()
        
        # Get or create health metrics record
        health = db.query(DeviceHealthMetrics).filter(DeviceHealthMetrics.device_id == device_id).first()
        if not health:
            health = DeviceHealthMetrics(device_id=device_id)
            db.add(health)
            db.flush()
        
        now = datetime.now(timezone.utc)
        
        # Update last_seen_at from latest telemetry
        if latest and latest.updated_at:
            health.last_seen_at = latest.updated_at
            if not health.first_seen_at:
                health.first_seen_at = latest.updated_at
        
        # Determine current status
        if health.last_seen_at:
            time_since_last_seen = (now - health.last_seen_at).total_seconds()
            if time_since_last_seen < 600:  # 10 minutes
                health.current_status = "online"
            elif time_since_last_seen < 3600:  # 1 hour
                health.current_status = "degraded"
            else:
                health.current_status = "offline"
        else:
            health.current_status = "unknown"
        
        # Calculate message counts and intervals
        self._calculate_connectivity_metrics(device_id, health, db, now)
        
        # Calculate battery metrics if available
        self._calculate_battery_metrics(device_id, health, db, latest)
        
        # Calculate uptime percentages
        self._calculate_uptime_percentages(device_id, health, db, now)
        
        # Update calculated timestamp
        health.calculated_at = now
        
        # Create history snapshot (once per hour)
        # Check if we need to create a new snapshot (last one was more than 1 hour ago)
        last_snapshot = db.query(func.max(DeviceHealthHistory.snapshot_at)).filter(
            DeviceHealthHistory.device_id == device_id
        ).scalar()
        
        if not last_snapshot or (now - last_snapshot).total_seconds() >= 3600:
            self._create_health_snapshot(device_id, health, db, now)
    
    def _calculate_connectivity_metrics(self, device_id: int, health: DeviceHealthMetrics, db: Session, now: datetime):
        """Calculate connectivity metrics from telemetry timeseries."""
        # Count messages in last 24h and 7d
        cutoff_24h = now - timedelta(hours=24)
        cutoff_7d = now - timedelta(days=7)
        
        count_24h = db.query(func.count(TelemetryTimeseries.id)).filter(
            TelemetryTimeseries.device_id == device_id,
            TelemetryTimeseries.ts >= cutoff_24h
        ).scalar() or 0
        
        count_7d = db.query(func.count(TelemetryTimeseries.id)).filter(
            TelemetryTimeseries.device_id == device_id,
            TelemetryTimeseries.ts >= cutoff_7d
        ).scalar() or 0
        
        health.message_count_24h = count_24h
        health.message_count_7d = count_7d
        
        # Calculate average message interval (last 24h)
        if count_24h > 1:
            first_ts = db.query(func.min(TelemetryTimeseries.ts)).filter(
                TelemetryTimeseries.device_id == device_id,
                TelemetryTimeseries.ts >= cutoff_24h
            ).scalar()
            last_ts = db.query(func.max(TelemetryTimeseries.ts)).filter(
                TelemetryTimeseries.device_id == device_id,
                TelemetryTimeseries.ts >= cutoff_24h
            ).scalar()
            
            if first_ts and last_ts:
                time_span = (last_ts - first_ts).total_seconds()
                if time_span > 0:
                    health.avg_message_interval_seconds = time_span / (count_24h - 1)
        
        # Calculate connectivity score (0-100)
        # Based on message regularity: more regular = higher score
        if health.avg_message_interval_seconds:
            # Ideal interval is 300 seconds (5 minutes)
            ideal_interval = 300
            deviation = abs(health.avg_message_interval_seconds - ideal_interval)
            # Score decreases with deviation, max 100 if perfect
            score = max(0, 100 - (deviation / ideal_interval * 50))
            health.connectivity_score = min(100, score)
        else:
            health.connectivity_score = 0 if count_24h == 0 else 50
    
    def _calculate_battery_metrics(self, device_id: int, health: DeviceHealthMetrics, db: Session, latest: TelemetryLatest):
        """Calculate battery metrics from telemetry."""
        if not latest or not latest.data:
            return
        
        # Try to find battery level in telemetry (common field names)
        battery_level = None
        data = latest.data
        
        # Check common battery field names
        for field_path in ["battery", "battery.soc", "batteryLevel", "battery_level", "deviceStatus.battery"]:
            parts = field_path.split(".")
            value = data
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                    if isinstance(value, (int, float)):
                        battery_level = float(value)
                        break
                else:
                    break
            if battery_level is not None:
                break
        
        if battery_level is not None:
            health.last_battery_level = battery_level
            
            # Calculate battery trend (compare with 1 hour ago)
            cutoff_1h = datetime.now(timezone.utc) - timedelta(hours=1)
            old_battery = db.query(func.avg(TelemetryTimeseries.value)).filter(
                TelemetryTimeseries.device_id == device_id,
                TelemetryTimeseries.key.like("%battery%"),
                TelemetryTimeseries.ts >= cutoff_1h - timedelta(minutes=30),
                TelemetryTimeseries.ts < cutoff_1h
            ).scalar()
            
            if old_battery:
                diff = battery_level - old_battery
                if diff > 2:
                    health.battery_trend = "increasing"
                elif diff < -2:
                    health.battery_trend = "decreasing"
                else:
                    health.battery_trend = "stable"
                
                # Estimate days remaining (simple linear extrapolation)
                if health.battery_trend == "decreasing" and diff < 0:
                    hours_per_percent = 1 / abs(diff) if diff != 0 else None
                    if hours_per_percent:
                        percent_remaining = battery_level
                        hours_remaining = hours_per_percent * percent_remaining
                        health.estimated_battery_days_remaining = int(hours_remaining / 24)
    
    def _calculate_uptime_percentages(self, device_id: int, health: DeviceHealthMetrics, db: Session, now: datetime):
        """Calculate uptime percentages for different time windows."""
        # For 24h, 7d, 30d windows, count how many health snapshots show "online"
        for window_hours, attr_name in [(24, "uptime_24h_percent"), (168, "uptime_7d_percent"), (720, "uptime_30d_percent")]:
            cutoff = now - timedelta(hours=window_hours)
            
            total_snapshots = db.query(func.count(DeviceHealthHistory.id)).filter(
                DeviceHealthHistory.device_id == device_id,
                DeviceHealthHistory.snapshot_at >= cutoff
            ).scalar() or 0
            
            online_snapshots = db.query(func.count(DeviceHealthHistory.id)).filter(
                DeviceHealthHistory.device_id == device_id,
                DeviceHealthHistory.snapshot_at >= cutoff,
                DeviceHealthHistory.status == "online"
            ).scalar() or 0
            
            if total_snapshots > 0:
                uptime_percent = (online_snapshots / total_snapshots) * 100
                setattr(health, attr_name, uptime_percent)
            else:
                # If no history, use current status
                if health.current_status == "online":
                    setattr(health, attr_name, 100.0)
                elif health.current_status == "degraded":
                    setattr(health, attr_name, 50.0)
                else:
                    setattr(health, attr_name, 0.0)
    
    def _create_health_snapshot(self, device_id: int, health: DeviceHealthMetrics, db: Session, now: datetime):
        """Create a historical snapshot of device health."""
        snapshot = DeviceHealthHistory(
            device_id=device_id,
            snapshot_at=now,
            status=health.current_status,
            battery_level=health.last_battery_level,
            message_count_1h=health.message_count_24h,  # Approximate
            avg_message_interval_seconds=health.avg_message_interval_seconds,
            uptime_24h_percent=health.uptime_24h_percent,
            connectivity_score=health.connectivity_score,
        )
        db.add(snapshot)
        
        # Clean up old snapshots (keep last 90 days)
        cutoff = now - timedelta(days=90)
        db.query(DeviceHealthHistory).filter(
            DeviceHealthHistory.device_id == device_id,
            DeviceHealthHistory.snapshot_at < cutoff
        ).delete()


# Global health monitoring service instance
health_monitoring_service = HealthMonitoringService()

