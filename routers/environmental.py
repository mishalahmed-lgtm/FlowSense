"""Environmental monitoring API endpoints."""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from admin_auth import get_current_user
from database import get_db
from models import User
from services.environmental_service import EnvironmentalService

router = APIRouter(prefix="/admin/environmental", tags=["environmental"])


@router.get("/summary")
def get_environmental_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    hours: int = Query(24, ge=1, le=720, description="Lookback window in hours"),
):
    """Get environmental data summary (AQI, PM2.5, PM10, CO2, temperature, humidity)."""
    environmental_service = EnvironmentalService(db)
    return environmental_service.get_environmental_summary(
        user=current_user,
        hours=hours,
    )


@router.get("/air-quality")
def get_air_quality(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    from_date: date = Query(..., description="Start date (inclusive, YYYY-MM-DD)"),
    to_date: date = Query(..., description="End date (exclusive, YYYY-MM-DD)"),
):
    """Get air quality data (PM2.5, PM10, CO2) for devices over a time range."""
    environmental_service = EnvironmentalService(db)
    return environmental_service.get_air_quality_data(
        user=current_user,
        from_date=str(from_date),
        to_date=str(to_date),
    )


@router.get("/noise")
def get_noise_levels(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    from_date: date = Query(..., description="Start date (inclusive, YYYY-MM-DD)"),
    to_date: date = Query(..., description="End date (exclusive, YYYY-MM-DD)"),
):
    """Get noise level data for devices over a time range."""
    environmental_service = EnvironmentalService(db)
    return environmental_service.get_noise_data(
        user=current_user,
        from_date=str(from_date),
        to_date=str(to_date),
    )

