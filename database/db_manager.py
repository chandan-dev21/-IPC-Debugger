"""
Database Manager for IPC Debugger
Stores and retrieves event logs, message delivery metrics, and deadlock events using SQLite.
"""

import json
import os
import sqlite3
import time
from typing import Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ipc_debugger.db")


class DatabaseManager:
    """Thread-safe SQLite database manager for IPC monitoring and analytics."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection with autocommit or immediate isolation."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize required database tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Event logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    iso_time TEXT NOT NULL,
                    ipc_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    process_name TEXT,
                    process_pid INTEGER,
                    message TEXT NOT NULL,
                    details_json TEXT
                )
            """)

            # Messages transmitted table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    iso_time TEXT NOT NULL,
                    ipc_type TEXT NOT NULL,
                    sender_name TEXT,
                    sender_pid INTEGER,
                    receiver_name TEXT,
                    receiver_pid INTEGER,
                    payload_preview TEXT,
                    payload_size_bytes INTEGER,
                    sent_timestamp REAL,
                    recv_timestamp REAL,
                    latency_ms REAL,
                    status TEXT NOT NULL
                )
            """)

            # Deadlock and synchronization incidents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deadlock_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    iso_time TEXT NOT NULL,
                    scenario_type TEXT NOT NULL,
                    proc1_name TEXT,
                    proc1_pid INTEGER,
                    proc2_name TEXT,
                    proc2_pid INTEGER,
                    lock1_name TEXT,
                    lock2_name TEXT,
                    status TEXT NOT NULL,
                    details TEXT
                )
            """)

            conn.commit()

    def log_event(
        self,
        ipc_type: str,
        severity: str,
        message: str,
        process_name: str | None = None,
        process_pid: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        """Log a debugging/system event to the database."""
        now = time.time()
        iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        details_str = json.dumps(details) if details else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (timestamp, iso_time, ipc_type, severity, process_name, process_pid, message, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now, iso, ipc_type, severity, process_name, process_pid, message, details_str),
            )
            conn.commit()
            return cursor.lastrowid

    def log_message(
        self,
        ipc_type: str,
        sender_name: str,
        sender_pid: int | None,
        receiver_name: str,
        receiver_pid: int | None,
        payload_preview: str,
        payload_size_bytes: int,
        sent_timestamp: float,
        recv_timestamp: float | None = None,
        status: str = "DELIVERED",
    ) -> int:
        """Log a message transfer between processes with latency calculation."""
        now = time.time()
        iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        latency_ms = None
        if sent_timestamp and recv_timestamp and recv_timestamp >= sent_timestamp:
            latency_ms = round((recv_timestamp - sent_timestamp) * 1000.0, 3)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO messages (
                    timestamp, iso_time, ipc_type, sender_name, sender_pid,
                    receiver_name, receiver_pid, payload_preview, payload_size_bytes,
                    sent_timestamp, recv_timestamp, latency_ms, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    iso,
                    ipc_type,
                    sender_name,
                    sender_pid,
                    receiver_name,
                    receiver_pid,
                    str(payload_preview)[:255],
                    payload_size_bytes,
                    sent_timestamp,
                    recv_timestamp,
                    latency_ms,
                    status,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def log_deadlock_incident(
        self,
        scenario_type: str,
        proc1_name: str,
        proc1_pid: int | None,
        proc2_name: str,
        proc2_pid: int | None,
        lock1_name: str,
        lock2_name: str,
        status: str,
        details: str = "",
    ) -> int:
        """Log a deadlock or race-condition incident."""
        now = time.time()
        iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO deadlock_incidents (
                    timestamp, iso_time, scenario_type, proc1_name, proc1_pid,
                    proc2_name, proc2_pid, lock1_name, lock2_name, status, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    iso,
                    scenario_type,
                    proc1_name,
                    proc1_pid,
                    proc2_name,
                    proc2_pid,
                    lock1_name,
                    lock2_name,
                    status,
                    details,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_recent_events(self, limit: int = 100, ipc_type: str | None = None) -> list[dict[str, Any]]:
        """Fetch the most recent events."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if ipc_type and ipc_type != "ALL":
                cursor.execute(
                    """
                    SELECT * FROM events WHERE ipc_type = ? ORDER BY id DESC LIMIT ?
                    """,
                    (ipc_type, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM events ORDER BY id DESC LIMIT ?
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_recent_messages(self, limit: int = 100, ipc_type: str | None = None) -> list[dict[str, Any]]:
        """Fetch recent message transmissions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if ipc_type and ipc_type != "ALL":
                cursor.execute(
                    """
                    SELECT * FROM messages WHERE ipc_type = ? ORDER BY id DESC LIMIT ?
                    """,
                    (ipc_type, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM messages ORDER BY id DESC LIMIT ?
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_metrics_summary(self) -> dict[str, Any]:
        """Compute aggregate metrics across all IPC transmissions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) AS total_msgs FROM messages")
            total_msgs = cursor.fetchone()["total_msgs"]

            cursor.execute("SELECT COUNT(*) AS delivered FROM messages WHERE status = 'DELIVERED'")
            delivered = cursor.fetchone()["delivered"]

            cursor.execute("SELECT COUNT(*) AS timeouts FROM messages WHERE status = 'TIMEOUT'")
            timeouts = cursor.fetchone()["timeouts"]

            cursor.execute("SELECT AVG(latency_ms) AS avg_lat, MIN(latency_ms) AS min_lat, MAX(latency_ms) AS max_lat FROM messages WHERE latency_ms IS NOT NULL")
            lat_row = cursor.fetchone()

            cursor.execute("SELECT ipc_type, COUNT(*) AS count, AVG(latency_ms) AS avg_lat FROM messages GROUP BY ipc_type")
            by_ipc = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT COUNT(*) AS total_deadlocks FROM deadlock_incidents WHERE status = 'DETECTED'")
            deadlocks = cursor.fetchone()["total_deadlocks"]

            return {
                "total_messages": total_msgs,
                "delivered": delivered,
                "timeouts": timeouts,
                "avg_latency_ms": round(lat_row["avg_lat"], 3) if lat_row["avg_lat"] else 0.0,
                "min_latency_ms": round(lat_row["min_lat"], 3) if lat_row["min_lat"] else 0.0,
                "max_latency_ms": round(lat_row["max_lat"], 3) if lat_row["max_lat"] else 0.0,
                "by_ipc": by_ipc,
                "deadlocks_detected": deadlocks,
            }

    def clear_all(self):
        """Clear all historical events and metrics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events")
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM deadlock_incidents")
            conn.commit()


# Singleton instance
db_instance = DatabaseManager()
