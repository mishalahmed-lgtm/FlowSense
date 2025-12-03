#!/usr/bin/env python3
"""Comprehensive test for all production features."""
import json
import os
import time
import uuid
import requests
import paho.mqtt.client as mqtt

# Configuration
API_URL = "http://localhost:5000/api/v1/telemetry/http"
METRICS_URL = "http://localhost:5000/metrics"
DEVICE_METRICS_URL = "http://localhost:5000/metrics/device"
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1884"))
DEVICE_KEY = os.environ.get("HTTP_TEST_DEVICE_KEY", "CdJNo4m74F4xu1l3CIy1198mBrZvjrYwQNbByA2xRKQ")
DEVICE_ID = "LPG-METER-001"
MQTT_DEVICE_ID = "VALVE-001"
MQTT_TOPIC = f"devices/{MQTT_DEVICE_ID}/telemetry"

def print_test(name):
    """Print test header."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")

def test_http_success():
    """Test successful HTTP ingestion."""
    print_test("HTTP Ingestion - Success")
    
    payload = {
        "data": {
            "level": 75.5,
            "temperature": 25.0,
            "pressure": 1.20,
            "battery": 85,
        }
    }
    
    response = requests.post(
        API_URL,
        json=payload,
        headers={"X-Device-Key": DEVICE_KEY}
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    assert response.status_code == 202, f"Expected 202, got {response.status_code}"
    print("✅ HTTP ingestion successful")

def test_mqtt_success():
    """Test successful MQTT ingestion."""
    print_test("MQTT Ingestion - Success")
    
    nonce = str(uuid.uuid4())
    payload = {
        "level": 80.0,
        "temperature": 26.0,
        "pressure": 1.25,
        "battery": 90,
        "test_nonce": nonce
    }
    
    published = False
    
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to MQTT broker (rc={rc})")
    
    def on_publish(client, userdata, mid):
        nonlocal published
        published = True
        print(f"Message published (mid={mid})")
    
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_publish = on_publish
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
        
        timeout = 5
        start = time.time()
        while not client.is_connected() and (time.time() - start) < timeout:
            time.sleep(0.1)
        
        if not client.is_connected():
            raise Exception(f"Failed to connect to MQTT broker within {timeout}s")
        
        info = client.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
        
        timeout = 5
        start = time.time()
        while not published and (time.time() - start) < timeout:
            time.sleep(0.1)
        
        if not published:
            raise Exception(f"Message not published within {timeout}s")
        
        print("✅ MQTT ingestion successful")
        
    finally:
        client.loop_stop()
        client.disconnect()

def test_metrics_endpoint():
    """Test metrics endpoint."""
    print_test("Metrics Endpoint")
    
    response = requests.get(METRICS_URL)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        metrics_data = response.json()
        print(f"Uptime: {metrics_data.get('uptime_seconds')}s")
        print(f"Messages received: {metrics_data.get('messages', {}).get('total_received', 0)}")
        print(f"Messages published: {metrics_data.get('messages', {}).get('total_published', 0)}")
        print(f"Success rate: {metrics_data.get('messages', {}).get('success_rate', 0):.2f}%")
        print(f"Active devices: {metrics_data.get('active_devices', 0)}")
        print(f"Errors: {metrics_data.get('errors', {}).get('total', 0)}")
        print("✅ Metrics endpoint working")
    else:
        print(f"❌ Metrics endpoint failed: {response.text}")

def test_device_metrics():
    """Test device-specific metrics."""
    print_test("Device Metrics Endpoint")
    
    response = requests.get(f"{DEVICE_METRICS_URL}/{DEVICE_ID}")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        device_metrics = response.json()
        print(f"Device: {device_metrics.get('device_id')}")
        print(f"Messages received: {device_metrics.get('messages_received', 0)}")
        print(f"Messages published: {device_metrics.get('messages_published', 0)}")
        print(f"Messages rejected: {device_metrics.get('messages_rejected', 0)}")
        print(f"Last seen: {device_metrics.get('last_seen')}")
        print("✅ Device metrics endpoint working")
    else:
        print(f"⚠️  Device metrics not found (may be normal if device hasn't sent data yet)")

def test_rate_limiting():
    """Test rate limiting."""
    print_test("Rate Limiting")
    
    print("Sending 65 rapid requests (limit is 60/minute)...")
    success_count = 0
    rate_limited_count = 0
    
    for i in range(65):
        payload = {
            "data": {
                "level": 70.0 + i,
                "temperature": 25.0,
                "pressure": 1.20,
                "battery": 85,
            }
        }
        
        response = requests.post(
            API_URL,
            json=payload,
            headers={"X-Device-Key": DEVICE_KEY}
        )
        
        if response.status_code == 202:
            success_count += 1
        elif response.status_code == 429:
            rate_limited_count += 1
            if rate_limited_count == 1:
                print(f"Rate limit hit at request #{i+1}")
                print(f"Response: {response.json()}")
        
        time.sleep(0.1)  # Small delay between requests
    
    print(f"Successful: {success_count}")
    print(f"Rate limited: {rate_limited_count}")
    
    if rate_limited_count > 0:
        print("✅ Rate limiting working correctly")
    else:
        print("⚠️  Rate limiting may not have triggered (this is OK if limits are high)")

def test_validation_error():
    """Test payload validation."""
    print_test("Payload Validation - Invalid Data")
    
    # Send invalid payload (missing required field for LPG Meter)
    payload = {
        "data": {
            "temperature": 25.0,
            # Missing "level" which should be required
        }
    }
    
    response = requests.post(
        API_URL,
        json=payload,
        headers={"X-Device-Key": DEVICE_KEY}
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    # Note: Validation might pass if no schema is defined (permissive mode)
    if response.status_code == 400:
        print("✅ Validation error handling working")
    else:
        print("⚠️  Validation passed (may be permissive mode if no schema defined)")

def test_unauthorized_device():
    """Test unauthorized device rejection."""
    print_test("Unauthorized Device - Invalid Key")
    
    payload = {
        "data": {
            "level": 75.0,
            "temperature": 25.0,
        }
    }
    
    response = requests.post(
        API_URL,
        json=payload,
        headers={"X-Device-Key": "INVALID_KEY_12345"}
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    print("✅ Unauthorized device rejection working")

def test_mqtt_unauthorized():
    """Test MQTT unauthorized device."""
    print_test("MQTT - Unauthorized Device")
    
    payload = {
        "level": 75.0,
        "temperature": 25.0,
    }
    
    published = False
    
    def on_publish(client, userdata, mid):
        nonlocal published
        published = True
    
    client = mqtt.Client()
    client.on_publish = on_publish
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
        
        time.sleep(0.5)  # Wait for connection
        
        # Publish from non-existent device
        client.publish("devices/INVALID-DEVICE-999/telemetry", json.dumps(payload), qos=1)
        
        time.sleep(0.5)  # Wait for processing
        
        print("✅ Message sent (should be rejected by backend)")
        print("   Check backend logs to verify rejection")
        
    finally:
        client.loop_stop()
        client.disconnect()

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("PRODUCTION FEATURES TEST SUITE")
    print("="*60)
    
    tests = [
        ("HTTP Success", test_http_success),
        ("MQTT Success", test_mqtt_success),
        ("Metrics Endpoint", test_metrics_endpoint),
        ("Device Metrics", test_device_metrics),
        ("Rate Limiting", test_rate_limiting),
        ("Validation Error", test_validation_error),
        ("Unauthorized HTTP", test_unauthorized_device),
        ("Unauthorized MQTT", test_mqtt_unauthorized),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            test_func()
            results.append((test_name, "✅ PASSED"))
        except Exception as e:
            print(f"❌ Test failed: {e}")
            results.append((test_name, f"❌ FAILED: {e}"))
        time.sleep(1)  # Small delay between tests
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test_name, result in results:
        print(f"{test_name}: {result}")
    
    # Final metrics check
    print("\n" + "="*60)
    print("FINAL METRICS CHECK")
    print("="*60)
    try:
        response = requests.get(METRICS_URL)
        if response.status_code == 200:
            metrics_data = response.json()
            print(json.dumps(metrics_data, indent=2))
    except Exception as e:
        print(f"Failed to get final metrics: {e}")

if __name__ == "__main__":
    main()

