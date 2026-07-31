"""Cross-platform operating-system file lock with bounded waiting."""
from __future__ import annotations
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

class LockTimeoutError(TimeoutError):
    pass

class InterProcessLock:
    def __init__(self, path: Path, *, timeout_seconds: float, poll_seconds: float) -> None:
        if timeout_seconds <= 0 or poll_seconds <= 0:
            raise ValueError("lock timing must be positive")
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds

    @contextmanager
    def hold(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self._acquire(stream)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    stream.close()
                    raise LockTimeoutError(str(self.path))
                time.sleep(self.poll_seconds)
        try:
            yield
        finally:
            self._release(stream)
            stream.close()

    @staticmethod
    def _acquire(stream) -> None:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _release(stream) -> None:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
