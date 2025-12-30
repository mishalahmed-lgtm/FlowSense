#!/usr/bin/env python3
"""Script to sync installations from external API to Flowset tenant."""
import requests
import json
import sys
from typing import List, Dict, Any

# Configuration
EXTERNAL_API_URL = "https://flooddemo-qr2x.onrender.com/api/installations"
OUR_API_URL = "http://localhost:5000/api/v1/external/installations"
API_KEY = "ext_DOxMY4SinUXk1kgud1LZTBh06QRQvIgPSTJzx4hIO6k"

def fetch_installations(limit: int = None) -> List[Dict[str, Any]]:
    """Fetch installations from external API."""
    params = {}
    if limit:
        params['limit'] = limit
    
    print(f"Fetching installations from {EXTERNAL_API_URL}...")
    response = requests.get(EXTERNAL_API_URL, params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    
    # Handle different response formats
    if isinstance(data, dict):
        if 'data' in data:
            installations = data['data']
        elif 'success' in data and 'data' in data:
            installations = data['data']
        else:
            installations = [data]
    elif isinstance(data, list):
        installations = data
    else:
        installations = []
    
    print(f"Found {len(installations)} installations")
    return installations

def transform_installation(inst: Dict[str, Any]) -> Dict[str, Any]:
    """Transform external API format to our format."""
    return {
        "id": inst.get("id", "").split("_")[0] if "_" in inst.get("id", "") else inst.get("id", ""),
        "deviceId": inst.get("deviceId", ""),
        "amanah": inst.get("locationId", inst.get("amanah", "")),
        "createdAt": inst.get("createdAt", "")
    }

def send_to_our_api(installations: List[Dict[str, Any]], batch_size: int = 50):
    """Send installations to our API in batches."""
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    total = len(installations)
    created = 0
    updated = 0
    errors = 0
    
    for i in range(0, total, batch_size):
        batch = installations[i:i + batch_size]
        transformed_batch = [transform_installation(inst) for inst in batch]
        
        print(f"\nProcessing batch {i//batch_size + 1} ({len(batch)} installations)...")
        
        try:
            response = requests.post(
                OUR_API_URL,
                headers=headers,
                json=transformed_batch,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            created += result.get("created", 0)
            updated += result.get("updated", 0)
            errors += result.get("errors", 0)
            
            print(f"  ✓ Created: {result.get('created', 0)}, Updated: {result.get('updated', 0)}, Errors: {result.get('errors', 0)}")
            
        except Exception as e:
            print(f"  ✗ Error processing batch: {e}")
            errors += len(batch)
    
    print(f"\n=== SYNC SUMMARY ===")
    print(f"Total installations: {total}")
    print(f"Created: {created}")
    print(f"Updated: {updated}")
    print(f"Errors: {errors}")

def main():
    """Main function."""
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            print(f"Limiting to {limit} installations for testing...")
        except ValueError:
            print("Usage: python3 sync_installations.py [limit]")
            sys.exit(1)
    
    try:
        installations = fetch_installations(limit=limit)
        
        if not installations:
            print("No installations found!")
            return
        
        print(f"\nTransforming {len(installations)} installations...")
        send_to_our_api(installations)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

