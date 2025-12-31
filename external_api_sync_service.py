"""Background service that automatically fetches data from external APIs configured in integrations."""
import logging
import threading
import time
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from database import SessionLocal
from models import ExternalIntegration, User
from config import settings

logger = logging.getLogger(__name__)


class ExternalAPISyncService:
    """Service that periodically fetches data from external APIs and syncs it to our system."""
    
    def __init__(self):
        """Initialize external API sync service."""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._sync_interval = 300  # Sync every 5 minutes (300 seconds)
    
    def start(self):
        """Start the external API sync service."""
        if self._running:
            logger.warning("External API sync service is already running")
            return
        
        self._running = True
        
        # Start background worker thread
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info("External API sync service started")
    
    def stop(self):
        """Stop the external API sync service."""
        if not self._running:
            return
        
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("External API sync service stopped")
    
    def _worker_loop(self):
        """Background worker loop that syncs data from external APIs."""
        while self._running:
            try:
                self._sync_all_integrations()
                time.sleep(self._sync_interval)
            except Exception as e:
                logger.error(f"Error in external API sync worker loop: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute on error
    
    def _sync_all_integrations(self):
        """Sync data from all active external integrations."""
        db: Session = SessionLocal()
        try:
            # Get all active integrations
            integrations = db.query(ExternalIntegration).filter(
                ExternalIntegration.is_active == True
            ).all()
            
            if not integrations:
                logger.debug("No active external integrations found")
                return
            
            logger.info(f"Syncing data from {len(integrations)} external integration(s)...")
            
            for integration in integrations:
                try:
                    self._sync_integration(integration, db)
                except Exception as e:
                    logger.error(f"Error syncing integration {integration.id} ({integration.name}): {e}", exc_info=True)
        
        finally:
            db.close()
    
    def _sync_integration(self, integration: ExternalIntegration, db: Session):
        """Sync data from a single external integration."""
        if not integration.endpoint_urls:
            return
        
        # Get our API base URL from config or environment
        import os
        our_base_url = (
            settings.api_base_url or 
            os.getenv("API_BASE_URL") or 
            os.getenv("RENDER_EXTERNAL_URL")
        )
        if not our_base_url:
            # Try to detect from DATABASE_URL or use default
            db_url = getattr(settings, 'database_url', '')
            if 'render.com' in db_url:
                # For Render, try to extract service name or use default
                # User should set API_BASE_URL environment variable
                our_base_url = "https://flowsense-772d.onrender.com"  # Update with your actual URL
            else:
                our_base_url = "http://localhost:5000"  # Default for local
        
        # Check each endpoint URL
        for endpoint_type, external_url in integration.endpoint_urls.items():
            if not external_url:
                continue
            
            # Skip if the URL points to our own system (not an external API)
            parsed = urlparse(external_url)
            our_parsed = urlparse(our_base_url)
            
            # Check if URL is external (not pointing to our system)
            is_external = True
            if parsed.netloc == our_parsed.netloc:
                is_external = False
            elif parsed.netloc and our_parsed.netloc:
                # Check if both are on render.com but different services
                if '.onrender.com' in parsed.netloc and '.onrender.com' in our_parsed.netloc:
                    # If both are render.com, check if they're the same service
                    if parsed.netloc == our_parsed.netloc:
                        is_external = False
                    # If external URL contains 'flowsense' and matches our pattern, skip
                    elif 'flowsense' in parsed.netloc.lower() and 'flowsense' in our_parsed.netloc.lower():
                        is_external = False
            
            if not is_external:
                logger.debug(f"Skipping {endpoint_type} endpoint - points to our own system: {external_url}")
                continue
            
            try:
                self._fetch_and_sync_endpoint(integration, endpoint_type, external_url, our_base_url, db)
            except Exception as e:
                logger.error(f"Error syncing {endpoint_type} from {external_url}: {e}", exc_info=True)
    
    def _fetch_and_sync_endpoint(self, integration: ExternalIntegration, endpoint_type: str, 
                                  external_url: str, our_base_url: str, db: Session):
        """Fetch data from external endpoint and sync to our system."""
        logger.info(f"Fetching {endpoint_type} data from {external_url}...")
        
        try:
            # Fetch from external API
            response = requests.get(external_url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, dict):
                if 'data' in data:
                    items = data['data']
                elif 'success' in data and 'data' in data:
                    items = data['data']
                else:
                    items = [data] if data else []
            elif isinstance(data, list):
                items = data
            else:
                items = []
            
            if not items:
                logger.debug(f"No data found in {endpoint_type} response from {external_url}")
                return
            
            logger.info(f"Fetched {len(items)} items from {external_url}")
            
            # Determine our internal endpoint based on endpoint_type
            if endpoint_type == "installations":
                our_endpoint = f"{our_base_url}/api/v1/external/installations"
            elif endpoint_type == "data":
                our_endpoint = f"{our_base_url}/api/v1/external/data"
            elif endpoint_type == "devices":
                our_endpoint = f"{our_base_url}/api/v1/external/devices"
            elif endpoint_type == "health":
                our_endpoint = f"{our_base_url}/api/v1/external/health"
            else:
                logger.warning(f"Unknown endpoint type: {endpoint_type}, skipping")
                return
            
            # Send to our API
            headers = {
                "X-API-Key": integration.api_key,
                "Content-Type": "application/json"
            }
            
            # Transform and send data based on endpoint type
            if endpoint_type == "installations":
                # Transform installations format
                transformed_items = [self._transform_installation(item) for item in items]
                # Send in batches
                self._send_batch(our_endpoint, headers, transformed_items, batch_size=50)
            elif endpoint_type == "data":
                # For telemetry data, send each item individually
                for item in items:
                    try:
                        payload = self._transform_telemetry(item)
                        requests.post(our_endpoint, headers=headers, json=payload, timeout=30)
                    except Exception as e:
                        logger.error(f"Error sending telemetry item: {e}")
            elif endpoint_type == "devices":
                # Send device data
                for item in items:
                    try:
                        payload = self._transform_device(item)
                        requests.post(our_endpoint, headers=headers, json=payload, timeout=30)
                    except Exception as e:
                        logger.error(f"Error sending device item: {e}")
            elif endpoint_type == "health":
                # Send health data
                for item in items:
                    try:
                        payload = self._transform_health(item)
                        requests.post(our_endpoint, headers=headers, json=payload, timeout=30)
                    except Exception as e:
                        logger.error(f"Error sending health item: {e}")
            
            logger.info(f"✓ Successfully synced {len(items)} {endpoint_type} items")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error fetching from {external_url}: {e}")
        except Exception as e:
            logger.error(f"Error processing {endpoint_type} from {external_url}: {e}", exc_info=True)
    
    def _transform_installation(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Transform installation item to our format."""
        return {
            "id": item.get("id", "").split("_")[0] if "_" in item.get("id", "") else item.get("id", ""),
            "deviceId": item.get("deviceId", ""),
            "amanah": item.get("locationId", item.get("amanah", "")),
            "createdAt": item.get("createdAt", "")
        }
    
    def _transform_telemetry(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Transform telemetry item to our format."""
        return {
            "device_id": item.get("device_id") or item.get("deviceId", ""),
            "data": item.get("data", item),  # Use 'data' field or entire item
            "timestamp": item.get("timestamp") or datetime.now(timezone.utc).isoformat()
        }
    
    def _transform_device(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Transform device item to our format."""
        return {
            "device_id": item.get("device_id") or item.get("deviceId", ""),
            "name": item.get("name", item.get("device_id", "")),
            "device_type_name": item.get("device_type_name") or item.get("deviceType"),
            "is_active": item.get("is_active", True),
            "metadata": item.get("metadata", {})
        }
    
    def _transform_health(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Transform health item to our format."""
        return {
            "device_id": item.get("device_id") or item.get("deviceId", ""),
            "current_status": item.get("current_status", "unknown"),
            "last_seen_at": item.get("last_seen_at") or item.get("lastSeenAt"),
            "message_count_24h": item.get("message_count_24h", 0),
            "connectivity_score": item.get("connectivity_score"),
            "last_battery_level": item.get("last_battery_level"),
            "uptime_24h_percent": item.get("uptime_24h_percent")
        }
    
    def _send_batch(self, endpoint: str, headers: Dict[str, str], items: List[Dict[str, Any]], batch_size: int = 50):
        """Send items in batches."""
        total = len(items)
        for i in range(0, total, batch_size):
            batch = items[i:i + batch_size]
            try:
                response = requests.post(endpoint, headers=headers, json=batch, timeout=60)
                response.raise_for_status()
                logger.debug(f"Sent batch {i//batch_size + 1} ({len(batch)} items)")
            except Exception as e:
                logger.error(f"Error sending batch {i//batch_size + 1}: {e}")


# Global service instance
external_api_sync_service = ExternalAPISyncService()

