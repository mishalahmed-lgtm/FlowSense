#!/usr/bin/env python3
"""
Comcore DLMS meter simulator for device COMCORE-DLMS-001.

- Logs in to the admin API using the configured admin email/password.
- Looks up the provisioning key for COMCORE-DLMS-001.
- Sends HTTP telemetry every ~20 seconds (~3 messages per minute).

This simulates key DLMS-style instantaneous and energy values coming
from a DCU into your platform so you can:
- Build rules and dashboards on DLMS voltages, currents, energies, and events.
"""

import os
import random
import time
from datetime import datetime, timezone

import requests


API_BASE = os.environ.get("IOT_API_BASE", "http://localhost:5000/api/v1")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@flowsense.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "AdminFlow")
DEVICE_ID = os.environ.get("COMCORE_DLMS_DEVICE_ID", "COMCORE-DLMS-001")


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
    """
    Generate fake Comcore DLMS instantaneous and energy telemetry.

    The field names line up with the Comcore DLMS device type schema:
    - voltage_a/voltage_b/voltage_c (V)
    - current_a/current_b/current_c (A)
    - power_factor_a/b/c
    - frequency_hz
    - active_energy_import_total, active_energy_export_total (kWh)
    - reactive_energy_import_total, reactive_energy_export_total (kvarh)
    - event_code, event_type (basic event simulation)
    - dcu_address, meter_time, heartbeat_rssi
    """
    # Voltages ~230V
    voltage_a = round(random.uniform(225.0, 235.0), 1)
    voltage_b = round(random.uniform(225.0, 235.0), 1)
    voltage_c = round(random.uniform(225.0, 235.0), 1)

    # Currents 0–40A
    current_a = round(random.uniform(5.0, 30.0), 2)
    current_b = round(random.uniform(5.0, 30.0), 2)
    current_c = round(random.uniform(5.0, 30.0), 2)

    # Power factor
    power_factor_a = round(random.uniform(0.90, 0.99), 3)
    power_factor_b = round(random.uniform(0.90, 0.99), 3)
    power_factor_c = round(random.uniform(0.90, 0.99), 3)

    # Frequency
    frequency_hz = round(random.uniform(49.8, 50.2), 2)

    # Energies (kWh/kvarh) – steadily climbing
    active_energy_import_total = round(random.uniform(500.0, 520.0), 3)
    active_energy_export_total = round(random.uniform(0.0, 5.0), 3)
    reactive_energy_import_total = round(random.uniform(50.0, 60.0), 3)
    reactive_energy_export_total = round(random.uniform(0.0, 5.0), 3)

    # Simple event model: mostly no event, sometimes voltage sag/swell
    event_options = [
        (0, "none"),
        (200, "voltage_under_limit"),
        (204, "voltage_over_limit"),
        (59, "manual_disconnect"),
        (62, "remote_disconnect"),
    ]
    event_code, event_type = random.choices(event_options, weights=[0.8, 0.05, 0.05, 0.05, 0.05])[0]

    # DCU address and RSSI
    dcu_address = "00010001"
    heartbeat_rssi = random.randint(-95, -65)  # dBm

    meter_time = datetime.now(timezone.utc).isoformat()

    return {
        "data": {
            "voltage_a": voltage_a,
            "voltage_b": voltage_b,
            "voltage_c": voltage_c,
            "current_a": current_a,
            "current_b": current_b,
            "current_c": current_c,
            "power_factor_a": power_factor_a,
            "power_factor_b": power_factor_b,
            "power_factor_c": power_factor_c,
            "frequency_hz": frequency_hz,
            "active_energy_import_total": active_energy_import_total,
            "active_energy_export_total": active_energy_export_total,
            "reactive_energy_import_total": reactive_energy_import_total,
            "reactive_energy_export_total": reactive_energy_export_total,
            "event_code": event_code,
            "event_type": event_type,
            "dcu_address": dcu_address,
            "meter_time": meter_time,
            "heartbeat_rssi": heartbeat_rssi,
            "source": "comcore_dlms_sim",
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

    interval_seconds = 20  # ~3 messages per minute
    print(f"Starting Comcore DLMS meter simulation every {interval_seconds} seconds...")

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


