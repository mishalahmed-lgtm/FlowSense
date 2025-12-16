"""Database models for device management and provisioning."""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, JSON, Float, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


class DeviceType(Base):
    """Device type definitions (e.g., LPG Meter, Valve Controller, GPS Tracker)."""
    __tablename__ = "device_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    protocol = Column(String(50), nullable=False)  # HTTP, MQTT
    schema_definition = Column(Text, nullable=True)  # JSON schema for validation
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    devices = relationship("Device", back_populates="device_type")


class UserRole(str, enum.Enum):
    """User roles in the system."""
    ADMIN = "admin"  # Super admin - manages all tenants and users
    TENANT_ADMIN = "tenant_admin"  # Tenant admin - manages their tenant


class Tenant(Base):
    """Tenant/organization model."""
    __tablename__ = "tenants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    devices = relationship("Device", back_populates="tenant")
    users = relationship("User", back_populates="tenant")


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.TENANT_ADMIN)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Module permissions (JSON array of module names)
    # e.g., ["devices", "dashboards", "utility", "rules", "alerts"]
    enabled_modules = Column(JSON, nullable=False, default=list)
    
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    tenant = relationship("Tenant", back_populates="users")


class Device(Base):
    """Device model."""
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=True)
    device_type_id = Column(Integer, ForeignKey("device_types.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    is_provisioned = Column(Boolean, default=False)
    device_metadata = Column(Text, nullable=True)  # JSON metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    device_type = relationship("DeviceType", back_populates="devices")
    tenant = relationship("Tenant", back_populates="devices")
    provisioning_key = relationship("ProvisioningKey", back_populates="device", uselist=False)
    rules = relationship("DeviceRule", back_populates="device", cascade="all, delete-orphan")
    dashboard = relationship(
        "DeviceDashboard",
        back_populates="device",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ProvisioningKey(Base):
    """Device provisioning keys for authentication."""
    __tablename__ = "provisioning_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), unique=True, nullable=False, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)  # The actual provisioning key
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    device = relationship("Device", back_populates="provisioning_key")


class DeviceRule(Base):
    """Per-device rules executed inline during ingestion."""

    __tablename__ = "device_rules"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=100, index=True)
    is_active = Column(Boolean, default=True, index=True)
    condition = Column(JSON, nullable=False)  # JSON DSL describing checks
    action = Column(JSON, nullable=False)  # JSON describing resulting action
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    device = relationship("Device", back_populates="rules")


class DeviceDashboard(Base):
    """Per-device dashboard configuration (selected widgets/layout)."""

    __tablename__ = "device_dashboards"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(
        Integer,
        ForeignKey("devices.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    # Arbitrary JSON describing widgets, e.g.:
    # {
    #   "widgets": [
    #     {"id": "levelGauge", "type": "gauge", "field": "level", "min": 0, "max": 100},
    #     {"id": "batteryCard", "type": "stat", "field": "battery"}
    #   ]
    # }
    config = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    device = relationship("Device", back_populates="dashboard")


class TelemetryLatest(Base):
    """Latest telemetry snapshot per device for fast dashboard reads."""

    __tablename__ = "telemetry_latest"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(
        Integer,
        ForeignKey("devices.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    # Raw payload as JSON object (key/value pairs as sent by device)
    data = Column(JSON, nullable=False)
    # ISO timestamp string of the original telemetry payload (device or server time)
    event_timestamp = Column(DateTime(timezone=True), nullable=True)
    # When this record was last updated in the platform
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TelemetryTimeseries(Base):
    """Time-series telemetry for dashboards and historical charts."""

    __tablename__ = "telemetry_timeseries"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    # UTC event timestamp
    ts = Column(DateTime(timezone=True), nullable=False, index=True)
    # Flattened key for the metric, e.g. 'level', 'temperature'
    key = Column(String(120), nullable=False, index=True)
    # Numeric value for charts; non-numeric fields can be stored as text in the future if needed
    value = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Optional: relationship back to Device if needed later
    # device = relationship("Device")


class UtilityTariff(Base):
    """Tariff definition for utility billing (gas, electricity, water)."""

    __tablename__ = "utility_tariffs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    utility_kind = Column(String(50), nullable=False)  # gas, electricity, water
    rate_per_unit = Column(Float, nullable=False)  # e.g. price per kWh, m3, etc.
    currency = Column(String(10), nullable=False, default="USD")
    is_active = Column(Boolean, default=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UtilityDeviceContract(Base):
    """Link a device (meter) and tenant to a tariff for a given period."""

    __tablename__ = "utility_device_contracts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    utility_kind = Column(String(50), nullable=False)  # gas, electricity, water
    tariff_id = Column(Integer, ForeignKey("utility_tariffs.id", ondelete="RESTRICT"), nullable=False)
    contract_start = Column(DateTime(timezone=True), nullable=False)
    contract_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UtilityConsumption(Base):
    """Computed consumption per device/tenant/period."""

    __tablename__ = "utility_consumption"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    utility_kind = Column(String(50), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    start_index = Column(Float, nullable=True)
    end_index = Column(Float, nullable=True)
    consumption = Column(Float, nullable=True)
    unit = Column(String(20), nullable=True)  # kWh, m3, etc.
    generated_at = Column(DateTime(timezone=True), server_default=func.now())


class UtilityInvoice(Base):
    """Simple invoice per device/tenant/period based on consumption and tariff."""

    __tablename__ = "utility_invoices"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    utility_kind = Column(String(50), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    consumption = Column(Float, nullable=True)
    unit = Column(String(20), nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String(10), nullable=False, default="USD")
    status = Column(String(20), nullable=False, default="draft")  # draft, issued, paid
    tariff_snapshot = Column(JSON, nullable=True)  # tariff details at calculation time
    created_at = Column(DateTime(timezone=True), server_default=func.now())

