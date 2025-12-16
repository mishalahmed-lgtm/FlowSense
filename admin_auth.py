"""Admin authentication helpers for the web console."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User, UserRole

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AdminTokenPayload(BaseModel):
    """Token payload stored in JWT."""

    sub: str  # user email
    user_id: int
    role: str
    tenant_id: Optional[int]
    exp: int


http_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    # Bcrypt has a 72-byte limit, so truncate if necessary
    password_bytes = password.encode('utf-8')[:72]
    return pwd_context.hash(password_bytes.decode('utf-8'))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user: User) -> str:
    """Generate a JWT token for a user."""
    expires = datetime.utcnow() + timedelta(minutes=settings.admin_jwt_exp_minutes)
    payload = {
        "sub": user.email,
        "user_id": user.id,
        "role": user.role.value,
        "tenant_id": user.tenant_id,
        "exp": expires
    }
    return jwt.encode(payload, settings.admin_jwt_secret, algorithm=settings.admin_jwt_algorithm)


def decode_token(token: str) -> AdminTokenPayload:
    """Decode and validate JWT token."""
    try:
        decoded = jwt.decode(
            token,
            settings.admin_jwt_secret,
            algorithms=[settings.admin_jwt_algorithm],
        )
        return AdminTokenPayload(**decoded)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: Session = Depends(get_db)
) -> User:
    """FastAPI dependency to get the current authenticated user."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )

    token = credentials.credentials
    payload = decode_token(token)
    
    # Get user from database
    user = db.query(User).filter(User.id == payload.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """FastAPI dependency to enforce admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_module(module_name: str):
    """Factory function to create a dependency that checks for a specific module."""
    def check_module(current_user: User = Depends(get_current_user)) -> User:
        # Admins have access to everything
        if current_user.role == UserRole.ADMIN:
            return current_user
        
        # Check if user has the required module
        if module_name not in (current_user.enabled_modules or []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access to '{module_name}' module required",
            )
        return current_user
    
    return check_module


