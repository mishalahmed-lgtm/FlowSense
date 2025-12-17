"""Main FastAPI application for IoT Platform Ingestion Gateway."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
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
from routers.graphql import create_graphql_router
from routers import oauth as oauth_router
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

# Include GraphQL router
try:
    graphql_router = create_graphql_router()
    # GraphQLRouter is a FastAPI router, include it with prefix
    # The path "/" in GraphQLRouter + prefix "/api/v1" + internal "/graphql" = "/api/v1/graphql"
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

