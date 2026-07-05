from datetime import datetime, timedelta, timezone


class HeadlineCache:
    def __init__(self, ttl: timedelta, clock=None):
        self.ttl = ttl
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._items = {}

    def get(self, ticker: str):
        key = ticker.upper()
        cached = self._items.get(key)
        if not cached:
            return None

        created_at, headlines = cached
        if self.clock() - created_at > self.ttl:
            self._items.pop(key, None)
            return None
        return headlines

    def set(self, ticker: str, headlines):
        self._items[ticker.upper()] = (self.clock(), list(headlines))
