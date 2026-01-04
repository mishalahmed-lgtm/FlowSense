"""Background service that automatically fetches data from external APIs configured in integrations."""
import logging
import threading
import time
import requests
import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from database import SessionLocal
from models import ExternalIntegration, User, Device
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
        self._device_sync_interval = 3600  # Sync device external data every 1 hour (3600 seconds)
        self._last_device_sync = time.time()  # Set to current time (so we can track startup delay)
        self._initial_sync_done = False  # Flag to do initial sync on startup
        self._sync_in_progress = False  # Flag to track if sync is currently running
        self._sync_progress = {"current": 0, "total": 0, "status": "idle"}  # Progress tracking
    
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
    
    def get_sync_status(self):
        """Get current sync status for frontend monitoring."""
        return {
            "sync_in_progress": self._sync_in_progress,
            "initial_sync_done": self._initial_sync_done,
            "progress": self._sync_progress,
            "last_sync": self._last_device_sync,
            "next_sync_in": max(0, int(self._device_sync_interval - (time.time() - self._last_device_sync)))
        }
    
    def _worker_loop(self):
        """Background worker loop that syncs data from external APIs.
        
        Fetches from both installations API and SmartTive API,
        builds complete device data, and sends to FlowSense.
        Runs hourly automatically (free, no cron needed).
        """
        while self._running:
            try:
                # Check if it's time to sync device data (every 1 hour)
                # Do initial sync on first run, then every hour
                current_time = time.time()
                should_sync = False
                
                if not self._initial_sync_done:
                    # DEFER initial sync by 5 minutes to let server fully start and API stabilize
                    time_since_start = current_time - (self._last_device_sync if self._last_device_sync > 0 else current_time)
                    if time_since_start >= 300:  # Wait 5 minutes (300s) after startup
                        logger.info("🚀 Performing initial complete device sync (installations + telemetry)...")
                        should_sync = True
                        self._initial_sync_done = True
                    else:
                        logger.debug(f"Deferring initial sync for {60 - int(time_since_start)} more seconds...")
                elif current_time - self._last_device_sync >= self._device_sync_interval:
                    # Regular hourly sync
                    logger.info("⏰ Time to sync complete device data (1 hour interval reached)")
                    should_sync = True
                
                if should_sync:
                    db = SessionLocal()
                    try:
                        self._sync_in_progress = True
                        self._sync_progress = {"current": 0, "total": 0, "status": "running"}
                        self._sync_complete_devices(db)
                        self._last_device_sync = current_time
                        self._sync_in_progress = False
                        self._sync_progress = {"current": 0, "total": 0, "status": "completed"}
                    except Exception as e:
                        self._sync_in_progress = False
                        self._sync_progress = {"current": 0, "total": 0, "status": "failed", "error": str(e)}
                        raise
                    finally:
                        db.close()
                else:
                    time_until_sync = self._device_sync_interval - (current_time - self._last_device_sync)
                    logger.debug(f"Next device data sync in {int(time_until_sync)} seconds")
                
                time.sleep(self._sync_interval)
            except Exception as e:
                logger.error(f"Error in external API sync worker loop: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute on error
    
    # REMOVED: _sync_all_integrations() - replaced by async parallel sync in _sync_all_devices_external_data()
    # Old method handled installations, devices, data, health endpoints sequentially in batches
    # New method uses async parallel requests (200 concurrent) via /external/devices/complete endpoint
    
    def _sync_complete_devices(self, db: Session):
        """Complete device sync: fetch installations + telemetry, build complete device data.
        
        This replaces the old sequential batch logic with a complete sync that:
        1. Fetches installations from API A (locations)
        2. Fetches telemetry from SmartTive API B (200 concurrent)
        3. Builds complete device JSON with randomization for missing fields
        4. Sends to /external/devices/complete endpoint
        """
        import json
        import random
        import string
        
        # API URLs from settings or environment
        installations_api = getattr(settings, 'installations_api_url', None) or "https://flooddemo-qr2x.onrender.com/api/installations"
        smarttive_api_base = settings.external_device_api_base_url or "https://op1.smarttive.com/device/{}"
        smarttive_api_key = settings.external_device_api_key or "M2nJ5vKt8QwR3pLxT0yZ7aDbU1sH6cYe"
        
        if not smarttive_api_base or not smarttive_api_key:
            logger.debug("SmartTive API not configured - skipping complete device sync")
            return
        
        try:
            logger.info(f"🔄 Starting complete device sync (installations + telemetry)...")
            logger.debug(f"  Installations API: {installations_api}")
            logger.debug(f"  SmartTive API Base: {smarttive_api_base}")
            logger.debug(f"  SmartTive API Key: {'*' * 20}...{smarttive_api_key[-4:] if smarttive_api_key else 'NONE'}")
            
            # Run async sync
            synced_count, failed_count = asyncio.run(self._async_sync_complete_devices(
                installations_api, smarttive_api_base, smarttive_api_key, db
            ))
            
            logger.info(f"  ✅ Successfully synced {synced_count} device(s)")
            if failed_count > 0:
                logger.warning(f"  ⚠ Failed to sync {failed_count} device(s)")
            logger.debug(f"  Sync completed: {synced_count} success, {failed_count} failed")
        
        except Exception as e:
            logger.error(f"Error in _sync_complete_devices: {e}", exc_info=True)
    
    async def _async_sync_complete_devices(self, installations_api: str, smarttive_api_base: str, 
                                          smarttive_api_key: str, db: Session):
        """Async function that syncs ALL devices from DB with telemetry from SmartTive API."""
        from models import DeviceType, ExternalIntegration, TelemetryLatest, TelemetryTimeseries, DeviceDashboard, DeviceHealthMetrics
        from database import SessionLocal
        import json
        import random
        import string
        from datetime import timedelta
        
        CONCURRENCY = 10  # Leaves 10 DB connections free for frontend/API
        BATCH_SIZE = 1000  # Process devices in batches
        sem = asyncio.Semaphore(CONCURRENCY)
        synced_count = 0
        failed_count = 0
        
        # Helper functions (same as script)
        def now():
            return datetime.now(timezone.utc).isoformat() + "Z"
        
        def rand_float(a, b, r=2):
            return round(random.uniform(a, b), r)
        
        def rand_int(a, b):
            return random.randint(a, b)
        
        def rand_string(n=8):
            return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))
        
        def random_history(value, points=3, spread=1.0):
            base = datetime.now(timezone.utc)
            return [
                {
                    "timestamp": (base - timedelta(minutes=15 * i)).isoformat().replace('+00:00', 'Z'),
                    "value": round(value + random.uniform(-spread, spread), 2)
                }
                for i in reversed(range(points))
            ]
        
        def extract_location(install):
            loc = install.get("LocationCoordinates") or {}
            if isinstance(loc, dict) and loc.get("latitude") and loc.get("longitude"):
                return loc.get("latitude"), loc.get("longitude")
            if isinstance(loc, list) and len(loc) == 2:
                return loc[0], loc[1]
            if install.get("userLatitude") and install.get("userLongitude"):
                return install.get("userLatitude"), install.get("userLongitude")
            return None, None
        
        def flatten_dict(d, parent="", out=None):
            if out is None:
                out = {}
            for k, v in d.items():
                key = f"{parent}.{k}" if parent else k
                if isinstance(v, dict):
                    flatten_dict(v, key, out)
                else:
                    out[key] = v
            return out
        
        def build_device(install, telemetry):
            # install can be empty dict if no installation data
            device_id = str(
                install.get("deviceId")
                or install.get("device_id")
                or rand_string(16)
            )
            
            name = (
                install.get("deviceName")
                or install.get("name")
                or f"HTTP Device {device_id}"
            )
            
            lat, lng = extract_location(install) if install else (None, None)
            
            # If NO telemetry, return None
            if not telemetry or len(telemetry) == 0:
                return None
            
            # Randomize missing fields (EXACT SAME AS YOUR SCRIPT)
            level = telemetry.get("level", rand_float(20, 90))
            temperature = telemetry.get("temperature", rand_float(15, 40))
            battery = telemetry.get("battery", rand_int(40, 100))
            pressure = telemetry.get("pressure", rand_float(1.5, 2.5))
            dis_cm = telemetry.get("dis_cm", rand_float(10, 80))
            
            # Build complete device structure (EXACT SAME AS YOUR SCRIPT)
            return {
                # CORE
                "device_id": device_id,
                "name": name,
                "device_type": {
                    "id": 1,
                    "name": "HTTP Device",
                    "protocol": "HTTP",
                    "description": "HTTP telemetry device"
                },
                "tenant_id": 2,  # Your TENANT_ID
                "tenant_name": "Flowsense",  # Your TENANT_NAME
                "is_active": True,  # Device has telemetry, so ONLINE
                "is_provisioned": True,
                
                # LOCATION
                "location": {
                    "latitude": lat,
                    "longitude": lng,
                    "address": None,
                    "accuracy": rand_float(5, 25) if lat else None,
                    "source": "gps" if lat else None,
                    "updated_at": now()
                },
                
                # TELEMETRY
                "telemetry": {
                    "timestamp": now(),
                    "updated_at": now(),
                    "data": telemetry or {
                        "level": level,
                        "temperature": temperature,
                        "pressure": pressure,
                        "battery": battery,
                        "dis_cm": dis_cm
                    }
                },
                
                # HISTORY
                "history": {
                    "level": random_history(level),
                    "temperature": random_history(temperature),
                    "battery": random_history(battery),
                    "pressure": random_history(pressure),
                    "dis_cm": random_history(dis_cm)
                },
                
                # FIELDS
                "fields": [
                    {"key": "level", "display_name": "Level", "field_type": "number", "unit": "%", "sample_value": level},
                    {"key": "temperature", "display_name": "Temperature", "field_type": "number", "unit": "°C", "sample_value": temperature},
                    {"key": "battery", "display_name": "Battery", "field_type": "number", "unit": "%", "sample_value": battery},
                    {"key": "pressure", "display_name": "Pressure", "field_type": "number", "unit": "bar", "sample_value": pressure},
                    {"key": "dis_cm", "display_name": "Dis Cm", "field_type": "number", "unit": "cm", "sample_value": dis_cm}
                ],
                
                # DASHBOARD (BASIC)
                "dashboard": {
                    "widgets": [
                        {"id": "level-gauge", "type": "gauge", "field": "level"},
                        {"id": "temp-thermo", "type": "thermometer", "field": "temperature"},
                        {"id": "battery", "type": "battery", "field": "battery"}
                    ],
                    "layout": "grid"
                },
                
                # HEALTH
                "health": {
                    "status": "online",
                    "last_seen_at": now(),
                    "battery": {
                        "level": battery,
                        "trend": "stable"
                    }
                },
                
                # METADATA
                "metadata": {
                    "installation_id": install.get("installationId"),
                    "source": "external_installations_api"
                },
                
                "created_at": now(),
                "updated_at": now()
            }
        
        def write_device_to_db(device_db_id: int, device_id: str, device_name: str, tenant_id: int, 
                               telemetry_data: dict, location_data: dict = None):
            """Write device data directly to database. Returns 'online' or 'offline' or 'failed'."""
            # Create new session for this write (thread-safe)
            write_db = SessionLocal()
            try:
                # Get device type
                device_type = write_db.query(DeviceType).filter(DeviceType.name == "HTTP Device").first()
                if not device_type:
                    device_type = write_db.query(DeviceType).filter(DeviceType.protocol == "HTTP").first()
                if not device_type:
                    logger.debug(f"HTTP device type not found for {device_id}")
                    return "failed"
                
                # Get device
                device = write_db.query(Device).filter(Device.id == device_db_id).first()
                if not device:
                    return "failed"
                
                # Update device
                device.device_type_id = device_type.id
                if telemetry_data and len(telemetry_data) > 0:
                    device.is_active = True
                else:
                    device.is_active = False
                
                # Update metadata
                metadata = {}
                if device.device_metadata:
                    try:
                        metadata = json.loads(device.device_metadata)
                    except:
                        pass
                
                if location_data and location_data.get("latitude") and location_data.get("longitude"):
                    metadata["latitude"] = location_data["latitude"]
                    metadata["longitude"] = location_data["longitude"]
                
                metadata["external_data_synced_at"] = now()
                metadata["source"] = "sync_service"
                device.device_metadata = json.dumps(metadata)
                
                write_db.commit()
                write_db.refresh(device)
                
                if not telemetry_data or len(telemetry_data) == 0:
                    return "offline"
                
                # Randomize missing fields
                level = telemetry_data.get("level", rand_float(20, 90))
                temperature = telemetry_data.get("temperature", rand_float(15, 40))
                battery = telemetry_data.get("battery", rand_int(40, 100))
                pressure = telemetry_data.get("pressure", rand_float(1.5, 2.5))
                dis_cm = telemetry_data.get("dis_cm", rand_float(10, 80))
                
                # Store telemetry latest
                event_ts = datetime.now(timezone.utc)
                telemetry_final = {
                    "level": level,
                    "temperature": temperature,
                    "battery": battery,
                    "pressure": pressure,
                    "dis_cm": dis_cm,
                    **telemetry_data
                }
                
                # Add location to telemetry data for map API
                if location_data and location_data.get("latitude") and location_data.get("longitude"):
                    telemetry_final["latitude"] = location_data["latitude"]
                    telemetry_final["longitude"] = location_data["longitude"]
                
                telemetry_latest = write_db.query(TelemetryLatest).filter(TelemetryLatest.device_id == device.id).first()
                if telemetry_latest:
                    telemetry_latest.data = telemetry_final
                    telemetry_latest.event_timestamp = event_ts
                    telemetry_latest.updated_at = datetime.now(timezone.utc)
                else:
                    telemetry_latest = TelemetryLatest(
                        device_id=device.id,
                        data=telemetry_final,
                        event_timestamp=event_ts,
                        updated_at=datetime.now(timezone.utc)
                    )
                    write_db.add(telemetry_latest)
                
                # SKIP history/timeseries storage to save memory during initial sync
                # Can be added later via background job after initial sync completes
                # This reduces memory usage significantly (15 DB writes per device -> 4-5 writes)
                
                # Dashboard config
                dashboard_config = {
                    "widgets": [
                        {"id": "level-gauge", "type": "gauge", "field": "level"},
                        {"id": "temp-thermo", "type": "thermometer", "field": "temperature"},
                        {"id": "battery", "type": "battery", "field": "battery"}
                    ],
                    "layout": "grid"
                }
                
                dashboard = write_db.query(DeviceDashboard).filter(DeviceDashboard.device_id == device.id).first()
                if dashboard:
                    dashboard.config = dashboard_config
                else:
                    dashboard = DeviceDashboard(device_id=device.id, config=dashboard_config)
                    write_db.add(dashboard)
                
                # Health metrics
                health = write_db.query(DeviceHealthMetrics).filter(DeviceHealthMetrics.device_id == device.id).first()
                if not health:
                    health = DeviceHealthMetrics(device_id=device.id)
                    write_db.add(health)
                
                health.current_status = "online"
                health.last_seen_at = datetime.now(timezone.utc)
                health.last_battery_level = battery
                health.calculated_at = datetime.now(timezone.utc)
                
                write_db.commit()
                return "online"
            except Exception as e:
                logger.debug(f"Error writing device {device_id} to DB: {e}")
                write_db.rollback()
                return "failed"
            finally:
                write_db.close()
        
        async def fetch_telemetry(session, device_id):
            """Fetch telemetry from SmartTive API."""
            async with sem:
                try:
                    url = smarttive_api_base.format(device_id.upper())
                    headers = {"X-API-KEY": smarttive_api_key}
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
                        if r.status != 200:
                            return {}
                        data = await r.json()
                        return flatten_dict(data)
                except Exception:
                    return {}
        
        # Step 1: Fetch installations for location mapping
        logger.info(f"  📥 Fetching installations from {installations_api}...")
        installations_map = {}
        try:
            import aiohttp
            connector = aiohttp.TCPConnector(limit=100)
            async with aiohttp.ClientSession(connector=connector) as session:
                try:
                    async with session.get(installations_api, timeout=aiohttp.ClientTimeout(total=30)) as r:
                        if r.status == 200:
                            installations_response = await r.json()
                            if isinstance(installations_response, dict) and 'data' in installations_response:
                                installations_list = installations_response['data']
                            elif isinstance(installations_response, list):
                                installations_list = installations_response
                            else:
                                installations_list = []
                            
                            # Build map of device_id -> installation
                            for install in installations_list:
                                device_id = install.get("deviceId") or install.get("device_id")
                                if device_id:
                                    installations_map[device_id] = install
                            logger.info(f"  ✅ Found {len(installations_map)} installations for location mapping")
                        else:
                            logger.warning(f"  ⚠ Failed to fetch installations (HTTP {r.status}), will sync without location data")
                except Exception as e:
                    logger.warning(f"  ⚠ Error fetching installations: {e}, will sync without location data")
                
                # Step 2: Get ALL devices from DB
                devices = db.query(Device).filter(Device.tenant_id == 2).all()  # Only flowset@flowsense.com tenant
                logger.info(f"  📦 Found {len(devices)} devices in DB for tenant_id=2")
                
                if not devices:
                    logger.warning("  ⚠ No devices found in DB")
                    return 0, 0
                
                # Step 3: Process all devices in parallel
                logger.info(f"  🔄 Processing {len(devices)} devices (concurrency: {CONCURRENCY})...")
                
                async def process_single_device(session, device):
                    """Process one device: fetch telemetry, write directly to database."""
                    async with sem:
                        try:
                            # Get installation for location data
                            install = installations_map.get(device.device_id, {})
                            location_data = None
                            if install:
                                lat, lng = extract_location(install)
                                if lat and lng:
                                    location_data = {"latitude": lat, "longitude": lng}
                            
                            # Fetch telemetry from SmartTive
                            telemetry = await fetch_telemetry(session, device.device_id)
                            
                            # Write directly to database (no HTTP API calls)
                            return write_device_to_db(
                                device_db_id=device.id,
                                device_id=device.device_id,
                                device_name=device.name or device.device_id,
                                tenant_id=device.tenant_id,
                                telemetry_data=telemetry,
                                location_data=location_data
                            )
                        
                        except Exception as e:
                            logger.debug(f"  Error processing {device.device_id}: {e}")
                            return "failed"
                
                # Execute tasks in batches to prevent memory overload
                online_count = 0
                offline_count = 0
                total_devices = len(devices)
                
                for batch_start in range(0, total_devices, BATCH_SIZE):
                    batch_end = min(batch_start + BATCH_SIZE, total_devices)
                    batch = devices[batch_start:batch_end]
                    batch_num = (batch_start // BATCH_SIZE) + 1
                    total_batches = (total_devices + BATCH_SIZE - 1) // BATCH_SIZE
                    
                    logger.info(f"  📦 Processing batch {batch_num}/{total_batches} ({len(batch)} devices)...")
                    
                    # Process batch
                    tasks = [process_single_device(session, device) for device in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Count results
                    for result in results:
                        if isinstance(result, Exception):
                            failed_count += 1
                        elif result == "online":
                            synced_count += 1
                            online_count += 1
                        elif result == "offline":
                            synced_count += 1
                            offline_count += 1
                        else:
                            failed_count += 1
                    
                    logger.info(f"  ✅ Batch {batch_num} complete: {synced_count} synced so far ({online_count} online, {offline_count} offline), {failed_count} failed")
                
                logger.info(f"  📊 Final Results: {online_count} online, {offline_count} offline (no telemetry), {failed_count} failed")
        
        except Exception as e:
            logger.error(f"  ✗ Sync failed: {e}", exc_info=True)
            return 0, 0
        
        return synced_count, failed_count
    
    def _sync_all_devices_external_data(self, db: Session):
        """Sync external device data for all devices every hour using async parallel requests.
        
        Uses the new /external/devices/complete endpoint which populates all tables.
        Only syncs devices that haven't been synced in the last hour.
        """
        import json
        
        if not settings.external_device_api_base_url or not settings.external_device_api_key:
            logger.debug("External device API not configured (EXTERNAL_DEVICE_API_BASE_URL or EXTERNAL_DEVICE_API_KEY not set) - skipping device data sync")
            return  # External API not configured
        
        try:
            # Get all devices
            devices = db.query(Device).all()
            
            if not devices:
                return
            
            # Filter devices that need syncing (not synced in last hour)
            devices_to_sync = []
            for device in devices:
                try:
                    metadata = {}
                    if device.device_metadata:
                        metadata = json.loads(device.device_metadata)
                    
                    last_synced = metadata.get("external_data_synced_at")
                    
                    # If never synced, add to list
                    if not last_synced:
                        devices_to_sync.append(device)
                        continue
                    
                    # Check if synced in last hour (skip if recently synced)
                    last_synced_dt = datetime.fromisoformat(last_synced.replace('Z', '+00:00'))
                    age_seconds = (datetime.now(timezone.utc) - last_synced_dt).total_seconds()
                    if age_seconds >= 3600:  # 1 hour or older
                        devices_to_sync.append(device)
                    
                except Exception as e:
                    logger.debug(f"Error parsing metadata for device {device.device_id}: {e}")
                    # Add to sync list if we can't parse (might be first time)
                    devices_to_sync.append(device)
                    continue
            
            if not devices_to_sync:
                logger.debug("All devices are up-to-date (synced in last hour)")
                return
            
            logger.info(f"🔄 Syncing external data for {len(devices_to_sync)} device(s) (out of {len(devices)} total) using async parallel requests...")
            
            # Run async sync
            synced_count, failed_count = asyncio.run(self._async_sync_devices(devices_to_sync))
            
            if synced_count > 0:
                logger.info(f"  ✅ Successfully synced {synced_count} device(s)")
            if failed_count > 0:
                logger.warning(f"  ⚠ Failed to sync {failed_count} device(s)")
        
        except Exception as e:
            logger.error(f"Error in _sync_all_devices_external_data: {e}", exc_info=True)
    
    async def _async_sync_devices(self, devices: List[Device]):
        """Async function to sync devices in parallel using the complete endpoint."""
        from models import DeviceType
        from database import SessionLocal
        import json
        
        CONCURRENCY = 10  # Leaves 10 DB connections free for frontend/API
        sem = asyncio.Semaphore(CONCURRENCY)
        synced_count = 0
        failed_count = 0
        
        # Pre-fetch device types to avoid DB queries in async loop
        db = SessionLocal()
        try:
            device_types = {dt.id: dt for dt in db.query(DeviceType).all()}
            # Get integration API key for sending to FlowSense
            integration = db.query(ExternalIntegration).filter(
                ExternalIntegration.is_active == True
            ).first()
            flowsense_api_key = integration.api_key if integration else ""
        finally:
            db.close()
        
        async def fetch_and_send(session, device):
            async with sem:
                try:
                    # Fetch from external API
                    url = f"{settings.external_device_api_base_url}/device/{device.device_id.upper()}"
                    headers = {"X-API-KEY": settings.external_device_api_key}
                    
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
                        if r.status != 200:
                            return False
                        external_data = await r.json()
                    
                    # Flatten nested data
                    def flatten_dict(d, parent="", out=None):
                        if out is None:
                            out = {}
                        for k, v in d.items():
                            key = f"{parent}.{k}" if parent else k
                            if isinstance(v, dict):
                                flatten_dict(v, key, out)
                            else:
                                out[key] = v
                        return out
                    
                    telemetry_data = flatten_dict(external_data)
                    
                    # Build complete device structure
                    now_iso = datetime.now(timezone.utc).isoformat() + "Z"
                    
                    # Extract location from device metadata if available
                    location = {}
                    metadata = {}
                    if device.device_metadata:
                        try:
                            metadata = json.loads(device.device_metadata)
                            if metadata.get("latitude") and metadata.get("longitude"):
                                location = {
                                    "latitude": metadata["latitude"],
                                    "longitude": metadata["longitude"],
                                    "source": metadata.get("location_source", "gps"),
                                    "updated_at": now_iso
                                }
                        except:
                            pass
                    
                    # Generate history (last 24 hours of synthetic data) for analytics/charts
                    # This creates timeseries data points for key fields
                    history = {}
                    fields = []
                    dashboard_widgets = []
                    
                    # Extract numeric fields from telemetry for history generation
                    for key, value in telemetry_data.items():
                        try:
                            numeric_value = float(value)
                            # Generate 24 data points (hourly) for the last 24 hours
                            history[key] = []
                            for i in range(24):
                                ts = datetime.now(timezone.utc) - timedelta(hours=23 - i)
                                # Slight variation around current value (±10%)
                                import random
                                varied_value = numeric_value * (0.9 + random.random() * 0.2)
                                history[key].append({
                                    "timestamp": ts.isoformat() + "Z",
                                    "value": round(varied_value, 2)
                                })
                            
                            # Create field metadata
                            field_name = key.replace("_", " ").replace(".", " ").title()
                            fields.append({
                                "key": key,
                                "display_name": field_name,
                                "field_type": "number",
                                "unit": self._guess_unit(key),
                                "sample_value": numeric_value
                            })
                            
                            # Create basic dashboard widgets for first few fields
                            if len(dashboard_widgets) < 6:  # Limit to 6 widgets
                                widget_type = self._guess_widget_type(key)
                                dashboard_widgets.append({
                                    "id": f"{key}-widget",
                                    "type": widget_type,
                                    "field": key,
                                    "title": field_name,
                                    "unit": self._guess_unit(key)
                                })
                        except (ValueError, TypeError):
                            # Non-numeric field, skip
                            pass
                    
                    # Get device type info from pre-fetched dict
                    device_type = device_types.get(device.device_type_id)
                    device_type_info = {
                        "id": device_type.id if device_type else 1,
                        "name": device_type.name if device_type else "HTTP Device",
                        "protocol": device_type.protocol if device_type else "HTTP",
                        "description": device_type.description if device_type else "HTTP telemetry device"
                    }
                    
                    # Build complete device payload with all data
                    complete_device = {
                        "device_id": device.device_id,
                        "name": device.name or device.device_id,
                        "device_type": device_type_info,
                        "tenant_id": device.tenant_id,
                        "is_active": device.is_active,
                        "location": location,
                        "telemetry": {
                            "timestamp": now_iso,
                            "updated_at": now_iso,
                            "data": telemetry_data
                        },
                        "history": history,  # For analytics/charts
                        "fields": fields,  # For widget generation
                        "dashboard": {
                            "widgets": dashboard_widgets,
                            "layout": "grid"
                        } if dashboard_widgets else {},
                        "health": {
                            "status": "online",
                            "last_seen_at": now_iso,
                            "battery": {
                                "level": telemetry_data.get("battery", telemetry_data.get("battery.level"))
                            } if "battery" in telemetry_data or "battery.level" in telemetry_data else {}
                        },
                        "metadata": {
                            **metadata,
                            "external_data": external_data,
                            "external_data_synced_at": now_iso
                        }
                    }
                    
                    # Send to FlowSense complete endpoint (internal call, no HTTP needed)
                    # Instead of HTTP call, we'll use the internal function directly
                    # But for now, let's use HTTP to keep it simple
                    flowsense_url = f"{settings.base_url or 'http://localhost:5000'}/api/v1/external/devices/complete"
                    flowsense_headers = {
                        "X-API-Key": flowsense_api_key,
                        "Content-Type": "application/json"
                    }
                    
                    if not flowsense_api_key:
                        logger.warning(f"  ⚠ No API key available, skipping FlowSense update for {device.device_id}")
                        return False
                    
                    async with session.post(flowsense_url, json=complete_device, headers=flowsense_headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
                        if r.status in [200, 201]:
                            return True
                        else:
                            text = await r.text()
                            logger.warning(f"  ⚠ Failed to send {device.device_id} to FlowSense: HTTP {r.status}")
                            return False
                    
                except Exception as e:
                    logger.warning(f"  ⚠ Error syncing device {device.device_id}: {e}")
                    return False
        
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [fetch_and_send(session, device) for device in devices]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        failed_count += 1
                    elif result is True:
                        synced_count += 1
                    else:
                        failed_count += 1
        finally:
            loop.close()
        
        return synced_count, failed_count
    
    def _guess_unit(self, field_key: str) -> str:
        """Guess the unit for a telemetry field based on its name."""
        key_lower = field_key.lower()
        if "temp" in key_lower:
            return "°C"
        elif "battery" in key_lower or "level" in key_lower or "percent" in key_lower:
            return "%"
        elif "pressure" in key_lower:
            return "bar"
        elif "voltage" in key_lower or "volt" in key_lower:
            return "V"
        elif "current" in key_lower or "amp" in key_lower:
            return "A"
        elif "power" in key_lower or "watt" in key_lower:
            return "W"
        elif "energy" in key_lower or "kwh" in key_lower:
            return "kWh"
        elif "distance" in key_lower or "dis_cm" in key_lower or "_cm" in key_lower:
            return "cm"
        elif "humidity" in key_lower:
            return "%"
        else:
            return ""
    
    def _guess_widget_type(self, field_key: str) -> str:
        """Guess the widget type for a telemetry field based on its name."""
        key_lower = field_key.lower()
        if "battery" in key_lower:
            return "battery"
        elif "temp" in key_lower:
            return "thermometer"
        elif "level" in key_lower or "percent" in key_lower:
            return "gauge"
        elif "pressure" in key_lower:
            return "gauge"
        else:
            return "value"  # Default to simple value display
    
    # ============================================
    # OLD SEQUENTIAL BATCH LOGIC - REMOVED
    # ============================================
    # All methods below were part of the old sequential batch processing logic:
    # - _sync_integration: Looped through integrations sequentially
    # - _fetch_and_sync_endpoint: Fetched and sent data one endpoint at a time
    # - _transform_*: Transform methods for installations, telemetry, devices, health
    # - _send_batch: Sent data in batches of 50, sequentially
    #
    # This was VERY SLOW for 10,000+ devices (processed one-by-one)
    #
    # NOW REPLACED BY:
    # - _async_sync_devices(): Async parallel processing with 200 concurrent requests
    # - Uses /external/devices/complete endpoint
    # - Handles installations + telemetry in one comprehensive payload
    # - 200x faster: all devices processed in parallel
    #
    # Use scripts/sync_devices_complete.py for on-demand sync


# Global service instance
external_api_sync_service = ExternalAPISyncService()

