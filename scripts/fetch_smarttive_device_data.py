#!/usr/bin/env python3
"""Simple script to fetch device data from SmartTive API to see the structure."""

import requests
import json
import os

# Get API configuration from environment or use defaults
API_BASE_URL = os.getenv("EXTERNAL_DEVICE_API_BASE_URL", "https://op1.smarttive.com")
API_KEY = os.getenv("EXTERNAL_DEVICE_API_KEY", "M2nJ5vKt8QwR3pLxT0yZ7aDbU1sH6cYe")

# Test device ID (you can change this)
DEVICE_ID = "1B43F66495AF57AA"  # Example device ID from your logs

print(f"Fetching data for device: {DEVICE_ID}")
print(f"API URL: {API_BASE_URL}/device/{DEVICE_ID.upper()}")
print("-" * 60)

try:
    url = f"{API_BASE_URL}/device/{DEVICE_ID.upper()}"
    headers = {"X-API-KEY": API_KEY}
    
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    
    data = response.json()
    
    print("✅ Success! Data structure:")
    print("=" * 60)
    print(json.dumps(data, indent=2))
    print("=" * 60)
    
    print("\n📊 Data Summary:")
    print(f"  - Type: {type(data)}")
    if isinstance(data, dict):
        print(f"  - Keys: {list(data.keys())}")
        for key, value in data.items():
            print(f"    • {key}: {type(value).__name__} = {value if not isinstance(value, (dict, list)) else f'({len(value)} items)'}")
    
except requests.exceptions.RequestException as e:
    print(f"❌ Error: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"   Status Code: {e.response.status_code}")
        print(f"   Response: {e.response.text[:500]}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")

