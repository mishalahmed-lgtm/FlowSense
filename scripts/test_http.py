#!/usr/bin/env python3
"""Test HTTP telemetry ingestion endpoint."""
import os
import requests

API_URL = os.environ.get("HTTP_TEST_URL", "http://localhost:5000/api/v1/telemetry/http")
DEVICE_KEY = os.environ.get("HTTP_TEST_DEVICE_KEY", "")

payload = {
    "data": {
        "level": 72.5,
        "temperature": 24.3,
        "pressure": 1.18,
        "battery": 90,
    }
}

if not DEVICE_KEY:
    print("HTTP_TEST_DEVICE_KEY not set. Please export the provisioning key and rerun.")
    raise SystemExit(1)

print(f"Sending telemetry to {API_URL} ...")
response = requests.post(
    API_URL,
    json=payload,
    headers={"X-Device-Key": DEVICE_KEY}
)

print("Status:", response.status_code)
print("Response:", response.text)
