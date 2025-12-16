"""Notification service for sending alerts via multiple channels."""
import json
import logging
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime, timezone

from database import SessionLocal
from models import Notification
from config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via various channels."""
    
    def __init__(self):
        """Initialize notification service."""
        # Email settings (from config or environment)
        self.smtp_host = getattr(settings, 'smtp_host', None) or None
        self.smtp_port = getattr(settings, 'smtp_port', None) or 587
        self.smtp_user = getattr(settings, 'smtp_user', None) or None
        self.smtp_password = getattr(settings, 'smtp_password', None) or None
        self.smtp_from = getattr(settings, 'smtp_from', None) or "alerts@flowsense.com"
        
        # SMS settings (placeholder - integrate with SMS provider like Twilio)
        self.sms_provider = getattr(settings, 'sms_provider', None) or None
        self.sms_api_key = getattr(settings, 'sms_api_key', None) or None
    
    def send_email(self, notification: Notification) -> bool:
        """Send email notification."""
        if not self.smtp_host:
            logger.warning("SMTP not configured, skipping email notification")
            notification.status = "failed"
            notification.error_message = "SMTP not configured"
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.smtp_from
            msg['To'] = notification.recipient
            msg['Subject'] = notification.subject or "Alert Notification"
            
            # Add body
            body = notification.body or "You have received an alert notification."
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_user and self.smtp_password:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            notification.status = "sent"
            notification.sent_at = datetime.now(timezone.utc)
            logger.info(f"Email sent to {notification.recipient}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            notification.status = "failed"
            notification.error_message = str(e)
            return False
    
    def send_sms(self, notification: Notification) -> bool:
        """Send SMS notification."""
        if not self.sms_provider:
            logger.warning("SMS provider not configured, skipping SMS notification")
            notification.status = "failed"
            notification.error_message = "SMS provider not configured"
            return False
        
        try:
            # Placeholder for SMS integration
            # Integrate with Twilio, AWS SNS, or other SMS provider
            # For now, just log
            logger.info(f"SMS notification to {notification.recipient}: {notification.body}")
            notification.status = "sent"
            notification.sent_at = datetime.now(timezone.utc)
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}", exc_info=True)
            notification.status = "failed"
            notification.error_message = str(e)
            return False
    
    def send_webhook(self, notification: Notification) -> bool:
        """Send webhook notification."""
        try:
            payload = json.loads(notification.body) if notification.body else {}
            
            response = requests.post(
                notification.recipient,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                notification.status = "sent"
                notification.sent_at = datetime.now(timezone.utc)
                logger.info(f"Webhook sent to {notification.recipient}")
                return True
            else:
                notification.status = "failed"
                notification.error_message = f"HTTP {response.status_code}: {response.text}"
                return False
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}", exc_info=True)
            notification.status = "failed"
            notification.error_message = str(e)
            return False
    
    def process_notification(self, notification: Notification) -> bool:
        """Process a notification based on its channel."""
        db = SessionLocal()
        try:
            success = False
            
            if notification.channel == "email":
                success = self.send_email(notification)
            elif notification.channel == "sms":
                success = self.send_sms(notification)
            elif notification.channel == "webhook":
                success = self.send_webhook(notification)
            else:
                logger.warning(f"Unknown notification channel: {notification.channel}")
                notification.status = "failed"
                notification.error_message = f"Unknown channel: {notification.channel}"
            
            db.commit()
            return success
        except Exception as e:
            logger.error(f"Error processing notification: {e}", exc_info=True)
            db.rollback()
            return False
        finally:
            db.close()
    
    def process_pending_notifications(self):
        """Process all pending notifications (called by background worker)."""
        db = SessionLocal()
        try:
            pending = db.query(Notification).filter(
                Notification.status == "pending"
            ).limit(100).all()
            
            for notification in pending:
                try:
                    self.process_notification(notification)
                except Exception as e:
                    logger.error(f"Error processing notification {notification.id}: {e}")
        finally:
            db.close()


# Global notification service instance
notification_service = NotificationService()

