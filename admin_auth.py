"""Admin authentication helpers for the web console."""

from datetime import datetime, timedelta
from typing import Optional, Dict

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


# Simple in-memory cache for user lookups (reduces DB queries on free-tier)
_user_cache: Dict[int, tuple[User, float]] = {}  # {user_id: (user, timestamp)}
_CACHE_TTL = 300.0  # Cache for 5 minutes (increased from 60s for better performance)

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: Session = Depends(get_db)
) -> User:
    """FastAPI dependency to get the current authenticated user.
    
    OPTIMIZED FOR FREE-TIER DB (no indexes):
    - Aggressive caching (5 minutes TTL) to minimize DB queries
    - Uses Session.get() for primary key lookup (fastest method, even without indexes)
    - Only checks is_active if user exists (avoids double query)
    - No DB writes (read-only)
    
    Performance:
    - Cache hit: <1ms (no DB query)
    - Cache miss: ~50-200ms (single primary key lookup)
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )

    token = credentials.credentials
    payload = decode_token(token)
    
    # Check cache first (aggressive caching for free-tier DB)
    import time
    now = time.time()
    if payload.user_id in _user_cache:
        cached_user, cache_time = _user_cache[payload.user_id]
        if now - cache_time < _CACHE_TTL:
            # Return cached user immediately (no DB query)
            return cached_user
    
    # OPTIMIZED: Use Session.get() for primary key lookup (fastest method)
    # This is faster than filter().first() even without indexes
    user = db.get(User, payload.user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    # Check is_active after getting user (single query, not two)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )
    
    # Cache the user (expires in 5 minutes)
    _user_cache[payload.user_id] = (user, now)
    
    # Clean old cache entries periodically (keep cache size reasonable)
    if len(_user_cache) > 200:
        # Remove entries older than cache TTL
        expired_keys = [
            user_id for user_id, (_, cache_time) in _user_cache.items()
            if now - cache_time >= _CACHE_TTL
        ]
        for key in expired_keys:
            _user_cache.pop(key, None)
    
    # REMOVED: last_login_at update - this was causing a DB write on every request!
    # last_login_at is now only updated during actual login in /admin/login endpoint
    
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


def get_current_user_from_token(token: str, db: Session) -> Optional[User]:
    """Get user from token string (for WebSocket authentication).
    
    OPTIMIZED: Uses Session.get() for primary key lookup (fastest method).
    """
    try:
        payload = decode_token(token)
        # OPTIMIZED: Use Session.get() instead of filter().first()
        user = db.get(User, payload.user_id)
        if user and user.is_active:
            return user
        return None
    except Exception:
        return None


