import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple, Optional

from fastapi import Request, HTTPException, status

from src.api.config import get_settings

# Windowed fixed bucket rate limiter stored in memory
# Note: For production use, replace with Redis/memcached shared store.


class RateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str) -> Tuple[bool, int]:
        """Returns (allowed, remaining)."""
        now = time.time()
        window_start = now - self.window
        q = self.requests[key]

        # Purge old entries
        while q and q[0] <= window_start:
            q.popleft()

        if len(q) < self.limit:
            q.append(now)
            remaining = self.limit - len(q)
            return True, remaining
        else:
            remaining = 0
            return False, remaining


rate_limiter = RateLimiter(
    limit=get_settings().rate_limit_requests, window_seconds=get_settings().rate_limit_window_seconds
)


def client_key_from_request(request: Request, subject: Optional[str]) -> str:
    """Generate a rate limiting key per client ip and subject if present."""
    ip = request.client.host if request.client else "unknown"
    sub_part = subject or "anon"
    return f"{ip}:{sub_part}"


async def enforce_rate_limit(request: Request, subject: Optional[str]) -> None:
    """Raise HTTP 429 if rate limit exceeded."""
    allowed, remaining = rate_limiter.is_allowed(client_key_from_request(request, subject))
    if not allowed:
        headers = {"Retry-After": str(get_settings().rate_limit_window_seconds)}
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
            headers=headers,
        )
