#!/usr/bin/env python3
"""Test script to validate all imports and basic code structure."""
import sys

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        print("  ✓ Importing config...")
        import config
        
        print("  ✓ Importing database...")
        import database
        
        print("  ✓ Importing models...")
        import models
        
        print("  ✓ Importing auth...")
        import auth
        
        print("  ✓ Importing kafka_producer...")
        import kafka_producer
        
        print("  ✓ Importing mqtt_client...")
        import mqtt_client
        
        print("  ✓ Importing routers.telemetry...")
        from routers import telemetry
        
        print("\n✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    try:
        from config import settings
        print(f"  ✓ Database URL: {settings.database_url[:30]}...")
        print(f"  ✓ Kafka Bootstrap: {settings.kafka_bootstrap_servers}")
        print(f"  ✓ Kafka Topic: {settings.kafka_raw_telemetry_topic}")
        print(f"  ✓ MQTT Broker: {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")
        print(f"  ✓ API Prefix: {settings.api_v1_prefix}")
        return True
    except Exception as e:
        print(f"  ❌ Config error: {e}")
        return False

def test_models():
    """Test model definitions."""
    print("\nTesting models...")
    try:
        from models import DeviceType, Tenant, Device, ProvisioningKey
        print("  ✓ DeviceType model")
        print("  ✓ Tenant model")
        print("  ✓ Device model")
        print("  ✓ ProvisioningKey model")
        return True
    except Exception as e:
        print(f"  ❌ Models error: {e}")
        return False

def test_auth():
    """Test auth module."""
    print("\nTesting auth module...")
    try:
        from auth import verify_device_key, api_key_header
        print("  ✓ verify_device_key function")
        print("  ✓ api_key_header security")
        return True
    except Exception as e:
        print(f"  ❌ Auth error: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("IoT Platform - Code Validation Test")
    print("=" * 60)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Models", test_models()))
    results.append(("Auth", test_auth()))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✅ All code validation tests passed!")
        print("\nNote: To test with Docker services, run:")
        print("  sudo docker-compose up -d")
        print("  sudo docker-compose exec backend python init_db.py")
        print("  python3 test_ingestion.py <provisioning_key>")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

