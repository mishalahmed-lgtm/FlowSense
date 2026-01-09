"""Cache endpoints for pre-computed dashboard data."""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

from database import get_db
from admin_auth import get_current_user
from models import User, UserRole

# Initialize logger before using it
logger = logging.getLogger(__name__)

# Firebase service (for tenant_id = 2 only - demo)
FIREBASE_TENANT_ID = 2
try:
    # Try REST API first (uses client credentials)
    from services.firebase_rest_service import get_metrics as firebase_get_metrics, get_devices as firebase_get_devices, get_health as firebase_get_health
    FIREBASE_AVAILABLE = True
    logger.info("✅ Using Firebase REST API (client credentials)")
except ImportError:
    try:
        # Fallback to Admin SDK (requires service account)
        from services.firebase_service import get_metrics as firebase_get_metrics, get_devices as firebase_get_devices, get_health as firebase_get_health
        FIREBASE_AVAILABLE = True
        logger.info("✅ Using Firebase Admin SDK")
    except ImportError:
        FIREBASE_AVAILABLE = False
        logger.warning("Firebase service not available (optional for demo)")

Base = declarative_base()

class DashboardCache(Base):
    __tablename__ = "dashboard_cache"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    cache_key = Column(String(100), nullable=False, index=True)
    data = Column(JSON, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/metrics")
def get_cached_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get cached metrics (fast, single query)."""
    if current_user.role != UserRole.TENANT_ADMIN or not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin access required"
        )
    
    # Route tenant_id = 2 to Firebase (bypass PostgreSQL)
    if current_user.tenant_id == FIREBASE_TENANT_ID and FIREBASE_AVAILABLE:
        logger.info(f"Using Firebase for tenant {FIREBASE_TENANT_ID} (bypassing PostgreSQL)")
        firebase_data = firebase_get_metrics(current_user.tenant_id)
        if firebase_data:
            return firebase_data
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Firebase data not found for tenant"
            )
    
    # PostgreSQL path for other tenants
    cache_entry = db.query(DashboardCache).filter(
        DashboardCache.tenant_id == current_user.tenant_id,
        DashboardCache.cache_key == "metrics",
        DashboardCache.expires_at > datetime.now(timezone.utc)
    ).first()
    
    if not cache_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cache not found or expired. Run sync_dashboard_cache.py"
        )
    
    return cache_entry.data


@router.get("/devices")
def get_cached_devices(
    page: int = 1,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get cached devices page (fast, single query)."""
    if current_user.role != UserRole.TENANT_ADMIN or not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin access required"
        )
    
    # Route tenant_id = 2 to Firebase (bypass PostgreSQL)
    if current_user.tenant_id == FIREBASE_TENANT_ID and FIREBASE_AVAILABLE:
        logger.info(f"Using Firebase for tenant {FIREBASE_TENANT_ID} (bypassing PostgreSQL)")
        firebase_data = firebase_get_devices(current_user.tenant_id, page)
        if firebase_data:
            return firebase_data
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Firebase data not found for tenant"
            )
    
    # PostgreSQL path for other tenants
    cache_key = f"devices_page_{page}"
    cache_entry = db.query(DashboardCache).filter(
        DashboardCache.tenant_id == current_user.tenant_id,
        DashboardCache.cache_key == cache_key,
        DashboardCache.expires_at > datetime.now(timezone.utc)
    ).first()
    
    if not cache_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cache not found for page {page}. Run sync_dashboard_cache.py"
        )
    
    return cache_entry.data


@router.get("/health")
def get_cached_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get cached health data (fast, single query)."""
    if current_user.role != UserRole.TENANT_ADMIN or not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin access required"
        )
    
    # Route tenant_id = 2 to Firebase (bypass PostgreSQL)
    if current_user.tenant_id == FIREBASE_TENANT_ID and FIREBASE_AVAILABLE:
        logger.info(f"Using Firebase for tenant {FIREBASE_TENANT_ID} (bypassing PostgreSQL)")
        firebase_data = firebase_get_health(current_user.tenant_id)
        if firebase_data:
            return firebase_data
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Firebase data not found for tenant"
            )
    
    # PostgreSQL path for other tenants
    cache_entry = db.query(DashboardCache).filter(
        DashboardCache.tenant_id == current_user.tenant_id,
        DashboardCache.cache_key == "health",
        DashboardCache.expires_at > datetime.now(timezone.utc)
    ).first()
    
    if not cache_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cache not found or expired. Run sync_dashboard_cache.py"
        )
    
    return cache_entry.data

