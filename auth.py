"""Device authentication using provisioning keys."""
from datetime import datetime
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from models import ProvisioningKey, Device
from database import get_db
from typing import Optional

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

