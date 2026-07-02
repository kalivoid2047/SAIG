import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, Request

from saig.shared.config import Settings, get_settings
from saig.shared.errors import RateLimitedError


class SlidingWindowLimiter:
    """In-process sliding-window rate limiter.

    Per-instance by design (ADR-0001): the coarse outer layer is Cloudflare;
    this bounds abuse of expensive endpoints within one process.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, times: int, seconds: float) -> None:
        now = time.monotonic()
        with self._lock:
            window = self._hits[key]
            while window and now - window[0] > seconds:
                window.popleft()
            if len(window) >= times:
                retry_after = int(seconds - (now - window[0])) + 1
                raise RateLimitedError(
                    "Rate limit exceeded. Try again later.",
                    extra={"retryAfter": retry_after},
                )
            window.append(now)


_limiter = SlidingWindowLimiter()


def rate_limit(name: str, times: int, seconds: float):
    """Dependency factory: limits by client IP for the named endpoint group."""

    def dependency(request: Request, settings: Settings = Depends(get_settings)) -> None:
        if not settings.rate_limit_enabled:
            return
        client_ip = request.client.host if request.client else "unknown"
        _limiter.check(f"{name}:{client_ip}", times, seconds)

    return dependency
