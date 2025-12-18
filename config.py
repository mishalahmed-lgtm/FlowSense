"""Configuration settings for the IoT Platform."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql://iot_user:iot_password@postgres:5432/iot_platform"

    # InfluxDB - time-series database (optional but recommended)
    # When influx_token is not set, InfluxDB integration is disabled gracefully.
    influx_url: str = "http://influxdb:8086"
    influx_org: str = "iot_org"
    influx_token: Optional[str] = None
    influx_bucket_hot: str = "iot_hot"
    influx_bucket_warm: str = "iot_warm"
    influx_bucket_cold: str = "iot_cold"
    # Retention policies (in days) for each tier
    influx_hot_retention_days: int = 30          # Hot storage (~30 days)
    influx_warm_retention_days: int = 365        # Warm storage (~1 year)
    influx_cold_retention_days: int = 0          # 0 = infinite (5+ years cold storage)
    influx_measurement_name: str = "telemetry"   # Measurement name used for all points
    
    # Kafka
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_raw_telemetry_topic: str = "raw_telemetry"
    
    # MQTT
    mqtt_broker_host: str = "mqtt-broker"
    mqtt_broker_port: int = 1883
    mqtt_broker_username: Optional[str] = None
    mqtt_broker_password: Optional[str] = None

    # TCP ingestion
    tcp_ingest_host: str = "0.0.0.0"
    tcp_ingest_port: int = 6000
    tcp_connection_limit: int = 100
    tcp_read_timeout_seconds: int = 30

    # Admin portal
    admin_email: str = "admin@example.com"
    admin_password: str = "admin123"  # Override in .env
    admin_jwt_secret: str = "supersecretjwtkey"
    admin_jwt_algorithm: str = "HS256"
    admin_jwt_exp_minutes: int = 60
    
    # Application
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # JasperReports Server integration (optional)
    jasper_base_url: Optional[str] = None  # e.g. "http://jasper:8080/jasperserver"
    jasper_username: Optional[str] = None
    jasper_password: Optional[str] = None
    # Path to the tenant billing report inside Jasper, e.g. "/reports/iot/tenant_utility_billing"
    jasper_tenant_billing_path: Optional[str] = None
    
    # Email notifications (SMTP)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: str = "alerts@flowsense.com"
    
    # SMS notifications (optional - integrate with Twilio, AWS SNS, etc.)
    sms_provider: Optional[str] = None
    sms_api_key: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

