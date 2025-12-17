"""Analytics Engine for real-time stream processing, batch analytics, ML models, and predictive maintenance."""
import logging
import threading
import time
import json
import os
import pickle
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import SessionLocal
from models import (
    Device, TelemetryTimeseries, TelemetryLatest,
    AnalyticsJob, AnalyticsJobStatus, AnalyticsJobType,
    MLModel, Prediction, PatternAnalysis, CorrelationResult,
    Tenant
)

logger = logging.getLogger(__name__)

# Try to import scikit-learn, but handle gracefully if not available
try:
    from sklearn.ensemble import IsolationForest, RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, r2_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available. ML features will be limited.")


class AnalyticsEngine:
    """Engine for running various analytics jobs."""
    
    def __init__(self):
        """Initialize analytics engine."""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._model_cache: Dict[int, Any] = {}  # Cache loaded ML models
    
    def start(self):
        """Start the analytics engine worker."""
        if self._running:
            logger.warning("Analytics engine is already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info("Analytics engine started")
    
    def stop(self):
        """Stop the analytics engine."""
        if not self._running:
            return
        
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Analytics engine stopped")
    
    def _worker_loop(self):
        """Background worker that processes pending analytics jobs."""
        while self._running:
            try:
                self._process_pending_jobs()
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Error in analytics worker loop: {e}", exc_info=True)
                time.sleep(30)
    
    def _process_pending_jobs(self):
        """Process pending analytics jobs."""
        db = SessionLocal()
        try:
            pending_jobs = db.query(AnalyticsJob).filter(
                AnalyticsJob.status == AnalyticsJobStatus.PENDING
            ).limit(5).all()
            
            for job in pending_jobs:
                try:
                    job.status = AnalyticsJobStatus.RUNNING
                    job.started_at = datetime.now(timezone.utc)
                    job.progress_percent = 0.0
                    db.commit()
                    
                    # Process job based on type
                    if job.job_type == AnalyticsJobType.REALTIME_STREAM:
                        self._process_realtime_stream(job, db)
                    elif job.job_type == AnalyticsJobType.BATCH_ANALYTICS:
                        self._process_batch_analytics(job, db)
                    elif job.job_type == AnalyticsJobType.ML_TRAINING:
                        self._process_ml_training(job, db)
                    elif job.job_type == AnalyticsJobType.PREDICTIVE_MAINTENANCE:
                        self._process_predictive_maintenance(job, db)
                    elif job.job_type == AnalyticsJobType.PATTERN_ANALYSIS:
                        self._process_pattern_analysis(job, db)
                    elif job.job_type == AnalyticsJobType.CORRELATION_ANALYSIS:
                        self._process_correlation_analysis(job, db)
                    
                    job.status = AnalyticsJobStatus.COMPLETED
                    job.completed_at = datetime.now(timezone.utc)
                    job.progress_percent = 100.0
                    db.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing analytics job {job.id}: {e}", exc_info=True)
                    job.status = AnalyticsJobStatus.FAILED
                    job.error_message = str(e)
                    job.completed_at = datetime.now(timezone.utc)
                    db.commit()
        except Exception as e:
            logger.error(f"Error in _process_pending_jobs: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    def _process_realtime_stream(self, job: AnalyticsJob, db: Session):
        """Process real-time stream analytics (simulate Apache Flink)."""
        logger.info(f"Processing real-time stream job: {job.name}")
        job.progress_percent = 10.0
        db.commit()
        
        # Simulate real-time stream processing
        # In production, this would connect to Flink or process Kafka streams
        device_ids = job.device_ids or []
        config = job.config or {}
        window_size_minutes = config.get("window_size_minutes", 5)
        
        results = {
            "processed_records": 0,
            "anomalies_detected": 0,
            "aggregations": {},
            "window_size_minutes": window_size_minutes
        }
        
        # Get recent telemetry for streaming analysis
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_size_minutes)
        for device_id_str in device_ids:
            device = db.query(Device).filter(Device.device_id == device_id_str).first()
            if not device:
                continue
            
            # Get recent telemetry
            recent_telemetry = db.query(TelemetryTimeseries).filter(
                TelemetryTimeseries.device_id == device.id,
                TelemetryTimeseries.ts >= cutoff
            ).all()
            
            results["processed_records"] += len(recent_telemetry)
            
            # Simple anomaly detection in stream
            if recent_telemetry:
                values = [t.value for t in recent_telemetry if t.value is not None]
                if len(values) > 2:
                    mean_val = np.mean(values)
                    std_val = np.std(values)
                    anomalies = [v for v in values if abs(v - mean_val) > 2 * std_val]
                    results["anomalies_detected"] += len(anomalies)
        
        job.progress_percent = 100.0
        job.results = results
        db.commit()
        logger.info(f"Real-time stream job {job.id} completed")
    
    def _process_batch_analytics(self, job: AnalyticsJob, db: Session):
        """Process batch analytics (simulate Apache Spark)."""
        logger.info(f"Processing batch analytics job: {job.name}")
        job.progress_percent = 10.0
        db.commit()
        
        device_ids = job.device_ids or []
        config = job.config or {}
        start_date = config.get("start_date")
        end_date = config.get("end_date")
        
        if not start_date or not end_date:
            start_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            end_date = datetime.now(timezone.utc).isoformat()
        
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        results = {
            "start_date": start_date,
            "end_date": end_date,
            "devices_analyzed": len(device_ids),
            "total_records": 0,
            "aggregations": {}
        }
        
        job.progress_percent = 30.0
        db.commit()
        
        # Batch process telemetry
        for device_id_str in device_ids:
            device = db.query(Device).filter(Device.device_id == device_id_str).first()
            if not device:
                continue
            
            telemetry = db.query(TelemetryTimeseries).filter(
                TelemetryTimeseries.device_id == device.id,
                TelemetryTimeseries.ts >= start_dt,
                TelemetryTimeseries.ts <= end_dt
            ).all()
            
            results["total_records"] += len(telemetry)
            
            # Aggregate by key
            by_key = defaultdict(list)
            for t in telemetry:
                by_key[t.key].append(t.value)
            
            for key, values in by_key.items():
                if key not in results["aggregations"]:
                    results["aggregations"][key] = {
                        "count": 0,
                        "min": None,
                        "max": None,
                        "avg": None
                    }
                
                numeric_values = [v for v in values if v is not None]
                if numeric_values:
                    results["aggregations"][key]["count"] += len(numeric_values)
                    if results["aggregations"][key]["min"] is None:
                        results["aggregations"][key]["min"] = min(numeric_values)
                    else:
                        results["aggregations"][key]["min"] = min(results["aggregations"][key]["min"], min(numeric_values))
                    
                    if results["aggregations"][key]["max"] is None:
                        results["aggregations"][key]["max"] = max(numeric_values)
                    else:
                        results["aggregations"][key]["max"] = max(results["aggregations"][key]["max"], max(numeric_values))
                    
                    # Update average
                    current_avg = results["aggregations"][key]["avg"]
                    if current_avg is None:
                        results["aggregations"][key]["avg"] = np.mean(numeric_values)
                    else:
                        # Weighted average
                        total_count = results["aggregations"][key]["count"]
                        results["aggregations"][key]["avg"] = (
                            (current_avg * (total_count - len(numeric_values)) + sum(numeric_values)) / total_count
                        )
        
        job.progress_percent = 100.0
        job.results = results
        db.commit()
        logger.info(f"Batch analytics job {job.id} completed")
    
    def _process_ml_training(self, job: AnalyticsJob, db: Session):
        """Train a machine learning model."""
        if not SKLEARN_AVAILABLE:
            raise Exception("scikit-learn not available. Cannot train ML models.")
        
        logger.info(f"Training ML model for job: {job.name}")
        job.progress_percent = 10.0
        db.commit()
        
        config = job.config or {}
        model_type = config.get("model_type", "anomaly_detection")
        algorithm = config.get("algorithm", "isolation_forest")
        device_ids = job.device_ids or []
        
        # Get training data
        start_date = config.get("start_date")
        end_date = config.get("end_date")
        if not start_date or not end_date:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        job.progress_percent = 20.0
        db.commit()
        
        # Collect training data
        training_data = []
        for device_id_str in device_ids:
            device = db.query(Device).filter(Device.device_id == device_id_str).first()
            if not device:
                continue
            
            telemetry = db.query(TelemetryTimeseries).filter(
                TelemetryTimeseries.device_id == device.id,
                TelemetryTimeseries.ts >= start_date,
                TelemetryTimeseries.ts <= end_date
            ).all()
            
            for t in telemetry:
                if t.value is not None:
                    training_data.append({
                        "device_id": device.id,
                        "key": t.key,
                        "value": t.value,
                        "timestamp": t.ts.timestamp()
                    })
        
        if len(training_data) < 10:
            raise Exception("Insufficient training data. Need at least 10 samples.")
        
        job.progress_percent = 40.0
        db.commit()
        
        # Prepare features
        df = pd.DataFrame(training_data)
        if model_type == "anomaly_detection":
            # Use Isolation Forest for anomaly detection
            features = df[["value", "timestamp"]].values
            model = IsolationForest(contamination=0.1, random_state=42)
            model.fit(features)
            
            # Evaluate
            predictions = model.predict(features)
            anomaly_count = sum(predictions == -1)
            accuracy = 1.0 - (anomaly_count / len(predictions))
            
        elif model_type == "failure_prediction":
            # Use Random Forest for failure prediction
            # This is simplified - in production you'd have failure labels
            features = df[["value", "timestamp"]].values
            # Create dummy labels (in production, use actual failure data)
            labels = np.random.randint(0, 2, len(features))  # Placeholder
            
            X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42)
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X_train, y_train)
            
            y_pred = model.predict(X_test)
            accuracy = r2_score(y_test, y_pred)
        else:
            raise Exception(f"Unknown model type: {model_type}")
        
        job.progress_percent = 80.0
        db.commit()
        
        # Save model
        model_dir = "/data/ml_models"
        os.makedirs(model_dir, exist_ok=True)
        model_filename = f"model_{job.id}_{int(time.time())}.pkl"
        model_path = os.path.join(model_dir, model_filename)
        
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        
        # Create or update MLModel record
        ml_model = db.query(MLModel).filter(MLModel.id == config.get("model_id")).first() if config.get("model_id") else None
        
        if not ml_model:
            ml_model = MLModel(
                name=job.name,
                model_type=model_type,
                tenant_id=job.tenant_id,
                algorithm=algorithm,
                model_path=model_path,
                training_data_range_start=start_date,
                training_data_range_end=end_date,
                training_accuracy=float(accuracy),
                training_samples=len(training_data),
                is_trained=True,
                trained_at=datetime.now(timezone.utc)
            )
            db.add(ml_model)
        else:
            ml_model.model_path = model_path
            ml_model.training_accuracy = float(accuracy)
            ml_model.training_samples = len(training_data)
            ml_model.is_trained = True
            ml_model.trained_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(ml_model)
        
        job.results = {
            "model_id": ml_model.id,
            "model_name": ml_model.name,
            "accuracy": float(accuracy),
            "training_samples": len(training_data),
            "model_path": model_path
        }
        
        job.progress_percent = 100.0
        db.commit()
        logger.info(f"ML training job {job.id} completed. Model ID: {ml_model.id}")
    
    def _process_predictive_maintenance(self, job: AnalyticsJob, db: Session):
        """Run predictive maintenance analysis."""
        logger.info(f"Processing predictive maintenance job: {job.name}")
        job.progress_percent = 10.0
        db.commit()
        
        device_ids = job.device_ids or []
        config = job.config or {}
        model_id = config.get("model_id")
        
        results = {
            "devices_analyzed": len(device_ids),
            "predictions": []
        }
        
        # Load ML model if provided
        model = None
        if model_id:
            ml_model = db.query(MLModel).filter(MLModel.id == model_id, MLModel.is_trained == True).first()
            if ml_model and ml_model.model_path and os.path.exists(ml_model.model_path):
                try:
                    with open(ml_model.model_path, "rb") as f:
                        model = pickle.load(f)
                except Exception as e:
                    logger.error(f"Error loading ML model: {e}")
        
        job.progress_percent = 30.0
        db.commit()
        
        # Analyze each device
        for device_id_str in device_ids:
            device = db.query(Device).filter(Device.device_id == device_id_str).first()
            if not device:
                continue
            
            # Get recent telemetry
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            recent_telemetry = db.query(TelemetryTimeseries).filter(
                TelemetryTimeseries.device_id == device.id,
                TelemetryTimeseries.ts >= cutoff
            ).all()
            
            if not recent_telemetry:
                continue
            
            # Calculate failure probability (simplified)
            # In production, use trained ML model
            values = [t.value for t in recent_telemetry if t.value is not None]
            if not values:
                continue
            
            # Simple heuristic: if values are outside normal range, higher failure probability
            mean_val = np.mean(values)
            std_val = np.std(values) if len(values) > 1 else 0
            
            # Use model if available
            if model and SKLEARN_AVAILABLE:
                try:
                    features = np.array([[mean_val, std_val]])
                    if hasattr(model, "predict"):
                        prediction = model.predict(features)[0]
                        if hasattr(model, "decision_function"):
                            # Isolation Forest
                            score = model.decision_function(features)[0]
                            failure_probability = max(0, min(1, (1 - score) / 2))
                        else:
                            # Regression model
                            failure_probability = max(0, min(1, prediction))
                    else:
                        failure_probability = 0.5
                except:
                    failure_probability = 0.5
            else:
                # Simple heuristic
                deviation = abs(values[-1] - mean_val) if values else 0
                failure_probability = min(1.0, deviation / (std_val + 1) if std_val > 0 else 0.1)
            
            prediction_result = {
                "device_id": device.device_id,
                "device_name": device.name,
                "failure_probability": float(failure_probability),
                "confidence": 0.7,  # Placeholder
                "recommended_action": "Schedule maintenance" if failure_probability > 0.7 else "Monitor"
            }
            
            results["predictions"].append(prediction_result)
            
            # Store prediction in database
            if model_id:
                prediction = Prediction(
                    model_id=model_id,
                    device_id=device.id,
                    tenant_id=device.tenant_id,
                    prediction_type="failure_probability",
                    predicted_value=failure_probability,
                    confidence=0.7,
                    input_features={"mean": float(mean_val), "std": float(std_val) if std_val else 0}
                )
                db.add(prediction)
        
        db.commit()
        job.progress_percent = 100.0
        job.results = results
        db.commit()
        logger.info(f"Predictive maintenance job {job.id} completed")
    
    def _process_pattern_analysis(self, job: AnalyticsJob, db: Session):
        """Analyze usage patterns (occupancy, traffic, energy consumption)."""
        logger.info(f"Processing pattern analysis job: {job.name}")
        job.progress_percent = 10.0
        db.commit()
        
        device_ids = job.device_ids or []
        config = job.config or {}
        analysis_type = config.get("analysis_type", "occupancy")
        field_key = config.get("field_key")
        days = config.get("days", 7)
        
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        end_date = datetime.now(timezone.utc)
        
        job.progress_percent = 20.0
        db.commit()
        
        # Analyze patterns for each device
        for device_id_str in device_ids:
            device = db.query(Device).filter(Device.device_id == device_id_str).first()
            if not device:
                continue
            
            # Get telemetry data
            query = db.query(TelemetryTimeseries).filter(
                TelemetryTimeseries.device_id == device.id,
                TelemetryTimeseries.ts >= start_date,
                TelemetryTimeseries.ts <= end_date
            )
            
            if field_key:
                query = query.filter(TelemetryTimeseries.key == field_key)
            
            telemetry = query.all()
            
            if not telemetry:
                continue
            
            # Convert to DataFrame for analysis
            data = [{"timestamp": t.ts, "key": t.key, "value": t.value} for t in telemetry if t.value is not None]
            if not data:
                continue
            
            df = pd.DataFrame(data)
            df["hour"] = df["timestamp"].dt.hour
            df["day_of_week"] = df["timestamp"].dt.dayofweek
            
            # Calculate patterns
            hourly_avg = df.groupby("hour")["value"].mean().to_dict()
            daily_avg = df.groupby("day_of_week")["value"].mean().to_dict()
            
            # Find peak times
            peak_hour = max(hourly_avg.items(), key=lambda x: x[1])[0] if hourly_avg else None
            peak_day = max(daily_avg.items(), key=lambda x: x[1])[0] if daily_avg else None
            
            # Detect trends
            df_sorted = df.sort_values("timestamp")
            if len(df_sorted) > 1:
                first_half = df_sorted[:len(df_sorted)//2]["value"].mean()
                second_half = df_sorted[len(df_sorted)//2:]["value"].mean()
                if second_half > first_half * 1.1:
                    trend = "increasing"
                elif second_half < first_half * 0.9:
                    trend = "decreasing"
                else:
                    trend = "stable"
            else:
                trend = "stable"
            
            # Create pattern analysis record
            pattern = PatternAnalysis(
                tenant_id=device.tenant_id,
                device_id=device.id,
                analysis_type=analysis_type,
                field_key=field_key,
                pattern_type="daily",
                peak_times={"hour": int(peak_hour) if peak_hour else None, "day": int(peak_day) if peak_day else None},
                average_values={"hourly": {str(k): float(v) for k, v in hourly_avg.items()}, "daily": {str(k): float(v) for k, v in daily_avg.items()}},
                trends={"overall": trend},
                analysis_start=start_date,
                analysis_end=end_date,
                summary=f"Analyzed {len(telemetry)} data points. Peak usage at hour {peak_hour}.",
                insights={"trend": trend, "peak_hour": int(peak_hour) if peak_hour else None}
            )
            db.add(pattern)
        
        db.commit()
        job.progress_percent = 100.0
        job.results = {"pattern_analyses_created": len(device_ids)}
        db.commit()
        logger.info(f"Pattern analysis job {job.id} completed")
    
    def _process_correlation_analysis(self, job: AnalyticsJob, db: Session):
        """Analyze correlation between multiple sensors/devices."""
        logger.info(f"Processing correlation analysis job: {job.name}")
        job.progress_percent = 10.0
        db.commit()
        
        config = job.config or {}
        device_ids = config.get("device_ids", [])
        field_keys = config.get("field_keys", [])
        days = config.get("days", 7)
        
        if len(device_ids) < 2 or len(field_keys) < 2:
            raise Exception("Correlation analysis requires at least 2 devices and 2 field keys")
        
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        end_date = datetime.now(timezone.utc)
        
        job.progress_percent = 20.0
        db.commit()
        
        # Collect data from all devices
        all_data = {}
        for device_id_str in device_ids:
            device = db.query(Device).filter(Device.device_id == device_id_str).first()
            if not device:
                continue
            
            # Get telemetry for specified field
            field_key = field_keys[device_ids.index(device_id_str)] if device_ids.index(device_id_str) < len(field_keys) else field_keys[0]
            
            telemetry = db.query(TelemetryTimeseries).filter(
                TelemetryTimeseries.device_id == device.id,
                TelemetryTimeseries.key == field_key,
                TelemetryTimeseries.ts >= start_date,
                TelemetryTimeseries.ts <= end_date
            ).all()
            
            all_data[device_id_str] = [(t.ts, t.value) for t in telemetry if t.value is not None]
        
        if len(all_data) < 2:
            raise Exception("Insufficient data for correlation analysis")
        
        job.progress_percent = 50.0
        db.commit()
        
        # Align timestamps and calculate correlation
        # Simple approach: align by nearest timestamp
        device_pairs = list(all_data.keys())
        correlations = []
        
        for i in range(len(device_pairs)):
            for j in range(i + 1, len(device_pairs)):
                dev1, dev2 = device_pairs[i], device_pairs[j]
                data1 = all_data[dev1]
                data2 = all_data[dev2]
                
                # Align data by timestamp (within 5 minutes)
                aligned_values = []
                for ts1, val1 in data1:
                    # Find closest timestamp in data2
                    closest = min(data2, key=lambda x: abs((x[0] - ts1).total_seconds()))
                    if abs((closest[0] - ts1).total_seconds()) < 300:  # 5 minutes
                        aligned_values.append((val1, closest[1]))
                
                if len(aligned_values) >= 10:
                    values1 = [v[0] for v in aligned_values]
                    values2 = [v[1] for v in aligned_values]
                    
                    # Calculate Pearson correlation
                    correlation = np.corrcoef(values1, values2)[0, 1]
                    
                    if not np.isnan(correlation):
                        correlations.append({
                            "device1": dev1,
                            "device2": dev2,
                            "correlation": float(correlation)
                        })
                        
                        # Create correlation result
                        corr_result = CorrelationResult(
                            tenant_id=job.tenant_id,
                            device_ids=[dev1, dev2],
                            field_keys=[field_keys[device_ids.index(dev1)] if device_ids.index(dev1) < len(field_keys) else None,
                                       field_keys[device_ids.index(dev2)] if device_ids.index(dev2) < len(field_keys) else None],
                            correlation_coefficient=float(correlation),
                            correlation_type="positive" if correlation > 0.5 else "negative" if correlation < -0.5 else "none",
                            analysis_start=start_date,
                            analysis_end=end_date,
                            insights=f"Correlation coefficient: {correlation:.3f}",
                            visualization_data={"values1": values1[:100], "values2": values2[:100]}  # Limit for storage
                        )
                        db.add(corr_result)
        
        db.commit()
        job.progress_percent = 100.0
        job.results = {"correlations": correlations, "total_pairs": len(correlations)}
        db.commit()
        logger.info(f"Correlation analysis job {job.id} completed")
    
    # Direct analysis methods (no jobs required)
    def _analyze_pattern_direct(self, device: Device, analysis_type: str, field_key: Optional[str], days: int, db: Session) -> Optional[Dict[str, Any]]:
        """Direct pattern analysis - returns results immediately."""
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        end_date = datetime.now(timezone.utc)
        
        query = db.query(TelemetryTimeseries).filter(
            TelemetryTimeseries.device_id == device.id,
            TelemetryTimeseries.ts >= start_date,
            TelemetryTimeseries.ts <= end_date
        )
        
        if field_key:
            query = query.filter(TelemetryTimeseries.key == field_key)
        
        telemetry = query.all()
        if not telemetry:
            return None
        
        data = [{"timestamp": t.ts, "key": t.key, "value": t.value} for t in telemetry if t.value is not None]
        if not data:
            return None
        
        df = pd.DataFrame(data)
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek
        
        hourly_avg = df.groupby("hour")["value"].mean().to_dict()
        daily_avg = df.groupby("day_of_week")["value"].mean().to_dict()
        
        peak_hour = max(hourly_avg.items(), key=lambda x: x[1])[0] if hourly_avg else None
        peak_day = max(daily_avg.items(), key=lambda x: x[1])[0] if daily_avg else None
        
        df_sorted = df.sort_values("timestamp")
        if len(df_sorted) > 1:
            first_half = df_sorted[:len(df_sorted)//2]["value"].mean()
            second_half = df_sorted[len(df_sorted)//2:]["value"].mean()
            if second_half > first_half * 1.1:
                trend = "increasing"
            elif second_half < first_half * 0.9:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return {
            "analysis_type": analysis_type,
            "field_key": field_key,
            "peak_times": {"hour": int(peak_hour) if peak_hour else None, "day": int(peak_day) if peak_day else None},
            "trends": {"overall": trend},
            "summary": f"Analyzed {len(telemetry)} data points. Peak usage at hour {peak_hour}.",
            "insights": {"trend": trend, "peak_hour": int(peak_hour) if peak_hour else None}
        }
    
    def _analyze_correlation_direct(self, device_ids: List[str], field_keys: List[str], days: int, tenant_id: int, db: Session) -> List[Dict[str, Any]]:
        """Direct correlation analysis - returns results immediately."""
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        end_date = datetime.now(timezone.utc)
        
        all_data = {}
        for device_id_str in device_ids:
            device = db.query(Device).filter(Device.device_id == device_id_str, Device.tenant_id == tenant_id).first()
            if not device:
                continue
            
            field_key = field_keys[device_ids.index(device_id_str)] if device_ids.index(device_id_str) < len(field_keys) else field_keys[0]
            
            telemetry = db.query(TelemetryTimeseries).filter(
                TelemetryTimeseries.device_id == device.id,
                TelemetryTimeseries.key == field_key,
                TelemetryTimeseries.ts >= start_date,
                TelemetryTimeseries.ts <= end_date
            ).all()
            
            all_data[device_id_str] = [(t.ts, t.value) for t in telemetry if t.value is not None]
        
        if len(all_data) < 2:
            return []
        
        device_pairs = list(all_data.keys())
        correlations = []
        
        for i in range(len(device_pairs)):
            for j in range(i + 1, len(device_pairs)):
                dev1, dev2 = device_pairs[i], device_pairs[j]
                data1 = all_data[dev1]
                data2 = all_data[dev2]
                
                aligned_values = []
                for ts1, val1 in data1:
                    closest = min(data2, key=lambda x: abs((x[0] - ts1).total_seconds()))
                    if abs((closest[0] - ts1).total_seconds()) < 300:
                        aligned_values.append((val1, closest[1]))
                
                if len(aligned_values) >= 10:
                    values1 = [v[0] for v in aligned_values]
                    values2 = [v[1] for v in aligned_values]
                    
                    correlation = np.corrcoef(values1, values2)[0, 1]
                    
                    if not np.isnan(correlation):
                        correlations.append({
                            "device1_id": dev1,
                            "device2_id": dev2,
                            "field1_key": field_keys[device_ids.index(dev1)] if device_ids.index(dev1) < len(field_keys) else None,
                            "field2_key": field_keys[device_ids.index(dev2)] if device_ids.index(dev2) < len(field_keys) else None,
                            "correlation_coefficient": float(correlation),
                            "correlation_type": "positive" if correlation > 0.5 else "negative" if correlation < -0.5 else "none",
                            "insights": f"Correlation coefficient: {correlation:.3f}"
                        })
        
        return correlations
    
    def _train_model_direct(self, name: str, model_type: str, algorithm: str, device_ids: List[str], days: int, tenant_id: int, db: Session) -> MLModel:
        """Direct ML model training - runs in backend, returns model."""
        if not SKLEARN_AVAILABLE:
            raise Exception("scikit-learn not available. Cannot train ML models.")
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        training_data = []
        for device_id_str in device_ids:
            device = db.query(Device).filter(Device.device_id == device_id_str, Device.tenant_id == tenant_id).first()
            if not device:
                continue
            
            telemetry = db.query(TelemetryTimeseries).filter(
                TelemetryTimeseries.device_id == device.id,
                TelemetryTimeseries.ts >= start_date,
                TelemetryTimeseries.ts <= end_date
            ).all()
            
            for t in telemetry:
                if t.value is not None:
                    training_data.append({
                        "device_id": device.id,
                        "key": t.key,
                        "value": t.value,
                        "timestamp": t.ts.timestamp()
                    })
        
        if len(training_data) < 10:
            raise Exception("Insufficient training data. Need at least 10 samples.")
        
        df = pd.DataFrame(training_data)
        features = df[["value", "timestamp"]].values
        
        if model_type == "anomaly_detection":
            model = IsolationForest(contamination=0.1, random_state=42)
            model.fit(features)
            predictions = model.predict(features)
            anomaly_count = sum(predictions == -1)
            accuracy = 1.0 - (anomaly_count / len(predictions))
        elif model_type == "failure_prediction":
            labels = np.random.randint(0, 2, len(features))  # Placeholder - in production use actual failure data
            X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42)
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            accuracy = r2_score(y_test, y_pred)
        else:
            raise Exception(f"Unknown model type: {model_type}")
        
        model_dir = "/data/ml_models"
        os.makedirs(model_dir, exist_ok=True)
        model_filename = f"model_{int(time.time())}.pkl"
        model_path = os.path.join(model_dir, model_filename)
        
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        
        ml_model = MLModel(
            name=name,
            model_type=model_type,
            tenant_id=tenant_id,
            algorithm=algorithm,
            model_path=model_path,
            training_data_range_start=start_date,
            training_data_range_end=end_date,
            training_accuracy=float(accuracy),
            training_samples=len(training_data),
            is_trained=True,
            trained_at=datetime.now(timezone.utc)
        )
        db.add(ml_model)
        db.commit()
        db.refresh(ml_model)
        
        logger.info(f"ML model {ml_model.id} trained successfully")
        return ml_model
    
    def _predict_maintenance_direct(self, device_ids: List[str], model_id: Optional[int], tenant_id: int, db: Session) -> List[Dict[str, Any]]:
        """Direct predictive maintenance - returns results immediately."""
        model = None
        if model_id:
            ml_model = db.query(MLModel).filter(MLModel.id == model_id, MLModel.is_trained == True, MLModel.tenant_id == tenant_id).first()
            if ml_model and ml_model.model_path and os.path.exists(ml_model.model_path):
                try:
                    with open(ml_model.model_path, "rb") as f:
                        model = pickle.load(f)
                except Exception as e:
                    logger.error(f"Error loading ML model: {e}")
        
        predictions = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        
        for device_id_str in device_ids:
            device = db.query(Device).filter(Device.device_id == device_id_str, Device.tenant_id == tenant_id).first()
            if not device:
                continue
            
            recent_telemetry = db.query(TelemetryTimeseries).filter(
                TelemetryTimeseries.device_id == device.id,
                TelemetryTimeseries.ts >= cutoff
            ).all()
            
            if not recent_telemetry:
                continue
            
            values = [t.value for t in recent_telemetry if t.value is not None]
            if not values:
                continue
            
            mean_val = np.mean(values)
            std_val = np.std(values) if len(values) > 1 else 0
            
            if model and SKLEARN_AVAILABLE:
                try:
                    features = np.array([[mean_val, std_val]])
                    if hasattr(model, "decision_function"):
                        score = model.decision_function(features)[0]
                        failure_probability = max(0, min(1, (1 - score) / 2))
                    else:
                        prediction = model.predict(features)[0]
                        failure_probability = max(0, min(1, prediction))
                except:
                    failure_probability = 0.5
            else:
                deviation = abs(values[-1] - mean_val) if values else 0
                failure_probability = min(1.0, deviation / (std_val + 1) if std_val > 0 else 0.1)
            
            predictions.append({
                "device_id": device.device_id,
                "device_name": device.name,
                "failure_probability": float(failure_probability),
                "confidence": 0.7,
                "recommended_action": "Schedule maintenance" if failure_probability > 0.7 else "Monitor"
            })
            
            if model_id:
                prediction = Prediction(
                    model_id=model_id,
                    device_id=device.id,
                    tenant_id=device.tenant_id,
                    prediction_type="failure_probability",
                    predicted_value=failure_probability,
                    confidence=0.7,
                    input_features={"mean": float(mean_val), "std": float(std_val) if std_val else 0}
                )
                db.add(prediction)
        
        db.commit()
        return predictions


# Global analytics engine instance
analytics_engine = AnalyticsEngine()

