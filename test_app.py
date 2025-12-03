#!/usr/bin/env python3
"""Test FastAPI application structure."""
import sys

def test_app_structure():
    """Test that the FastAPI app can be created and has correct routes."""
    print("Testing FastAPI application structure...")
    
    try:
        from main import app
        print("  ✓ FastAPI app imported successfully")
        
        # Check app attributes
        assert hasattr(app, 'routes'), "App should have routes"
        print(f"  ✓ App has {len(app.routes)} routes")
        
        # Check for expected routes
        route_paths = [route.path for route in app.routes]
        assert "/" in route_paths, "Root route should exist"
        print("  ✓ Root route exists")
        
        assert "/health" in route_paths, "Health route should exist"
        print("  ✓ Health route exists")
        
        assert "/api/v1/telemetry/http" in route_paths, "Telemetry HTTP route should exist"
        print("  ✓ Telemetry HTTP route exists")
        
        assert "/api/v1/telemetry/health" in route_paths, "Telemetry health route should exist"
        print("  ✓ Telemetry health route exists")
        
        # Check app metadata
        assert app.title == "IoT Platform - Ingestion Gateway"
        print(f"  ✓ App title: {app.title}")
        
        print("\n✅ FastAPI application structure test passed!")
        print("\nNote: To test with actual HTTP requests, start the server:")
        print("  python3 main.py")
        print("  Then use: curl http://localhost:5000/health")
        return True
        
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_app_structure()
    sys.exit(0 if success else 1)

