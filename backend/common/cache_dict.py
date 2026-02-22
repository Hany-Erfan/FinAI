import threading


class ThreadSafeDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()

    def __getitem__(self, key):
        with self._lock:
            return super().__getitem__(key)

    def __setitem__(self, key, value):
        with self._lock:
            return super().__setitem__(key, value)

    def __delitem__(self, key):
        with self._lock:
            return super().__delitem__(key)

    def get(self, key, default=None):
        with self._lock:
            return super().get(key, default)

    def pop(self, key, default=None):
        with self._lock:
            return super().pop(key, default)

    def items(self):
        with self._lock:
            return list(super().items())

    def __contains__(self, key):
        with self._lock:
            return super().__contains__(key)

    def setdefault(self, key, default=None):
        with self._lock:
            return super().setdefault(key, default)

RetailAgentCache: ThreadSafeDict = ThreadSafeDict()
ProductAgentCache: ThreadSafeDict = ThreadSafeDict()