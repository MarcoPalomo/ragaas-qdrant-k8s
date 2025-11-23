"""Security utilities for API authentication."""

from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

api_key_header = APIKeyHeader(
    name=settings.api_key_header,
    auto_error=False,
)


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
) -> str:
    """
    Verify the API key from request header.

    Args:
        api_key: API key from X-API-Key header

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    # If no token is configured, allow all requests (development mode)
    if not settings.rag_service_token:
        return "development"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key != settings.rag_service_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key


async def optional_api_key(
    api_key: Optional[str] = Security(api_key_header),
) -> Optional[str]:
    """
    Optional API key verification for public endpoints.

    Args:
        api_key: API key from X-API-Key header (optional)

    Returns:
        The API key if provided and valid, None otherwise
    """
    if not api_key:
        return None

    if settings.rag_service_token and api_key == settings.rag_service_token:
        return api_key

    return None


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._requests: dict[str, list[float]] = {}

    async def check_rate_limit(self, client_id: str) -> bool:
        """
        Check if client has exceeded rate limit.

        Args:
            client_id: Unique identifier for the client

        Returns:
            True if request is allowed, False if rate limited
        """
        import time

        current_time = time.time()
        minute_ago = current_time - 60

        # Clean old requests
        if client_id in self._requests:
            self._requests[client_id] = [
                req_time
                for req_time in self._requests[client_id]
                if req_time > minute_ago
            ]
        else:
            self._requests[client_id] = []

        # Check limit
        if len(self._requests[client_id]) >= self.requests_per_minute:
            return False

        # Record request
        self._requests[client_id].append(current_time)
        return True


rate_limiter = RateLimiter()


async def check_rate_limit(
    api_key: str = Depends(verify_api_key),
) -> str:
    """
    Dependency that checks rate limit for authenticated requests.

    Args:
        api_key: Verified API key

    Returns:
        The API key if rate limit not exceeded

    Raises:
        HTTPException: If rate limit exceeded
    """
    if not await rate_limiter.check_rate_limit(api_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )
    return api_key
