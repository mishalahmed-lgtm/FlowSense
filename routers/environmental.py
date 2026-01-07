"""Environmental monitoring API endpoints."""
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

