"""API endpoints for analytics engine - direct analysis, no jobs."""
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models import (
    Device, TelemetryTimeseries,
    MLModel, Prediction, PatternAnalysis, CorrelationResult,
    User, UserRole
)
from admin_auth import get_current_user
from analytics_engine import analytics_engine

router = APIRouter(prefix="/analytics", tags=["analytics"])


# Request/Response models
class PatternAnalysisRequest(BaseModel):
    device_ids: List[str]
    analysis_type: str = "occupancy"  # occupancy, traffic, energy_consumption
    field_key: Optional[str] = None
    days: int = 7


class CorrelationAnalysisRequest(BaseModel):
    device_ids: List[str]
    field_keys: List[str]  # One per device
    days: int = 7


class MLTrainingRequest(BaseModel):
    name: str
    model_type: str = "anomaly_detection"  # anomaly_detection, failure_prediction
    algorithm: str = "isolation_forest"  # isolation_forest, random_forest
    device_ids: List[str]
    days: int = 30


class PatternAnalysisResult(BaseModel):
    device_id: str
    device_name: str
    analysis_type: str
    field_key: Optional[str]
    peak_times: Optional[dict]
    trends: Optional[dict]
    summary: Optional[str]
    insights: Optional[dict]


class CorrelationResult(BaseModel):
    device1_id: str
    device2_id: str
    field1_key: str
    field2_key: str
    correlation_coefficient: float
    correlation_type: str
    insights: Optional[str]


class MLModelResponse(BaseModel):
    id: int
    name: str
    model_type: str
    algorithm: str
    is_trained: bool
    training_accuracy: Optional[float]
    training_samples: Optional[int]
    trained_at: Optional[str]
    
    class Config:
        from_attributes = True


class PredictionResponse(BaseModel):
    device_id: str
    device_name: str
    prediction_type: str
    predicted_value: Optional[float]
    confidence: Optional[float]
    predicted_at: str
    
    class Config:
        from_attributes = True


@router.post("/analyze-patterns", response_model=List[PatternAnalysisResult])
def analyze_patterns(
    request: PatternAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyze usage patterns for devices (occupancy, traffic, energy). Returns results immediately."""
    tenant_id = current_user.tenant_id if current_user.role == UserRole.TENANT_ADMIN else None
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin has no tenant")
    
    results = []
    for device_id_str in request.device_ids:
        device = db.query(Device).filter(Device.device_id == device_id_str).first()
        if not device or (tenant_id and device.tenant_id != tenant_id):
            continue
        
        # Run pattern analysis directly
        try:
            pattern_result = analytics_engine._analyze_pattern_direct(
                device, request.analysis_type, request.field_key, request.days, db
            )
            if pattern_result:
                results.append(PatternAnalysisResult(
                    device_id=device.device_id,
                    device_name=device.name,
                    analysis_type=pattern_result.get("analysis_type", request.analysis_type),
                    field_key=pattern_result.get("field_key"),
                    peak_times=pattern_result.get("peak_times"),
                    trends=pattern_result.get("trends"),
                    summary=pattern_result.get("summary"),
                    insights=pattern_result.get("insights")
                ))
        except Exception as e:
            # Continue with other devices if one fails
            continue
    
    return results


@router.post("/analyze-correlations", response_model=List[CorrelationResult])
def analyze_correlations(
    request: CorrelationAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyze correlations between multiple devices/sensors. Returns results immediately."""
    tenant_id = current_user.tenant_id if current_user.role == UserRole.TENANT_ADMIN else None
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin has no tenant")
    
    if len(request.device_ids) < 2 or len(request.field_keys) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Need at least 2 devices and 2 fields")
    
    # Run correlation analysis directly
    try:
        correlation_results = analytics_engine._analyze_correlation_direct(
            request.device_ids, request.field_keys, request.days, tenant_id, db
        )
        return correlation_results
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/train-model", response_model=MLModelResponse)
def train_ml_model(
    request: MLTrainingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Train an ML model (runs in backend). Returns model info after training."""
    tenant_id = current_user.tenant_id if current_user.role == UserRole.TENANT_ADMIN else None
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin has no tenant")
    
    # Train model directly (this runs in backend)
    try:
        ml_model = analytics_engine._train_model_direct(
            request.name, request.model_type, request.algorithm,
            request.device_ids, request.days, tenant_id, db
        )
        
        return MLModelResponse(
            id=ml_model.id,
            name=ml_model.name,
            model_type=ml_model.model_type,
            algorithm=ml_model.algorithm,
            is_trained=ml_model.is_trained,
            training_accuracy=ml_model.training_accuracy,
            training_samples=ml_model.training_samples,
            trained_at=ml_model.trained_at.isoformat() if ml_model.trained_at else None
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/models", response_model=List[MLModelResponse])
def list_ml_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List ML models (tenant-scoped)."""
    query = db.query(MLModel)
    
    if current_user.role == UserRole.TENANT_ADMIN:
        if not current_user.tenant_id:
            return []
        query = query.filter(MLModel.tenant_id == current_user.tenant_id)
    
    models = query.filter(MLModel.is_active == True).order_by(MLModel.created_at.desc()).all()
    
    return [
        MLModelResponse(
            id=m.id,
            name=m.name,
            model_type=m.model_type,
            algorithm=m.algorithm,
            is_trained=m.is_trained,
            training_accuracy=m.training_accuracy,
            training_samples=m.training_samples,
            trained_at=m.trained_at.isoformat() if m.trained_at else None
        )
        for m in models
    ]


@router.get("/predictions", response_model=List[PredictionResponse])
def get_predictions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    device_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Get predictions from ML models (automatically generated in backend)."""
    query = db.query(Prediction).join(Device)
    
    if current_user.role == UserRole.TENANT_ADMIN:
        if not current_user.tenant_id:
            return []
        query = query.filter(Prediction.tenant_id == current_user.tenant_id)
    
    if device_id:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if device:
            query = query.filter(Prediction.device_id == device.id)
    
    predictions = query.order_by(Prediction.predicted_at.desc()).limit(limit).all()
    
    return [
        PredictionResponse(
            device_id=p.device.device_id if p.device else "unknown",
            device_name=p.device.name if p.device else "Unknown",
            prediction_type=p.prediction_type,
            predicted_value=p.predicted_value,
            confidence=p.confidence,
            predicted_at=p.predicted_at.isoformat()
        )
        for p in predictions
    ]


@router.post("/predict-maintenance")
def predict_maintenance(
    device_ids: List[str],
    model_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run predictive maintenance analysis (runs in backend, returns results immediately)."""
    tenant_id = current_user.tenant_id if current_user.role == UserRole.TENANT_ADMIN else None
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin has no tenant")
    
    # Run predictive maintenance directly
    try:
        predictions = analytics_engine._predict_maintenance_direct(
            device_ids, model_id, tenant_id, db
        )
        return predictions
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
