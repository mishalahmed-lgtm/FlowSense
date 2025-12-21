"""Device authentication using provisioning keys."""
import logging
from datetime import datetime
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from models import ProvisioningKey, Device
from database import get_db
from typing import Optional

logger = logging.getLogger(__name__)

# API Key header for device authentication
api_key_header = APIKeyHeader(name="X-Device-Key", auto_error=False)


async def verify_device_key(
    api_key: Optional[str] = Security(api_key_header),
) -> str:
    """
    Extract and return the device provisioning key from X-Device-Key header.
    
    Args:
        api_key: The provisioning key from X-Device-Key header
        
    Returns:
        The provisioning key string
        
    Raises:
        HTTPException: If the header is missing
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing device provisioning key. Provide X-Device-Key header."
        )
    
    return api_key


async def get_device_from_key(
    api_key: str = Depends(verify_device_key),
    db: Session = Depends(get_db)
) -> Device:
    """
    Verify provisioning key and return the associated device.
    Uses the route handler's database session to avoid detached instance errors.
    """
    from sqlalchemy.orm import joinedload
    
    # Query provisioning key
    provisioning_key = db.query(ProvisioningKey).filter(
        ProvisioningKey.key == api_key,
        ProvisioningKey.is_active == True
    ).first()
    
    if not provisioning_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive device provisioning key"
        )
    
    # Check if key has expired
    if provisioning_key.expires_at and provisioning_key.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device provisioning key has expired"
        )
    
    # Get associated device with eagerly loaded relationships
    device = db.query(Device).options(
        joinedload(Device.device_type)
    ).filter(
        Device.id == provisioning_key.device_id,
        Device.is_active == True
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device associated with this key is not active"
        )
    
    # Update last_used_at timestamp
    provisioning_key.last_used_at = datetime.utcnow()
    db.commit()
    
    return device


def verify_device_access_token(device: Device, provided_token: Optional[str]) -> bool:
    """
    Verify if the provided access token matches the device's configured access token.
    
    Args:
        device: The device object
        provided_token: The access token provided by the device
        
    Returns:
        True if token is valid, False otherwise
        
    Raises:
        HTTPException: If token is missing or invalid
    """
    import json
    
    try:
        metadata = json.loads(device.device_metadata) if isinstance(device.device_metadata, str) else device.device_metadata
        device_token = metadata.get("access_token") if metadata else None
        
        # Access token is required - if not configured, reject (should not happen for new devices)
        if not device_token:
            logger.warning(f"Device {device.device_id} has no access token configured")
            return False
        
        # Token must be provided and must match
        if not provided_token:
            return False
        
        if provided_token != device_token:
            return False
        
        return True
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        # Invalid metadata format - reject for security
        logger.error(f"Invalid device metadata for device {device.device_id}: {e}")
        return False

