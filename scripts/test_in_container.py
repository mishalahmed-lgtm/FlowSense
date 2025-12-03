#!/usr/bin/env python3
"""Test production features from inside container."""
import json
import time
import uuid
import requests
import paho.mqtt.client as mqtt

# Configuration for container environment
API_URL = "http://localhost:5000/api/v1/telemetry/http"
METRICS_URL = "http://localhost:5000/metrics"
MQTT_HOST = "mqtt-broker"
MQTT_PORT = 1883
DEVICE_KEY = "CdJNo4m74F4xu1l3CIy1198mBrZvjrYwQNbByA2xRKQ"
DEVICE_ID = "LPG-METER-001"
MQTT_DEVICE_ID = "VALVE-001"

def test_http():
    """Test HTTP ingestion."""
    print("\n[TEST] HTTP Ingestion")
    payload = {"data": {"level": 75.0, "temperature": 25.0, "pressure": 1.20, "battery": 85}}
    r = requests.post(API_URL, json=payload, headers={"X-Device-Key": DEVICE_KEY}, timeout=5)
    print(f"  Status: {r.status_code}")
    print(f"  Response: {r.json()}")
    return r.status_code == 202

def test_mqtt():
    """Test MQTT ingestion."""
    print("\n[TEST] MQTT Ingestion")
    payload = {"level": 80.0, "temperature": 26.0, "pressure": 1.25, "battery": 90}
    
    published = False
    def on_connect(c, u, f, rc):
        if rc == 0:
            print(f"  Connected to MQTT broker")
    def on_publish(c, u, mid):
        nonlocal published
        published = True
    
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_publish = on_publish
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    time.sleep(0.5)
    
    client.publish(f"devices/{MQTT_DEVICE_ID}/telemetry", json.dumps(payload), qos=1)
    time.sleep(0.5)
    
    client.loop_stop()
    client.disconnect()
    print(f"  Published: {published}")
    return published

def test_metrics():
    """Test metrics endpoint."""
    print("\n[TEST] Metrics Endpoint")
    r = requests.get(METRICS_URL, timeout=5)
    if r.status_code == 200:
        m = r.json()
        print(f"  Uptime: {m.get('uptime_seconds')}s")
        print(f"  Messages received: {m.get('messages', {}).get('total_received', 0)}")
        print(f"  Messages published: {m.get('messages', {}).get('total_published', 0)}")
        print(f"  Success rate: {m.get('messages', {}).get('success_rate', 0):.2f}%")
        return True
    return False

def test_unauthorized():
    """Test unauthorized device."""
    print("\n[TEST] Unauthorized Device")
    r = requests.post(API_URL, json={"data": {"level": 75.0}}, headers={"X-Device-Key": "INVALID"}, timeout=5)
    print(f"  Status: {r.status_code} (expected 401)")
    return r.status_code == 401

def main():
    print("="*60)
    print("PRODUCTION FEATURES TEST")
    print("="*60)
    
    results = []
    results.append(("HTTP Ingestion", test_http()))
    time.sleep(1)
    results.append(("MQTT Ingestion", test_mqtt()))
    time.sleep(1)
    results.append(("Metrics", test_metrics()))
    time.sleep(1)
    results.append(("Unauthorized", test_unauthorized()))
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    for name, passed in results:
        print(f"{name}: {'✅ PASS' if passed else '❌ FAIL'}")
    
    print("\nFinal metrics:")
    test_metrics()

if __name__ == "__main__":
    main()

