#!/usr/bin/env python3
"""
Script to send live telemetry data for all devices in a tenant.
Sends telemetry every 5 hours (configurable) to simulate real device data.

Usage:
    python scripts/send_live_telemetry.py --tenant-id 2 --interval 5
    python scripts/send_live_telemetry.py --tenant-id 2 --interval 5 --once  # Run once and exit
"""

import argparse
import asyncio
import logging
import random
import time
from datetime import datetime, timezone
from typing import Dict, List, Any
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from sqlalchemy import text
from database import SessionLocal
from models import DeviceSnapshot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
EXTERNAL_API_KEY = os.getenv("EXTERNAL_API_KEY", "")  # Set this in your .env


def get_tenant_device_ids(tenant_id: int) -> List[str]:
    """Get only device IDs for a tenant (no telemetry data)."""
    db = SessionLocal()
    try:
        # Query only device_id column - fast query, no JSONB parsing
        query = text("SELECT device_id FROM devices_snapshot WHERE tenant_id = :tenant_id")
        result = db.execute(query, {"tenant_id": tenant_id})
        device_ids = [row[0] for row in result]
        
        logger.info(f"Found {len(device_ids)} device IDs for tenant_id={tenant_id}")
        return device_ids
    finally:
        db.close()


def generate_random_telemetry() -> Dict[str, Any]:
    """Generate completely random telemetry data (not based on device type or existing values)."""
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Generate random telemetry with common fields
    return {
        # Energy/consumption values (random cumulative values)
        "total_active_energy": round(random.uniform(1000, 50000), 3),
        "active_energy_import_total": round(random.uniform(1000, 50000), 3),
        "level": round(random.uniform(10, 95), 2),
        "volume_index": round(random.uniform(500, 8000), 3),
        
        # Electrical measurements
        "voltage": round(random.uniform(220, 240), 2),
        "current": round(random.uniform(1, 30), 2),
        "power": round(random.uniform(500, 8000), 2),
        
        # Device health
        "battery": random.randint(70, 100),
        "signal_strength": random.randint(15, 30),
        
        # Environmental
        "temperature": round(random.uniform(18, 35), 2),
        "humidity": round(random.uniform(30, 80), 2),
        "pressure": round(random.uniform(1.0, 3.0), 2),
        
        # Other
        "flow_rate": round(random.uniform(0, 5), 2),
        "timestamp": timestamp,
        "is_active": True,
    }


def send_telemetry_via_external_api(device_id: str, data: Dict[str, Any]) -> bool:
    """Send telemetry data via external API endpoint."""
    if not EXTERNAL_API_KEY:
        logger.error("EXTERNAL_API_KEY not set. Cannot send telemetry.")
        return False
    
    url = f"{API_BASE_URL}/api/v1/external/data"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": EXTERNAL_API_KEY,
    }
    payload = {
        "device_id": device_id,
        "data": data,
        "timestamp": data.get("timestamp"),
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)  # Increased timeout for free-tier DB
        if response.status_code == 202:
            logger.debug(f"✓ Sent telemetry for {device_id}")
            return True
        else:
            logger.warning(f"✗ Failed to send telemetry for {device_id}: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.Timeout:
        logger.warning(f"✗ Timeout sending telemetry for {device_id} (API took >60s)")
        return False
    except Exception as e:
        logger.error(f"✗ Error sending telemetry for {device_id}: {e}")
        return False


def send_telemetry_batch(device_ids: List[str], batch_size: int = 50) -> Dict[str, int]:
    """Send random telemetry for all device IDs in batches."""
    total = len(device_ids)
    success_count = 0
    error_count = 0
    
    logger.info(f"Sending random telemetry for {total} devices in batches of {batch_size}...")
    
    for i in range(0, total, batch_size):
        batch = device_ids[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size
        
        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} devices)...")
        
        for device_id in batch:
            try:
                # Generate fresh random telemetry for this device
                telemetry_data = generate_random_telemetry()
                
                if send_telemetry_via_external_api(device_id, telemetry_data):
                    success_count += 1
                else:
                    error_count += 1
                
                # Small delay to avoid overwhelming the API
                time.sleep(0.05)
            except Exception as e:
                logger.error(f"Error processing device {device_id}: {e}")
                error_count += 1
        
        logger.info(f"Batch {batch_num} complete: {success_count} success, {error_count} errors")
    
    return {
        "total": total,
        "success": success_count,
        "errors": error_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Send live telemetry data for tenant devices")
    parser.add_argument("--tenant-id", type=int, required=True, help="Tenant ID")
    parser.add_argument("--interval", type=int, default=5, help="Interval in hours (default: 5)")
    parser.add_argument("--once", action="store_true", help="Run once and exit (don't loop)")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for sending (default: 50)")
    parser.add_argument("--api-url", type=str, default=None, help="API base URL (overrides env var)")
    parser.add_argument("--api-key", type=str, default=None, help="API key (overrides env var)")
    
    args = parser.parse_args()
    
    # Override env vars if provided
    global API_BASE_URL, EXTERNAL_API_KEY
    if args.api_url:
        API_BASE_URL = args.api_url
    if args.api_key:
        EXTERNAL_API_KEY = args.api_key
    
    if not EXTERNAL_API_KEY:
        logger.error("EXTERNAL_API_KEY must be set (via --api-key or environment variable)")
        sys.exit(1)
    
    logger.info(f"Starting telemetry sender for tenant_id={args.tenant_id}")
    logger.info(f"API URL: {API_BASE_URL}")
    logger.info(f"Interval: {args.interval} hours")
    logger.info(f"Batch size: {args.batch_size}")
    
    # Get device IDs only (no telemetry data needed)
    device_ids = get_tenant_device_ids(args.tenant_id)
    if not device_ids:
        logger.error(f"No devices found for tenant_id={args.tenant_id}")
        sys.exit(1)
    
    # Send telemetry
    def send_telemetry():
        logger.info("=" * 60)
        logger.info(f"Starting telemetry send at {datetime.now().isoformat()}")
        results = send_telemetry_batch(device_ids, batch_size=args.batch_size)
        logger.info(f"Telemetry send complete: {results['success']}/{results['total']} successful, {results['errors']} errors")
        logger.info("=" * 60)
    
    # Run once or loop
    if args.once:
        send_telemetry()
    else:
        # Convert hours to seconds
        interval_seconds = args.interval * 3600
        
        logger.info(f"Will send telemetry every {args.interval} hours ({interval_seconds} seconds)")
        logger.info("Press Ctrl+C to stop")
        
        try:
            while True:
                send_telemetry()
                logger.info(f"Sleeping for {args.interval} hours until next send...")
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Stopped by user")


if __name__ == "__main__":
    main()

