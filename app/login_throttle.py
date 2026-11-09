"""In-memory limit on failed logins, kept per worker process."""

import threading
import time


class LoginThrottle:
    """Blocks a key (a client address) after too many failed logins within a time window."""

    def __init__(self, max_failures: int = 10, window_seconds: int = 900, max_keys: int = 10_000):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._failures: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def _current(self, key: str, now: float) -> int:
        count, started = self._failures.get(key, (0, now))
        if now - started >= self.window_seconds:
            self._failures.pop(key, None)
            return 0
        return count

    def blocked(self, key: str) -> bool:
        with self._lock:
            return self._current(key, time.monotonic()) >= self.max_failures

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            count = self._current(key, now)
            if count == 0:
                if len(self._failures) >= self.max_keys:
                    # Bounded memory: a flood of addresses must not grow this forever.
                    self._failures.clear()
                self._failures[key] = (1, now)
            else:
                self._failures[key] = (count + 1, self._failures[key][1])

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
