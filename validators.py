"""Data validation for telemetry payloads."""
import json
import logging
from typing import Dict, Any, Optional, Tuple
from jsonschema import validate, ValidationError, SchemaError
from database import SessionLocal
from models import DeviceType

logger = logging.getLogger(__name__)


class TelemetryValidator:
    """
    Validates telemetry payloads against device type schemas.
    """
    
    def __init__(self):
        """Initialize validator."""
        self._schema_cache: Dict[str, Dict] = {}  # Cache schemas by device type name
    
    def _get_device_schema(self, device_type_name: str) -> Optional[Dict]:
        """
        Get JSON schema for a device type.
        
        Args:
            device_type_name: Name of the device type
            
        Returns:
            JSON schema dict or None if not found
        """
        # Check cache first
        if device_type_name in self._schema_cache:
            return self._schema_cache[device_type_name]
        
        # Query database
        db = SessionLocal()
        try:
            device_type = db.query(DeviceType).filter(
                DeviceType.name == device_type_name
            ).first()
            
            if device_type and device_type.schema_definition:
                try:
                    schema = json.loads(device_type.schema_definition)
                    self._schema_cache[device_type_name] = schema
                    return schema
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Invalid JSON schema for device type {device_type_name}: {e}"
                    )
                    return None
            else:
                # No schema defined - use default permissive schema
                logger.debug(f"No schema defined for device type {device_type_name}, using permissive validation")
                return None
                
        except Exception as e:
            logger.error(f"Error loading schema for device type {device_type_name}: {e}")
            return None
        finally:
            db.close()
    
    def validate_payload(
        self,
        device_type_name: Optional[str],
        payload: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate telemetry payload against device type schema.
        
        Args:
            device_type_name: Name of the device type (e.g., "LPG Meter")
            payload: Telemetry payload to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # If no device type, skip validation (permissive mode)
        if not device_type_name:
            return True, None
        
        # Get schema for device type
        schema = self._get_device_schema(device_type_name)
        
        # If no schema defined, allow all payloads (permissive mode)
        if schema is None:
            return True, None
        
        # Validate against schema
        try:
            validate(instance=payload, schema=schema)
            return True, None
        except ValidationError as e:
            error_msg = f"Validation error: {e.message}"
            if e.path:
                error_msg += f" (path: {'.'.join(str(p) for p in e.path)})"
            logger.warning(
                f"Payload validation failed for device type {device_type_name}: {error_msg}"
            )
            return False, error_msg
        except SchemaError as e:
            logger.error(f"Invalid schema for device type {device_type_name}: {e}")
            return False, f"Schema error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during validation: {e}")
            return False, f"Validation error: {str(e)}"
    
    def get_default_schemas(self) -> Dict[str, Dict]:
        """
        Get default JSON schemas for common device types.
        These can be used as templates when creating device types.
        
        Returns:
            Dict mapping device type names to their default schemas
        """
        return {
            "LPG Meter": {
                "type": "object",
                "properties": {
                    "level": {"type": "number", "minimum": 0, "maximum": 100},
                    "temperature": {"type": "number"},
                    "pressure": {"type": "number", "minimum": 0},
                    "battery": {"type": "number", "minimum": 0, "maximum": 100}
                },
                "required": ["level"]
            },
            "Valve Controller": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["open", "closed", "error"]},
                    "battery": {"type": "number", "minimum": 0, "maximum": 100},
                    "signal_strength": {"type": "number"}
                },
                "required": ["status"]
            },
            "GPS Tracker": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                    "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                    "altitude": {"type": "number"},
                    "speed": {"type": "number", "minimum": 0},
                    "battery": {"type": "number", "minimum": 0, "maximum": 100}
                },
                "required": ["latitude", "longitude"]
            }
        }


# Global validator instance
telemetry_validator = TelemetryValidator()

