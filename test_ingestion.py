#!/usr/bin/env python3
"""Test script for telemetry ingestion."""
import requests
import json
import sys
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:5000"
TELEMETRY_ENDPOINT = f"{API_BASE_URL}/api/v1/telemetry/http"

def test_health_check():
    """Test health check endpoint."""
    print("Testing health check...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        response.raise_for_status()
        print(f"✓ Health check passed: {response.json()}")
        return True
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False

def test_telemetry_ingestion(device_key: str):
    """Test telemetry ingestion with a provisioning key."""
    print(f"\nTesting telemetry ingestion with device key: {device_key[:20]}...")
    
    payload = {
        "data": {
            "level": 75.5,
            "temperature": 25.3,
            "pressure": 1.2,
            "battery": 85
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Device-Key": device_key
    }
    
    try:
        response = requests.post(TELEMETRY_ENDPOINT, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        print(f"✓ Telemetry ingestion successful: {json.dumps(result, indent=2)}")
        return True
    except requests.exceptions.HTTPError as e:
        print(f"✗ Telemetry ingestion failed: {e}")
        if e.response is not None:
            print(f"  Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def main():
    """Main test function."""
    print("=" * 60)
    print("IoT Platform - Telemetry Ingestion Test")
    print("=" * 60)
    
    # Test health check
    if not test_health_check():
        print("\n⚠ Service may not be running. Start with: docker-compose up")
        sys.exit(1)
    
    # Get device key from command line or prompt
    if len(sys.argv) > 1:
        device_key = sys.argv[1]
    else:
        device_key = input("\nEnter device provisioning key (or press Enter to skip): ").strip()
        if not device_key:
            print("Skipping telemetry ingestion test (no key provided)")
            print("\nTo get provisioning keys, run: docker-compose exec backend python init_db.py")
            sys.exit(0)
    
    # Test telemetry ingestion
    test_telemetry_ingestion(device_key)
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()

