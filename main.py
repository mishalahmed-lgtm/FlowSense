"""Main FastAPI application for IoT Platform Ingestion Gateway."""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import engine, Base
from routers import telemetry
from routers import admin as admin_router
from routers import dashboard as dashboard_router
from routers import utility as utility_router
from routers import user_management as user_management_router
from routers import alerts as alerts_router
from routers import fota as fota_router
from routers import health as health_router
from routers import analytics as analytics_router
from routers import websocket as websocket_router
from routers import export as export_router
from routers import maps as maps_router
from routers import oauth as oauth_router
from routers import external_api as external_api_router
from mqtt_client import mqtt_handler
from tcp_server import tcp_ingestion_server
from fota_service import fota_service
from health_monitoring_service import health_monitoring_service
from analytics_engine import analytics_engine
from rule_scheduler import rule_scheduler
from cep_engine import cep_engine
from mqtt_command_service import mqtt_command_service
from modbus_handler import modbus_handler
from dali_handler import dali_handler
from metrics import metrics
from admin_auth import get_current_user
from database import get_db
from sqlalchemy.orm import Session
from models import Device, User, UserRole

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting IoT Platform Ingestion Gateway...")
    
    # Create database tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
    
    # Connect to MQTT broker
    try:
        mqtt_handler.connect()
        logger.info("MQTT handler started")
    except Exception as e:
        logger.warning(f"Failed to connect to MQTT broker: {e}. Continuing without MQTT...")

    # Start TCP ingestion server
    try:
        await tcp_ingestion_server.start()
        logger.info("TCP ingestion server started")
    except Exception as e:
        logger.warning(f"Failed to start TCP ingestion server: {e}. Continuing without TCP...")
    
    # Start FOTA service
    try:
        fota_service.start()
        logger.info("FOTA service started")
    except Exception as e:
        logger.warning(f"Failed to start FOTA service: {e}. Continuing without FOTA...")
    
    # Start health monitoring service
    try:
        health_monitoring_service.start()
        logger.info("Health monitoring service started")
    except Exception as e:
        logger.warning(f"Failed to start health monitoring service: {e}. Continuing without health monitoring...")
    
    # Start analytics engine
    try:
        analytics_engine.start()
        logger.info("Analytics engine started")
    except Exception as e:
        logger.warning(f"Failed to start analytics engine: {e}. Continuing without analytics...")
    
    # Start rule scheduler (for cron-based rules)
    try:
        rule_scheduler.start()
        logger.info("Rule scheduler started")
    except Exception as e:
        logger.warning(f"Failed to start rule scheduler: {e}. Continuing without scheduled rules...")
    
    # Start CEP engine (for complex event processing)
    try:
        cep_engine.start()
        logger.info("CEP engine started")
    except Exception as e:
        logger.warning(f"Failed to start CEP engine: {e}. Continuing without CEP...")
    
    # Start Modbus TCP server
    try:
        await modbus_handler.start(host="0.0.0.0", port=5020)
        logger.info("Modbus TCP server started on port 5020")
    except Exception as e:
        logger.warning(f"Failed to start Modbus TCP server: {e}. Continuing without Modbus...")
    
    # Start DALI server
    try:
        await dali_handler.start(host="0.0.0.0", port=6001)
        logger.info("DALI server started on port 6001")
    except Exception as e:
        logger.warning(f"Failed to start DALI server: {e}. Continuing without DALI...")
    
    yield
    
    # Shutdown
    logger.info("Shutting down IoT Platform Ingestion Gateway...")
    cep_engine.stop()
    logger.info("CEP engine stopped")
    rule_scheduler.stop()
    logger.info("Rule scheduler stopped")
    analytics_engine.stop()
    logger.info("Analytics engine stopped")
    health_monitoring_service.stop()
    logger.info("Health monitoring service stopped")
    fota_service.stop()
    logger.info("FOTA service stopped")
    mqtt_command_service.disconnect()
    logger.info("MQTT command service stopped")
    await modbus_handler.stop()
    logger.info("Modbus TCP server stopped")
    await dali_handler.stop()
    logger.info("DALI server stopped")
    mqtt_handler.disconnect()
    logger.info("MQTT handler stopped")
    await tcp_ingestion_server.stop()


# Create FastAPI application
app = FastAPI(
    title="FlowSense IoT Platform API",
    description="""
    Comprehensive IoT Platform API with:
    - Device Management & Telemetry Ingestion
    - Real-time Data Streaming (WebSocket)
    - Analytics & Machine Learning
    - Alert & Notification Management
    - FOTA (Firmware Over-The-Air) Updates
    - Device Health Monitoring
    - Rule Engine with CEP
    - Multi-protocol Support (MQTT, HTTP, TCP, LoRaWAN, Modbus, DALI)
    - Export Capabilities (CSV, Excel, PDF)
    - Maps & Geographic Visualization
    
    ## Authentication
    - JWT tokens for API access
    - OAuth 2.0 support (coming soon)
    
    ## Rate Limiting
    - Per-device rate limits for telemetry ingestion
    - API rate limiting for REST endpoints
    
    ## Documentation
    - OpenAPI/Swagger: `/docs`
    - ReDoc: `/redoc`
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    telemetry.router,
    prefix=f"{settings.api_v1_prefix}/telemetry",
    tags=["telemetry"]
)
app.include_router(
    admin_router.router,
    prefix=f"{settings.api_v1_prefix}",
)
app.include_router(
    dashboard_router.router,
    prefix=f"{settings.api_v1_prefix}",
)
app.include_router(
    utility_router.router,
    prefix=f"{settings.api_v1_prefix}",
)
app.include_router(
    user_management_router.router,
    prefix=f"{settings.api_v1_prefix}",
)
app.include_router(
    alerts_router.router,
    prefix=f"{settings.api_v1_prefix}",
)
app.include_router(
    fota_router.router,
    prefix=f"{settings.api_v1_prefix}",
)
app.include_router(
    health_router.router,
    prefix=f"{settings.api_v1_prefix}",
)
app.include_router(
    analytics_router.router,
    prefix=f"{settings.api_v1_prefix}",
)
app.include_router(
    websocket_router.router,
    prefix=f"{settings.api_v1_prefix}",
)
app.include_router(
    export_router.router,
    prefix=f"{settings.api_v1_prefix}",
)
app.include_router(
    maps_router.router,
    prefix=f"{settings.api_v1_prefix}",
)
app.include_router(
    external_api_router.router,
    prefix=f"{settings.api_v1_prefix}",
)

# Include GraphQL router (best-effort, do not crash if unavailable)
try:
    from routers.graphql import create_graphql_router  # type: ignore

    graphql_router = create_graphql_router()
    app.include_router(graphql_router, prefix=f"{settings.api_v1_prefix}/graphql")
    logger.info(f"GraphQL router registered at {settings.api_v1_prefix}/graphql")
except Exception as e:
    logger.error(f"Failed to register GraphQL router: {e}", exc_info=True)

# Include OAuth 2.0 router
app.include_router(
    oauth_router.router,
    prefix=f"{settings.api_v1_prefix}",
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "IoT Platform - Ingestion Gateway",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_handler.is_connected
    }


@app.get("/metrics")
async def get_metrics():
    """Get ingestion pipeline metrics."""
    return metrics.get_stats()


@app.get("/metrics/tenant")
async def get_tenant_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get tenant-scoped ingestion metrics.
    
    - Tenant admins: metrics for their own tenant's devices only.
    - Admins / other roles: fall back to global metrics.
    """
    # Platform admins get global view
    if current_user.role != UserRole.TENANT_ADMIN or not current_user.tenant_id:
        base_stats = metrics.get_stats()
        # Add database-sourced protocol counts for admins too
        from models import DeviceType
        protocol_counts = {}
        devices_all = db.query(Device).all()
        for device in devices_all:
            if device.device_type:
                protocol = device.device_type.protocol or "unknown"
                protocol_counts[protocol] = protocol_counts.get(protocol, 0) + 1
        
        # Override sources with database counts
        base_stats["sources"] = protocol_counts
        return base_stats

    # Fetch devices for this tenant
    devices = (
        db.query(Device)
        .filter(Device.tenant_id == current_user.tenant_id)
        .all()
    )
    device_ids = [d.device_id for d in devices]

    # Get message counts from database (TelemetryTimeseries) instead of in-memory metrics
    from models import TelemetryTimeseries
    from sqlalchemy import func
    
    # Count distinct (device_id, timestamp) pairs to get actual message count
    # Each message creates multiple TelemetryTimeseries rows (one per field), 
    # so we count distinct timestamps per device
    message_counts = (
        db.query(
            Device.device_id,
            func.count(func.distinct(TelemetryTimeseries.ts)).label("message_count")
        )
        .join(TelemetryTimeseries, TelemetryTimeseries.device_id == Device.id)
        .filter(Device.tenant_id == current_user.tenant_id)
        .group_by(Device.device_id)
        .all()
    )
    
    # Also get total count across all tenant devices
    total_message_count = (
        db.query(func.count(func.distinct(
            func.concat(TelemetryTimeseries.device_id, '-', TelemetryTimeseries.ts)
        )))
        .join(Device, Device.id == TelemetryTimeseries.device_id)
        .filter(Device.tenant_id == current_user.tenant_id)
        .scalar() or 0
    )
    
    # Build device stats from database
    tenant_device_stats = {}
    for device_id in device_ids:
        # Find message count for this device
        msg_count = next((mc.message_count for mc in message_counts if mc.device_id == device_id), 0)
        tenant_device_stats[device_id] = {
            "received": msg_count,
            "published": msg_count,  # Assume all received messages were published
            "rejected": 0,
            "last_seen": None,
        }
    
    # Use database count for total messages
    total_received = total_message_count
    total_published = total_message_count  # Assume all received messages were published
    total_rejected = 0
    
    base_stats = metrics.get_stats()

    # Count active devices based on live telemetry (consistent with /devices endpoint)
    # A device is active if it has sent telemetry in the last 10 minutes
    from models import TelemetryLatest
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=600)  # 10 minutes
    
    active_devices = 0
    for device in devices:
        latest = (
            db.query(TelemetryLatest)
            .filter(TelemetryLatest.device_id == device.id)
            .first()
        )
        is_live = bool(latest and latest.updated_at and latest.updated_at >= cutoff)
        if is_live:
            active_devices += 1

    # Get protocol distribution from database instead of in-memory metrics
    from models import DeviceType
    protocol_counts = {}
    for device in devices:
        if device.device_type:
            protocol = device.device_type.protocol or "unknown"
            protocol_counts[protocol] = protocol_counts.get(protocol, 0) + 1

    success_rate = (
        total_published / total_received * 100
        if total_received > 0 else 0
    )

    return {
        "uptime_seconds": base_stats.get("uptime_seconds", 0),
        "messages": {
            "total_received": total_received,
            "total_published": total_published,
            "total_rejected": total_rejected,
            "success_rate": success_rate,
        },
        # Keep error/rate/rules sections simple for now – not used on tenant dashboard
        "errors": {
            "total": 0,
            "by_type": {},
            "by_device": {},
        },
        "rate_limiting": {
            "total_hits": 0,
            "by_device": {},
        },
        "authentication": {
            "total_failures": 0,
            "by_device": {},
        },
        "processing": {
            "avg_time_ms": base_stats.get("processing", {}).get("avg_time_ms", 0),
            "samples": base_stats.get("processing", {}).get("samples", 0),
        },
        "rules": base_stats.get("rules", {}),
        "sources": protocol_counts,  # Use database-sourced protocol counts
        "active_devices": active_devices,
        "devices": tenant_device_stats,
    }

@app.get("/metrics/device/{device_id}")
async def get_device_metrics(device_id: str):
    """Get metrics for a specific device."""
    device_stats = metrics.get_device_stats(device_id)
    if not device_stats:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No metrics found for device {device_id}"
        )
    return device_stats


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        log_level=settings.log_level.lower()
    )

