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
from mqtt_client import mqtt_handler
from tcp_server import tcp_ingestion_server
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
    
    yield
    
    # Shutdown
    logger.info("Shutting down IoT Platform Ingestion Gateway...")
    mqtt_handler.disconnect()
    logger.info("MQTT handler stopped")
    await tcp_ingestion_server.stop()


# Create FastAPI application
app = FastAPI(
    title="IoT Platform - Ingestion Gateway",
    description="Data ingestion pipeline for IoT devices (LPG Meter, Valve Controller, GPS)",
    version="1.0.0",
    lifespan=lifespan
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

