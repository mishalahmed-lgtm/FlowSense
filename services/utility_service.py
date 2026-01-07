"""Utility service - handles utility consumption queries sequentially."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

from sqlalchemy import text, func
from sqlalchemy.orm import Session

from models import DeviceSnapshot, Device, TelemetryTimeseries, User, UserRole
from services.base_service import BaseService

logger = logging.getLogger(__name__)


class UtilityService(BaseService):
    """Service for utility consumption data access - all queries run sequentially."""
    
    def get_utility_consumption(
        self,
        user: User,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get utility consumption data for tenant.
        
        Sequential query execution:
        1. Determine date range (default: last month)
        2. Query devices with utility fields (electricity, gas, water)
        3. Aggregate consumption by device and date
        4. Return consumption data
        
        Args:
            user: Current authenticated user
            start_date: Start date for consumption (default: 30 days ago)
            end_date: End date for consumption (default: now)
            
        Returns:
            Dictionary with consumption data by device and utility type
        """
        self._log_query("get_utility_consumption", f"user={user.email}")
        
        if user.role != UserRole.TENANT_ADMIN or not user.tenant_id:
            return {"consumption": [], "total_electricity": 0, "total_gas": 0, "total_water": 0}
        
        tenant_id = user.tenant_id
        end_date = end_date or datetime.now(timezone.utc)
        start_date = start_date or (end_date - timedelta(days=30))
        
        # Query 1: Get devices with utility fields
        self._log_query("query_devices_with_utility", f"tenant_id={tenant_id}")
        devices_query = text("""
            SELECT device_id, payload
            FROM devices_snapshot
            WHERE tenant_id = :tenant_id
              AND (
                (payload->'telemetry'->'data')::jsonb ? 'total_active_energy'
                OR (payload->'telemetry'->'data')::jsonb ? 'level'
                OR (payload->'telemetry'->'data')::jsonb ? 'volume_index'
              )
        """)
        devices = self.db.execute(devices_query, {"tenant_id": tenant_id}).fetchall()
        
        consumption_data = []
        total_electricity = 0.0
        total_gas = 0.0
        total_water = 0.0
        
        # Query 2-N: For each device, get consumption (simplified - using latest telemetry)
        for device_id, payload in devices:
            if not payload or not isinstance(payload, dict):
                continue
            
            telemetry_data = payload.get("telemetry", {}).get("data", {})
            
            # Electricity
            if "total_active_energy" in telemetry_data:
                energy = float(telemetry_data.get("total_active_energy", 0))
                total_electricity += energy
                consumption_data.append({
                    "device_id": device_id,
                    "utility_type": "electricity",
                    "consumption": energy,
                    "unit": "kWh",
                })
            
            # Gas
            if "level" in telemetry_data:
                level = float(telemetry_data.get("level", 0))
                total_gas += level
                consumption_data.append({
                    "device_id": device_id,
                    "utility_type": "gas",
                    "consumption": level,
                    "unit": "%",
                })
            
            # Water
            if "volume_index" in telemetry_data:
                volume = float(telemetry_data.get("volume_index", 0))
                total_water += volume
                consumption_data.append({
                    "device_id": device_id,
                    "utility_type": "water",
                    "consumption": volume,
                    "unit": "m³",
                })
        
        return {
            "consumption": consumption_data,
            "total_electricity": total_electricity,
            "total_gas": total_gas,
            "total_water": total_water,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        }

