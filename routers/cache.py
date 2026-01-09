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

logger = logging.getLogger(__name__)
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

