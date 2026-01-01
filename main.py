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
from external_api_sync_service import external_api_sync_service
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
            
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to auto-initialize admin user: {e}. You may need to run init_admin.py manually.")
    
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
    try:
        external_api_sync_service.start()
        logger.info("External API sync service started")
    except Exception as e:
        logger.warning(f"Failed to start external API sync service: {e}. Continuing without auto-sync...")
    
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
    external_api_sync_service.stop()
    logger.info("External API sync service stopped")
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


@app.get("/debug/health")
async def debug_health():
    """Simple health check for debug endpoints."""
    return {
        "status": "ok",
        "message": "Debug endpoints are working",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/debug/test-external-api")
async def test_external_api(db: Session = Depends(get_db)):
    """Test fetching data from external API to see what it returns."""
    try:
        import requests
        from models import ExternalIntegration, Device
        
        integration = db.query(ExternalIntegration).filter(
            ExternalIntegration.is_active == True
        ).first()
        
        if not integration:
            return {
                "status": "error",
                "message": "No active integration found"
            }
        
        # Get source URL
        try:
            source_urls = integration.source_urls or integration.endpoint_urls or {}
        except AttributeError:
            source_urls = integration.endpoint_urls or {}
        
        if not source_urls:
            return {
                "status": "error",
                "message": "No source URLs configured",
                "integration_id": integration.id
            }
        
        # Get first URL
        external_url = list(source_urls.values())[0] if source_urls else None
        if not external_url:
            return {
                "status": "error",
                "message": "No external URL found",
                "source_urls": source_urls
            }
        
        # Get user to access tenant_id
        user = db.query(User).filter(User.id == integration.user_id).first()
        if not user:
            return {
                "status": "error",
                "message": f"User not found for integration {integration.id}"
            }
        
        # Fetch from external API
        logger.info(f"Testing fetch from {external_url}...")
        response = requests.get(external_url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Count devices before
        device_count_before = db.query(Device).filter(
            Device.tenant_id == user.tenant_id
        ).count()
        
        return {
            "status": "success",
            "external_url": external_url,
            "response_status": response.status_code,
            "data_type": type(data).__name__,
            "data_length": len(data) if isinstance(data, (list, dict)) else None,
            "data_sample": data[:3] if isinstance(data, list) else (data if isinstance(data, dict) else str(data)[:500]),
            "integration_id": integration.id,
            "tenant_id": user.tenant_id if user else None,
            "devices_in_tenant_before": device_count_before
        }
    except Exception as e:
        logger.error(f"Error testing external API: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__
        }


@app.get("/debug/admin-check")
async def debug_admin_check(db: Session = Depends(get_db)):
    """Debug endpoint to check if admin user exists (for troubleshooting)."""
    try:
        admin_email = "admin@flowsense.com".lower()
        user = db.query(User).filter(User.email == admin_email).first()
        
        if user:
            return {
                "status": "success",
                "exists": True,
                "email": user.email,
                "id": user.id,
                "role": user.role.value,
                "is_active": user.is_active,
                "hashed_password_length": len(user.hashed_password) if user.hashed_password else 0,
            }
        else:
            # Check if any users exist
            all_users = db.query(User).all()
            return {
                "status": "success",
                "exists": False,
                "admin_email_looking_for": admin_email,
                "total_users_in_db": len(all_users),
                "all_user_emails": [u.email for u in all_users],
            }
    except Exception as e:
        logger.error(f"Error in admin-check endpoint: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__
        }


@app.get("/debug/trigger-sync")
@app.post("/debug/trigger-sync")
async def trigger_sync_manually(db: Session = Depends(get_db)):
    """Manually trigger external API sync (for testing/debugging)."""
    try:
        from external_api_sync_service import external_api_sync_service
        from models import ExternalIntegration, Device
        
        # Get integration details before sync
        integration = db.query(ExternalIntegration).filter(
            ExternalIntegration.is_active == True
        ).first()
        
        device_count_before = db.query(Device).count()
        
        # Trigger sync
        external_api_sync_service._sync_all_integrations()
        
        # Check device count after sync
        device_count_after = db.query(Device).count()
        devices_created = device_count_after - device_count_before
        
        return {
            "status": "success",
            "message": "Sync triggered manually. Check logs for details.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "devices_before": device_count_before,
            "devices_after": device_count_after,
            "devices_created": devices_created,
            "integration_id": integration.id if integration else None
        }
    except Exception as e:
        logger.error(f"Error triggering manual sync: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@app.get("/debug/sync-status")
async def get_sync_status(db: Session = Depends(get_db)):
    """Get status of external API sync service."""
    try:
        from external_api_sync_service import external_api_sync_service
        from models import ExternalIntegration, User
        
        integrations = db.query(ExternalIntegration).filter(
            ExternalIntegration.is_active == True
        ).all()
        
        integration_details = []
        for integration in integrations:
            try:
                user = db.query(User).filter(User.id == integration.user_id).first()
                # Handle source_urls gracefully - might not exist in older DBs
                try:
                    source_urls = integration.source_urls or integration.endpoint_urls or {}
                except AttributeError:
                    source_urls = integration.endpoint_urls or {}
                
                integration_details.append({
                    "id": integration.id,
                    "name": integration.name,
                    "user_email": user.email if user else None,
                    "tenant_id": user.tenant_id if user else None,
                    "source_urls": source_urls,
                    "endpoint_urls": integration.endpoint_urls,
                    "last_used_at": integration.last_used_at.isoformat() if integration.last_used_at else None,
                    "is_active": integration.is_active
                })
            except Exception as e:
                logger.error(f"Error processing integration {integration.id}: {e}", exc_info=True)
                integration_details.append({
                    "id": integration.id,
                    "error": str(e)
                })
        
        return {
            "status": "success",
            "service_running": external_api_sync_service._running,
            "sync_interval_seconds": external_api_sync_service._sync_interval,
            "active_integrations": len(integrations),
            "integrations": integration_details
        }
    except Exception as e:
        logger.error(f"Error in sync-status endpoint: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__
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

