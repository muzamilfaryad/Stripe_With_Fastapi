"""
Rate limiting middleware using in-memory storage.

For production, consider using Redis-based rate limiting with:
- slowapi + Redis
- fastapi-limiter
- Custom Redis implementation
"""
from fastapi import Request, HTTPException
from typing import Dict, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter for development.
    NOT suitable for multi-process deployments (use Redis in production).
    """
    
    def __init__(self):
        # Storage: {client_ip: [(timestamp, endpoint), ...]}
        self.requests: Dict[str, list] = {}
        self.cleanup_interval = 60  # Clean up old entries every 60 seconds
        self.last_cleanup = datetime.now()
    
    def _cleanup_old_entries(self):
        """Remove entries older than 1 hour"""
        if (datetime.now() - self.last_cleanup).seconds > self.cleanup_interval:
            cutoff = datetime.now() - timedelta(hours=1)
            for ip in list(self.requests.keys()):
                self.requests[ip] = [
                    (ts, endpoint) for ts, endpoint in self.requests[ip]
                    if ts > cutoff
                ]
                if not self.requests[ip]:
                    del self.requests[ip]
            self.last_cleanup = datetime.now()
    
    def is_rate_limited(
        self,
        client_ip: str,
        endpoint: str,
        limit: int = 10,
        window_seconds: int = 60
    ) -> Tuple[bool, int]:
        """
        Check if client has exceeded rate limit.
        
        Args:
            client_ip: Client IP address
            endpoint: API endpoint being accessed
            limit: Maximum requests allowed
            window_seconds: Time window in seconds
        
        Returns:
            Tuple of (is_limited, requests_made)
        """
        self._cleanup_old_entries()
        
        now = datetime.now()
        window_start = now - timedelta(seconds=window_seconds)
        
        # Get requests for this IP
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        
        # Filter to only requests in current window for this endpoint
        recent_requests = [
            (ts, ep) for ts, ep in self.requests[client_ip]
            if ts > window_start and ep == endpoint
        ]
        
        # Check if limit exceeded
        if len(recent_requests) >= limit:
            return True, len(recent_requests)
        
        # Add this request
        self.requests[client_ip].append((now, endpoint))
        
        return False, len(recent_requests) + 1


# Global rate limiter instance
rate_limiter = InMemoryRateLimiter()


def rate_limit(limit: int = 10, window_seconds: int = 60):
    """
    Rate limiting dependency for FastAPI endpoints.
    
    Usage:
        @router.post("/", dependencies=[Depends(rate_limit(limit=10, window_seconds=60))])
        def my_endpoint():
            ...
    
    Args:
        limit: Maximum requests allowed
        window_seconds: Time window in seconds
    """
    async def rate_limit_dependency(request: Request):
        # Get client IP (consider X-Forwarded-For in production behind proxy)
        client_ip = request.client.host if request.client else "unknown"
        
        # For production behind a proxy, use:
        # client_ip = request.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()
        
        endpoint = f"{request.method}:{request.url.path}"
        
        is_limited, request_count = rate_limiter.is_rate_limited(
            client_ip=client_ip,
            endpoint=endpoint,
            limit=limit,
            window_seconds=window_seconds
        )
        
        if is_limited:
            logger.warning(
                f"Rate limit exceeded for {client_ip} on {endpoint}. "
                f"Requests: {request_count}/{limit} in {window_seconds}s"
            )
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {limit} requests per {window_seconds} seconds."
            )
        
        logger.debug(f"Rate limit check: {client_ip} on {endpoint} - {request_count}/{limit}")
    
    return rate_limit_dependency
