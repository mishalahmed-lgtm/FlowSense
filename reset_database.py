"""Reset database - drop all tables and recreate them.

This script will:
1. Drop all existing tables
2. Recreate tables from models.py
3. Create initial admin user and tenant
4. Verify all dashboard requirements are met

DANGER: This will DELETE ALL DATA in the database!
"""

import sys
import logging
from sqlalchemy import text, inspect
from database import engine, SessionLocal, Base
from models import (
    User, Tenant, Device, DeviceSnapshot,
    Alert, AlertRule, Notification, AlertAuditLog,
    DeviceRule,
    ExternalIntegration,
    UtilityTariff, UtilityRecord,
    FirmwareVersion, FOTAJob, FOTAJobDevice,
    UserRole, DeviceData, DeviceHealth,
    Team, TeamMember, Installation, Location
)
from admin_auth import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def confirm_reset():
    """Ask user to confirm database reset."""
    print("\n" + "="*80)
    print("⚠️  WARNING: DATABASE RESET")
    print("="*80)
    print("\nThis will:")
    print("  1. DROP ALL TABLES in the database")
    print("  2. DELETE ALL DATA (devices, users, telemetry, alerts, etc.)")
    print("  3. RECREATE tables from models.py")
    print("  4. Create initial admin user and tenant")
    print("\n" + "="*80)
    
    response = input("\nType 'YES' to confirm database reset: ")
    return response.strip() == "YES"


def drop_all_tables():
    """Drop all tables in the database."""
    logger.info("Dropping all tables...")
    
    with engine.connect() as conn:
        # Get all table names
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if not tables:
            logger.info("No tables found in database")
            return
        
        logger.info(f"Found {len(tables)} tables to drop: {tables}")
        
        # Drop all tables (CASCADE to handle foreign keys)
        for table in tables:
            try:
                conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                conn.commit()
                logger.info(f"  ✓ Dropped table: {table}")
            except Exception as e:
                logger.error(f"  ✗ Failed to drop table {table}: {e}")
                raise
    
    logger.info("✓ All tables dropped successfully")


def create_all_tables():
    """Create all tables from models.py."""
    logger.info("Creating all tables from models.py...")
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✓ All tables created successfully")
        
        # Verify tables were created
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"✓ Created {len(tables)} tables: {tables}")
        
    except Exception as e:
        logger.error(f"✗ Failed to create tables: {e}")
        raise


def create_initial_data():
    """Create initial admin user and tenant."""
    logger.info("Creating initial data...")
    
    db = SessionLocal()
    try:
        # Create default tenant
        tenant = Tenant(
            name="Default Tenant",
            code="DEFAULT",
            country="SA",  # Saudi Arabia
            is_active=True
        )
        db.add(tenant)
        db.flush()  # Get tenant.id
        logger.info(f"✓ Created tenant: {tenant.name} (ID: {tenant.id})")
        
        # Create admin user
        admin_user = User(
            email="admin@iot.local",
            hashed_password=hash_password("admin123"),
            full_name="System Administrator",
            role=UserRole.ADMIN,
            tenant_id=None,  # Global admin has no tenant
            enabled_modules=["devices", "dashboards", "utility", "rules", "alerts", "analytics", "fota"],
            is_active=True
        )
        db.add(admin_user)
        logger.info(f"✓ Created admin user: {admin_user.email} (password: admin123)")
        
        # Create tenant admin user
        tenant_admin = User(
            email="tenant@iot.local",
            hashed_password=hash_password("tenant123"),
            full_name="Tenant Administrator",
            role=UserRole.TENANT_ADMIN,
            tenant_id=tenant.id,
            enabled_modules=["devices", "dashboards", "utility", "rules", "alerts"],
            is_active=True
        )
        db.add(tenant_admin)
        logger.info(f"✓ Created tenant admin: {tenant_admin.email} (password: tenant123)")
        
        # Create device types
        device_types = [
            DeviceType(name="LPG Meter", protocol="HTTP", description="LPG level monitoring device"),
            DeviceType(name="Valve Controller", protocol="MQTT", description="Smart valve control device"),
            DeviceType(name="GPS Tracker", protocol="TCP_HEX", description="Vehicle GPS tracking device"),
            DeviceType(name="Smart Bench", protocol="HTTP", description="Smart city bench with sensors"),
            DeviceType(name="Comcore AMI", protocol="HTTP", description="Comcore AMI electricity meter"),
            DeviceType(name="Comcore DLMS", protocol="HTTP", description="Comcore DLMS electricity meter"),
            DeviceType(name="Water Meter", protocol="HTTP", description="Water consumption meter"),
        ]
        
        for dt in device_types:
            db.add(dt)
        
        db.commit()
        logger.info(f"✓ Created {len(device_types)} device types")
        
        logger.info("\n" + "="*80)
        logger.info("✓ Initial data created successfully")
        logger.info("="*80)
        logger.info("\nLogin credentials:")
        logger.info("  Admin:        admin@iot.local / admin123")
        logger.info("  Tenant Admin: tenant@iot.local / tenant123")
        logger.info("="*80)
        
    except Exception as e:
        db.rollback()
        logger.error(f"✗ Failed to create initial data: {e}")
        raise
    finally:
        db.close()


def verify_dashboard_requirements():
    """Verify all tables required by the dashboard exist."""
    logger.info("\nVerifying dashboard requirements...")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    # Required tables for dashboard
    required_tables = {
        "users": "User authentication",
        "tenants": "Tenant management",
        "devices": "Device registry",
        "devices_snapshot": "Device snapshot data (for external imports)",
        "device_types": "Device type definitions",
        "telemetry_latest": "Latest telemetry data",
        "telemetry_timeseries": "Historical telemetry data",
        "device_health_metrics": "Device health and uptime",
        "alerts": "Alert instances",
        "alert_rules": "Alert rule definitions",
        "device_dashboards": "Device dashboard configurations",
    }
    
    missing_tables = []
    for table, description in required_tables.items():
        if table in tables:
            logger.info(f"  ✓ {table:30s} - {description}")
        else:
            logger.error(f"  ✗ {table:30s} - MISSING!")
            missing_tables.append(table)
    
    if missing_tables:
        logger.error(f"\n✗ Missing {len(missing_tables)} required tables!")
        return False
    
    logger.info("\n✓ All dashboard requirements verified")
    return True


def main():
    """Main reset function."""
    print("\n" + "="*80)
    print("DATABASE RESET SCRIPT")
    print("="*80)
    
    # Confirm reset
    if not confirm_reset():
        print("\n✗ Database reset cancelled")
        sys.exit(0)
    
    try:
        # Step 1: Drop all tables
        print("\nStep 1: Dropping all tables...")
        drop_all_tables()
        
        # Step 2: Create all tables
        print("\nStep 2: Creating all tables...")
        create_all_tables()
        
        # Step 3: Create initial data
        print("\nStep 3: Creating initial data...")
        create_initial_data()
        
        # Step 4: Verify dashboard requirements
        print("\nStep 4: Verifying dashboard requirements...")
        if not verify_dashboard_requirements():
            print("\n✗ Dashboard requirements not met!")
            sys.exit(1)
        
        print("\n" + "="*80)
        print("✓ DATABASE RESET COMPLETE")
        print("="*80)
        print("\nYou can now:")
        print("  1. Start the backend: uvicorn main:app --reload")
        print("  2. Login to the dashboard with admin@iot.local / admin123")
        print("  3. Add devices and start receiving telemetry")
        print("="*80 + "\n")
        
    except Exception as e:
        logger.error(f"\n✗ Database reset failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

