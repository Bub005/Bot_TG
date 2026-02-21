import time
from collections import defaultdict
from typing import Dict, List


class RateLimiter:
    """Simple sliding-window rate limiter (in-memory, per user)."""

    def __init__(self, max_calls: int, window_seconds: float) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: Dict[int, List[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        now = time.monotonic()
        calls = self._calls[user_id]
        # Drop calls outside the window
        self._calls[user_id] = [t for t in calls if now - t < self.window]
        if len(self._calls[user_id]) >= self.max_calls:
            return False
        self._calls[user_id].append(now)
        return True
