"""Initialize the database with admin user, default tenant, and tenant user."""

import sys
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from models import User, UserRole, Tenant
from admin_auth import hash_password

def init_database():
    """Initialize database with admin user, default tenant, and tenant user."""
    # Create all tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created")
    
    db: Session = SessionLocal()
    try:
        # Check if admin user already exists
        admin_email = "admin@flowsense.com"
        existing_admin = db.query(User).filter(User.email == admin_email).first()
        
        if existing_admin:
            print(f"✓ Admin user already exists: {admin_email}")
        else:
            # Create admin user
            admin_password = "AdminFlow"
            admin_user = User(
                email=admin_email,
                hashed_password=hash_password(admin_password),
                full_name="System Administrator",
                role=UserRole.ADMIN,
                tenant_id=None,  # Admin not tied to any tenant
                enabled_modules=[],  # Admins don't need tenant modules
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            print(f"\n✅ Admin user created successfully!")
            print(f"   Email: {admin_email}")
            print(f"   Password: {admin_password}")
        
        # Check if default tenant exists
        tenant_code = "DEFAULT"
        existing_tenant = db.query(Tenant).filter(Tenant.code == tenant_code).first()
        
        if existing_tenant:
            print(f"✓ Default tenant already exists: {existing_tenant.name}")
            default_tenant = existing_tenant
        else:
            # Create default tenant
            default_tenant = Tenant(
                name="Default Tenant",
                code=tenant_code,
                is_active=True,
            )
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)
            print(f"\n✅ Default tenant created successfully!")
            print(f"   Name: {default_tenant.name}")
            print(f"   Code: {default_tenant.code}")
        
        # Check if tenant user already exists
        tenant_email = "tenant@flowsense.com"
        existing_tenant_user = db.query(User).filter(User.email == tenant_email).first()
        
        if existing_tenant_user:
            print(f"✓ Tenant user already exists: {tenant_email}")
        else:
            # Create tenant user
            tenant_password = "tenantFlow"
            tenant_user = User(
                email=tenant_email,
                hashed_password=hash_password(tenant_password),
                full_name="Default Tenant User",
                role=UserRole.TENANT_ADMIN,
                tenant_id=default_tenant.id,
                enabled_modules=["devices", "dashboards", "utility"],  # Tenant modules
                is_active=True,
            )
            db.add(tenant_user)
            db.commit()
            print(f"\n✅ Tenant user created successfully!")
            print(f"   Email: {tenant_email}")
            print(f"   Password: {tenant_password}")
            print(f"   Tenant: {default_tenant.name}")
            print(f"   Modules: {', '.join(tenant_user.enabled_modules)}")
        
        print(f"\n⚠️  IMPORTANT: Please change passwords after first login!")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    init_database()

