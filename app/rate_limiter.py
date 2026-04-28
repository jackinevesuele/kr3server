import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

# In-memory fixed-window-like limiter for educational purposes.
# Key format: "<endpoint>:<client_ip>" -> list of request timestamps.
_REQUESTS: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(request: Request, endpoint_key: str, limit: int, period_seconds: int = 60) -> None:
    client_host = request.client.host if request.client else "unknown"
    storage_key = f"{endpoint_key}:{client_host}"
    now = time.monotonic()

    recent_requests = [
        timestamp
        for timestamp in _REQUESTS[storage_key]
        if now - timestamp < period_seconds
    ]

    if len(recent_requests) >= limit:
        _REQUESTS[storage_key] = recent_requests
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
        )

    recent_requests.append(now)
    _REQUESTS[storage_key] = recent_requests
