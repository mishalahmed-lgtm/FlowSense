"""FOTA (Firmware Over-The-Air) service for processing jobs and sending commands to devices."""
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session

from database import SessionLocal
from models import (
    FOTAJob, FOTAJobDevice, DeviceFirmwareStatus, FirmwareVersion,
    Device, FirmwareUpdateStatus, FOTAJobStatus
)
from config import settings

logger = logging.getLogger(__name__)


class FOTAService:
    """Service for processing FOTA jobs and sending firmware update commands to devices."""
    
    def __init__(self):
        """Initialize FOTA service."""
        self.mqtt_client: Optional[mqtt.Client] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def start(self):
        """Start the FOTA service."""
        if self._running:
            logger.warning("FOTA service is already running")
            return
        
        self._running = True
        
        # Initialize MQTT client for sending commands
        self.mqtt_client = mqtt.Client(client_id="iot-fota-service")
        if settings.mqtt_broker_username and settings.mqtt_broker_password:
            self.mqtt_client.username_pw_set(
                settings.mqtt_broker_username,
                settings.mqtt_broker_password
            )
        
        try:
            self.mqtt_client.connect(
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
                keepalive=60
            )
            self.mqtt_client.loop_start()
            logger.info("FOTA service MQTT client connected")
        except Exception as e:
            logger.error(f"Failed to connect FOTA MQTT client: {e}")
            self._running = False
            return
        
        # Start background worker thread
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info("FOTA service started")
    
    def stop(self):
        """Stop the FOTA service."""
        if not self._running:
            return
        
        self._running = False
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            logger.info("FOTA service MQTT client disconnected")
        
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("FOTA service stopped")
    
    def _worker_loop(self):
        """Background worker loop that processes FOTA jobs."""
        while self._running:
            try:
                self._process_pending_jobs()
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Error in FOTA worker loop: {e}", exc_info=True)
                time.sleep(30)  # Wait longer on error
    
    def _process_pending_jobs(self):
        """Process pending and scheduled FOTA jobs."""
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            
            # Find jobs that need processing
            # 1. Scheduled jobs that are ready to start
            scheduled_jobs = db.query(FOTAJob).filter(
                FOTAJob.status == FOTAJobStatus.SCHEDULED,
                FOTAJob.scheduled_at <= now
            ).all()
            
            for job in scheduled_jobs:
                job.status = FOTAJobStatus.RUNNING
                job.started_at = now
                db.commit()
                logger.info(f"Started scheduled FOTA job: {job.id} - {job.name}")
            
            # 2. Running jobs with pending devices
            running_jobs = db.query(FOTAJob).filter(
                FOTAJob.status == FOTAJobStatus.RUNNING
            ).all()
            
            for job in running_jobs:
                self._process_job(job, db)
            
            db.commit()
        except Exception as e:
            logger.error(f"Error processing FOTA jobs: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    def _process_job(self, job: FOTAJob, db: Session):
        """Process a single FOTA job - send commands to pending devices."""
        # Get firmware version
        firmware_version = db.query(FirmwareVersion).filter(
            FirmwareVersion.id == job.firmware_version_id
        ).first()
        
        if not firmware_version:
            logger.error(f"Firmware version {job.firmware_version_id} not found for job {job.id}")
            return
        
        # Get pending devices for this job
        pending_devices = db.query(FOTAJobDevice).filter(
            FOTAJobDevice.job_id == job.id,
            FOTAJobDevice.status == FirmwareUpdateStatus.PENDING
        ).all()
        
        if not pending_devices:
            # Check if job is complete
            all_devices = db.query(FOTAJobDevice).filter(
                FOTAJobDevice.job_id == job.id
            ).all()
            
            success_count = sum(1 for d in all_devices if d.status == FirmwareUpdateStatus.SUCCESS)
            failed_count = sum(1 for d in all_devices if d.status == FirmwareUpdateStatus.FAILED)
            
            if success_count + failed_count == len(all_devices):
                # All devices are done
                job.status = FOTAJobStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"FOTA job {job.id} completed: {success_count} success, {failed_count} failed")
            return
        
        # Send commands to pending devices
        for job_device in pending_devices:
            device = db.query(Device).filter(Device.id == job_device.device_id).first()
            if not device:
                continue
            
            # Build firmware download URL
            # In production, this would be a public URL (S3, CDN, etc.)
            # For now, we'll use a placeholder that the device agent should handle
            firmware_url = f"http://{settings.mqtt_broker_host}:5000/api/v1/fota/firmwares/{firmware_version.firmware_id}/versions/{firmware_version.id}/download"
            
            # Build MQTT command payload
            command_payload = {
                "action": "update_firmware",
                "version": firmware_version.version,
                "url": firmware_url,
                "checksum": firmware_version.checksum,
                "file_size": firmware_version.file_size_bytes,
                "force": firmware_version.is_mandatory,
                "job_id": job.id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Publish command to device
            topic = f"devices/{device.device_id}/fota/command"
            try:
                if self.mqtt_client and self.mqtt_client.is_connected():
                    import json
                    result = self.mqtt_client.publish(
                        topic,
                        json.dumps(command_payload),
                        qos=1
                    )
                    
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        # Update device status to DOWNLOADING
                        job_device.status = FirmwareUpdateStatus.DOWNLOADING
                        job_device.last_update_at = datetime.now(timezone.utc)
                        
                        # Update DeviceFirmwareStatus
                        dfs = db.query(DeviceFirmwareStatus).filter(
                            DeviceFirmwareStatus.device_id == device.id
                        ).first()
                        if dfs:
                            dfs.status = FirmwareUpdateStatus.DOWNLOADING
                            dfs.last_update_at = datetime.now(timezone.utc)
                        
                        db.commit()
                        logger.info(f"Sent FOTA command to device {device.device_id} (job {job.id})")
                    else:
                        logger.error(f"Failed to publish FOTA command to {device.device_id}: MQTT error {result.rc}")
                        job_device.status = FirmwareUpdateStatus.FAILED
                        job_device.last_error = f"MQTT publish failed: {result.rc}"
                        job_device.last_update_at = datetime.now(timezone.utc)
                        db.commit()
                else:
                    logger.warning("MQTT client not connected, cannot send FOTA command")
            except Exception as e:
                logger.error(f"Error sending FOTA command to {device.device_id}: {e}", exc_info=True)
                job_device.status = FirmwareUpdateStatus.FAILED
                job_device.last_error = str(e)
                job_device.last_update_at = datetime.now(timezone.utc)
                db.commit()


# Global FOTA service instance
fota_service = FOTAService()

