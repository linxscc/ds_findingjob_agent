import time
import random


class RateLimiter:
    def __init__(self, min_interval: float = 3.0):
        self.min_interval = min_interval
        self._last_request: float = 0.0

    def wait(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.min_interval:
            jitter = random.uniform(0, self.min_interval * 0.5)
            sleep_time = self.min_interval - elapsed + jitter
            time.sleep(sleep_time)
        self._last_request = time.time()
