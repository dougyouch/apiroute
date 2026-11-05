import asyncio
import threading
import weakref


class LoopLocks:
    """One asyncio.Lock per event loop, since an asyncio.Lock can't be shared between loops
    (each thread running asyncio.run has its own)."""

    def __init__(self) -> None:
        self._locks: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = (
            weakref.WeakKeyDictionary()
        )
        self._guard = threading.Lock()

    def current(self) -> asyncio.Lock:
        """The lock for the running loop, created on first use."""
        loop = asyncio.get_running_loop()
        with self._guard:
            lock = self._locks.get(loop)
            if lock is None:
                lock = self._locks[loop] = asyncio.Lock()
            return lock
