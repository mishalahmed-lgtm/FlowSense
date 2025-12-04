#!/usr/bin/env python3
"""
Database viewer script - shows what's in your IoT platform database.
Usage: docker-compose exec backend python scripts/view_db.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SessionLocal
from models import (
    Device, DeviceType, Tenant, ProvisioningKey, 
    DeviceRule, TelemetryLatest, TelemetryTimeseries,
    DeviceDashboard, UtilityTariff, UtilityDeviceContract,
    UtilityConsumption, UtilityInvoice
)
from sqlalchemy import func
from datetime import datetime, timedelta, timezone


def print_header(title):
    """Print a formatted header."""
    print('\n' + '='*70)
    print(f'  {title}')
    print('='*70)


def show_overview(db):
    """Show database overview with counts."""
    print_header('📊 DATABASE OVERVIEW')
    
    counts = {
        'Device Types': db.query(DeviceType).count(),
        'Tenants': db.query(Tenant).count(),
        'Devices': db.query(Device).count(),
        'Provisioning Keys': db.query(ProvisioningKey).count(),
        'Device Rules': db.query(DeviceRule).count(),
        'Device Dashboards': db.query(DeviceDashboard).count(),
        'Telemetry (Latest)': db.query(TelemetryLatest).count(),
        'Telemetry (Timeseries)': db.query(TelemetryTimeseries).count(),
        'Utility Tariffs': db.query(UtilityTariff).count(),
        'Utility Contracts': db.query(UtilityDeviceContract).count(),
        'Utility Consumption': db.query(UtilityConsumption).count(),
        'Utility Invoices': db.query(UtilityInvoice).count(),
    }
    
    for name, count in counts.items():
        print(f'  {name:<25} {count:>6,}')


def show_device_types(db):
    """Show all device types."""
    print_header('🔧 DEVICE TYPES')
    
    device_types = db.query(DeviceType).order_by(DeviceType.name).all()
    for dt in device_types:
        device_count = db.query(Device).filter(Device.device_type_id == dt.id).count()
        print(f'  {dt.id:2d}. {dt.name:<30} ({dt.protocol:<10}) [{device_count} devices]')


def show_tenants(db):
    """Show all tenants."""
    print_header('🏢 TENANTS')
    
    tenants = db.query(Tenant).all()
    for t in tenants:
        device_count = db.query(Device).filter(Device.tenant_id == t.id).count()
        status = '✅' if t.is_active else '❌'
        print(f'  {status} {t.id:2d}. {t.name:<30} Code: {t.code:<15} [{device_count} devices]')


def show_devices(db):
    """Show all devices."""
    print_header('📱 DEVICES')
    
    devices = db.query(Device).all()
    for d in devices:
        key = db.query(ProvisioningKey).filter(ProvisioningKey.device_id == d.id).first()
        latest = db.query(TelemetryLatest).filter(TelemetryLatest.device_id == d.id).first()
        
        # Check if device is active (telemetry within last 90 seconds)
        is_live = False
        if latest and latest.updated_at:
            is_live = (datetime.now(timezone.utc) - latest.updated_at).total_seconds() < 90
        
        status = '🟢' if is_live else '⚪'
        
        print(f'\n  {status} {d.device_id:<25} "{d.name}"')
        print(f'     Type: {d.device_type.name:<30} Tenant: {d.tenant.name}')
        if key:
            print(f'     Key:  {key.key[:40]}...')
        
        # Show rules
        rules = db.query(DeviceRule).filter(DeviceRule.device_id == d.id).all()
        if rules:
            print(f'     Rules: {len(rules)} configured')


def show_telemetry_stats(db):
    """Show telemetry statistics."""
    print_header('📊 TELEMETRY STATISTICS')
    
    # Latest telemetry
    latest_count = db.query(TelemetryLatest).count()
    print(f'\n  Latest Snapshots: {latest_count}')
    
    # Timeseries stats
    timeseries_count = db.query(TelemetryTimeseries).count()
    print(f'  Historical Records: {timeseries_count:,}')
    
    if timeseries_count > 0:
        oldest = db.query(func.min(TelemetryTimeseries.ts)).scalar()
        newest = db.query(func.max(TelemetryTimeseries.ts)).scalar()
        
        if oldest and newest:
            print(f'  Oldest Record: {oldest}')
            print(f'  Newest Record: {newest}')
            print(f'  Timespan: {(newest - oldest).days} days')
    
    # Active devices (sent data in last 90 seconds)
    threshold = datetime.now(timezone.utc) - timedelta(seconds=90)
    active_devices = db.query(TelemetryLatest).filter(
        TelemetryLatest.updated_at >= threshold
    ).count()
    print(f'\n  Active Devices (last 90s): {active_devices}')


def show_rules(db):
    """Show all device rules."""
    print_header('⚙️  DEVICE RULES')
    
    rules = db.query(DeviceRule).all()
    if not rules:
        print('  No rules configured.')
        return
    
    for rule in rules:
        device = db.query(Device).filter(Device.id == rule.device_id).first()
        status = '✅' if rule.is_active else '❌'
        print(f'\n  {status} Rule ID: {rule.id}')
        print(f'     Device: {device.device_id} ({device.name})')
        print(f'     Name: {rule.name}')
        print(f'     Priority: {rule.priority}')


def main():
    """Main function."""
    db = SessionLocal()
    
    try:
        print('\n' + '█'*70)
        print('█' + ' '*68 + '█')
        print('█' + '  IoT PLATFORM DATABASE VIEWER'.center(68) + '█')
        print('█' + ' '*68 + '█')
        print('█'*70)
        
        show_overview(db)
        show_device_types(db)
        show_tenants(db)
        show_devices(db)
        show_telemetry_stats(db)
        show_rules(db)
        
        print('\n' + '█'*70)
        print()
        
    finally:
        db.close()


if __name__ == '__main__':
    main()

