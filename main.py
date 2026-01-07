"""Main FastAPI application for IoT Platform Ingestion Gateway."""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

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
from routers import debug as debug_router
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
# External API sync service removed - frontend now only reads from database
# from external_api_sync_service import external_api_sync_service
from admin_auth import get_current_user
from database import get_db
from sqlalchemy.orm import Session
from models import Device, User, UserRole, Tenant
from admin_auth import hash_password
from database import SessionLocal

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
        
        # Add missing columns if needed (for schema updates)
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                # Check if source_urls column exists, if not add it
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='external_integrations' AND column_name='source_urls'
                """))
                if not result.fetchone():
                    logger.info("Adding source_urls column to external_integrations table...")
                    conn.execute(text("ALTER TABLE external_integrations ADD COLUMN source_urls JSON DEFAULT '{}'::json"))
                    conn.commit()
                    logger.info("✓ source_urls column added successfully")
        except Exception as e:
            logger.warning(f"Could not add missing columns (may already exist): {e}")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
    
    # Auto-initialize admin user and default tenant if they don't exist
    try:
        db = SessionLocal()
        try:
            # Check if admin user exists
            admin_email = "admin@flowsense.com".lower()  # Ensure lowercase
            existing_admin = db.query(User).filter(User.email == admin_email).first()
            
            if not existing_admin:
                admin_password = "AdminFlow"
                admin_user = User(
                    email=admin_email,  # Store in lowercase
                    hashed_password=hash_password(admin_password),
                    full_name="System Administrator",
                    role=UserRole.ADMIN,
                    tenant_id=None,
                    enabled_modules=[],
                    is_active=True,
                )
                db.add(admin_user)
                db.commit()
                db.refresh(admin_user)
                logger.info(f"✅ Admin user created: {admin_email} / {admin_password}")
                logger.info(f"   User ID: {admin_user.id}, Active: {admin_user.is_active}")
            else:
                logger.info(f"✓ Admin user already exists: {admin_email} (ID: {existing_admin.id})")
            
            # Check if default tenant exists
            tenant_code = "DEFAULT"
            existing_tenant = db.query(Tenant).filter(Tenant.code == tenant_code).first()
            
            if not existing_tenant:
                default_tenant = Tenant(
                    name="Default Tenant",
                    code=tenant_code,
                    is_active=True,
                )
                db.add(default_tenant)
                db.commit()
                db.refresh(default_tenant)
                logger.info(f"✅ Default tenant created: {default_tenant.name}")
            else:
                logger.info(f"✓ Default tenant already exists: {existing_tenant.name}")
            
            # Auto-create HTTP and MQTT device types if they don't exist
            from models import DeviceType
            device_types_to_create = [
                {"name": "HTTP", "protocol": "HTTP", "description": "Generic HTTP device"},
                {"name": "MQTT", "protocol": "MQTT", "description": "Generic MQTT device"},
            ]
            
            for dt_data in device_types_to_create:
                existing_dt = db.query(DeviceType).filter(
                    DeviceType.name == dt_data["name"],
                    DeviceType.protocol == dt_data["protocol"]
                ).first()
                
                if not existing_dt:
                    device_type = DeviceType(
                        name=dt_data["name"],
                        protocol=dt_data["protocol"],
                        description=dt_data["description"],
                        schema_definition='{"type": "object", "additionalProperties": true}'
                    )
                    db.add(device_type)
                    db.commit()
                    logger.info(f"✅ Device type created: {dt_data['name']} ({dt_data['protocol']})")
                else:
                    logger.debug(f"✓ Device type already exists: {dt_data['name']} ({dt_data['protocol']})")
            
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to auto-initialize admin user/device types: {e}. You may need to run init_admin.py manually.")
    
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
    
    # Start external API sync service (fetches data from external APIs automatically)
    # DISABLED: Auto-sync disabled - frontend now only reads from database
    # try:
    #     external_api_sync_service.start()
    #     logger.info("External API sync service started")
    # except Exception as e:
    #     logger.warning(f"Failed to start external API sync service: {e}. Continuing without auto-sync...")
    logger.info("External API sync service DISABLED - using database-only mode")
    
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
    # external_api_sync_service.stop()  # Disabled - service not running
    # logger.info("External API sync service stopped")
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
    admin_router.metrics_router,
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
app.include_router(
    debug_router.router,
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
async def health_check():
    """
    Public health check endpoint (no authentication required).
    
    Checks:
    - API is running
    - PostgreSQL database connection is working
    - Connection pool status
    
    Returns:
    - 200 OK if all checks pass
    - 503 Service Unavailable if database is unreachable
    """
    from sqlalchemy import text
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "api": "ok",
            "database": "unknown",
        }
    }
    
    # Check database connection
    db = SessionLocal()
    try:
        # Simple query to test connection
        result = db.execute(text("SELECT 1")).scalar()
        
        if result == 1:
            health_status["checks"]["database"] = "ok"
            
            # Add connection pool info (optional, useful for debugging)
            try:
                health_status["pool"] = {
                    "size": engine.pool.size(),
                    "checked_out": engine.pool.checkedout(),
                    "overflow": engine.pool.overflow(),
                }
            except Exception:
                pass  # Pool info is optional
        else:
            health_status["status"] = "degraded"
            health_status["checks"]["database"] = "unexpected_response"
            
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = "error"
        health_status["error"] = str(e)
        logger.error(f"Health check database error: {e}")
        
        # Return 503 Service Unavailable if database is down
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_status
        )
    finally:
        db.close()
    
    return health_status


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPExceptions with CORS headers."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to ensure CORS headers are always included."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": f"Internal server error: {str(exc)}",
            "type": type(exc).__name__
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with CORS headers."""
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_handler.is_connected
    }


    raise HTTPException(status_code=status.HTTP_410_GONE, detail="External API sync service has been removed. Frontend now only reads from database.")
    # DISABLED CODE BELOW
    # """Manually trigger external API sync (for testing/debugging)."""
    # try:
    #     from external_api_sync_service import external_api_sync_service
    #     from models import ExternalIntegration, Device
    #     
    #     # Get integration details before sync
    #     integration = db.query(ExternalIntegration).filter(
    #         ExternalIntegration.is_active == True
    #     ).first()
    #     
    #     device_count_before = db.query(Device).count()
    #     
    #     # Trigger sync
    #     external_api_sync_service._sync_all_integrations()
    #     
    #     # Check device count after sync
    #     device_count_after = db.query(Device).count()
    #     devices_created = device_count_after - device_count_before
    #     
    #     return {
    #         "status": "success",
    #         "message": "Sync triggered manually. Check logs for details.",
    #         "timestamp": datetime.now(timezone.utc).isoformat(),
    #         "devices_before": device_count_before,
    #         "devices_after": device_count_after,
    #         "devices_created": devices_created,
    #         "integration_id": integration.id if integration else None
    #     }
    # except Exception as e:
    #     logger.error(f"Error triggering manual sync: {e}", exc_info=True)
    #     return {
    #         "status": "error",
    #         "message": str(e),
    #         "timestamp": datetime.now(timezone.utc).isoformat()
    #     }


    # DISABLED CODE BELOW
    # """Manually trigger external API sync (for testing/debugging)."""
    # try:
    #     from external_api_sync_service import external_api_sync_service
    #     from models import ExternalIntegration, Device
    #     
    #     # Get integration details before sync
    #     integration = db.query(ExternalIntegration).filter(
    #         ExternalIntegration.is_active == True
    #     ).first()
    #     
    #     device_count_before = db.query(Device).count()
    #     
    #     # Trigger sync
    #     external_api_sync_service._sync_all_integrations()
    #     
    #     # Check device count after sync
    #     device_count_after = db.query(Device).count()
    #     devices_created = device_count_after - device_count_before
    #     
    #     return {
    #         "status": "success",
    #         "message": "Sync triggered manually. Check logs for details.",
    #         "timestamp": datetime.now(timezone.utc).isoformat(),
    #         "devices_before": device_count_before,
    #         "devices_after": device_count_after,
    #         "devices_created": devices_created,
    #         "integration_id": integration.id if integration else None
    #     }
    # except Exception as e:
    #     logger.error(f"Error triggering manual sync: {e}", exc_info=True)
    #     return {
    #         "status": "error",
    #         "message": str(e),
    #         "timestamp": datetime.now(timezone.utc).isoformat()
    #     }
    # 
    # 
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail=f"No metrics found for device {device_id}"
    #     )
    #     return device_stats


    # if __name__ == "__main__":
    # import uvicorn
    # uvicorn.run(
    # "main:app",
    # host="0.0.0.0",
    # port=5000,
    # reload=True,
    # log_level=settings.log_level.lower()
    # )

