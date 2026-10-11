"""Fixed-window rate limiter. Redis when configured (shared across instances), else in-process."""
import threading
import time

from app.config import get_settings
from app.errors import AppError


class RateLimiter:
    def __init__(self) -> None:
        self._mem: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()
        self._redis = None
        url = get_settings().redis_url
        if url:
            try:
                import redis

                self._redis = redis.Redis.from_url(url)
                self._redis.ping()
            except Exception:
                self._redis = None

    def hit(self, key: str, limit: int, window_s: int) -> bool:
        """Returns True if allowed."""
        bucket = int(time.time() // window_s)
        k = f"rl:{key}:{bucket}"
        if self._redis is not None:
            try:
                n = self._redis.incr(k)
                if n == 1:
                    self._redis.expire(k, window_s + 1)
                return n <= limit
            except Exception:
                pass
        now = time.time()
        with self._lock:
            n, exp = self._mem.get(k, (0, now + window_s))
            n += 1
            self._mem[k] = (n, exp)
            if len(self._mem) > 50_000:
                self._mem = {kk: v for kk, v in self._mem.items() if v[1] > now}
        return n <= limit

    def enforce(self, key: str, limit: int, window_s: int) -> None:
        if not self.hit(key, limit, window_s):
            raise AppError(429, "rate_limited", "Too many requests. Please slow down.", {"retry_after": window_s})

    def reset(self) -> None:
        with self._lock:
            self._mem.clear()


limiter = RateLimiter()
