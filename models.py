"""Optimized database models for IoT platform - performance-focused design."""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, JSON, Float, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


# ============================================================================
# CORE TENANT STRUCTURE
# ============================================================================

class UserRole(str, enum.Enum):
    """User roles in the system."""
    ADMIN = "admin"
    TENANT_ADMIN = "tenant_admin"


class Tenant(Base):
    """Tenant/organization model."""
    __tablename__ = "tenants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    country = Column(String(100), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    # Contact & Business Information
    contact_email = Column(String(255), nullable=True, index=True)
    contact_phone = Column(String(50), nullable=True)
    business_address = Column(Text, nullable=True)
    timezone = Column(String(100), nullable=True, default="UTC")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    devices = relationship("Device", back_populates="tenant")
    users = relationship("User", back_populates="tenant")
    teams = relationship("Team", back_populates="tenant")


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.TENANT_ADMIN)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    enabled_modules = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    tenant = relationship("Tenant", back_populates="users")
    external_integrations = relationship("ExternalIntegration", back_populates="user", cascade="all, delete-orphan")
    team_memberships = relationship("TeamMember", back_populates="user")


class Team(Base):
    """Team model for grouping users within a tenant."""
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    tenant = relationship("Tenant", back_populates="teams")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    """Team members linking users to teams."""
    __tablename__ = "team_members"
    
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default="member")  # member, lead
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    
    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")


class ExternalIntegration(Base):
    """External integration API keys for tenant data access (Firebase profiles)."""
    __tablename__ = "external_integrations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    api_key = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    allowed_endpoints = Column(JSON, nullable=False, default=list)
    endpoint_urls = Column(JSON, nullable=True, default=dict)
    source_urls = Column(JSON, nullable=True, default=dict)
    webhook_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="external_integrations")


# ============================================================================
# DEVICES & INSTALLATION
# ============================================================================

class Device(Base):
    """Device model - optimized with denormalized fields."""
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(100), unique=True, nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    device_type = Column(String(100), nullable=False, index=True)  # DENORMALIZED: "LPG_Meter", "Valve_Controller", etc.
    name = Column(String(200), nullable=True)
    provisioning_key = Column(String(255), unique=True, nullable=True, index=True)  # DENORMALIZED
    provisioning_key_expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    is_provisioned = Column(Boolean, default=False)
    # Firmware status (DENORMALIZED - was in device_firmware_status table)
    firmware_current_version = Column(String(100), nullable=True)
    firmware_target_version = Column(String(100), nullable=True)
    firmware_status = Column(String(20), nullable=False, default="idle")  # idle, pending, downloading, installing, success, failed
    firmware_last_error = Column(Text, nullable=True)
    firmware_last_update_at = Column(DateTime(timezone=True), nullable=True)
    device_metadata = Column(JSON, nullable=True)  # JSON for flexible fields, dashboard config, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    tenant = relationship("Tenant", back_populates="devices")
    installation = relationship("Installation", back_populates="device", uselist=False)
    device_data = relationship("DeviceData", back_populates="device", cascade="all, delete-orphan")
    rules = relationship("DeviceRule", back_populates="device", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="device", cascade="all, delete-orphan")
    health = relationship("DeviceHealth", back_populates="device", uselist=False)


class DeviceSnapshot(Base):
    """Snapshot of devices per tenant (for external data imports or read-only views - Firebase)."""
    __tablename__ = "devices_snapshot"

    tenant_id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(255), primary_key=True, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class Installation(Base):
    """Installation data with initial sensor readings."""
    __tablename__ = "installations"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    installed_at = Column(DateTime(timezone=True), nullable=False)
    installed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    installation_notes = Column(Text, nullable=True)
    initial_sensor_readings = Column(JSON, nullable=True)  # Sensor data captured at install
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    device = relationship("Device", back_populates="installation")
    location = relationship("Location", back_populates="installation", uselist=False)
    installer = relationship("User")


class Location(Base):
    """Location data filled at installation."""
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    installation_id = Column(Integer, ForeignKey("installations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    accuracy = Column(Float, nullable=True)  # GPS accuracy in meters
    source = Column(String(50), default="gps")  # gps, manual
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    installation = relationship("Installation", back_populates="location")


# ============================================================================
# TELEMETRY (OPTIMIZED)
# ============================================================================

class DeviceData(Base):
    """Live telemetry - latest query gets most recent."""
    __tablename__ = "device_data"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    data = Column(JSON, nullable=False)  # All telemetry fields: {level, temperature, battery, ...}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    device = relationship("Device", back_populates="device_data")
    
    # Composite index for fast latest query: SELECT * FROM device_data WHERE device_id=? ORDER BY timestamp DESC LIMIT 1
    __table_args__ = (
        Index('idx_device_timestamp', 'device_id', 'timestamp'),
    )


class DeviceHealth(Base):
    """Lightweight device health metrics for monitoring."""
    __tablename__ = "device_health"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True, index=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=True)
    current_status = Column(String(20), default="unknown", index=True)  # online, offline, degraded
    connectivity_score = Column(Float, nullable=True)  # 0-100
    message_count_24h = Column(Integer, default=0)
    message_count_7d = Column(Integer, default=0)
    last_battery_level = Column(Float, nullable=True)
    battery_trend = Column(String(20), nullable=True)  # increasing, decreasing, stable
    uptime_24h_percent = Column(Float, nullable=True)
    uptime_7d_percent = Column(Float, nullable=True)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)
    
    device = relationship("Device", back_populates="health")


# ============================================================================
# RULES & ALERTS
# ============================================================================

class DeviceRule(Base):
    """Per-device rules executed inline during ingestion or on schedule."""
    __tablename__ = "device_rules"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=100, index=True)
    is_active = Column(Boolean, default=True, index=True)
    condition = Column(JSON, nullable=False)
    action = Column(JSON, nullable=False)
    rule_type = Column(String(20), default="event", index=True)  # "event" or "scheduled"
    cron_schedule = Column(String(100), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    device = relationship("Device", back_populates="rules")


class AlertPriority(str, enum.Enum):
    """Alert priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertStatus(str, enum.Enum):
    """Alert status."""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AlertRule(Base):
    """Alert rules that define when alerts should be triggered."""
    __tablename__ = "alert_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    condition = Column(JSON, nullable=False)
    priority = Column(Enum(AlertPriority), nullable=False, default=AlertPriority.MEDIUM, index=True)
    title_template = Column(String(500), nullable=False)
    message_template = Column(Text, nullable=True)
    notify_email = Column(Boolean, default=True)
    notify_sms = Column(Boolean, default=False)
    notify_webhook = Column(Boolean, default=False)
    webhook_url = Column(Text, nullable=True)
    escalation_enabled = Column(Boolean, default=False)
    escalation_delay_minutes = Column(Integer, default=30)
    escalation_priority = Column(Enum(AlertPriority), nullable=True)
    aggregation_enabled = Column(Boolean, default=True)
    aggregation_window_minutes = Column(Integer, default=5)
    max_alerts_per_window = Column(Integer, default=10)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    device = relationship("Device")
    tenant = relationship("Tenant")
    alerts = relationship("Alert", back_populates="rule")


class Alert(Base):
    """Alert instances triggered by alert rules."""
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=True)
    priority = Column(Enum(AlertPriority), nullable=False, index=True)
    status = Column(Enum(AlertStatus), nullable=False, default=AlertStatus.OPEN, index=True)
    trigger_data = Column(JSON, nullable=True)
    alert_metadata = Column(JSON, nullable=True)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    escalated = Column(Boolean, default=False)
    aggregated_count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    rule = relationship("AlertRule", back_populates="alerts")
    device = relationship("Device")
    tenant = relationship("Tenant")
    acknowledger = relationship("User", foreign_keys=[acknowledged_by])
    resolver = relationship("User", foreign_keys=[resolved_by])
    notifications = relationship("Notification", back_populates="alert", cascade="all, delete-orphan")


class Notification(Base):
    """Notification attempts for alerts."""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(50), nullable=False, index=True)  # email, sms, webhook
    recipient = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="pending", index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    alert = relationship("Alert", back_populates="notifications")


# ============================================================================
# FIRMWARE
# ============================================================================

class FirmwareUpdateStatus(str, enum.Enum):
    """Per-device firmware update status."""
    IDLE = "idle"
    PENDING = "pending"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    SUCCESS = "success"
    FAILED = "failed"


class FOTAJobStatus(str, enum.Enum):
    """Overall status of a FOTA job."""
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FirmwareVersion(Base):
    """Firmware versions - consolidated table (replaces firmwares + firmware_versions)."""
    __tablename__ = "firmware_versions"

    id = Column(Integer, primary_key=True, index=True)
    device_type = Column(String(100), nullable=False, index=True)  # DENORMALIZED: matches device.device_type
    name = Column(String(200), nullable=False)  # Firmware name/family
    version = Column(String(100), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    checksum = Column(String(128), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    release_notes = Column(Text, nullable=True)
    min_hw_version = Column(String(100), nullable=True)
    is_recommended = Column(Boolean, default=False, index=True)
    is_mandatory = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    jobs = relationship("FOTAJob", back_populates="firmware_version")


class FOTAJob(Base):
    """Firmware update job targeting a set of devices within a tenant."""
    __tablename__ = "fota_jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    firmware_version_id = Column(Integer, ForeignKey("firmware_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(FOTAJobStatus), nullable=False, default=FOTAJobStatus.SCHEDULED, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant")
    firmware_version = relationship("FirmwareVersion", back_populates="jobs")
    created_by = relationship("User")
    devices = relationship("FOTAJobDevice", back_populates="job", cascade="all, delete-orphan")


class FOTAJobDevice(Base):
    """Per-device progress for a FOTA job."""
    __tablename__ = "fota_job_devices"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("fota_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(FirmwareUpdateStatus), nullable=False, default=FirmwareUpdateStatus.PENDING, index=True)
    last_error = Column(Text, nullable=True)
    last_update_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("FOTAJob", back_populates="devices")
    device = relationship("Device")


# ============================================================================
# UTILITY / ENERGY
# ============================================================================

class UtilityTariff(Base):
    """Tariff definition for utility billing (gas, electricity, water)."""
    __tablename__ = "utility_tariffs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    utility_kind = Column(String(50), nullable=False)  # gas, electricity, water
    rate_per_unit = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    is_active = Column(Boolean, default=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UtilityRecord(Base):
    """Consolidated utility records - contracts, consumption, and invoices."""
    __tablename__ = "utility_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    utility_kind = Column(String(50), nullable=False, index=True)  # gas, electricity, water
    
    # Contract fields
    tariff_id = Column(Integer, ForeignKey("utility_tariffs.id", ondelete="RESTRICT"), nullable=True)
    contract_start = Column(DateTime(timezone=True), nullable=True)
    contract_end = Column(DateTime(timezone=True), nullable=True)
    
    # Consumption fields
    period_start = Column(DateTime(timezone=True), nullable=True, index=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    start_index = Column(Float, nullable=True)
    end_index = Column(Float, nullable=True)
    consumption = Column(Float, nullable=True)
    unit = Column(String(20), nullable=True)  # kWh, m3, etc.
    
    # Invoice fields
    amount = Column(Float, nullable=True)
    currency = Column(String(10), default="USD")
    status = Column(String(20), default="draft", index=True)  # draft, issued, paid (for invoices)
    tariff_snapshot = Column(JSON, nullable=True)  # Snapshot of tariff at calculation time
    
    # Record type to distinguish contract/consumption/invoice
    record_type = Column(String(20), nullable=False, index=True)  # "contract", "consumption", "invoice"
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    tenant = relationship("Tenant")
    device = relationship("Device")
    tariff = relationship("UtilityTariff")


# Aliases for backward compatibility (models that were denormalized/removed)
TelemetryLatest = DeviceData  # DeviceData replaces TelemetryLatest
TelemetryTimeseries = DeviceData  # Use DeviceData for time-series queries

# Stub classes for removed models (to prevent import errors)
class DeviceDashboard:
    """Stub - was denormalized into Device.device_metadata"""
    pass

class AlertAuditLog:
    """Stub - removed in optimized schema"""
    pass

class DeviceType:
    """Stub - device_type is now a string field on Device"""
    pass

class ProvisioningKey:
    """Stub - provisioning_key is now a field on Device"""
    pass

class DeviceHealthMetrics:
    """Stub - use DeviceHealth instead"""
    pass

class DeviceHealthHistory:
    """Stub - removed in optimized schema"""
    pass

class MLModel:
    """Stub - removed in optimized schema"""
    pass

class Prediction:
    """Stub - removed in optimized schema"""
    pass

class PatternAnalysis:
    """Stub - removed in optimized schema"""
    pass

class CorrelationResult:
    """Stub - removed in optimized schema"""
    pass

class AnalyticsJob:
    """Stub - removed in optimized schema"""
    pass

class AnalyticsJobStatus:
    """Stub - removed in optimized schema"""
    pass

class AnalyticsJobType:
    """Stub - removed in optimized schema"""
    pass

class CEPRule:
    """Stub - removed in optimized schema"""
    pass
