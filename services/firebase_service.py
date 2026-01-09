"""Firebase service for tenant_id = 2 (demo only - isolated)."""

import logging
from typing import Dict, Any, List, Optional
import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

# Firebase config (from user)
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyAZ39e477sCTQqhgsxXeIWCSo5ijGJh5xQ",
    "authDomain": "flowset-143fc.firebaseapp.com",
    "projectId": "flowset-143fc",
    "storageBucket": "flowset-143fc.firebasestorage.app",
    "messagingSenderId": "799211858991",
    "appId": "1:799211858991:web:f7e63c89332e729fcdaada",
    "measurementId": "G-HJ81T0FK9W"
}

# Firebase client (initialized on first use)
_firestore_client: Optional[firestore.Client] = None


def get_firestore_client() -> firestore.Client:
    """Get or initialize Firebase Firestore client using client credentials."""
    global _firestore_client
    
    if _firestore_client is None:
        import os
        
        if not firebase_admin._apps:
            # Try service account first (if provided)
            firebase_creds_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
            firebase_creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
            
            if firebase_creds_path and os.path.exists(firebase_creds_path):
                # Option 1: Service account JSON file
                try:
                    cred = credentials.Certificate(firebase_creds_path)
                    firebase_admin.initialize_app(cred)
                    logger.info(f"✅ Firebase initialized from service account file: {firebase_creds_path}")
                except Exception as e:
                    logger.warning(f"Service account file failed: {e}, trying client credentials...")
                    # Fall through to client credentials
            elif firebase_creds_json:
                # Option 2: Service account JSON from env var
                try:
                    import json
                    import tempfile
                    creds_dict = json.loads(firebase_creds_json)
                    if creds_dict.get("type") == "service_account":
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                            json.dump(creds_dict, f)
                            temp_path = f.name
                        cred = credentials.Certificate(temp_path)
                        firebase_admin.initialize_app(cred)
                        logger.info("✅ Firebase initialized from service account JSON")
                    else:
                        raise ValueError("Not a service account JSON")
                except Exception as e:
                    logger.warning(f"Service account JSON failed: {e}, trying client credentials...")
                    # Fall through to client credentials
            
            # Option 3: Use client credentials (project ID only - requires Application Default Credentials)
            if not firebase_admin._apps:
                try:
                    # Initialize with just project ID (requires GOOGLE_APPLICATION_CREDENTIALS or gcloud auth)
                    firebase_admin.initialize_app(options={"projectId": FIREBASE_CONFIG["projectId"]})
                    logger.info(f"✅ Firebase initialized with client credentials for project: {FIREBASE_CONFIG['projectId']}")
                except Exception as e:
                    logger.error(f"❌ Firebase initialization failed: {e}")
                    logger.error("Options:")
                    logger.error("  1. Set GOOGLE_APPLICATION_CREDENTIALS to service account JSON path")
                    logger.error("  2. Run: gcloud auth application-default login")
                    logger.error("  3. Or provide FIREBASE_CREDENTIALS_PATH with service account JSON")
                    raise
        
        _firestore_client = firestore.client()
        logger.info(f"✅ Firebase Firestore client ready for project: {FIREBASE_CONFIG['projectId']}")
    
    return _firestore_client


def get_tenant_data(tenant_id: int, collection: str) -> Optional[Dict[str, Any]]:
    """Get pre-computed data from Firebase for tenant."""
    try:
        db = get_firestore_client()
        doc_ref = db.collection("tenants").document(str(tenant_id)).collection(collection).document("data")
        doc = doc_ref.get()
        
        if doc.exists:
            return doc.to_dict()
        else:
            logger.warning(f"Firebase document not found: tenants/{tenant_id}/{collection}/data")
            return None
    except Exception as e:
        logger.error(f"Firebase error getting {collection} for tenant {tenant_id}: {e}", exc_info=True)
        return None


def get_devices_with_location(tenant_id: int) -> List[Dict[str, Any]]:
    """Get devices with device_id and location from Firebase."""
    try:
        db = get_firestore_client()
        
        # Get devices collection
        devices_ref = db.collection("tenants").document(str(tenant_id)).collection("devices")
        devices = devices_ref.stream()
        
        result = []
        for device_doc in devices:
            device_data = device_doc.to_dict()
            if device_data:
                # Extract device_id and location
                result.append({
                    "device_id": device_data.get("device_id") or device_doc.id,
                    "latitude": device_data.get("latitude"),
                    "longitude": device_data.get("longitude"),
                    "location": device_data.get("location", {}),
                    **device_data  # Include all other fields
                })
        
        logger.info(f"✅ Retrieved {len(result)} devices with location from Firebase for tenant {tenant_id}")
        return result
    except Exception as e:
        logger.error(f"Firebase error getting devices with location for tenant {tenant_id}: {e}", exc_info=True)
        return []


def get_metrics(tenant_id: int) -> Optional[Dict[str, Any]]:
    """Get metrics from Firebase."""
    return get_tenant_data(tenant_id, "metrics")


def get_devices(tenant_id: int, page: int = 1) -> Optional[Dict[str, Any]]:
    """Get devices from Firebase - reads device_id and location from Firebase."""
    try:
        # Option 1: Try getting from pre-computed data document
        data = get_tenant_data(tenant_id, "devices")
        if data:
            devices = data.get("devices", [])
        else:
            # Option 2: Read directly from devices collection
            devices = get_devices_with_location(tenant_id)
        
        if not devices:
            return None
        
        # Handle pagination
        limit = 50
        offset = (page - 1) * limit
        paginated_devices = devices[offset:offset + limit]
        
        return {
            "devices": paginated_devices,
            "total": len(devices),
            "page": page,
            "limit": limit,
            "total_pages": (len(devices) + limit - 1) // limit,
        }
    except Exception as e:
        logger.error(f"Error getting devices from Firebase: {e}", exc_info=True)
        return None


def get_health(tenant_id: int) -> Optional[Dict[str, Any]]:
    """Get health data from Firebase."""
    return get_tenant_data(tenant_id, "health")


def get_environmental(tenant_id: int) -> Optional[Dict[str, Any]]:
    """Get environmental data from Firebase."""
    return get_tenant_data(tenant_id, "environmental")


def get_alerts(tenant_id: int) -> Optional[List[Dict[str, Any]]]:
    """Get alerts from Firebase."""
    data = get_tenant_data(tenant_id, "alerts")
    if data:
        return data.get("alerts", [])
    return []

