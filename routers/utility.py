"""Utility metering API for per-tenant, per-device consumption and billing."""

import io
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from admin_auth import require_admin, get_current_user
from models import User, UserRole
from config import settings
from database import get_db
from models import (
    Device,
    Tenant,
    TelemetryTimeseries,
    User,
    UserRole,
)

router = APIRouter(prefix="/admin/utility", tags=["utility"])


class UtilityConsumptionPreview(BaseModel):
    tenant_id: int
    tenant_name: str
    device_id: int
    device_external_id: str
    device_name: Optional[str]
    utility_kind: str
    index_key: str
    period_start: datetime
    period_end: datetime
    start_index: Optional[float]
    end_index: Optional[float]
    consumption: Optional[float]
    unit: str
    rate_per_unit: Optional[float]
    currency: Optional[str]
    amount: Optional[float]


class DeviceConsumptionSummary(BaseModel):
    """Individual device contribution to tenant's total."""
    device_id: int
    device_external_id: str
    device_name: Optional[str]
    consumption: Optional[float]
    amount: Optional[float]


class ConsolidatedTenantBilling(BaseModel):
    """Consolidated billing for all devices under a tenant."""
    tenant_id: int
    tenant_name: str
    utility_kind: str
    period_start: datetime
    period_end: datetime
    total_consumption: float
    unit: str
    rate_per_unit: float
    currency: str
    total_amount: float
    device_count: int
    devices: List[DeviceConsumptionSummary]  # Breakdown by device


def _resolve_index_key(utility_kind: str, device: Device) -> tuple[str, str]:
    """Decide which telemetry key and unit to use as index for a given device.
    
    Returns (index_key, unit) tuple if mapping exists, otherwise raises HTTPException
    to signal the device should be skipped for this utility kind.
    """
    dt_name = device.device_type.name if device.device_type else ""

    # Electricity meters
    if utility_kind == "electricity":
        if "Comcore AMI" in dt_name:
            return "total_active_energy", "kWh"
        if "Comcore DLMS" in dt_name:
            return "active_energy_import_total", "kWh"

    # Gas (LPG meters) – use level as a simple proxy for consumption (demo purposes)
    if utility_kind == "gas":
        if "LPG Meter" in dt_name:
            return "level", "percent"

    # Water meters – only for actual water meter device types
    if utility_kind == "water":
        if "Water Meter" in dt_name or "Water" in dt_name:
            # Expect water meters to expose 'volume_index' or similar field
            return "volume_index", "m3"

    # If we don't know how to interpret this device for the requested
    # utility kind, signal to the caller so it can be skipped.
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"No utility index mapping for device type '{dt_name}' and utility_kind '{utility_kind}'",
    )


def _resolve_rate(utility_kind: str) -> tuple[float, str]:
    """Resolve a simple flat rate and currency per utility kind.

    In a real system this would query UtilityTariff / contracts. For now we
    hard-code reasonable demo defaults so the UI can show billing amounts.
    """
    if utility_kind == "electricity":
        return 0.20, "USD"  # $0.20 per kWh
    if utility_kind == "gas":
        return 0.08, "USD"  # $0.08 per arbitrary gas unit
    if utility_kind == "water":
        return 0.02, "USD"  # $0.02 per m3
    return 0.0, "USD"


@router.get(
    "/consumption/preview",
    response_model=List[UtilityConsumptionPreview],
)
def preview_consumption(
    tenant_id: Optional[int] = Query(None),
    device_id: Optional[int] = Query(None, description="Filter by specific device ID"),
    utility_kind: str = Query(..., regex="^(gas|electricity|water)$"),
    from_date: date = Query(..., description="Start date (inclusive, YYYY-MM-DD)"),
    to_date: date = Query(..., description="End date (exclusive, YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview per-device consumption for a tenant and period without persisting invoices.

    This looks at TelemetryTimeseries and for each matching device:
    - Finds the first and last index values in the period
    - Computes consumption as max(end - start, 0)
    """
    if from_date >= to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be before to_date",
        )

    period_start = datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
    period_end = datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)

    device_query = db.query(Device).join(Tenant)
    
    # Tenant admins can only access their own tenant's data
    if current_user.role == UserRole.TENANT_ADMIN:
        device_query = device_query.filter(Device.tenant_id == current_user.tenant_id)
    elif tenant_id is not None:
        device_query = device_query.filter(Device.tenant_id == tenant_id)
    
    if device_id is not None:
        device_query = device_query.filter(Device.id == device_id)

    devices = device_query.all()

    results: List[UtilityConsumptionPreview] = []

    rate_per_unit, currency = _resolve_rate(utility_kind)

    for device in devices:
        # Not every device type participates in every utility kind
        # (e.g. Valve Controller for gas). If there is no mapping,
        # we simply skip that device instead of failing the whole request.
        try:
            idx_key, unit = _resolve_index_key(utility_kind, device)
        except HTTPException as exc:
            if (
                exc.status_code == status.HTTP_400_BAD_REQUEST
                and "No utility index mapping" in str(exc.detail)
            ):
                continue
            raise

        samples = (
            db.query(TelemetryTimeseries)
            .filter(
                TelemetryTimeseries.device_id == device.id,
                TelemetryTimeseries.key == idx_key,
                TelemetryTimeseries.ts >= period_start,
                TelemetryTimeseries.ts < period_end,
            )
            .order_by(TelemetryTimeseries.ts.asc())
            .all()
        )

        if not samples:
            results.append(
                UtilityConsumptionPreview(
                    tenant_id=device.tenant_id,
                    tenant_name=device.tenant.name if device.tenant else "",
                    device_id=device.id,
                    device_external_id=device.device_id,
                    device_name=device.name,
                    utility_kind=utility_kind,
                    index_key=idx_key,
                    period_start=period_start,
                    period_end=period_end,
                    start_index=None,
                    end_index=None,
                    consumption=None,
                    unit=unit,
                    rate_per_unit=rate_per_unit,
                    currency=currency,
                    amount=None,
                )
            )
            continue

        start_index = samples[0].value
        end_index = samples[-1].value

        if start_index is None or end_index is None:
            consumption = None
            amount = None
        else:
            # For cumulative indexes (electricity), consumption is end - start.
            # For level-like indexes (e.g. LPG level), we guard against negative.
            raw = end_index - start_index
            consumption = raw if raw >= 0 else 0.0
            amount = round(consumption * rate_per_unit, 4)

        results.append(
            UtilityConsumptionPreview(
                tenant_id=device.tenant_id,
                tenant_name=device.tenant.name if device.tenant else "",
                device_id=device.id,
                device_external_id=device.device_id,
                device_name=device.name,
                utility_kind=utility_kind,
                index_key=idx_key,
                period_start=period_start,
                period_end=period_end,
                start_index=start_index,
                end_index=end_index,
                consumption=consumption,
                unit=unit,
                rate_per_unit=rate_per_unit,
                currency=currency,
                amount=amount,
            )
        )

    return results


@router.get(
    "/consumption/consolidated",
    response_model=List[ConsolidatedTenantBilling],
)
def preview_consolidated_consumption(
    tenant_id: Optional[int] = Query(None),
    device_id: Optional[int] = Query(None, description="Filter by specific device ID"),
    utility_kind: str = Query(..., regex="^(gas|electricity|water)$"),
    from_date: date = Query(..., description="Start date (inclusive, YYYY-MM-DD)"),
    to_date: date = Query(..., description="End date (exclusive, YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview consolidated billing per tenant (aggregates all devices).
    
    Returns one record per tenant with total consumption across all their devices.
    Includes device-level breakdown for transparency.
    """
    # Tenant admins can only access their own tenant's data
    effective_tenant_id = tenant_id
    if current_user.role == UserRole.TENANT_ADMIN:
        effective_tenant_id = current_user.tenant_id
    
    # Get per-device consumption data
    device_consumption = preview_consumption(effective_tenant_id, device_id, utility_kind, from_date, to_date, current_user, db)
    
    if not device_consumption:
        return []
    
    # Group by tenant
    tenant_map = {}
    
    for record in device_consumption:
        tid = record.tenant_id
        
        if tid not in tenant_map:
            tenant_map[tid] = {
                "tenant_id": tid,
                "tenant_name": record.tenant_name,
                "utility_kind": utility_kind,
                "period_start": record.period_start,
                "period_end": record.period_end,
                "unit": record.unit,
                "rate_per_unit": record.rate_per_unit,
                "currency": record.currency,
                "total_consumption": 0.0,
                "total_amount": 0.0,
                "device_count": 0,
                "devices": [],
            }
        
        # Add device contribution
        consumption = record.consumption if record.consumption is not None else 0.0
        amount = record.amount if record.amount is not None else 0.0
        
        tenant_map[tid]["total_consumption"] += consumption
        tenant_map[tid]["total_amount"] += amount
        tenant_map[tid]["device_count"] += 1
        tenant_map[tid]["devices"].append(
            DeviceConsumptionSummary(
                device_id=record.device_id,
                device_external_id=record.device_external_id,
                device_name=record.device_name,
                consumption=record.consumption,
                amount=record.amount,
            )
        )
    
    # Convert to list
    results = [
        ConsolidatedTenantBilling(**tenant_data)
        for tenant_data in tenant_map.values()
    ]
    
    return results


@router.get(
    "/reports/billing.pdf",
)
def download_billing_report_pdf(
    tenant_id: Optional[int] = Query(None),
    device_id: Optional[int] = Query(None, description="Filter by specific device ID"),
    utility_kind: str = Query(..., regex="^(gas|electricity|water)$"),
    from_date: date = Query(..., description="Start date (inclusive, YYYY-MM-DD)"),
    to_date: date = Query(..., description="End date (exclusive, YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate and download utility billing PDF report using ReportLab.

    Creates a professional invoice-style PDF with consumption and billing data.
    """
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="ReportLab not installed. Run: pip install reportlab",
        )

    if from_date >= to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be before to_date",
        )
    
    # Tenant admins can only access their own tenant's data
    effective_tenant_id = tenant_id
    if current_user.role == UserRole.TENANT_ADMIN:
        effective_tenant_id = current_user.tenant_id

    # Fetch consumption data
    consumption_data = preview_consumption(effective_tenant_id, device_id, utility_kind, from_date, to_date, current_user, db)

    if not consumption_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No consumption data found for the selected period and utility type.",
        )

    # Generate PDF using ReportLab
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=50, leftMargin=50,
                                topMargin=50, bottomMargin=50)
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=1,  # center
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#374151'),
            spaceAfter=12,
        )
        
        # Title
        elements.append(Paragraph("Utility Billing Report", title_style))
        elements.append(Spacer(1, 12))
        
        # Report Info
        info_text = f"""
        <b>Utility Type:</b> {utility_kind.capitalize()}<br/>
        <b>Period:</b> {from_date.isoformat()} to {to_date.isoformat()}<br/>
        <b>Generated:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}<br/>
        """
        if tenant_id:
            info_text += f"<b>Tenant:</b> {consumption_data[0].tenant_name}<br/>"
        else:
            info_text += "<b>Tenant:</b> All Tenants<br/>"
        
        elements.append(Paragraph(info_text, styles['Normal']))
        elements.append(Spacer(1, 24))
        
        # Table header
        elements.append(Paragraph("Consumption Details", heading_style))
        elements.append(Spacer(1, 12))
        
        # Prepare table data
        table_data = [[
            'Tenant', 'Device', 'Index', 'Start', 'End', 
            'Consumption', 'Unit', 'Rate', 'Amount'
        ]]
        
        total_amount = 0.0
        currency = consumption_data[0].currency if consumption_data else "USD"
        
        for row in consumption_data:
            table_data.append([
                row.tenant_name[:15],
                f"{row.device_external_id[:12]}\n{row.device_name[:12] if row.device_name else ''}",
                row.index_key[:10],
                f"{row.start_index:.2f}" if row.start_index is not None else "—",
                f"{row.end_index:.2f}" if row.end_index is not None else "—",
                f"{row.consumption:.2f}" if row.consumption is not None else "—",
                row.unit[:6],
                f"{row.rate_per_unit:.4f}" if row.rate_per_unit is not None else "—",
                f"{row.amount:.2f}" if row.amount is not None else "—",
            ])
            if row.amount is not None:
                total_amount += row.amount
        
        # Create table
        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        
        elements.append(t)
        elements.append(Spacer(1, 24))
        
        # Total
        total_text = f"<b>Total Amount: {total_amount:.2f} {currency}</b>"
        elements.append(Paragraph(total_text, heading_style))
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        filename = f"utility_billing_{utility_kind}_{from_date.isoformat()}_{to_date.isoformat()}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
            
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {str(exc)}",
        ) from exc


@router.get(
    "/reports/consolidated-billing.pdf",
)
def download_consolidated_billing_pdf(
    tenant_id: Optional[int] = Query(None),
    device_id: Optional[int] = Query(None, description="Filter by specific device ID"),
    utility_kind: str = Query(..., regex="^(gas|electricity|water)$"),
    from_date: date = Query(..., description="Start date (inclusive, YYYY-MM-DD)"),
    to_date: date = Query(..., description="End date (exclusive, YYYY-MM-DD)"),
    show_device_breakdown: bool = Query(True, description="Include device-level breakdown"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate consolidated billing PDF report (per-tenant aggregates).
    
    Creates a PDF showing total consumption per tenant across all their devices.
    Optionally includes device-level breakdown for transparency.
    """
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="ReportLab not installed. Run: pip install reportlab",
        )

    if from_date >= to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be before to_date",
        )

    # Tenant admins can only access their own tenant's data
    effective_tenant_id = tenant_id
    if current_user.role == UserRole.TENANT_ADMIN:
        effective_tenant_id = current_user.tenant_id
    
    # Fetch consolidated consumption data
    consolidated_data = preview_consolidated_consumption(
        effective_tenant_id, device_id, utility_kind, from_date, to_date, current_user, db
    )

    if not consolidated_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No consumption data found for the selected period and utility type.",
        )

    # Generate PDF using ReportLab
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=50, leftMargin=50,
                                topMargin=50, bottomMargin=50)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=1,
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#374151'),
            spaceAfter=12,
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=11,
            textColor=colors.HexColor('#6b7280'),
            spaceAfter=8,
        )
        
        # Title
        elements.append(Paragraph("Consolidated Utility Billing Report", title_style))
        elements.append(Spacer(1, 12))
        
        # Report Info
        info_text = f"""
        <b>Utility Type:</b> {utility_kind.capitalize()}<br/>
        <b>Period:</b> {from_date.isoformat()} to {to_date.isoformat()}<br/>
        <b>Generated:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}<br/>
        <b>Report Type:</b> Consolidated (Per-Tenant Summary)<br/>
        """
        if tenant_id:
            info_text += f"<b>Tenant:</b> {consolidated_data[0].tenant_name}<br/>"
        else:
            info_text += "<b>Scope:</b> All Tenants<br/>"
        
        elements.append(Paragraph(info_text, styles['Normal']))
        elements.append(Spacer(1, 24))
        
        # Tenant Summary Table
        elements.append(Paragraph("Tenant Summary", heading_style))
        elements.append(Spacer(1, 12))
        
        summary_table_data = [[
            'Tenant', 'Devices', 'Total Consumption', 'Unit', 'Rate', 'Total Amount'
        ]]
        
        grand_total = 0.0
        currency = consolidated_data[0].currency if consolidated_data else "USD"
        
        for tenant in consolidated_data:
            summary_table_data.append([
                tenant.tenant_name[:25],
                str(tenant.device_count),
                f"{tenant.total_consumption:.2f}",
                tenant.unit[:8],
                f"{tenant.rate_per_unit:.4f}",
                f"{tenant.total_amount:.2f}",
            ])
            grand_total += tenant.total_amount
        
        # Summary table
        summary_table = Table(summary_table_data, repeatRows=1)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#eff6ff')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 24))
        
        # Grand Total
        total_text = f"<b>Grand Total: {grand_total:.2f} {currency}</b>"
        elements.append(Paragraph(total_text, heading_style))
        elements.append(Spacer(1, 24))
        
        # Device Breakdown (optional)
        if show_device_breakdown:
            elements.append(Paragraph("Device-Level Breakdown", heading_style))
            elements.append(Spacer(1, 12))
            
            for tenant in consolidated_data:
                # Tenant header
                tenant_header = f"<b>{tenant.tenant_name}</b> ({tenant.device_count} devices)"
                elements.append(Paragraph(tenant_header, subheading_style))
                
                # Device table
                device_table_data = [[
                    'Device ID', 'Device Name', 'Consumption', 'Amount'
                ]]
                
                for device in tenant.devices:
                    device_table_data.append([
                        device.device_external_id[:15],
                        (device.device_name[:20] if device.device_name else "—"),
                        f"{device.consumption:.2f}" if device.consumption is not None else "—",
                        f"{device.amount:.2f}" if device.amount is not None else "—",
                    ])
                
                device_table = Table(device_table_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 1.5*inch], repeatRows=1)
                device_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6b7280')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('TOPPADDING', (0, 1), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ]))
                
                elements.append(device_table)
                elements.append(Spacer(1, 16))
        
        # Build PDF
        doc.build(elements)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        filename = f"consolidated_billing_{utility_kind}_{from_date.isoformat()}_{to_date.isoformat()}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
            
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate consolidated PDF: {str(exc)}",
        ) from exc


@router.get(
    "/reports/all-utilities-billing.pdf",
)
def download_all_utilities_billing_pdf(
    from_date: date = Query(..., description="Start date (inclusive, YYYY-MM-DD)"),
    to_date: date = Query(..., description="End date (exclusive, YYYY-MM-DD)"),
    show_device_breakdown: bool = Query(True, description="Include device-level breakdown"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate comprehensive billing PDF report for all utilities (electricity, gas, water).
    
    Creates a PDF showing consumption across all utility types per tenant.
    """
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="ReportLab not installed. Run: pip install reportlab",
        )

    if from_date >= to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be before to_date",
        )
    
    # Tenant admins can only access their own tenant's data
    effective_tenant_id = None
    if current_user.role == UserRole.TENANT_ADMIN:
        effective_tenant_id = current_user.tenant_id

    # Fetch consolidated consumption data for ALL utility types
    all_utilities = ["electricity", "gas", "water"]
    all_consolidated_data = []
    
    for utility_kind in all_utilities:
        try:
            data = preview_consolidated_consumption(
                tenant_id=effective_tenant_id,
                device_id=None,
                utility_kind=utility_kind,
                from_date=from_date,
                to_date=to_date,
                current_user=current_user,
                db=db,
            )
            all_consolidated_data.extend(data)
        except Exception:
            # Skip utilities with no data
            continue

    if not all_consolidated_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No consumption data found for the selected period.",
        )

    # Generate PDF using ReportLab
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=50, leftMargin=50,
                                topMargin=50, bottomMargin=50)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=1,
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#374151'),
            spaceAfter=12,
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=11,
            textColor=colors.HexColor('#6b7280'),
            spaceAfter=8,
        )
        
        # Title
        elements.append(Paragraph("Comprehensive Utility Billing Report", title_style))
        elements.append(Spacer(1, 12))
        
        # Report Info
        info_text = f"""
        <b>Period:</b> {from_date.isoformat()} to {to_date.isoformat()}<br/>
        <b>Generated:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}<br/>
        <b>Scope:</b> All Utilities (Electricity, Gas, Water)<br/>
        <b>Report Type:</b> Consolidated Per-Tenant Summary<br/>
        """
        
        elements.append(Paragraph(info_text, styles['Normal']))
        elements.append(Spacer(1, 24))
        
        # Summary by Tenant and Utility
        elements.append(Paragraph("Summary by Tenant & Utility Type", heading_style))
        elements.append(Spacer(1, 12))
        
        summary_table_data = [[
            'Tenant', 'Utility', 'Devices', 'Consumption', 'Unit', 'Rate', 'Amount'
        ]]
        
        grand_total = 0.0
        currency = all_consolidated_data[0].currency if all_consolidated_data else "USD"
        
        for row in all_consolidated_data:
            summary_table_data.append([
                row.tenant_name[:20],
                row.utility_kind.capitalize(),
                str(row.device_count),
                f"{row.total_consumption:.2f}",
                row.unit[:8],
                f"{row.rate_per_unit:.4f}",
                f"{row.total_amount:.2f}",
            ])
            grand_total += row.total_amount
        
        # Summary table
        summary_table = Table(summary_table_data, repeatRows=1)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#eff6ff')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 24))
        
        # Grand Total
        total_text = f"<b>Grand Total (All Utilities): {grand_total:.2f} {currency}</b>"
        elements.append(Paragraph(total_text, heading_style))
        elements.append(Spacer(1, 24))
        
        # Device Breakdown (optional)
        if show_device_breakdown:
            elements.append(Paragraph("Device-Level Breakdown by Utility", heading_style))
            elements.append(Spacer(1, 12))
            
            # Group by utility type
            by_utility = {}
            for row in all_consolidated_data:
                utility = row.utility_kind
                if utility not in by_utility:
                    by_utility[utility] = []
                by_utility[utility].append(row)
            
            for utility_kind, rows in by_utility.items():
                # Utility section header
                utility_header = f"<b>{utility_kind.upper()}</b>"
                elements.append(Paragraph(utility_header, subheading_style))
                elements.append(Spacer(1, 8))
                
                for tenant_row in rows:
                    # Tenant header
                    tenant_header = f"{tenant_row.tenant_name} ({tenant_row.device_count} devices, {tenant_row.total_consumption:.2f} {tenant_row.unit})"
                    elements.append(Paragraph(tenant_header, styles['Normal']))
                    
                    # Device table
                    device_table_data = [[
                        'Device ID', 'Device Name', 'Consumption', 'Amount'
                    ]]
                    
                    for device in tenant_row.devices:
                        device_table_data.append([
                            device.device_external_id[:15],
                            (device.device_name[:20] if device.device_name else "—"),
                            f"{device.consumption:.2f}" if device.consumption is not None else "—",
                            f"{device.amount:.2f}" if device.amount is not None else "—",
                        ])
                    
                    device_table = Table(device_table_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 1.5*inch], repeatRows=1)
                    device_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6b7280')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                        ('FONTSIZE', (0, 1), (-1, -1), 7),
                        ('TOPPADDING', (0, 1), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                    ]))
                    
                    elements.append(device_table)
                    elements.append(Spacer(1, 12))
                
                elements.append(Spacer(1, 8))
        
        # Build PDF
        doc.build(elements)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        filename = f"all_utilities_billing_{from_date.isoformat()}_{to_date.isoformat()}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
            
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate comprehensive PDF: {str(exc)}",
        ) from exc


