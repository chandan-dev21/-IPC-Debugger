"""
Process Manager and Monitoring Utilities
Provides real-time inspection, lifecycle management, and cleanup for child processes.
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List
import multiprocessing as mp

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("IPC_ProcessManager")


class ProcessInfo:
    """Snapshot of process metrics and status."""

    def __init__(
        self,
        name: str,
        pid: Optional[int],
        is_alive: bool,
        status: str = "UNKNOWN",
        cpu_percent: float = 0.0,
        memory_mb: float = 0.0,
        num_threads: int = 1,
        create_time: float = 0.0,
    ):
        self.name = name
        self.pid = pid
        self.is_alive = is_alive
        self.status = status
        self.cpu_percent = cpu_percent
        self.memory_mb = memory_mb
        self.num_threads = num_threads
        self.create_time = create_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "pid": self.pid,
            "is_alive": self.is_alive,
            "status": self.status,
            "cpu_percent": self.cpu_percent,
            "memory_mb": round(self.memory_mb, 2),
            "num_threads": self.num_threads,
            "create_time": self.create_time,
        }


class ProcessManager:
    """Manages active multiprocessing.Process instances and monitors their OS-level state."""

    def __init__(self):
        self._processes: Dict[str, mp.Process] = {}

    def register(self, name: str, process: mp.Process):
        """Register a spawned process for lifecycle management."""
        self._processes[name] = process

    def get_process(self, name: str) -> Optional[mp.Process]:
        return self._processes.get(name)

    def get_info(self, name: str) -> ProcessInfo:
        """Inspect actual OS-level metrics for a registered process."""
        proc = self._processes.get(name)
        if proc is None:
            return ProcessInfo(name=name, pid=None, is_alive=False, status="NOT_CREATED")

        pid = proc.pid
        alive = proc.is_alive()

        if not alive:
            exitcode = proc.exitcode
            status_str = f"TERMINATED (code {exitcode})" if exitcode is not None else "STOPPED"
            return ProcessInfo(name=name, pid=pid, is_alive=False, status=status_str)

        # Query OS metrics via psutil if available
        cpu_pct = 0.0
        mem_mb = 0.0
        threads = 1
        ps_status = "RUNNING"
        ctime = 0.0

        if psutil and pid:
            try:
                p = psutil.Process(pid)
                ps_status = p.status().upper()
                # Non-blocking cpu percent
                cpu_pct = p.cpu_percent(interval=None)
                mem_info = p.memory_info()
                mem_mb = mem_info.rss / (1024 * 1024)
                threads = p.num_threads()
                ctime = p.create_time()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                ps_status = "STALE"
                alive = False

        return ProcessInfo(
            name=name,
            pid=pid,
            is_alive=alive,
            status=ps_status,
            cpu_percent=cpu_pct,
            memory_mb=mem_mb,
            num_threads=threads,
            create_time=ctime,
        )

    def terminate_process(self, name: str, timeout: float = 2.0) -> bool:
        """Safely terminate a process, escalating to kill if it does not exit within timeout."""
        proc = self._processes.get(name)
        if proc is None or not proc.is_alive():
            return True

        try:
            proc.terminate()
            proc.join(timeout=timeout)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1.0)
            return not proc.is_alive()
        except Exception as e:
            logger.error(f"Error terminating process {name}: {e}")
            return False

    def terminate_all(self):
        """Terminate all registered processes to ensure no orphans remain."""
        for name in list(self._processes.keys()):
            self.terminate_process(name)
        self._processes.clear()

    def get_all_info(self) -> List[Dict[str, Any]]:
        """Return status dictionaries for all registered processes."""
        return [self.get_info(name).to_dict() for name in self._processes]
