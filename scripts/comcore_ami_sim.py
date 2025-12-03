#!/usr/bin/env python3
"""
Simple Comcore AMI electricity meter simulator for device COMCORE-METER-001.

- Logs in to the admin API using the configured admin email/password.
- Looks up the provisioning key for COMCORE-METER-001.
- Sends HTTP telemetry every ~20 seconds (~3 messages per minute).

This does NOT talk to the real Comcore AMI API – it just simulates
the payload shape you would get from that system, so you can:
- Build rules on voltage, current, energy, power factor, relay status, etc.
- Build dashboards (gauges, charts) for this meter.
"""

import os
import random
import time
from datetime import datetime, timezone

import requests


API_BASE = os.environ.get("IOT_API_BASE", "http://localhost:5000/api/v1")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DEVICE_ID = os.environ.get("COMCORE_DEVICE_ID", "COMCORE-METER-001")


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
    Generate fake Comcore AMI realtime telemetry.

    Fields are aligned with the OBIS list and intermediate DB tables:
    - Energies (kWh / kvarh)
    - Voltages, currents, power factors, powers
    - Frequency
    - Relay status
    """
    # Energies slowly accumulate
    total_active_energy = round(random.uniform(1000.0, 1100.0), 3)
    total_active_energy_plus = total_active_energy
    total_active_energy_minus = 0.0
    total_reactive_energy = round(random.uniform(100.0, 130.0), 3)
    total_reactive_energy_plus = total_reactive_energy
    total_reactive_energy_minus = 0.0

    # Voltages (typical 3-phase 230/400V system)
    voltage_l1 = round(random.uniform(225.0, 235.0), 1)
    voltage_l2 = round(random.uniform(225.0, 235.0), 1)
    voltage_l3 = round(random.uniform(225.0, 235.0), 1)

    # Currents (A)
    current_l1 = round(random.uniform(5.0, 25.0), 2)
    current_l2 = round(random.uniform(5.0, 25.0), 2)
    current_l3 = round(random.uniform(5.0, 25.0), 2)

    # Frequency (Hz)
    frequency = round(random.uniform(49.8, 50.2), 2)

    # Power factor
    power_factor_total = round(random.uniform(0.90, 0.99), 3)
    power_factor_l1 = round(random.uniform(0.90, 0.99), 3)
    power_factor_l2 = round(random.uniform(0.90, 0.99), 3)
    power_factor_l3 = round(random.uniform(0.90, 0.99), 3)

    # Active power (kW)
    active_power_total = round(
        (voltage_l1 * current_l1 + voltage_l2 * current_l2 + voltage_l3 * current_l3)
        * power_factor_total
        / 1000.0,
        3,
    )
    active_power_l1 = round(voltage_l1 * current_l1 * power_factor_l1 / 1000.0, 3)
    active_power_l2 = round(voltage_l2 * current_l2 * power_factor_l2 / 1000.0, 3)
    active_power_l3 = round(voltage_l3 * current_l3 * power_factor_l3 / 1000.0, 3)

    # Reactive power (kvar), approximate using sqrt(1-pf^2)
    def reactive_from_pf(pf, p_kw):
        try:
            q_over_s = (1.0 - pf * pf) ** 0.5
            return round(p_kw * q_over_s / pf, 3)
        except Exception:
            return 0.0

    reactive_power_total = reactive_from_pf(power_factor_total, active_power_total)
    reactive_power_l1 = reactive_from_pf(power_factor_l1, active_power_l1)
    reactive_power_l2 = reactive_from_pf(power_factor_l2, active_power_l2)
    reactive_power_l3 = reactive_from_pf(power_factor_l3, active_power_l3)

    # Relay status: simulate mostly ON, sometimes OFF
    relay_status = random.choices(["on", "off"], weights=[0.9, 0.1])[0]

    meter_time = datetime.now(timezone.utc).isoformat()

    return {
        "data": {
            "total_active_energy": total_active_energy,
            "total_active_energy_plus": total_active_energy_plus,
            "total_active_energy_minus": total_active_energy_minus,
            "total_reactive_energy": total_reactive_energy,
            "total_reactive_energy_plus": total_reactive_energy_plus,
            "total_reactive_energy_minus": total_reactive_energy_minus,
            "voltage_l1": voltage_l1,
            "voltage_l2": voltage_l2,
            "voltage_l3": voltage_l3,
            "current_l1": current_l1,
            "current_l2": current_l2,
            "current_l3": current_l3,
            "frequency": frequency,
            "power_factor_total": power_factor_total,
            "power_factor_l1": power_factor_l1,
            "power_factor_l2": power_factor_l2,
            "power_factor_l3": power_factor_l3,
            "active_power_total": active_power_total,
            "active_power_l1": active_power_l1,
            "active_power_l2": active_power_l2,
            "active_power_l3": active_power_l3,
            "reactive_power_total": reactive_power_total,
            "reactive_power_l1": reactive_power_l1,
            "reactive_power_l2": reactive_power_l2,
            "reactive_power_l3": reactive_power_l3,
            "meter_time": meter_time,
            "relay_status": relay_status,
            "source": "comcore_ami_sim",
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
    print(f"Starting Comcore AMI meter simulation every {interval_seconds} seconds...")

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


