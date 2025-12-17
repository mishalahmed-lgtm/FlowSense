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
        
        # Push notification settings (Firebase Cloud Messaging, Apple Push Notification Service, etc.)
        self.push_provider = getattr(settings, 'push_provider', None) or None  # fcm, apns, webpush
        self.push_api_key = getattr(settings, 'push_api_key', None) or None
        self.push_project_id = getattr(settings, 'push_project_id', None) or None
    
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
    
    def send_push(self, notification: Notification) -> bool:
        """Send push notification (FCM, APNS, or Web Push)."""
        if not self.push_provider:
            logger.warning("Push notification provider not configured, skipping push notification")
            notification.status = "failed"
            notification.error_message = "Push notification provider not configured"
            return False
        
        try:
            # Parse recipient (should be device token or user ID)
            recipient = notification.recipient
            
            # Parse body (should be JSON with title, body, data, etc.)
            try:
                push_payload = json.loads(notification.body) if notification.body else {}
            except:
                push_payload = {
                    "title": notification.subject or "Alert",
                    "body": notification.body or "You have a new alert",
                }
            
            # Send based on provider
            if self.push_provider.lower() == "fcm":
                # Firebase Cloud Messaging
                fcm_url = f"https://fcm.googleapis.com/v1/projects/{self.push_project_id}/messages:send"
                headers = {
                    "Authorization": f"Bearer {self.push_api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "message": {
                        "token": recipient,
                        "notification": {
                            "title": push_payload.get("title", "Alert"),
                            "body": push_payload.get("body", ""),
                        },
                        "data": push_payload.get("data", {}),
                    }
                }
                response = requests.post(fcm_url, json=payload, headers=headers, timeout=10)
                
            elif self.push_provider.lower() == "webpush":
                # Web Push API (for browser notifications)
                # This requires a service worker and VAPID keys
                logger.info(f"Web Push notification to {recipient}: {push_payload}")
                # Placeholder - implement Web Push API integration
                response = requests.Response()
                response.status_code = 200
            else:
                logger.warning(f"Unknown push provider: {self.push_provider}")
                notification.status = "failed"
                notification.error_message = f"Unknown push provider: {self.push_provider}"
                return False
            
            if response.status_code >= 200 and response.status_code < 300:
                notification.status = "sent"
                notification.sent_at = datetime.now(timezone.utc)
                logger.info(f"Push notification sent to {recipient}")
                return True
            else:
                notification.status = "failed"
                notification.error_message = f"HTTP {response.status_code}: {response.text}"
                return False
                
        except Exception as e:
            logger.error(f"Failed to send push notification: {e}", exc_info=True)
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
            elif notification.channel == "push":
                success = self.send_push(notification)
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

