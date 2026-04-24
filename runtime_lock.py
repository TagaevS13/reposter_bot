from __future__ import annotations

import time
from pathlib import Path


try:
    import msvcrt  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - non-Windows fallback
    msvcrt = None
    import fcntl  # type: ignore[no-redef]


class FileLock:
    def __init__(
        self,
        lock_path: str | Path,
        *,
        timeout_seconds: float = 0.0,
        poll_interval_seconds: float = 0.2,
    ) -> None:
        self.lock_path = Path(lock_path)
        self.timeout_seconds = max(0.0, timeout_seconds)
        self.poll_interval_seconds = max(0.05, poll_interval_seconds)
        self._fp = None
        self._locked = False

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = self.lock_path.open("a+b")
        deadline = time.monotonic() + self.timeout_seconds

        while True:
            try:
                if msvcrt is not None:
                    self._fp.seek(0)
                    msvcrt.locking(self._fp.fileno(), msvcrt.LK_NBLCK, 1)
                else:  # pragma: no cover - non-Windows fallback
                    fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._locked = True
                return
            except OSError:
                if self.timeout_seconds <= 0 or time.monotonic() >= deadline:
                    raise TimeoutError(f"Failed to acquire lock: {self.lock_path}")
                time.sleep(self.poll_interval_seconds)

    def release(self) -> None:
        if not self._fp:
            return
        try:
            if self._locked:
                if msvcrt is not None:
                    self._fp.seek(0)
                    msvcrt.locking(self._fp.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover - non-Windows fallback
                    fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
        finally:
            self._locked = False
            self._fp.close()
            self._fp = None

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
