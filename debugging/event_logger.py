"""
Event Logger for IPC Debugging
Maintains real-time event logs in memory and persists them to SQLite via DatabaseManager.
"""

import time
import logging
from collections import deque
from typing import List, Dict, Any, Optional
from database.db_manager import db_instance

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("IPC_Debugger")


class EventLogger:
    """Thread-safe event logger maintaining a rolling in-memory buffer and database persistence."""

    def __init__(self, max_buffer_size: int = 500):
        self.buffer = deque(maxlen=max_buffer_size)

    def log(
        self,
        ipc_type: str,
        severity: str,
        message: str,
        process_name: Optional[str] = None,
        process_pid: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an event to both the in-memory rolling buffer and database."""
        now = time.time()
        iso = time.strftime("%H:%M:%S", time.localtime(now)) + f".{int((now % 1) * 1000):03d}"

        event_record = {
            "timestamp": now,
            "time_str": iso,
            "ipc_type": ipc_type.upper(),
            "severity": severity.upper(),  # INFO, WARNING, ERROR, SUCCESS
            "process_name": process_name or "SYSTEM",
            "process_pid": process_pid,
            "message": message,
            "details": details or {},
        }

        self.buffer.append(event_record)

        # Standard console output
        log_msg = f"[{event_record['ipc_type']}] [{event_record['severity']}] {event_record['process_name']}({event_record['process_pid']}): {message}"
        if severity.upper() == "ERROR":
            logger.error(log_msg)
        elif severity.upper() == "WARNING":
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        # Persist to database
        try:
            db_instance.log_event(
                ipc_type=ipc_type,
                severity=severity,
                message=message,
                process_name=process_name,
                process_pid=process_pid,
                details=details,
            )
        except Exception as e:
            logger.error(f"Failed to persist event to DB: {e}")

        return event_record

    def get_recent(self, count: int = 50, filter_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve recent events from in-memory buffer."""
        events = list(self.buffer)
        if filter_type and filter_type != "ALL":
            events = [e for e in events if e["ipc_type"] == filter_type.upper()]
        return list(reversed(events[-count:]))

    def clear(self):
        """Clear the in-memory event buffer."""
        self.buffer.clear()


# Global singleton logger instance
event_logger = EventLogger()
