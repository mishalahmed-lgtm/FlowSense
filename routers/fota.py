"""Firmware Over-The-Air (FOTA) endpoints."""
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Query
from sqlalchemy.orm import Session

from database import get_db
from models import (
    User,
    UserRole,
    Device,
    DeviceType,
    Tenant,
    Firmware,
    FirmwareVersion,
    FOTAJob,
    FOTAJobDevice,
    DeviceFirmwareStatus,
    FirmwareUpdateStatus,
    FOTAJobStatus,
)
from admin_auth import get_current_user


router = APIRouter(prefix="/fota", tags=["fota"])


# ---------- Pydantic schemas ----------

from pydantic import BaseModel


class FirmwareVersionBase(BaseModel):
    version: str
    release_notes: Optional[str] = None
    min_hw_version: Optional[str] = None
    is_recommended: bool = False
    is_mandatory: bool = False


class FirmwareVersionResponse(FirmwareVersionBase):
    id: int
    firmware_id: int
    file_path: str
    checksum: Optional[str] = None
    file_size_bytes: Optional[int] = None
    created_at: datetime


class FirmwareBase(BaseModel):
    name: str
    device_type_id: int
    description: Optional[str] = None


class FirmwareResponse(FirmwareBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class FOTAJobCreateRequest(BaseModel):
    name: str
    firmware_version_id: int
    device_ids: List[int]
    scheduled_at: Optional[datetime] = None


class FOTAJobDeviceStatusResponse(BaseModel):
    device_id: int
    status: FirmwareUpdateStatus
    last_error: Optional[str] = None
    last_update_at: Optional[datetime] = None


class FOTAJobResponse(BaseModel):
    id: int
    name: str
    tenant_id: int
    firmware_version_id: int
    status: FOTAJobStatus
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_by_user_id: Optional[int]
    created_at: datetime
    devices: List[FOTAJobDeviceStatusResponse]


class DeviceFirmwareStatusResponse(BaseModel):
    device_id: int
    current_version: Optional[str]
    target_version: Optional[str]
    status: FirmwareUpdateStatus
    last_error: Optional[str]
    last_update_at: Optional[datetime]


class DeviceFirmwareReportRequest(BaseModel):
    current_version: str
    status: FirmwareUpdateStatus
    error: Optional[str] = None


# ---------- Helpers ----------


def _ensure_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


def _ensure_tenant_admin_or_admin(user: User) -> None:
    if user.role not in (UserRole.ADMIN, UserRole.TENANT_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin or admin access required",
        )


# ---------- Firmware catalog (admin) ----------


@router.post("/firmwares", response_model=FirmwareResponse, status_code=status.HTTP_201_CREATED)
def create_firmware(
    payload: FirmwareBase,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a firmware definition (admin only)."""
    _ensure_admin(current_user)

    device_type = db.query(DeviceType).filter(DeviceType.id == payload.device_type_id).first()
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device type not found")

    firmware = Firmware(
        name=payload.name,
        device_type_id=payload.device_type_id,
        description=payload.description,
    )
    db.add(firmware)
    db.commit()
    db.refresh(firmware)
    return FirmwareResponse(
        id=firmware.id,
        name=firmware.name,
        device_type_id=firmware.device_type_id,
        description=firmware.description,
        created_at=firmware.created_at,
        updated_at=firmware.updated_at,
    )


@router.get("/firmwares", response_model=List[FirmwareResponse])
def list_firmwares(
    device_type_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List firmware definitions. Tenant admins see all, but can only use those matching their devices."""
    _ensure_tenant_admin_or_admin(current_user)

    query = db.query(Firmware)
    if device_type_id is not None:
        query = query.filter(Firmware.device_type_id == device_type_id)

    firmwares = query.all()
    return [
        FirmwareResponse(
            id=f.id,
            name=f.name,
            device_type_id=f.device_type_id,
            description=f.description,
            created_at=f.created_at,
            updated_at=f.updated_at,
        )
        for f in firmwares
    ]


@router.post(
    "/firmwares/{firmware_id}/versions",
    response_model=FirmwareVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_firmware_version(
    firmware_id: int,
    version: str = Form(...),
    release_notes: Optional[str] = Form(None),
    min_hw_version: Optional[str] = Form(None),
    is_recommended: bool = Form(False),
    is_mandatory: bool = Form(False),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a new firmware binary for a firmware definition (admin only).

    NOTE: For now we store the file on local disk under /data/firmware.
    """
    _ensure_admin(current_user)

    firmware = db.query(Firmware).filter(Firmware.id == firmware_id).first()
    if not firmware:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firmware not found")

    # Simple local storage path; in production you'd use object storage (S3, etc.)
    import os
    base_dir = "/data/firmware"
    os.makedirs(base_dir, exist_ok=True)

    file_ext = os.path.splitext(file.filename or "")[1]
    safe_version = version.replace("/", "_")
    filename = f"firmware_{firmware_id}_{safe_version}{file_ext}"
    full_path = os.path.join(base_dir, filename)

    content = await file.read()
    with open(full_path, "wb") as f:
        f.write(content)

    import hashlib

    checksum = hashlib.sha256(content).hexdigest()
    size_bytes = len(content)

    fv = FirmwareVersion(
        firmware_id=firmware.id,
        version=version,
        file_path=full_path,
        checksum=checksum,
        file_size_bytes=size_bytes,
        release_notes=release_notes,
        min_hw_version=min_hw_version,
        is_recommended=is_recommended,
        is_mandatory=is_mandatory,
    )
    db.add(fv)
    db.commit()
    db.refresh(fv)

    return FirmwareVersionResponse(
        id=fv.id,
        firmware_id=fv.firmware_id,
        version=fv.version,
        file_path=fv.file_path,
        checksum=fv.checksum,
        file_size_bytes=fv.file_size_bytes,
        release_notes=fv.release_notes,
        min_hw_version=fv.min_hw_version,
        is_recommended=fv.is_recommended,
        is_mandatory=fv.is_mandatory,
        created_at=fv.created_at,
    )


@router.get("/firmwares/{firmware_id}/versions", response_model=List[FirmwareVersionResponse])
def list_firmware_versions(
    firmware_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List versions for a firmware definition."""
    _ensure_tenant_admin_or_admin(current_user)

    firmware = db.query(Firmware).filter(Firmware.id == firmware_id).first()
    if not firmware:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firmware not found")

    versions = (
        db.query(FirmwareVersion)
        .filter(FirmwareVersion.firmware_id == firmware_id)
        .order_by(FirmwareVersion.created_at.desc())
        .all()
    )
    return [
        FirmwareVersionResponse(
            id=v.id,
            firmware_id=v.firmware_id,
            version=v.version,
            file_path=v.file_path,
            checksum=v.checksum,
            file_size_bytes=v.file_size_bytes,
            release_notes=v.release_notes,
            min_hw_version=v.min_hw_version,
            is_recommended=v.is_recommended,
            is_mandatory=v.is_mandatory,
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.get("/firmwares/{firmware_id}/versions/{version_id}/download")
def download_firmware(
    firmware_id: int,
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download firmware binary file."""
    from fastapi.responses import FileResponse
    import os
    
    _ensure_tenant_admin_or_admin(current_user)
    
    firmware_version = (
        db.query(FirmwareVersion)
        .filter(FirmwareVersion.id == version_id, FirmwareVersion.firmware_id == firmware_id)
        .first()
    )
    if not firmware_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firmware version not found")
    
    if not os.path.exists(firmware_version.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firmware file not found on server")
    
    return FileResponse(
        firmware_version.file_path,
        media_type="application/octet-stream",
        filename=f"firmware_{firmware_id}_v{firmware_version.version}.bin"
    )


# ---------- FOTA jobs ----------


@router.post("/jobs", response_model=FOTAJobResponse, status_code=status.HTTP_201_CREATED)
def create_fota_job(
    payload: FOTAJobCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a FOTA job.

    - Admin: can target any tenant/devices.
    - Tenant admin: can only target devices in their tenant; tenant_id is inferred.
    """
    _ensure_tenant_admin_or_admin(current_user)

    firmware_version = (
        db.query(FirmwareVersion)
        .filter(FirmwareVersion.id == payload.firmware_version_id)
        .first()
    )
    if not firmware_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firmware version not found")

    # Resolve tenant for job
    if current_user.role == UserRole.ADMIN:
        # Admin must ensure all devices belong to the same tenant
        devices = db.query(Device).filter(Device.id.in_(payload.device_ids)).all()
        if not devices:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid devices selected")
        tenant_ids = {d.tenant_id for d in devices}
        if len(tenant_ids) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All devices must belong to the same tenant",
            )
        tenant_id = tenant_ids.pop()
    else:
        # Tenant admin: enforce their tenant
        tenant_id = current_user.tenant_id
        if tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant admin has no tenant assigned",
            )
        devices = (
            db.query(Device)
            .filter(Device.id.in_(payload.device_ids), Device.tenant_id == tenant_id)
            .all()
        )
        if len(devices) != len(payload.device_ids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="One or more devices do not belong to your tenant",
            )

    job = FOTAJob(
        name=payload.name,
        tenant_id=tenant_id,
        firmware_version_id=firmware_version.id,
        status=FOTAJobStatus.SCHEDULED if payload.scheduled_at else FOTAJobStatus.RUNNING,
        scheduled_at=payload.scheduled_at,
        started_at=None if payload.scheduled_at else datetime.now(timezone.utc),
        created_by_user_id=current_user.id,
    )
    db.add(job)
    db.flush()  # get job.id

    # Create per-device job entries and initialise device firmware status
    for device in devices:
        job_device = FOTAJobDevice(
            job_id=job.id,
            device_id=device.id,
            status=FirmwareUpdateStatus.PENDING,
            last_error=None,
            last_update_at=None,
        )
        db.add(job_device)

        # Ensure DeviceFirmwareStatus row exists
        dfs = (
            db.query(DeviceFirmwareStatus)
            .filter(DeviceFirmwareStatus.device_id == device.id)
            .first()
        )
        if not dfs:
            dfs = DeviceFirmwareStatus(
                device_id=device.id,
                current_version=None,
                target_version=firmware_version.version,
                status=FirmwareUpdateStatus.PENDING,
                last_error=None,
                last_update_at=None,
            )
            db.add(dfs)
        else:
            dfs.target_version = firmware_version.version
            dfs.status = FirmwareUpdateStatus.PENDING
            dfs.last_error = None
            dfs.last_update_at = None

    db.commit()
    db.refresh(job)

    # Build response
    device_statuses = []
    for jd in job.devices:
        device_statuses.append(
            FOTAJobDeviceStatusResponse(
                device_id=jd.device_id,
                status=jd.status,
                last_error=jd.last_error,
                last_update_at=jd.last_update_at,
            )
        )

    return FOTAJobResponse(
        id=job.id,
        name=job.name,
        tenant_id=job.tenant_id,
        firmware_version_id=job.firmware_version_id,
        status=job.status,
        scheduled_at=job.scheduled_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_by_user_id=job.created_by_user_id,
        created_at=job.created_at,
        devices=device_statuses,
    )


@router.get("/jobs", response_model=List[FOTAJobResponse])
def list_fota_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List FOTA jobs visible to the current user."""
    _ensure_tenant_admin_or_admin(current_user)

    query = db.query(FOTAJob)
    if current_user.role == UserRole.TENANT_ADMIN:
        query = query.filter(FOTAJob.tenant_id == current_user.tenant_id)

    jobs = query.order_by(FOTAJob.created_at.desc()).all()

    results: List[FOTAJobResponse] = []
    for job in jobs:
        device_statuses = [
            FOTAJobDeviceStatusResponse(
                device_id=jd.device_id,
                status=jd.status,
                last_error=jd.last_error,
                last_update_at=jd.last_update_at,
            )
            for jd in job.devices
        ]
        results.append(
            FOTAJobResponse(
                id=job.id,
                name=job.name,
                tenant_id=job.tenant_id,
                firmware_version_id=job.firmware_version_id,
                status=job.status,
                scheduled_at=job.scheduled_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                created_by_user_id=job.created_by_user_id,
                created_at=job.created_at,
                devices=device_statuses,
            )
        )
    return results


@router.get("/jobs/{job_id}", response_model=FOTAJobResponse)
def get_fota_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get details of a single FOTA job."""
    _ensure_tenant_admin_or_admin(current_user)

    job = db.query(FOTAJob).filter(FOTAJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FOTA job not found")

    if current_user.role == UserRole.TENANT_ADMIN and job.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this job")

    device_statuses = [
        FOTAJobDeviceStatusResponse(
            device_id=jd.device_id,
            status=jd.status,
            last_error=jd.last_error,
            last_update_at=jd.last_update_at,
        )
        for jd in job.devices
    ]
    return FOTAJobResponse(
        id=job.id,
        name=job.name,
        tenant_id=job.tenant_id,
        firmware_version_id=job.firmware_version_id,
        status=job.status,
        scheduled_at=job.scheduled_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_by_user_id=job.created_by_user_id,
        created_at=job.created_at,
        devices=device_statuses,
    )


# ---------- Device firmware status & reporting ----------


@router.get("/devices/{device_id}/status", response_model=DeviceFirmwareStatusResponse)
def get_device_firmware_status(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get firmware status for a single device."""
    _ensure_tenant_admin_or_admin(current_user)

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    if current_user.role == UserRole.TENANT_ADMIN and device.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this device")

    dfs = (
        db.query(DeviceFirmwareStatus)
        .filter(DeviceFirmwareStatus.device_id == device_id)
        .first()
    )
    if not dfs:
        # Return a default "idle" status
        return DeviceFirmwareStatusResponse(
            device_id=device_id,
            current_version=None,
            target_version=None,
            status=FirmwareUpdateStatus.IDLE,
            last_error=None,
            last_update_at=None,
        )

    return DeviceFirmwareStatusResponse(
        device_id=dfs.device_id,
        current_version=dfs.current_version,
        target_version=dfs.target_version,
        status=dfs.status,
        last_error=dfs.last_error,
        last_update_at=dfs.last_update_at,
    )


@router.post("/devices/{device_id}/report", status_code=status.HTTP_204_NO_CONTENT)
def report_device_firmware_status(
    device_id: int,
    payload: DeviceFirmwareReportRequest,
    db: Session = Depends(get_db),
):
    """Device (or gateway) reports its firmware status back to the platform.

    This endpoint is intentionally not protected by user auth because it is meant for devices.
    In a production system you would secure this with device authentication (API key, cert, etc.).
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    dfs = (
        db.query(DeviceFirmwareStatus)
        .filter(DeviceFirmwareStatus.device_id == device_id)
        .first()
    )
    if not dfs:
        dfs = DeviceFirmwareStatus(
            device_id=device_id,
            current_version=payload.current_version,
            target_version=None,
            status=payload.status,
            last_error=payload.error,
            last_update_at=datetime.now(timezone.utc),
        )
        db.add(dfs)
    else:
        dfs.current_version = payload.current_version
        # If device reached success, clear target_version
        if payload.status == FirmwareUpdateStatus.SUCCESS:
            dfs.target_version = None
        dfs.status = payload.status
        dfs.last_error = payload.error
        dfs.last_update_at = datetime.now(timezone.utc)

    # Update any active job-device entries for this device
    active_job_devices = (
        db.query(FOTAJobDevice)
        .join(FOTAJob, FOTAJob.id == FOTAJobDevice.job_id)
        .filter(
            FOTAJobDevice.device_id == device_id,
            FOTAJob.status.in_([FOTAJobStatus.SCHEDULED, FOTAJobStatus.RUNNING]),
        )
        .all()
    )
    for jd in active_job_devices:
        jd.status = payload.status
        jd.last_error = payload.error
        jd.last_update_at = datetime.now(timezone.utc)

    # Optionally, update overall job status if all devices finished
    for jd in active_job_devices:
        job = jd.job
        if job:
            device_statuses = [d.status for d in job.devices]
            if all(s in (FirmwareUpdateStatus.SUCCESS, FirmwareUpdateStatus.FAILED) for s in device_statuses):
                job.status = FOTAJobStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)
            else:
                job.status = FOTAJobStatus.RUNNING
                if job.started_at is None:
                    job.started_at = datetime.now(timezone.utc)

    db.commit()


