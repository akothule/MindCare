import hashlib
import time
from collections import deque
from threading import Lock
from typing import Deque, Optional


class SlidingWindowRateLimiter:
    """In-memory per-key sliding-window limiter."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[str, Deque[float]] = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self._max_requests:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class ChatRateLimiter:
    """Rate-limits chat requests by both session and hashed client IP."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._session_limiter = SlidingWindowRateLimiter(max_requests, window_seconds)
        self._ip_limiter = SlidingWindowRateLimiter(max_requests, window_seconds)

    @staticmethod
    def _hashed_ip(ip: str) -> str:
        return hashlib.sha256(ip.encode("utf-8")).hexdigest()

    def allow(self, *, session_id: str, client_ip: str) -> bool:
        # Enforce both dimensions: if either limit is reached, deny.
        if not self._session_limiter.allow(f"session:{session_id}"):
            return False
        if not self._ip_limiter.allow(f"ip:{self._hashed_ip(client_ip)}"):
            return False
        return True

    def reset(self) -> None:
        self._session_limiter.reset()
        self._ip_limiter.reset()


_limiter: Optional[ChatRateLimiter] = None


def get_chat_rate_limiter(*, max_requests: int, window_seconds: int) -> ChatRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = ChatRateLimiter(max_requests=max_requests, window_seconds=window_seconds)
    return _limiter
