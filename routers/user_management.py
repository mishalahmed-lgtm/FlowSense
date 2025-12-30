"""User and tenant management API endpoints for admin portal."""

from datetime import datetime
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

import secrets
from admin_auth import require_admin, get_current_user, hash_password
from database import get_db
from models import User, UserRole, Tenant, ExternalIntegration

router = APIRouter(prefix="/admin", tags=["user-management"])


# ============================================
# Pydantic Models
# ============================================

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=50)
    country: Optional[str] = Field(None, max_length=100)
    is_active: bool = True


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    country: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class TenantResponse(BaseModel):
    id: int
    name: str
    code: str
    country: Optional[str] = None
    is_active: bool
    created_at: datetime
    device_count: int = 0
    user_count: int = 0

    class Config:
        orm_mode = True


class ExternalIntegrationConfig(BaseModel):
    """Configuration for external integration."""
    name: Optional[str] = None
    description: Optional[str] = None
    allowed_endpoints: List[str] = Field(default_factory=list)  # ["health", "data", "devices"]
    endpoint_urls: Optional[Dict[str, str]] = Field(default_factory=dict)  # {"health": "url", "data": "url", "devices": "url"}
    webhook_url: Optional[str] = None  # Deprecated, use endpoint_urls instead


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    role: UserRole = UserRole.TENANT_ADMIN
    tenant_id: Optional[int] = None
    enabled_modules: List[str] = Field(default_factory=list)
    external_integration: Optional[ExternalIntegrationConfig] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6)
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    tenant_id: Optional[int] = None
    enabled_modules: Optional[List[str]] = None
    is_active: Optional[bool] = None
    external_integration: Optional[ExternalIntegrationConfig] = None


class ExternalIntegrationResponse(BaseModel):
    id: int
    api_key: str
    name: Optional[str]
    description: Optional[str]
    allowed_endpoints: List[str]
    endpoint_urls: Optional[Dict[str, str]] = None
    webhook_url: Optional[str]
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime

    class Config:
        orm_mode = True


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    tenant_id: Optional[int]
    tenant_name: Optional[str]
    enabled_modules: List[str]
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    external_integrations: List[ExternalIntegrationResponse] = Field(default_factory=list)

    class Config:
        orm_mode = True


# ============================================
# Tenant Management Endpoints
# ============================================

@router.get("/tenants", response_model=List[TenantResponse])
def list_tenants(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all tenants (admin only)."""
    tenants = db.query(Tenant).order_by(Tenant.name).all()
    
    result = []
    for tenant in tenants:
        user_count = db.query(User).filter(User.tenant_id == tenant.id).count()
        
        result.append(TenantResponse(
            id=tenant.id,
            name=tenant.name,
            code=tenant.code,
            country=tenant.country,
            is_active=tenant.is_active,
            created_at=tenant.created_at,
            device_count=len(tenant.devices),
            user_count=user_count,
        ))
    
    return result


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new tenant (admin only)."""
    # Check if code already exists
    existing = db.query(Tenant).filter(Tenant.code == payload.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant code already exists",
        )
    
    tenant = Tenant(
        name=payload.name,
        code=payload.code,
        country=payload.country,
        is_active=payload.is_active,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        code=tenant.code,
        country=tenant.country,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        device_count=0,
        user_count=0,
    )


@router.put("/tenants/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: int,
    payload: TenantUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a tenant (admin only)."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    
    # Check code uniqueness if being updated
    if payload.code and payload.code != tenant.code:
        existing = db.query(Tenant).filter(Tenant.code == payload.code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant code already exists",
            )
    
    if payload.name is not None:
        tenant.name = payload.name
    if payload.code is not None:
        tenant.code = payload.code
    if payload.country is not None:
        tenant.country = payload.country
    if payload.is_active is not None:
        tenant.is_active = payload.is_active
    
    db.commit()
    db.refresh(tenant)
    
    user_count = db.query(User).filter(User.tenant_id == tenant.id).count()
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        code=tenant.code,
        country=tenant.country,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        device_count=len(tenant.devices),
        user_count=user_count,
    )


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a tenant (admin only)."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    
    # Check if tenant has devices or users
    if len(tenant.devices) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete tenant with existing devices",
        )
    
    user_count = db.query(User).filter(User.tenant_id == tenant.id).count()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete tenant with existing users",
        )
    
    db.delete(tenant)
    db.commit()


# ============================================
# User Management Endpoints
# ============================================

@router.get("/users", response_model=List[UserResponse])
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List users (admins see all, tenant admins see their tenant's users)."""
    if current_user.role == UserRole.ADMIN:
        users = db.query(User).order_by(User.email).all()
    else:
        # Tenant admin can only see users in their tenant
        users = db.query(User).filter(User.tenant_id == current_user.tenant_id).order_by(User.email).all()
    
    result = []
    for user in users:
        tenant_name = None
        if user.tenant_id:
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            tenant_name = tenant.name if tenant else None
        
        # Get external integrations
        integrations = db.query(ExternalIntegration).filter(
            ExternalIntegration.user_id == user.id
        ).all()
        external_integrations = [
            ExternalIntegrationResponse(
                id=integration.id,
                api_key=integration.api_key,
                name=integration.name,
                description=integration.description,
                allowed_endpoints=integration.allowed_endpoints or [],
                endpoint_urls=integration.endpoint_urls or {},
                webhook_url=integration.webhook_url,
                is_active=integration.is_active,
                last_used_at=integration.last_used_at,
                created_at=integration.created_at,
            )
            for integration in integrations
        ]
        
        result.append(UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            tenant_id=user.tenant_id,
            tenant_name=tenant_name,
            enabled_modules=user.enabled_modules or [],
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            external_integrations=external_integrations,
        ))
    
    return result


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new user (admin only)."""
    # Check if email already exists
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )
    
    # Validate tenant_id if provided
    if payload.tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == payload.tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant not found",
            )
    
    # Tenant admins must have a tenant_id
    if payload.role == UserRole.TENANT_ADMIN and not payload.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant admin users must be assigned to a tenant",
        )
    
    # Hash password
    hashed_password = hash_password(payload.password)
    
    user = User(
        email=payload.email.lower(),
        hashed_password=hashed_password,
        full_name=payload.full_name,
        role=payload.role,
        tenant_id=payload.tenant_id,
        enabled_modules=payload.enabled_modules,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create external integration if configured
    external_integrations = []
    if payload.external_integration:
        # Generate API key
        api_key = f"ext_{secrets.token_urlsafe(32)}"
        integration = ExternalIntegration(
            user_id=user.id,
            api_key=api_key,
            name=payload.external_integration.name or f"Integration for {user.email}",
            description=payload.external_integration.description,
            allowed_endpoints=payload.external_integration.allowed_endpoints,
            endpoint_urls=payload.external_integration.endpoint_urls or {},
            webhook_url=payload.external_integration.webhook_url,
            is_active=True,
        )
        db.add(integration)
        db.commit()
        db.refresh(integration)
        external_integrations.append(ExternalIntegrationResponse(
            id=integration.id,
            api_key=integration.api_key,
            name=integration.name,
            description=integration.description,
            allowed_endpoints=integration.allowed_endpoints or [],
            endpoint_urls=integration.endpoint_urls or {},
            webhook_url=integration.webhook_url,
            is_active=integration.is_active,
            last_used_at=integration.last_used_at,
            created_at=integration.created_at,
        ))
    
    tenant_name = None
    if user.tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        tenant_name = tenant.name if tenant else None
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        tenant_id=user.tenant_id,
        tenant_name=tenant_name,
        enabled_modules=user.enabled_modules or [],
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        external_integrations=external_integrations,
    )


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Check email uniqueness if being updated
    if payload.email and payload.email.lower() != user.email:
        existing = db.query(User).filter(User.email == payload.email.lower()).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )
    
    # Validate tenant_id if being updated
    if payload.tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == payload.tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant not found",
            )
    
    # Update fields
    if payload.email is not None:
        user.email = payload.email.lower()
    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = payload.role
    if payload.tenant_id is not None:
        user.tenant_id = payload.tenant_id
    if payload.enabled_modules is not None:
        user.enabled_modules = payload.enabled_modules
    if payload.is_active is not None:
        user.is_active = payload.is_active
    
    # Handle external integration update
    if payload.external_integration is not None:
        # Check if integration already exists
        existing_integration = db.query(ExternalIntegration).filter(
            ExternalIntegration.user_id == user.id
        ).first()
        
        if existing_integration:
            # Update existing integration
            if payload.external_integration.name is not None:
                existing_integration.name = payload.external_integration.name
            if payload.external_integration.description is not None:
                existing_integration.description = payload.external_integration.description
            if payload.external_integration.allowed_endpoints is not None:
                existing_integration.allowed_endpoints = payload.external_integration.allowed_endpoints
            if payload.external_integration.endpoint_urls is not None:
                existing_integration.endpoint_urls = payload.external_integration.endpoint_urls
            if payload.external_integration.webhook_url is not None:
                existing_integration.webhook_url = payload.external_integration.webhook_url
        else:
            # Create new integration
            api_key = f"ext_{secrets.token_urlsafe(32)}"
            integration = ExternalIntegration(
                user_id=user.id,
                api_key=api_key,
                name=payload.external_integration.name or f"Integration for {user.email}",
                description=payload.external_integration.description,
                allowed_endpoints=payload.external_integration.allowed_endpoints or [],
                endpoint_urls=payload.external_integration.endpoint_urls or {},
                webhook_url=payload.external_integration.webhook_url,
                is_active=True,
            )
            db.add(integration)
    
    db.commit()
    db.refresh(user)
    
    # Get external integrations
    integrations = db.query(ExternalIntegration).filter(
        ExternalIntegration.user_id == user.id
    ).all()
    external_integrations = [
        ExternalIntegrationResponse(
            id=integration.id,
            api_key=integration.api_key,
            name=integration.name,
            description=integration.description,
            allowed_endpoints=integration.allowed_endpoints or [],
            webhook_url=integration.webhook_url,
            is_active=integration.is_active,
            last_used_at=integration.last_used_at,
            created_at=integration.created_at,
        )
        for integration in integrations
    ]
    
    tenant_name = None
    if user.tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        tenant_name = tenant.name if tenant else None
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        tenant_id=user.tenant_id,
        tenant_name=tenant_name,
        enabled_modules=user.enabled_modules or [],
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        external_integrations=external_integrations,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Prevent deleting yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    
    db.delete(user)
    db.commit()


@router.get("/users/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user info."""
    tenant_name = None
    if current_user.tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
        tenant_name = tenant.name if tenant else None
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        tenant_id=current_user.tenant_id,
        tenant_name=tenant_name,
        enabled_modules=current_user.enabled_modules or [],
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
    )


@router.get("/modules", response_model=List[str])
def get_available_modules(
    _: User = Depends(require_admin),
):
    """Get list of available modules."""
    return ["devices", "dashboards", "utility", "rules", "alerts", "fota", "health", "analytics"]

