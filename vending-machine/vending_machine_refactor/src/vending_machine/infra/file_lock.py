from __future__ import annotations

import os
import time
from contextlib import AbstractContextManager
from pathlib import Path


class FileLockTimeoutError(TimeoutError):
    pass


class FileLock(AbstractContextManager["FileLock"]):
    """Simple cross-process lock based on exclusive lock-file creation."""

    def __init__(self, target_path: str | Path, timeout: float = 5.0, poll_interval: float = 0.05):
        self.target_path = Path(target_path)
        self.lock_path = self.target_path.with_suffix(self.target_path.suffix + ".lock")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._fd: int | None = None

    def acquire(self) -> "FileLock":
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self._fd, str(os.getpid()).encode("utf-8"))
                return self
            except FileExistsError:
                if self._is_stale_lock():
                    self._remove_stale_lock()
                    continue
                if time.monotonic() >= deadline:
                    raise FileLockTimeoutError(f"파일 잠금을 획득하지 못했습니다: {self.lock_path}")
                time.sleep(self.poll_interval)

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            finally:
                self._fd = None
        try:
            self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    def __enter__(self) -> "FileLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def _is_stale_lock(self) -> bool:
        try:
            raw = self.lock_path.read_text(encoding="utf-8").strip()
        except OSError:
            return False

        if not raw:
            return True

        try:
            pid = int(raw)
        except ValueError:
            return True

        if pid == os.getpid():
            return False

        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        except OSError:
            return False
        return False

    def _remove_stale_lock(self) -> None:
        try:
            self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass
