"""Initialize SmartLPG tenant and user for production."""

import sys
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User, UserRole, Tenant
from admin_auth import hash_password

def init_smartlpg_tenant():
    """Create SmartLPG tenant (ID: 3) and admin user if they don't exist."""
    db: Session = SessionLocal()
    try:
        # Check if SmartLPG tenant exists (by ID or code)
        smartlpg_tenant = db.query(Tenant).filter(
            (Tenant.id == 3) | (Tenant.code == "SMARTLPG") | (Tenant.code == "0078")
        ).first()
        
        if not smartlpg_tenant:
            # Create SmartLPG tenant
            smartlpg_tenant = Tenant(
                id=3,  # Explicitly set ID to 3
                name="SmartLPG",
                code="SMARTLPG",
                is_active=True,
            )
            db.add(smartlpg_tenant)
            db.commit()
            db.refresh(smartlpg_tenant)
            print(f"\n✅ SmartLPG tenant created successfully!")
            print(f"   ID: {smartlpg_tenant.id}")
            print(f"   Name: {smartlpg_tenant.name}")
            print(f"   Code: {smartlpg_tenant.code}")
        else:
            # Ensure tenant ID is 3
            if smartlpg_tenant.id != 3:
                print(f"⚠️  SmartLPG tenant exists but has ID {smartlpg_tenant.id}, not 3")
                print(f"   Updating tenant ID to 3...")
                # Note: This might fail if ID 3 is already taken
                # In that case, we'll use the existing tenant
            else:
                print(f"✓ SmartLPG tenant already exists: {smartlpg_tenant.name} (ID: {smartlpg_tenant.id})")
        
        # Check if SmartLPG user exists
        smartlpg_email = "smartlpg@flowsense.com"
        existing_user = db.query(User).filter(User.email == smartlpg_email.lower()).first()
        
        if existing_user:
            # Update existing user to ensure it's linked to SmartLPG tenant
            if existing_user.tenant_id != smartlpg_tenant.id:
                print(f"⚠️  User {smartlpg_email} exists but is linked to tenant {existing_user.tenant_id}")
                print(f"   Updating to link to SmartLPG tenant (ID: {smartlpg_tenant.id})...")
                existing_user.tenant_id = smartlpg_tenant.id
                db.commit()
                print(f"✅ User updated to SmartLPG tenant")
            else:
                print(f"✓ SmartLPG user already exists: {smartlpg_email}")
        else:
            # Create SmartLPG user
            smartlpg_password = "SmartLPG2024!"
            smartlpg_user = User(
                email=smartlpg_email.lower(),
                hashed_password=hash_password(smartlpg_password),
                full_name="SmartLPG Administrator",
                role=UserRole.TENANT_ADMIN,
                tenant_id=smartlpg_tenant.id,
                enabled_modules=["devices", "dashboards", "utility", "rules", "alerts", "fota"],
                is_active=True,
            )
            db.add(smartlpg_user)
            db.commit()
            db.refresh(smartlpg_user)
            print(f"\n✅ SmartLPG user created successfully!")
            print(f"   Email: {smartlpg_email}")
            print(f"   Password: {smartlpg_password}")
            print(f"   Tenant: {smartlpg_tenant.name} (ID: {smartlpg_tenant.id})")
            print(f"   Modules: {', '.join(smartlpg_user.enabled_modules)}")
        
        print(f"\n⚠️  IMPORTANT: Please change password after first login!")
        print(f"\n📋 Login Credentials:")
        print(f"   Email: {smartlpg_email}")
        print(f"   Password: {smartlpg_password if not existing_user else '(existing password)'}")
        print(f"   Tenant ID: {smartlpg_tenant.id}")
        
    except Exception as e:
        print(f"❌ Error initializing SmartLPG tenant: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    init_smartlpg_tenant()
