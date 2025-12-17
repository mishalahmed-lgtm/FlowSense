"""Scheduler service for cron-based device rules."""
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from croniter import croniter

from database import SessionLocal
from sqlalchemy.orm import Session
from models import Device, DeviceRule
from rule_engine import rule_engine

logger = logging.getLogger(__name__)


class RuleScheduler:
    """Scheduler for executing cron-based device rules."""
    
    def __init__(self):
        """Initialize rule scheduler."""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def start(self):
        """Start the scheduler worker."""
        if self._running:
            logger.warning("Rule scheduler is already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info("Rule scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        if not self._running:
            return
        
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Rule scheduler stopped")
    
    def _worker_loop(self):
        """Background worker that checks and executes scheduled rules."""
        while self._running:
            try:
                self._check_and_execute_scheduled_rules()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in rule scheduler worker loop: {e}", exc_info=True)
                time.sleep(60)
    
    def _check_and_execute_scheduled_rules(self):
        """Check for scheduled rules that need to be executed."""
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            
            # Get all active scheduled rules
            scheduled_rules = db.query(DeviceRule).filter(
                DeviceRule.rule_type == "scheduled",
                DeviceRule.is_active == True,
                DeviceRule.cron_schedule.isnot(None)
            ).all()
            
            for rule in scheduled_rules:
                try:
                    # Check if rule should run now
                    should_run = False
                    
                    if rule.next_run_at and rule.next_run_at <= now:
                        should_run = True
                    elif not rule.next_run_at:
                        # First run - calculate next run time
                        should_run = True
                    
                    if should_run:
                        self._execute_scheduled_rule(rule, db, now)
                        
                        # Calculate next run time
                        cron = croniter(rule.cron_schedule, now)
                        next_run = cron.get_next(datetime)
                        rule.next_run_at = next_run.replace(tzinfo=timezone.utc)
                        rule.last_run_at = now
                        db.commit()
                        
                except Exception as e:
                    logger.error(f"Error executing scheduled rule {rule.id}: {e}", exc_info=True)
                    db.rollback()
        
        except Exception as e:
            logger.error(f"Error in _check_and_execute_scheduled_rules: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    def _execute_scheduled_rule(self, rule: DeviceRule, db: Session, now: datetime):
        """Execute a scheduled rule."""
        device = db.query(Device).filter(Device.id == rule.device_id).first()
        if not device:
            logger.warning(f"Scheduled rule {rule.id} references non-existent device")
            return
        
        logger.info(f"Executing scheduled rule '{rule.name}' for device {device.device_id}")
        
        # Create a synthetic payload/context for scheduled rule execution
        # Scheduled rules typically don't have incoming telemetry, so we use device state
        payload = {}
        metadata = {
            "timestamp": now.isoformat(),
            "source": "scheduled_rule",
            "rule_id": rule.id,
            "rule_name": rule.name
        }
        
        context = {
            "payload": payload,
            "metadata": metadata,
            "source": "scheduled_rule",
            "device": {
                "device_id": device.device_id,
                "tenant_id": device.tenant_id,
                "device_type": device.device_type.name if device.device_type else None,
            },
            "state": rule_engine._get_device_state(device.device_id),
        }
        
        # Evaluate condition (scheduled rules may have conditions based on device state)
        try:
            matched = rule_engine._evaluate_condition(rule.condition, context)
            if matched:
                # Execute action
                rule_engine._apply_action(rule.action, payload, metadata, context=context)
                logger.info(f"Scheduled rule '{rule.name}' executed successfully")
            else:
                logger.debug(f"Scheduled rule '{rule.name}' condition not met, skipping")
        except Exception as e:
            logger.error(f"Error executing scheduled rule '{rule.name}': {e}", exc_info=True)


# Global scheduler instance
rule_scheduler = RuleScheduler()

