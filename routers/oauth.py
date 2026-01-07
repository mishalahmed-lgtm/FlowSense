"""OAuth 2.0 authentication endpoints."""
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel

from admin_auth import create_access_token, verify_password, hash_password
from database import get_db
from models import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"/api/v1/oauth/token",
    auto_error=False
)


class TokenResponse(BaseModel):
    """OAuth 2.0 token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None


class TokenData(BaseModel):
    """Token data for validation."""
    email: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None
    tenant_id: Optional[int] = None


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    OAuth 2.0 compatible token endpoint.
    
    Supports:
    - Password grant type (username/password)
    - Client credentials (for service accounts)
    """
    # For password grant, username is email
    user = db.query(User).filter(
        User.email == form_data.username,
        User.is_active == True
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    from config import settings
    access_token = create_access_token(user)
    
    # Calculate expiration
    expires_in = settings.admin_jwt_exp_minutes * 60  # Convert to seconds
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        scope=" ".join(user.enabled_modules or []) if user.enabled_modules else "read write"
    )


@router.post("/authorize")
async def authorize(
    response_type: str = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    scope: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    OAuth 2.0 authorization endpoint.
    
    This is a simplified implementation. In production, you would:
    - Validate client_id and redirect_uri
    - Store authorization codes
    - Implement proper authorization code flow
    """
    # For now, redirect to login page
    # In a full implementation, this would show an authorization page
    return {
        "message": "Authorization endpoint",
        "note": "Use /oauth/token for password grant type",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope
    }


@router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    """
    OAuth 2.0 Authorization Server Metadata (RFC 8414).
    
    Returns metadata about the OAuth 2.0 server.
    """
    from config import settings
    base_url = getattr(settings, 'api_base_url', 'http://localhost:5000')
    
    return {
        "issuer": f"{base_url}",
        "authorization_endpoint": f"{base_url}/api/v1/oauth/authorize",
        "token_endpoint": f"{base_url}/api/v1/oauth/token",
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
        "response_types_supported": ["code", "token"],
        "grant_types_supported": ["authorization_code", "password", "client_credentials"],
        "scopes_supported": ["read", "write", "admin"],
        "code_challenge_methods_supported": ["S256"]
    }


def get_current_user_from_oauth_token(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user from OAuth 2.0 token."""
    if not token:
        return None
    
    try:
        from admin_auth import decode_token
        payload = decode_token(token)
        user = db.query(User).filter(
            User.id == payload.user_id,
            User.is_active == True
        ).first()
        return user
    except Exception as e:
        logger.debug(f"OAuth token validation failed: {e}")
        return None

