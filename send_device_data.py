#!/usr/bin/env python3
"""Send telemetry data for device 0101BDDDEA5E4D03 every minute"""
import requests
import time
import random
from datetime import datetime, timezone

DEVICE_ID = "0101BDDDEA5E4D03"
API_BASE_URL = "https://flowsense-772d.onrender.com"
API_KEY = "simulator_key_1767811700"

print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting device data sender...")
print(f"[{datetime.now().strftime('%H:%M:%S')}] Device ID: {DEVICE_ID}")
print(f"[{datetime.now().strftime('%H:%M:%S')}] API Base URL: {API_BASE_URL}")
print(f"[{datetime.now().strftime('%H:%M:%S')}] API Key: {API_KEY[:20]}...")
print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Ready! Sending data every 60 seconds...\n")

iteration = 0
while True:
    iteration += 1
    telemetry = {
        "device_id": DEVICE_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "level": round(random.uniform(20, 90), 2),
            "temperature": round(random.uniform(15, 35), 2),
            "battery": random.randint(50, 100),
            "pressure": round(random.uniform(1, 3), 2),
            "dis_cm": round(random.uniform(10, 50), 2)
        }
    }
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{iteration}] Sending telemetry: level={telemetry['data']['level']}, temp={telemetry['data']['temperature']}°C, battery={telemetry['data']['battery']}%", flush=True)
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/external/data",
            headers={"X-API-Key": API_KEY},
            json=telemetry,
            timeout=30
        )
        if response.status_code in [200, 202]:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{iteration}] ✅ SUCCESS - Data sent for {DEVICE_ID} (Status: {response.status_code})", flush=True)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{iteration}] ❌ FAILED - Status: {response.status_code}, Response: {response.text}", flush=True)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{iteration}] ❌ ERROR - {type(e).__name__}: {e}", flush=True)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{iteration}] Waiting 60 seconds...\n", flush=True)
    time.sleep(60)

