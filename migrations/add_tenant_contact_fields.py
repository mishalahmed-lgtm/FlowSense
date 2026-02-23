"""
Migration script to add contact and business information fields to tenants table.
Run this script to update your database schema.

Usage:
    python migrations/add_tenant_contact_fields.py
"""

import sys
import os

# Add parent directory to path to import database modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine
from sqlalchemy import text

def run_migration():
    """Add new contact and business information fields to tenants table."""
    print("🔄 Running migration: Add tenant contact fields...")
    
    try:
        with engine.connect() as conn:
            # Check if columns exist and add them if they don't
            from sqlalchemy import inspect
            inspector = inspect(engine)
            existing_columns = [col['name'] for col in inspector.get_columns('tenants')]
            
            columns_to_add = [
                ('contact_email', 'VARCHAR(255)'),
                ('contact_phone', 'VARCHAR(50)'),
                ('business_address', 'TEXT'),
                ('timezone', "VARCHAR(100) DEFAULT 'UTC'"),
            ]
            
            for col_name, col_def in columns_to_add:
                if col_name not in existing_columns:
                    print(f"   Adding column: {col_name}")
                    try:
                        conn.execute(text(f"ALTER TABLE tenants ADD COLUMN {col_name} {col_def}"))
                    except Exception as e:
                        if 'already exists' not in str(e).lower() and 'duplicate' not in str(e).lower():
                            raise
                        print(f"   Column {col_name} already exists, skipping")
                else:
                    print(f"   Column {col_name} already exists, skipping")
            
            # Create index on contact_email if it doesn't exist
            try:
                existing_indexes = [idx['name'] for idx in inspector.get_indexes('tenants')]
                if 'idx_tenants_contact_email' not in existing_indexes:
                    print("   Creating index on contact_email")
                    conn.execute(text("CREATE INDEX idx_tenants_contact_email ON tenants(contact_email)"))
                else:
                    print("   Index idx_tenants_contact_email already exists, skipping")
            except Exception as e:
                if 'already exists' not in str(e).lower() and 'duplicate' not in str(e).lower():
                    print(f"   Warning: Could not check/create index: {e}")
            
            # Update existing tenants to have UTC timezone if NULL
            conn.execute(text("UPDATE tenants SET timezone = 'UTC' WHERE timezone IS NULL"))
            
            conn.commit()
        
        print("✅ Migration completed successfully!")
        print("   Added fields: contact_email, contact_phone, business_address, timezone")
        return True
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
