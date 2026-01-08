"""Environmental service - handles environmental data queries sequentially."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

from sqlalchemy import text, func
from sqlalchemy.orm import Session

from models import DeviceSnapshot, TelemetryTimeseries, User, UserRole
from services.base_service import BaseService

logger = logging.getLogger(__name__)


class EnvironmentalService(BaseService):
    """Service for environmental data access - all queries run sequentially."""
    
    def get_environmental_summary(
        self,
        user: User,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Get environmental data summary (AQI, PM2.5, PM10, CO2, temperature, humidity).
        
        Sequential query execution:
        1. Query devices with environmental sensors
        2. Aggregate environmental data from telemetry
        3. Calculate AQI if possible
        4. Return summary statistics
        
        Args:
            user: Current authenticated user
            hours: Number of hours to look back (default: 24)
            
        Returns:
            Dictionary with environmental metrics
        """
        self._log_query("get_environmental_summary", f"user={user.email}, hours={hours}")
        
        if user.role != UserRole.TENANT_ADMIN or not user.tenant_id:
            return {
                "pm25_avg": 0,
                "pm10_avg": 0,
                "co2_avg": 0,
                "temperature_avg": 0,
                "humidity_avg": 0,
                "aqi": 0,
            }
        
        tenant_id = user.tenant_id
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Query 1: Get environmental data from devices_snapshot
        self._log_query("query_environmental_data", f"tenant_id={tenant_id}")
        env_query = text("""
            SELECT 
                payload->'telemetry'->'data'->>'pm25' as pm25,
                payload->'telemetry'->'data'->>'pm10' as pm10,
                payload->'telemetry'->'data'->>'co2' as co2,
                payload->'telemetry'->'data'->>'temperature' as temperature,
                payload->'telemetry'->'data'->>'humidity' as humidity
            FROM devices_snapshot
            WHERE tenant_id = :tenant_id
              AND (
                (payload->'telemetry'->'data')::jsonb ? 'pm25'
                OR (payload->'telemetry'->'data')::jsonb ? 'pm10'
                OR (payload->'telemetry'->'data')::jsonb ? 'co2'
                OR (payload->'telemetry'->'data')::jsonb ? 'temperature'
                OR (payload->'telemetry'->'data')::jsonb ? 'humidity'
              )
              AND (payload->'telemetry'->>'timestamp')::timestamptz >= CAST(:cutoff AS timestamptz)
        """)
        try:
            results = self.db.execute(env_query, {"tenant_id": tenant_id, "cutoff": cutoff.isoformat()}).fetchall()
        except Exception as e:
            self._handle_error(e, "Error querying environmental data")
            return {
                "pm25_avg": 0,
                "pm10_avg": 0,
                "co2_avg": 0,
                "temperature_avg": 0,
                "humidity_avg": 0,
                "aqi": 0,
                "sample_count": 0,
            }
        
        # Aggregate data
        pm25_values = []
        pm10_values = []
        co2_values = []
        temp_values = []
        humidity_values = []
        
        for row in results:
            if row.pm25:
                try:
                    pm25_values.append(float(row.pm25))
                except:
                    pass
            if row.pm10:
                try:
                    pm10_values.append(float(row.pm10))
                except:
                    pass
            if row.co2:
                try:
                    co2_values.append(float(row.co2))
                except:
                    pass
            if row.temperature:
                try:
                    temp_values.append(float(row.temperature))
                except:
                    pass
            if row.humidity:
                try:
                    humidity_values.append(float(row.humidity))
                except:
                    pass
        
        # Calculate averages
        pm25_avg = sum(pm25_values) / len(pm25_values) if pm25_values else 0
        pm10_avg = sum(pm10_values) / len(pm10_values) if pm10_values else 0
        co2_avg = sum(co2_values) / len(co2_values) if co2_values else 0
        temp_avg = sum(temp_values) / len(temp_values) if temp_values else 0
        humidity_avg = sum(humidity_values) / len(humidity_values) if humidity_values else 0
        
        # Calculate AQI (simplified - based on PM2.5)
        aqi = 0
        if pm25_avg > 0:
            if pm25_avg <= 12:
                aqi = int((pm25_avg / 12) * 50)
            elif pm25_avg <= 35.4:
                aqi = int(50 + ((pm25_avg - 12) / 23.4) * 50)
            elif pm25_avg <= 55.4:
                aqi = int(100 + ((pm25_avg - 35.4) / 20) * 50)
            elif pm25_avg <= 150.4:
                aqi = int(150 + ((pm25_avg - 55.4) / 95) * 100)
            else:
                aqi = 300
        
        return {
            "pm25_avg": round(pm25_avg, 2),
            "pm10_avg": round(pm10_avg, 2),
            "co2_avg": round(co2_avg, 2),
            "temperature_avg": round(temp_avg, 2),
            "humidity_avg": round(humidity_avg, 2),
            "aqi": aqi,
            "sample_count": len(results),
        }

