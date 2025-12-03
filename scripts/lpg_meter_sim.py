#!/usr/bin/env python3
"""
Simple LPG meter simulator for device LPG-METER-001.

- Logs in to the admin API using the configured admin email/password.
- Looks up the provisioning key for LPG-METER-001.
- Sends HTTP telemetry every few seconds so the Live Dashboard shows real data.
"""

import os
import random
import time

import requests


API_BASE = os.environ.get("IOT_API_BASE", "http://localhost:5000/api/v1")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DEVICE_ID = os.environ.get("LPG_DEVICE_ID", "LPG-METER-001")


def get_admin_token() -> str:
  """Authenticate as admin and return JWT access token."""
  resp = requests.post(
    f"{API_BASE}/admin/login",
    json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    timeout=5,
  )
  resp.raise_for_status()
  data = resp.json()
  return data["access_token"]


def get_device_key(token: str, device_id: str) -> str:
  """Fetch provisioning key for the given device_id via admin API."""
  resp = requests.get(
    f"{API_BASE}/admin/devices",
    headers={"Authorization": f"Bearer {token}"},
    timeout=5,
  )
  resp.raise_for_status()
  devices = resp.json()
  for dev in devices:
    if dev.get("device_id") == device_id:
      provisioning = dev.get("provisioning_key") or {}
      key = provisioning.get("key")
      if not key:
        raise RuntimeError(f"Device {device_id} has no provisioning key.")
      return key
  raise RuntimeError(f"Device {device_id} not found in admin devices list.")


def generate_payload():
  """Generate fake LPG tank telemetry."""
  level = round(random.uniform(10.0, 95.0), 1)
  temperature = round(random.uniform(15.0, 40.0), 1)
  pressure = round(random.uniform(0.8, 1.5), 2)
  battery = random.randint(40, 100)
  return {
    "data": {
      "level": level,
      "temperature": temperature,
      "pressure": pressure,
      "battery": battery,
      "source": "lpg_meter_sim",
    }
  }


def main():
  print(f"Using API base: {API_BASE}")
  print(f"Admin user: {ADMIN_EMAIL}")
  print(f"Target device_id: {DEVICE_ID}")

  token = get_admin_token()
  print("Obtained admin token.")
  device_key = get_device_key(token, DEVICE_ID)
  print(f"Resolved provisioning key for {DEVICE_ID}.")

  headers = {
    "Content-Type": "application/json",
    "X-Device-Key": device_key,
  }
  url = f"{API_BASE}/telemetry/http"

  interval_seconds = 5
  print(f"Starting LPG meter simulation every {interval_seconds} seconds...")

  while True:
    payload = generate_payload()
    try:
      resp = requests.post(url, json=payload, headers=headers, timeout=5)
      print(f"Sent for {DEVICE_ID}: {payload['data']} -> {resp.status_code}")
    except Exception as exc:
      print(f"Error sending telemetry: {exc}")
    time.sleep(interval_seconds)


if __name__ == "__main__":
  main()


