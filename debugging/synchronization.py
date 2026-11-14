
"""
Synchronization Monitor and Lock Tracker
Tracks lock requests, acquisition latency, holding duration,
and contention between processes.
"""

import logging
import multiprocessing as mp
import time
from typing import Any, Dict, Optional

from debugging.event_logger import event_logger

logger = logging.getLogger("IPC_Synchronization")


class LockTelemetryRecord:
    """Represents a discrete lock event record."""

    def __init__(
        self,
        lock_name: str,
        process_name: str,
        process_pid: Optional[int],
        action: str,
        timestamp: float,
        wait_time_ms: float = 0.0,
        hold_time_ms: float = 0.0,
    ):
        self.lock_name = lock_name
        self.process_name = process_name
        self.process_pid = process_pid
        self.action = action
        self.timestamp = timestamp
        self.wait_time_ms = wait_time_ms
        self.hold_time_ms = hold_time_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lock_name": self.lock_name,
            "process_name": self.process_name,
            "process_pid": self.process_pid,
            "action": self.action,
            "timestamp": self.timestamp,
            "wait_time_ms": round(self.wait_time_ms, 2),
            "hold_time_ms": round(self.hold_time_ms, 2),
        }


class MonitoredLock:
    """
    Wrapper around multiprocessing.Lock that tracks:
    - Lock acquisition
    - Waiting time
    - Lock holding duration
    - Acquisition timeout
    """

    def __init__(
        self,
        name: str,
        lock: Optional[Any] = None,
    ):
        self.name = name
        self._lock = lock if lock is not None else mp.Lock()

        # These fields are local telemetry, not shared cross-process state.
        self.owner_pid: Optional[int] = None
        self.owner_name: Optional[str] = None
        self.acquire_timestamp: Optional[float] = None
        self.is_held = False

    def acquire(
        self,
        process_name: str,
        process_pid: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> bool:
        """Acquire the lock while recording waiting time."""

        req_time = time.perf_counter()

        event_logger.log(
            ipc_type="SYNC",
            severity="INFO",
            message=f"Process '{process_name}' requesting lock '{self.name}'",
            process_name=process_name,
            process_pid=process_pid,
        )

        if timeout is not None:
            if timeout < 0:
                raise ValueError("Timeout cannot be negative.")

            acquired = self._lock.acquire(timeout=timeout)
        else:
            acquired = self._lock.acquire()

        acq_time = time.perf_counter()
        wait_ms = (acq_time - req_time) * 1000.0

        if acquired:
            self.is_held = True
            self.owner_pid = process_pid
            self.owner_name = process_name
            self.acquire_timestamp = acq_time

            event_logger.log(
                ipc_type="SYNC",
                severity="SUCCESS",
                message=(
                    f"Lock '{self.name}' acquired by '{process_name}' "
                    f"after {wait_ms:.2f} ms"
                ),
                process_name=process_name,
                process_pid=process_pid,
            )

            return True

        event_logger.log(
            ipc_type="SYNC",
            severity="WARNING",
            message=(
                f"Lock '{self.name}' acquisition timed out for "
                f"'{process_name}' after {wait_ms:.2f} ms"
            ),
            process_name=process_name,
            process_pid=process_pid,
        )

        return False

    def release(
        self,
        process_name: str,
        process_pid: Optional[int] = None,
    ) -> None:
        """Release the lock and record its holding duration."""

        if not self.is_held:
            logger.warning(
                "Attempted to release lock '%s' when it was not tracked as held.",
                self.name,
            )
            return

        # Do not release a lock on behalf of another tracked process.
        if (
            self.owner_pid is not None
            and process_pid is not None
            and self.owner_pid != process_pid
        ):
            logger.warning(
                "Process '%s' attempted to release lock '%s' owned by PID %s.",
                process_name,
                self.name,
                self.owner_pid,
            )
            return

        now = time.perf_counter()

        hold_ms = (
            (now - self.acquire_timestamp) * 1000.0
            if self.acquire_timestamp is not None
            else 0.0
        )

        try:
            self._lock.release()
        except (ValueError, RuntimeError) as exc:
            logger.error("Failed to release lock '%s': %s", self.name, exc)
            return

        self.is_held = False
        self.owner_pid = None
        self.owner_name = None
        self.acquire_timestamp = None

        event_logger.log(
            ipc_type="SYNC",
            severity="INFO",
            message=(
                f"Lock '{self.name}' released by '{process_name}' "
                f"(Held for {hold_ms:.2f} ms)"
            ),
            process_name=process_name,
            process_pid=process_pid,
        )

    def get_state(self) -> Dict[str, Any]:
        """Return the current tracked lock state."""

        return {
            "lock_name": self.name,
            "is_held": self.is_held,
            "owner_name": self.owner_name,
            "owner_pid": self.owner_pid,
            "held_duration_sec": (
                round(time.perf_counter() - self.acquire_timestamp, 2)
                if self.is_held and self.acquire_timestamp is not None
                else 0.0
            ),
        }
