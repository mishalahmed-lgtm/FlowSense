#!/usr/bin/env python3
"""
Valve Controller simulator for device VALVE-001.

- Logs in to the admin API using the configured admin email/password.
- Looks up the provisioning key for VALVE-001.
- Sends MQTT telemetry every 20 seconds with valve state and battery level.
"""

import os
import random
import time

import paho.mqtt.client as mqtt
import requests


API_BASE = os.environ.get("IOT_API_BASE", "http://localhost:5000/api/v1")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DEVICE_ID = os.environ.get("VALVE_DEVICE_ID", "VALVE-001")
# Use Docker service name if running in container, otherwise localhost
# Check if we're in Docker by looking for common env vars or use service name
MQTT_BROKER = os.environ.get("MQTT_BROKER", os.environ.get("MQTT_HOST", "mqtt-broker" if os.path.exists("/.dockerenv") else "localhost"))
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
INTERVAL = int(os.environ.get("VALVE_INTERVAL", "20"))  # seconds


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
    raise RuntimeError(f"Device {device_id} not found.")


def get_device_mqtt_config(token: str, device_id: str) -> dict:
    """Get MQTT topic and other config from device metadata."""
    resp = requests.get(
        f"{API_BASE}/admin/devices",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    resp.raise_for_status()
    devices = resp.json()
    for dev in devices:
        if dev.get("device_id") == device_id:
            metadata = dev.get("device_metadata") or {}
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)
            # Default to the format expected by the MQTT client: devices/{device_id}/telemetry
            topic = metadata.get("topic", f"devices/{device_id}/telemetry")
            return {"topic": topic}
    raise RuntimeError(f"Device {device_id} not found.")


def main():
    print(f"🔧 Valve Controller Simulator for {DEVICE_ID}")
    print(f"   Connecting to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
    
    # Get admin token and device key
    print("   Authenticating as admin...")
    token = get_admin_token()
    print("   ✓ Admin authenticated")
    
    print(f"   Fetching provisioning key for {DEVICE_ID}...")
    device_key = get_device_key(token, DEVICE_ID)
    print(f"   ✓ Provisioning key obtained")
    
    print(f"   Fetching MQTT config for {DEVICE_ID}...")
    mqtt_config = get_device_mqtt_config(token, DEVICE_ID)
    topic = mqtt_config["topic"]
    print(f"   ✓ MQTT topic: {topic}")
    
    # Initialize MQTT client
    client = mqtt.Client(client_id=DEVICE_ID)
    client.username_pw_set(DEVICE_ID, device_key)
    
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"   ✓ Connected to MQTT broker")
        else:
            print(f"   ✗ Failed to connect, return code {rc}")
            exit(1)
    
    client.on_connect = on_connect
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        
        # Initial state
        state = random.choice(["open", "closed"])
        battery = random.uniform(80.0, 100.0)
        
        print(f"\n📡 Starting telemetry transmission (every {INTERVAL} seconds)...")
        print(f"   Initial state: {state}, Battery: {battery:.1f}%")
        
        message_count = 0
        while True:
            # Simulate valve state changes (occasionally)
            if random.random() < 0.1:  # 10% chance to change state
                state = "closed" if state == "open" else "open"
                print(f"   🔄 Valve state changed to: {state}")
            
            # Battery slowly decreases
            battery = max(20.0, battery - random.uniform(0.1, 0.3))
            
            # Create payload
            payload = {
                "state": state,
                "battery": round(battery, 1),
            }
            
            # Publish to MQTT
            import json
            result = client.publish(topic, json.dumps(payload), qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                message_count += 1
                print(f"   [{message_count}] Published: state={state}, battery={battery:.1f}%")
            else:
                print(f"   ✗ Failed to publish message")
            
            time.sleep(INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping simulator...")
        client.loop_stop()
        client.disconnect()
        print("   ✓ Disconnected from MQTT broker")
    except Exception as e:
        print(f"\n   ✗ Error: {e}")
        client.loop_stop()
        client.disconnect()
        raise


if __name__ == "__main__":
    main()

