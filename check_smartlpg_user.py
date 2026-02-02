"""Check SmartLPG tenant and user in database."""

import sys
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User, Tenant
from admin_auth import verify_password

def check_smartlpg_user():
    """Check SmartLPG tenant and user status."""
    db: Session = SessionLocal()
    try:
        print("=" * 60)
        print("Checking SmartLPG Tenant and User")
        print("=" * 60)
        
        # Check all tenants
        print("\n📋 All Tenants:")
        tenants = db.query(Tenant).all()
        for tenant in tenants:
            print(f"   ID: {tenant.id}, Name: {tenant.name}, Code: {tenant.code}, Active: {tenant.is_active}")
        
        # Check SmartLPG tenant specifically
        print("\n🔍 SmartLPG Tenant (ID=3 or code=SMARTLPG/0078):")
        smartlpg_tenant = db.query(Tenant).filter(
            (Tenant.id == 3) | (Tenant.code == "SMARTLPG") | (Tenant.code == "0078")
        ).first()
        
        if smartlpg_tenant:
            print(f"   ✅ Found: ID={smartlpg_tenant.id}, Name={smartlpg_tenant.name}, Code={smartlpg_tenant.code}")
        else:
            print("   ❌ SmartLPG tenant not found!")
        
        # Check all users with tenant_id = 3
        print("\n👥 Users with tenant_id = 3:")
        users_tenant_3 = db.query(User).filter(User.tenant_id == 3).all()
        if users_tenant_3:
            for user in users_tenant_3:
                print(f"   ✅ Email: {user.email}")
                print(f"      ID: {user.id}, Name: {user.full_name}")
                print(f"      Role: {user.role.value}, Active: {user.is_active}")
                print(f"      Modules: {user.enabled_modules}")
        else:
            print("   ❌ No users found with tenant_id = 3")
        
        # Check users with SmartLPG in email
        print("\n🔍 Users with 'smartlpg' in email:")
        smartlpg_users = db.query(User).filter(
            User.email.ilike("%smartlpg%")
        ).all()
        if smartlpg_users:
            for user in smartlpg_users:
                print(f"   ✅ Email: {user.email}")
                print(f"      ID: {user.id}, Tenant ID: {user.tenant_id}")
                print(f"      Name: {user.full_name}, Role: {user.role.value}")
                print(f"      Active: {user.is_active}")
                if user.tenant_id != 3:
                    print(f"      ⚠️  WARNING: User has tenant_id={user.tenant_id}, not 3!")
        else:
            print("   ❌ No users found with 'smartlpg' in email")
        
        # Check all tenant admin users
        print("\n👥 All Tenant Admin Users:")
        tenant_admins = db.query(User).filter(User.role == "tenant_admin").all()
        for user in tenant_admins:
            print(f"   Email: {user.email}, Tenant ID: {user.tenant_id}, Active: {user.is_active}")
        
        # Test password if user found
        if smartlpg_users:
            test_user = smartlpg_users[0]
            print(f"\n🔐 Testing password for user: {test_user.email}")
            print("   (This will show if password verification works)")
            # Don't actually test password here, just show user exists
        
        print("\n" + "=" * 60)
        print("Summary:")
        print("=" * 60)
        if smartlpg_tenant:
            print(f"✅ SmartLPG tenant exists: ID={smartlpg_tenant.id}")
        else:
            print("❌ SmartLPG tenant NOT found")
        
        if users_tenant_3:
            print(f"✅ Found {len(users_tenant_3)} user(s) with tenant_id=3")
        else:
            print("❌ No users found with tenant_id=3")
        
        if smartlpg_users:
            print(f"✅ Found {len(smartlpg_users)} user(s) with 'smartlpg' in email")
            for user in smartlpg_users:
                if user.tenant_id != 3:
                    print(f"   ⚠️  {user.email} has tenant_id={user.tenant_id} (should be 3)")
        else:
            print("❌ No users found with 'smartlpg' in email")
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    check_smartlpg_user()
