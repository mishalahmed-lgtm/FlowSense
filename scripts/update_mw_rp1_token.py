#!/usr/bin/env python3
"""Update MW-RP-1 device metadata with access token."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Device
import json

db = SessionLocal()

try:
    device = db.query(Device).filter(Device.device_id == "MW-RP-1").first()
    if not device:
        print("ERROR: Device MW-RP-1 not found in database!")
        sys.exit(1)
    
    # Parse existing metadata or create new dict
    if device.device_metadata:
        try:
            if isinstance(device.device_metadata, str):
                metadata = json.loads(device.device_metadata)
            else:
                metadata = device.device_metadata
        except:
            metadata = {}
    else:
        metadata = {}
    
    # Update access token
    metadata["access_token"] = "murabba"
    
    # Save back to database
    device.device_metadata = json.dumps(metadata)
    db.commit()
    
    print(f"✓ Updated device MW-RP-1 metadata with access_token: murabba")
    print(f"  Device name: {device.name}")
    print(f"  Metadata: {device.device_metadata}")
    
except Exception as e:
    db.rollback()
    print(f"ERROR: {e}")
    sys.exit(1)
finally:
    db.close()

