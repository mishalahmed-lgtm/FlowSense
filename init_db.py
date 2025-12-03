"""Database initialization script to create sample data."""
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, DeviceType, Tenant, Device, ProvisioningKey
import secrets

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # Create device types
    device_types = [
        DeviceType(
            name="LPG Meter",
            description="Ultrasonic LPG Meter with NB-IoT connectivity",
            protocol="HTTP",
            schema_definition='{"type": "object", "properties": {"level": {"type": "number"}, "temperature": {"type": "number"}, "pressure": {"type": "number"}}}'
        ),
        DeviceType(
            name="Valve Controller",
            description="NB-IoT Valve Controller",
            protocol="MQTT",
            schema_definition='{"type": "object", "properties": {"state": {"type": "string", "enum": ["open", "closed"]}, "battery": {"type": "number"}}}'
        ),
        DeviceType(
            name="GPS Tracker",
            description="Truck GPS/Verification Device",
            protocol="HTTP",
            schema_definition='{"type": "object", "properties": {"latitude": {"type": "number"}, "longitude": {"type": "number"}, "speed": {"type": "number"}}}'
        ),
        DeviceType(
            name="Dingtek DC41X",
            description="Dingtek ultrasonic LPG level sensor (hexadecimal TCP payload)",
            protocol="TCP_HEX",
            schema_definition='{"type": "object", "properties": {"height_mm": {"type": "number"}, "gps_present": {"type": "boolean"}, "longitude_deg": {"type": ["number", "null"]}, "latitude_deg": {"type": ["number", "null"]}, "temperature_c": {"type": "number"}, "angle_deg": {"type": "number"}, "full_alarm": {"type": "boolean"}, "move_alarm": {"type": "boolean"}, "battery_low_alarm": {"type": "boolean"}, "battery_mv": {"type": "number"}, "battery_v": {"type": "number"}, "rsrp_dbm": {"type": "number"}, "frame_counter": {"type": "number"}, "device_id_bcd": {"type": "string"}}, "required": ["height_mm", "gps_present", "temperature_c", "battery_mv", "rsrp_dbm", "frame_counter", "device_id_bcd"]}'
        ),
        DeviceType(
            name="DC41X Smart Manhole",
            description="Dingtek DC41X smart manhole sensor (hexadecimal TCP payload)",
            protocol="TCP_HEX",
            # Reuse the same schema as the DC41X tank sensor
            schema_definition='{"type": "object", "properties": {"height_mm": {"type": "number"}, "gps_present": {"type": "boolean"}, "longitude_deg": {"type": ["number", "null"]}, "latitude_deg": {"type": ["number", "null"]}, "temperature_c": {"type": "number"}, "angle_deg": {"type": "number"}, "full_alarm": {"type": "boolean"}, "move_alarm": {"type": "boolean"}, "battery_low_alarm": {"type": "boolean"}, "battery_mv": {"type": "number"}, "battery_v": {"type": "number"}, "rsrp_dbm": {"type": "number"}, "frame_counter": {"type": "number"}, "device_id_bcd": {"type": "string"}}, "required": ["height_mm", "gps_present", "temperature_c", "battery_mv", "rsrp_dbm", "frame_counter", "device_id_bcd"]}'
        ),
        DeviceType(
            name="Comcore AMI Meter",
            description="Electricity meter integrated via Comcore AMI realtime API",
            protocol="HTTP",
            schema_definition=(
                '{"type": "object", "properties": {'
                '"total_active_energy": {"type": "number"},'
                '"total_active_energy_plus": {"type": "number"},'
                '"total_active_energy_minus": {"type": "number"},'
                '"total_reactive_energy": {"type": "number"},'
                '"total_reactive_energy_plus": {"type": "number"},'
                '"total_reactive_energy_minus": {"type": "number"},'
                '"voltage_l1": {"type": "number"},'
                '"voltage_l2": {"type": "number"},'
                '"voltage_l3": {"type": "number"},'
                '"current_l1": {"type": "number"},'
                '"current_l2": {"type": "number"},'
                '"current_l3": {"type": "number"},'
                '"frequency": {"type": "number"},'
                '"power_factor_total": {"type": "number"},'
                '"power_factor_l1": {"type": "number"},'
                '"power_factor_l2": {"type": "number"},'
                '"power_factor_l3": {"type": "number"},'
                '"active_power_total": {"type": "number"},'
                '"active_power_l1": {"type": "number"},'
                '"active_power_l2": {"type": "number"},'
                '"active_power_l3": {"type": "number"},'
                '"reactive_power_total": {"type": "number"},'
                '"reactive_power_l1": {"type": "number"},'
                '"reactive_power_l2": {"type": "number"},'
                '"reactive_power_l3": {"type": "number"},'
                '"meter_time": {"type": "string"},'
                '"relay_status": {"type": "string"}'
                "}}"
            ),
        ),
        DeviceType(
            name="Comcore DLMS Meter",
            description="Electricity meter integrated via Comcore DLMS TCP protocol via gateway",
            protocol="HTTP",
            schema_definition=(
                '{"type": "object", "properties": {'
                '"voltage_a": {"type": "number"},'
                '"voltage_b": {"type": "number"},'
                '"voltage_c": {"type": "number"},'
                '"current_a": {"type": "number"},'
                '"current_b": {"type": "number"},'
                '"current_c": {"type": "number"},'
                '"power_factor_a": {"type": "number"},'
                '"power_factor_b": {"type": "number"},'
                '"power_factor_c": {"type": "number"},'
                '"frequency_hz": {"type": "number"},'
                '"active_energy_import_total": {"type": "number"},'
                '"active_energy_export_total": {"type": "number"},'
                '"reactive_energy_import_total": {"type": "number"},'
                '"reactive_energy_export_total": {"type": "number"},'
                '"event_code": {"type": "integer"},'
                '"event_type": {"type": "string"},'
                '"dcu_address": {"type": "string"},'
                '"meter_time": {"type": "string"},'
                '"heartbeat_rssi": {"type": "integer"}'
                "}}"
            ),
        ),
    ]
    
    for dt in device_types:
        existing = db.query(DeviceType).filter(DeviceType.name == dt.name).first()
        if not existing:
            db.add(dt)
    
    db.commit()
    
    # Create a default tenant
    tenant = db.query(Tenant).filter(Tenant.code == "default").first()
    if not tenant:
        tenant = Tenant(
            name="Default Tenant",
            code="default",
            is_active=True
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    
    # Create sample devices
    lpg_meter_type = db.query(DeviceType).filter(DeviceType.name == "LPG Meter").first()
    valve_type = db.query(DeviceType).filter(DeviceType.name == "Valve Controller").first()
    gps_type = db.query(DeviceType).filter(DeviceType.name == "GPS Tracker").first()
    dingtek_type = db.query(DeviceType).filter(DeviceType.name == "Dingtek DC41X").first()
    dingtek_manhole_type = db.query(DeviceType).filter(DeviceType.name == "DC41X Smart Manhole").first()
    comcore_type = db.query(DeviceType).filter(DeviceType.name == "Comcore AMI Meter").first()
    comcore_dlms_type = db.query(DeviceType).filter(DeviceType.name == "Comcore DLMS Meter").first()
    
    sample_devices = [
        {
            "device_id": "LPG-METER-001",
            "name": "LPG Meter 001",
            "device_type": lpg_meter_type,
            "tenant": tenant
        },
        {
            "device_id": "VALVE-001",
            "name": "Valve Controller 001",
            "device_type": valve_type,
            "tenant": tenant
        },
        {
            "device_id": "GPS-TRUCK-001",
            "name": "GPS Tracker 001",
            "device_type": gps_type,
            "tenant": tenant
        },
        {
            "device_id": "1865057042853303",
            "name": "DC41X Tank Sensor 001",
            "device_type": dingtek_type,
            "tenant": tenant
        },
        {
            # BCD device id 1865057042853304 (last digit 4) – separate sensor
            "device_id": "1865057042853304",
            "name": "DC41X Smart Manhole 001",
            "device_type": dingtek_manhole_type or dingtek_type,
            "tenant": tenant
        },
        {
            "device_id": "COMCORE-METER-001",
            "name": "Comcore AMI Meter 001",
            "device_type": comcore_type,
            "tenant": tenant
        },
        {
            "device_id": "COMCORE-DLMS-001",
            "name": "Comcore DLMS Meter 001",
            "device_type": comcore_dlms_type,
            "tenant": tenant
        }
    ]
    
    for device_data in sample_devices:
        device = db.query(Device).filter(Device.device_id == device_data["device_id"]).first()
        if not device:
            device = Device(
                device_id=device_data["device_id"],
                name=device_data["name"],
                device_type_id=device_data["device_type"].id,
                tenant_id=device_data["tenant"].id,
                is_active=True,
                is_provisioned=True
            )
            db.add(device)
            db.commit()
            db.refresh(device)
            
            # Create provisioning key
            provisioning_key = ProvisioningKey(
                device_id=device.id,
                key=secrets.token_urlsafe(32),  # Generate secure random key
                is_active=True
            )
            db.add(provisioning_key)
            db.commit()
            
            print(f"Created device: {device.device_id}")
            print(f"  Provisioning Key: {provisioning_key.key}")
            print()
    
    print("Database initialization complete!")
    
except Exception as e:
    print(f"Error initializing database: {e}")
    db.rollback()
finally:
    db.close()

