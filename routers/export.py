"""Export endpoints for CSV, Excel, and PDF generation."""
import csv
import io
import logging
from datetime import datetime, date, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import pandas as pd

from admin_auth import get_current_user
from database import get_db
from models import Device, TelemetryTimeseries, TelemetryLatest, User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/devices/{device_id}/readings.csv")
async def export_readings_csv(
    device_id: str,
    key: Optional[str] = Query(None, description="Filter by telemetry field key"),
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(10000, ge=1, le=100000, description="Maximum number of readings"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export device readings as CSV file."""
    device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Tenant admins can only access their own tenant's devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access devices from your own tenant"
        )
    
    # Build query
    query = db.query(TelemetryTimeseries).filter(
        TelemetryTimeseries.device_id == device.id
    )
    
    if key:
        query = query.filter(TelemetryTimeseries.key == key)
    
    if from_date:
        from_dt = datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
        query = query.filter(TelemetryTimeseries.ts >= from_dt)
    
    if to_date:
        to_dt = datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)
        to_dt = to_dt + timedelta(days=1)
        query = query.filter(TelemetryTimeseries.ts < to_dt)
    
    rows = query.order_by(TelemetryTimeseries.ts.desc()).limit(limit).all()
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Field Key", "Value"])
    
    for row in rows:
        writer.writerow([
            row.ts.isoformat(),
            row.key,
            row.value,
        ])
    
    output.seek(0)
    
    filename = f"{device_id}_readings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/devices/{device_id}/readings.xlsx")
async def export_readings_excel(
    device_id: str,
    key: Optional[str] = Query(None, description="Filter by telemetry field key"),
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(10000, ge=1, le=100000, description="Maximum number of readings"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export device readings as Excel file."""
    device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Tenant admins can only access their own tenant's devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access devices from your own tenant"
        )
    
    # Build query
    query = db.query(TelemetryTimeseries).filter(
        TelemetryTimeseries.device_id == device.id
    )
    
    if key:
        query = query.filter(TelemetryTimeseries.key == key)
    
    if from_date:
        from_dt = datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
        query = query.filter(TelemetryTimeseries.ts >= from_dt)
    
    if to_date:
        to_dt = datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)
        to_dt = to_dt + timedelta(days=1)
        query = query.filter(TelemetryTimeseries.ts < to_dt)
    
    rows = query.order_by(TelemetryTimeseries.ts.desc()).limit(limit).all()
    
    # Create DataFrame
    data = []
    for row in rows:
        data.append({
            "Timestamp": row.ts.isoformat(),
            "Field Key": row.key,
            "Value": row.value,
        })
    
    df = pd.DataFrame(data)
    
    # Generate Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Readings')
    
    output.seek(0)
    
    filename = f"{device_id}_readings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/devices/{device_id}/readings.pdf")
async def export_readings_pdf(
    device_id: str,
    key: Optional[str] = Query(None, description="Filter by telemetry field key"),
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(1000, ge=1, le=5000, description="Maximum number of readings (PDF limit)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export device readings as PDF report."""
    device = db.query(Device).filter(Device.device_id == device_id).one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    # Tenant admins can only access their own tenant's devices
    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access devices from your own tenant"
        )
    
    # Build query
    query = db.query(TelemetryTimeseries).filter(
        TelemetryTimeseries.device_id == device.id
    )
    
    if key:
        query = query.filter(TelemetryTimeseries.key == key)
    
    if from_date:
        from_dt = datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
        query = query.filter(TelemetryTimeseries.ts >= from_dt)
    
    if to_date:
        to_dt = datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)
        to_dt = to_dt + timedelta(days=1)
        query = query.filter(TelemetryTimeseries.ts < to_dt)
    
    rows = query.order_by(TelemetryTimeseries.ts.desc()).limit(limit).all()
    
    # Generate PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph(f"Device Readings Report: {device_id}", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 0.2 * inch))
    
    # Metadata
    metadata_text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
    if key:
        metadata_text += f"Field Key: {key}<br/>"
    if from_date:
        metadata_text += f"From: {from_date}<br/>"
    if to_date:
        metadata_text += f"To: {to_date}<br/>"
    metadata_text += f"Total Readings: {len(rows)}"
    
    metadata = Paragraph(metadata_text, styles['Normal'])
    elements.append(metadata)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Table data
    table_data = [["Timestamp", "Field Key", "Value"]]
    for row in rows[:500]:  # Limit to 500 rows for PDF
        table_data.append([
            row.ts.strftime('%Y-%m-%d %H:%M:%S'),
            row.key,
            str(row.value) if row.value is not None else "N/A",
        ])
    
    # Create table
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    
    elements.append(table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"{device_id}_readings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

