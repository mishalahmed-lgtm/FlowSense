"""Admin authentication helpers for the web console."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from config import settings


class AdminTokenPayload(BaseModel):
    """Token payload stored in JWT."""

    sub: str
    exp: int


http_bearer = HTTPBearer(auto_error=False)


def create_admin_token(email: str) -> str:
    """Generate a short-lived admin JWT."""
    expires = datetime.utcnow() + timedelta(minutes=settings.admin_jwt_exp_minutes)
    payload = {"sub": email, "exp": expires}
    return jwt.encode(payload, settings.admin_jwt_secret, algorithm=settings.admin_jwt_algorithm)


def decode_admin_token(token: str) -> AdminTokenPayload:
    """Decode and validate admin JWT."""
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


def require_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> str:
    """FastAPI dependency to enforce admin authentication."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )

    token = credentials.credentials
    payload = decode_admin_token(token)

    if payload.sub != settings.admin_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin identity",
        )

    return payload.sub


