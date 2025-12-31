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
    protocol = Column(String(50), nullable=False)  # HTTP, MQTT, TCP_HEX, LoRaWAN, Modbus_TCP, DALI
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
    country = Column(String(100), nullable=True, index=True)  # Country code (e.g., "SA", "US", "AE") for billing rates
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
    external_integrations = relationship("ExternalIntegration", back_populates="user", cascade="all, delete-orphan")


class ExternalIntegration(Base):
    """External integration API keys for tenant data access."""
    __tablename__ = "external_integrations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    api_key = Column(String(255), unique=True, nullable=False, index=True)  # Generated API key
    name = Column(String(200), nullable=True)  # Friendly name for the integration
    description = Column(Text, nullable=True)
    
    # Permissions: which endpoints can be accessed
    # JSON array: ["health", "data", "devices"]
    allowed_endpoints = Column(JSON, nullable=False, default=list)
    
    # Custom endpoint URLs for each type (optional)
    # JSON object: {"health": "https://example.com/health", "data": "https://example.com/data", "devices": "https://example.com/devices"}
    endpoint_urls = Column(JSON, nullable=True, default=dict)
    
    # Source URLs for automatic fetching (where to fetch data FROM)
    # JSON object: {"installations": "https://external-api.com/api/installations", "data": "https://external-api.com/api/data"}
    source_urls = Column(JSON, nullable=True, default=dict)
    
    # Optional: webhook URL to receive data (deprecated, use endpoint_urls instead)
    webhook_url = Column(String(500), nullable=True)
    
    is_active = Column(Boolean, default=True, index=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="external_integrations")


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
    alerts = relationship("Alert", back_populates="device", cascade="all, delete-orphan")


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
    """Per-device rules executed inline during ingestion or on schedule."""

    __tablename__ = "device_rules"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=100, index=True)
    is_active = Column(Boolean, default=True, index=True)
    condition = Column(JSON, nullable=False)  # JSON DSL describing checks
    action = Column(JSON, nullable=False)  # JSON describing resulting action
    
    # Scheduled rule support (cron-based)
    rule_type = Column(String(20), default="event", index=True)  # "event" (real-time) or "scheduled" (cron)
    cron_schedule = Column(String(100), nullable=True)  # Cron expression (e.g., "0 */5 * * *" for every 5 minutes)
    last_run_at = Column(DateTime(timezone=True), nullable=True)  # Last time rule was executed
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)  # Next scheduled execution
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    device = relationship("Device", back_populates="rules")


class CEPRule(Base):
    """Complex Event Processing rules - detect patterns across multiple devices/events."""

    __tablename__ = "cep_rules"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=100, index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # CEP pattern definition
    pattern = Column(JSON, nullable=False)  # Pattern to detect (sequence, window, etc.)
    condition = Column(JSON, nullable=False)  # Condition on matched pattern
    action = Column(JSON, nullable=False)  # Action to take when pattern matches
    
    # Pattern matching state
    window_seconds = Column(Integer, default=300)  # Time window for pattern matching
    min_events = Column(Integer, default=2)  # Minimum events to match pattern
    
    # Execution tracking
    last_matched_at = Column(DateTime(timezone=True), nullable=True)
    match_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant")


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
    
    # Scope: device-specific, tenant-specific, or global
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Condition: JSON condition similar to DeviceRule
    condition = Column(JSON, nullable=False)
    
    # Alert properties
    priority = Column(Enum(AlertPriority), nullable=False, default=AlertPriority.MEDIUM, index=True)
    title_template = Column(String(500), nullable=False)  # Template for alert title
    message_template = Column(Text, nullable=True)  # Template for alert message
    
    # Notification channels
    notify_email = Column(Boolean, default=True)
    notify_sms = Column(Boolean, default=False)
    notify_webhook = Column(Boolean, default=False)
    webhook_url = Column(Text, nullable=True)
    
    # Escalation rules
    escalation_enabled = Column(Boolean, default=False)
    escalation_delay_minutes = Column(Integer, default=30)  # Escalate after X minutes if not acknowledged
    escalation_priority = Column(Enum(AlertPriority), nullable=True)  # New priority after escalation
    
    # Aggregation (prevent flooding)
    aggregation_enabled = Column(Boolean, default=True)
    aggregation_window_minutes = Column(Integer, default=5)  # Group alerts within X minutes
    max_alerts_per_window = Column(Integer, default=10)  # Max alerts before throttling
    
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
    
    # Alert details
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=True)
    priority = Column(Enum(AlertPriority), nullable=False, index=True)
    status = Column(Enum(AlertStatus), nullable=False, default=AlertStatus.OPEN, index=True)
    
    # Context data
    trigger_data = Column(JSON, nullable=True)  # The telemetry/event that triggered this alert
    alert_metadata = Column(JSON, nullable=True)  # Additional context (renamed from metadata to avoid SQLAlchemy conflict)
    
    # Timestamps
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    closed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Escalation
    escalated = Column(Boolean, default=False)
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    escalated_priority = Column(Enum(AlertPriority), nullable=True)
    
    # Aggregation
    aggregated_count = Column(Integer, default=1)  # Number of similar alerts grouped together
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    rule = relationship("AlertRule", back_populates="alerts")
    device = relationship("Device")
    tenant = relationship("Tenant")
    acknowledger = relationship("User", foreign_keys=[acknowledged_by])
    resolver = relationship("User", foreign_keys=[resolved_by])
    closer = relationship("User", foreign_keys=[closed_by])
    notifications = relationship("Notification", back_populates="alert", cascade="all, delete-orphan")
    audit_logs = relationship("AlertAuditLog", back_populates="alert", cascade="all, delete-orphan")


class Notification(Base):
    """Notification attempts for alerts."""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Channel
    channel = Column(String(50), nullable=False, index=True)  # email, sms, webhook, push
    
    # Recipient
    recipient = Column(String(255), nullable=False)  # email address, phone number, webhook URL, etc.
    
    # Status
    status = Column(String(50), nullable=False, default="pending", index=True)  # pending, sent, failed, retrying
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Content
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    alert = relationship("Alert", back_populates="notifications")


class AlertAuditLog(Base):
    """Audit trail for alert actions."""
    __tablename__ = "alert_audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    action = Column(String(100), nullable=False, index=True)  # created, acknowledged, resolved, closed, escalated, updated
    details = Column(JSON, nullable=True)  # Additional action details
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    alert = relationship("Alert", back_populates="audit_logs")
    user = relationship("User")


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


class Firmware(Base):
    """Firmware definition for a given device type (logical firmware family)."""
    __tablename__ = "firmwares"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    device_type_id = Column(Integer, ForeignKey("device_types.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    device_type = relationship("DeviceType")
    versions = relationship("FirmwareVersion", back_populates="firmware", cascade="all, delete-orphan")


class FirmwareVersion(Base):
    """Concrete firmware version and binary metadata."""
    __tablename__ = "firmware_versions"

    id = Column(Integer, primary_key=True, index=True)
    firmware_id = Column(Integer, ForeignKey("firmwares.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(100), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)  # Path or URL to firmware binary
    checksum = Column(String(128), nullable=True)  # e.g. SHA256
    file_size_bytes = Column(Integer, nullable=True)
    release_notes = Column(Text, nullable=True)
    min_hw_version = Column(String(100), nullable=True)
    is_recommended = Column(Boolean, default=False, index=True)
    is_mandatory = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    firmware = relationship("Firmware", back_populates="versions")
    jobs = relationship("FOTAJob", back_populates="firmware_version")


class DeviceFirmwareStatus(Base):
    """Current firmware state for a device."""
    __tablename__ = "device_firmware_status"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    current_version = Column(String(100), nullable=True)
    target_version = Column(String(100), nullable=True)
    status = Column(Enum(FirmwareUpdateStatus), nullable=False, default=FirmwareUpdateStatus.IDLE, index=True)
    last_error = Column(Text, nullable=True)
    last_update_at = Column(DateTime(timezone=True), nullable=True)

    device = relationship("Device")


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


class DeviceHealthMetrics(Base):
    """Aggregated health metrics for device monitoring (uptime, connectivity, battery trends)."""
    __tablename__ = "device_health_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Uptime tracking
    last_seen_at = Column(DateTime(timezone=True), nullable=True, index=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=True)
    total_uptime_seconds = Column(Integer, default=0)  # Cumulative uptime
    total_downtime_seconds = Column(Integer, default=0)  # Cumulative downtime
    current_status = Column(String(20), default="unknown", index=True)  # online, offline, degraded
    
    # Connectivity metrics
    avg_message_interval_seconds = Column(Float, nullable=True)  # Average time between messages
    message_count_24h = Column(Integer, default=0)
    message_count_7d = Column(Integer, default=0)
    connectivity_score = Column(Float, nullable=True)  # 0-100, based on message regularity
    
    # Battery status (if applicable)
    last_battery_level = Column(Float, nullable=True)
    battery_trend = Column(String(20), nullable=True)  # increasing, decreasing, stable
    estimated_battery_days_remaining = Column(Integer, nullable=True)
    
    # Calculated uptime percentages
    uptime_24h_percent = Column(Float, nullable=True)
    uptime_7d_percent = Column(Float, nullable=True)
    uptime_30d_percent = Column(Float, nullable=True)
    
    # Timestamps
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    device = relationship("Device")


class AnalyticsJobStatus(str, enum.Enum):
    """Analytics job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalyticsJobType(str, enum.Enum):
    """Type of analytics job."""
    REALTIME_STREAM = "realtime_stream"  # Apache Flink simulation
    BATCH_ANALYTICS = "batch_analytics"  # Apache Spark simulation
    ML_TRAINING = "ml_training"  # Train ML model
    PREDICTIVE_MAINTENANCE = "predictive_maintenance"
    PATTERN_ANALYSIS = "pattern_analysis"
    CORRELATION_ANALYSIS = "correlation_analysis"


class AnalyticsJob(Base):
    """Analytics job for processing data with various engines."""
    __tablename__ = "analytics_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    job_type = Column(Enum(AnalyticsJobType), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Job configuration
    config = Column(JSON, nullable=True)  # Job-specific configuration
    device_ids = Column(JSON, nullable=True)  # List of device IDs to analyze
    
    # Status
    status = Column(Enum(AnalyticsJobStatus), nullable=False, default=AnalyticsJobStatus.PENDING, index=True)
    progress_percent = Column(Float, default=0.0)
    
    # Results
    results = Column(JSON, nullable=True)  # Job results
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    tenant = relationship("Tenant")
    created_by = relationship("User")


class MLModel(Base):
    """Machine learning model for predictions and analytics."""
    __tablename__ = "ml_models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    model_type = Column(String(50), nullable=False)  # anomaly_detection, failure_prediction, pattern_recognition, etc.
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    device_type_id = Column(Integer, ForeignKey("device_types.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Model metadata
    algorithm = Column(String(100), nullable=False)  # isolation_forest, lstm, random_forest, etc.
    model_version = Column(String(50), nullable=False, default="1.0.0")
    model_path = Column(String(500), nullable=True)  # Path to serialized model file
    
    # Training info
    training_data_range_start = Column(DateTime(timezone=True), nullable=True)
    training_data_range_end = Column(DateTime(timezone=True), nullable=True)
    training_accuracy = Column(Float, nullable=True)
    training_samples = Column(Integer, nullable=True)
    
    # Model parameters
    parameters = Column(JSON, nullable=True)  # Model hyperparameters
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_trained = Column(Boolean, default=False)
    
    # Timestamps
    trained_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    tenant = relationship("Tenant")
    device_type = relationship("DeviceType")
    predictions = relationship("Prediction", back_populates="model")


class Prediction(Base):
    """Predictions generated by ML models."""
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Prediction details
    prediction_type = Column(String(50), nullable=False)  # failure_probability, anomaly_score, next_value, etc.
    predicted_value = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)  # 0-1 confidence score
    prediction_data = Column(JSON, nullable=True)  # Additional prediction details
    
    # Input features used
    input_features = Column(JSON, nullable=True)
    
    # Timestamp
    predicted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    model = relationship("MLModel", back_populates="predictions")
    device = relationship("Device")
    tenant = relationship("Tenant")


class PatternAnalysis(Base):
    """Results of usage pattern analysis (occupancy, traffic, energy consumption)."""
    __tablename__ = "pattern_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Analysis type
    analysis_type = Column(String(50), nullable=False, index=True)  # occupancy, traffic, energy_consumption, etc.
    field_key = Column(String(100), nullable=True)  # Telemetry field being analyzed
    
    # Pattern results
    pattern_type = Column(String(50), nullable=True)  # daily, weekly, seasonal, etc.
    peak_times = Column(JSON, nullable=True)  # List of peak time periods
    average_values = Column(JSON, nullable=True)  # Average values by time period
    trends = Column(JSON, nullable=True)  # Trend analysis (increasing, decreasing, stable)
    
    # Time range analyzed
    analysis_start = Column(DateTime(timezone=True), nullable=False)
    analysis_end = Column(DateTime(timezone=True), nullable=False)
    
    # Results summary
    summary = Column(Text, nullable=True)
    insights = Column(JSON, nullable=True)  # Key insights from analysis
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    tenant = relationship("Tenant")
    device = relationship("Device")


class CorrelationResult(Base):
    """Results of multi-sensor correlation analysis."""
    __tablename__ = "correlation_results"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Correlation details
    device_ids = Column(JSON, nullable=False)  # List of device IDs correlated
    field_keys = Column(JSON, nullable=False)  # List of field keys from each device
    
    # Correlation metrics
    correlation_coefficient = Column(Float, nullable=False)  # -1 to 1
    p_value = Column(Float, nullable=True)  # Statistical significance
    correlation_type = Column(String(50), nullable=True)  # positive, negative, none
    
    # Analysis period
    analysis_start = Column(DateTime(timezone=True), nullable=False)
    analysis_end = Column(DateTime(timezone=True), nullable=False)
    
    # Additional insights
    insights = Column(Text, nullable=True)
    visualization_data = Column(JSON, nullable=True)  # Data for correlation plots
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    tenant = relationship("Tenant")


class DeviceHealthHistory(Base):
    """Time-series history of device health snapshots for trend analysis."""
    __tablename__ = "device_health_history"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Snapshot timestamp
    snapshot_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Status at this time
    status = Column(String(20), nullable=False)  # online, offline, degraded
    battery_level = Column(Float, nullable=True)
    message_count_1h = Column(Integer, default=0)
    avg_message_interval_seconds = Column(Float, nullable=True)
    
    # Calculated metrics
    uptime_24h_percent = Column(Float, nullable=True)
    connectivity_score = Column(Float, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    device = relationship("Device")



