"""Firebase REST API service for tenant_id = 2 (using client credentials - no Admin SDK needed)."""

import logging
from typing import Dict, Any, List, Optional
import httpx
import json

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

# Firestore REST API base URL
FIRESTORE_API_BASE = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_CONFIG['projectId']}/databases/(default)/documents"


def get_document(collection_path: str, document_id: str) -> Optional[Dict[str, Any]]:
    """Get a document from Firestore using REST API (no auth required)."""
    try:
        url = f"{FIRESTORE_API_BASE}/{collection_path}/{document_id}"
        # No authentication - public read access
        
        with httpx.Client() as client:
            response = client.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            # Convert Firestore format to regular dict
            if "fields" in data:
                return _convert_firestore_fields(data["fields"])
            return None
    except Exception as e:
        logger.error(f"Firebase REST API error getting {collection_path}/{document_id}: {e}")
        return None


def list_documents(collection_path: str) -> List[Dict[str, Any]]:
    """List all documents in a collection using REST API (no auth required)."""
    try:
        url = f"{FIRESTORE_API_BASE}/{collection_path}"
        # No authentication - public read access
        
        with httpx.Client() as client:
            response = client.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            documents = []
            for doc in data.get("documents", []):
                doc_id = doc["name"].split("/")[-1]
                doc_data = _convert_firestore_fields(doc.get("fields", {}))
                doc_data["_id"] = doc_id
                documents.append(doc_data)
            
            return documents
    except Exception as e:
        logger.error(f"Firebase REST API error listing {collection_path}: {e}")
        return []


def _convert_firestore_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Firestore field format to regular Python dict."""
    result = {}
    for key, value in fields.items():
        if "stringValue" in value:
            result[key] = value["stringValue"]
        elif "integerValue" in value:
            result[key] = int(value["integerValue"])
        elif "doubleValue" in value:
            result[key] = float(value["doubleValue"])
        elif "booleanValue" in value:
            result[key] = value["booleanValue"]
        elif "mapValue" in value:
            result[key] = _convert_firestore_fields(value["mapValue"].get("fields", {}))
        elif "arrayValue" in value:
            result[key] = [
                _convert_firestore_fields(item.get("mapValue", {}).get("fields", {}))
                if "mapValue" in item else item.get("stringValue", "")
                for item in value["arrayValue"].get("values", [])
            ]
        elif "timestampValue" in value:
            result[key] = value["timestampValue"]
        elif "nullValue" in value:
            result[key] = None
    return result


def get_tenant_data(tenant_id: int, collection: str) -> Optional[Dict[str, Any]]:
    """Get pre-computed data from Firebase for tenant."""
    return get_document(f"tenants/{tenant_id}/{collection}", "data")


def get_metrics(tenant_id: int) -> Optional[Dict[str, Any]]:
    """Get metrics from Firebase."""
    return get_tenant_data(tenant_id, "metrics")


def get_devices(tenant_id: int, page: int = 1) -> Optional[Dict[str, Any]]:
    """Get devices from Firebase - reads device_id and location from Firebase."""
    try:
        # Try getting from pre-computed data document first
        data = get_tenant_data(tenant_id, "devices")
        if data and "devices" in data:
            devices = data["devices"]
        else:
            # Try reading from devices collection
            devices_list = list_documents(f"tenants/{tenant_id}/devices")
            devices = []
            for doc in devices_list:
                device_data = {k: v for k, v in doc.items() if not k.startswith("_")}
                if "device_id" not in device_data:
                    device_data["device_id"] = doc.get("_id", "")
                devices.append(device_data)
        
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


def get_devices_with_location(tenant_id: int) -> List[Dict[str, Any]]:
    """Get devices with device_id and location from Firebase."""
    try:
        devices_list = list_documents(f"tenants/{tenant_id}/devices")
        
        result = []
        for doc in devices_list:
            device_data = {k: v for k, v in doc.items() if not k.startswith("_")}
            if "device_id" not in device_data:
                device_data["device_id"] = doc.get("_id", "")
            result.append(device_data)
        
        logger.info(f"✅ Retrieved {len(result)} devices with location from Firebase for tenant {tenant_id}")
        return result
    except Exception as e:
        logger.error(f"Firebase REST API error getting devices with location for tenant {tenant_id}: {e}", exc_info=True)
        return []

