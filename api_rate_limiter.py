"""Enhanced API rate limiting middleware for REST endpoints."""
import time
import logging
from collections import defaultdict
from typing import Optional
from fastapi import Request, HTTPException, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

# Create rate limiter instance
limiter = Limiter(key_func=get_remote_address)


# Rate limit configurations per endpoint/user role
RATE_LIMITS = {
    "default": "100/minute",  # Default: 100 requests per minute
    "admin": "200/minute",    # Admin: 200 requests per minute
    "tenant_admin": "150/minute",  # Tenant admin: 150 requests per minute
    "telemetry_ingestion": "1000/minute",  # Telemetry ingestion: higher limit
    "export": "10/minute",    # Export endpoints: lower limit (heavy operations)
    "analytics": "20/minute", # Analytics endpoints: moderate limit
}


def get_rate_limit_for_user(role: Optional[str] = None) -> str:
    """Get rate limit string based on user role."""
    if role == "ADMIN":
        return RATE_LIMITS["admin"]
    elif role == "TENANT_ADMIN":
        return RATE_LIMITS["tenant_admin"]
    else:
        return RATE_LIMITS["default"]


def get_rate_limit_for_endpoint(endpoint_path: str) -> str:
    """Get rate limit string based on endpoint path."""
    if "/export/" in endpoint_path:
        return RATE_LIMITS["export"]
    elif "/analytics/" in endpoint_path:
        return RATE_LIMITS["analytics"]
    elif "/telemetry/" in endpoint_path:
        return RATE_LIMITS["telemetry_ingestion"]
    else:
        return RATE_LIMITS["default"]


# Custom rate limit exceeded handler
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded errors."""
    response = _rate_limit_exceeded_handler(request, exc)
    response.headers["X-RateLimit-Limit"] = str(exc.detail.get("limit", "unknown"))
    response.headers["X-RateLimit-Remaining"] = str(exc.detail.get("remaining", 0))
    response.headers["X-RateLimit-Reset"] = str(exc.detail.get("reset", int(time.time())))
    return response

