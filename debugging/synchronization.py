"""
Synchronization Monitor and Lock Tracker
Tracks lock requests, acquisition latency, holding duration,
and contention between processes.
"""

import logging
import multiprocessing as mp
import queue
import threading
import time
from collections import deque
from typing import Any, Dict, Optional

from debugging.event_logger import event_logger

logger = logging.getLogger("IPC_Synchronization")


class LockTelemetryRecord:
    """Stores one synchronization event."""

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
    Monitors a multiprocessing lock.

    A shared telemetry queue can transfer events from different
    processes to a central monitoring process.

    Note: ownership state is maintained locally in each wrapper.
    """

    def __init__(
        self,
        name: str,
        lock: Optional[Any] = None,
        telemetry_queue: Optional[Any] = None,
        max_history: int = 500,
    ):
        self.name = name
        self._lock = lock if lock is not None else mp.Lock()
        self.telemetry_queue = telemetry_queue

        self._state_lock = threading.Lock()
        self._history = deque(maxlen=max_history)

        self.owner_pid: Optional[int] = None
        self.owner_name: Optional[str] = None
        self.acquire_timestamp: Optional[float] = None
        self.is_held = False

    def _record_event(
        self,
        action: str,
        process_name: str,
        process_pid: Optional[int],
        wait_time_ms: float = 0.0,
        hold_time_ms: float = 0.0,
        severity: str = "INFO",
    ) -> Dict[str, Any]:

        record = LockTelemetryRecord(
            lock_name=self.name,
            process_name=process_name,
            process_pid=process_pid,
            action=action,
            timestamp=time.time(),
            wait_time_ms=wait_time_ms,
            hold_time_ms=hold_time_ms,
        ).to_dict()

        with self._state_lock:
            self._history.append(record)

        # Send telemetry to the central process if configured.
        if self.telemetry_queue is not None:
            try:
                self.telemetry_queue.put_nowait(record)
            except (queue.Full, OSError, ValueError) as exc:
                logger.warning("Telemetry queue unavailable: %s", exc)

        event_logger.log(
            ipc_type="SYNC",
            severity=severity,
            message=(
                f"{action}: lock '{self.name}' "
                f"by process '{process_name}'"
            ),
            process_name=process_name,
            process_pid=process_pid,
            details=record,
        )

        return record

    def acquire(
        self,
        process_name: str,
        process_pid: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> bool:
        """Acquire the lock and measure waiting time."""

        if timeout is not None and timeout < 0:
            raise ValueError("Timeout cannot be negative.")

        pid = process_pid if process_pid is not None else mp.current_process().pid
        start = time.perf_counter()

        self._record_event(
            action="LOCK_REQUESTED",
            process_name=process_name,
            process_pid=pid,
        )

        if timeout is None:
            acquired = self._lock.acquire()
        else:
            acquired = self._lock.acquire(timeout=timeout)

        wait_ms = (time.perf_counter() - start) * 1000.0

        if acquired:
            with self._state_lock:
                self.is_held = True
                self.owner_pid = pid
                self.owner_name = process_name
                self.acquire_timestamp = time.perf_counter()

            self._record_event(
                action="LOCK_ACQUIRED",
                process_name=process_name,
                process_pid=pid,
                wait_time_ms=wait_ms,
                severity="SUCCESS",
            )

            return True

        self._record_event(
            action="LOCK_TIMEOUT",
            process_name=process_name,
            process_pid=pid,
            wait_time_ms=wait_ms,
            severity="WARNING",
        )

        return False

    def release(
        self,
        process_name: str,
        process_pid: Optional[int] = None,
    ) -> None:
        """Release the lock and record holding duration."""

        pid = process_pid if process_pid is not None else mp.current_process().pid

        with self._state_lock:
            if not self.is_held:
                logger.warning(
                    "Lock '%s' is not tracked as held by this wrapper.",
                    self.name,
                )
                return

            if self.owner_pid is not None and self.owner_pid != pid:
                logger.warning(
                    "Process '%s' cannot release lock '%s' tracked for PID %s.",
                    process_name,
                    self.name,
                    self.owner_pid,
                )
                return

            hold_ms = (
                (time.perf_counter() - self.acquire_timestamp) * 1000.0
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

        self._record_event(
            action="LOCK_RELEASED",
            process_name=process_name,
            process_pid=pid,
            hold_time_ms=hold_ms,
        )

    def get_state(self) -> Dict[str, Any]:
        """Return this wrapper's locally tracked lock state."""

        with self._state_lock:
            held = self.is_held
            acquired_at = self.acquire_timestamp

            return {
                "lock_name": self.name,
                "is_held": held,
                "owner_name": self.owner_name,
                "owner_pid": self.owner_pid,
                "held_duration_sec": (
                    round(time.perf_counter() - acquired_at, 2)
                    if held and acquired_at is not None
                    else 0.0
                ),
            }

    def get_history(self, count: Optional[int] = None) -> list:
        """Return recent telemetry records."""

        with self._state_lock:
            records = list(self._history)

        if count is not None:
            if count < 0:
                raise ValueError("Count cannot be negative.")
            records = records[-count:] if count else []

        return list(reversed(records))
