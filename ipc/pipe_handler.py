"""
Pipe Communication Handler
Implements inter-process communication using multiprocessing.Pipe.
Demonstrates process-to-process message transfer, latency tracking, timeouts, and delivery status.
"""

import os
import time
import uuid
import logging
from typing import Dict, Any, Optional, Tuple
import multiprocessing as mp
from multiprocessing.connection import Connection

from debugging.event_logger import event_logger
from database.db_manager import db_instance

logger = logging.getLogger("IPC_PipeHandler")


def pipe_worker_a(
    conn: Connection,
    cmd_queue: mp.Queue,
    telemetry_queue: mp.Queue,
    stop_event: mp.Event,
):
    """
    Worker Process A: Can send messages through pipe and receive responses.
    Runs at module-level for Windows spawn compatibility.
    """
    pid = os.getpid()
    telemetry_queue.put({
        "type": "STATUS",
        "process_name": "Process_A",
        "pid": pid,
        "status": "STARTED",
        "timestamp": time.time(),
    })

    while not stop_event.is_set():
        try:
            # Check for commands to send across the pipe
            if not cmd_queue.empty():
                cmd = cmd_queue.get_nowait()
                action = cmd.get("action")

                if action == "SEND":
                    payload = cmd.get("payload", "")
                    delay = cmd.get("delay", 0.0)
                    if delay > 0:
                        time.sleep(delay)

                    msg_packet = {
                        "msg_id": str(uuid.uuid4())[:8],
                        "sender": "Process_A",
                        "sender_pid": pid,
                        "receiver": "Process_B",
                        "payload": payload,
                        "sent_timestamp": time.time(),
                    }

                    conn.send(msg_packet)
                    telemetry_queue.put({
                        "type": "MSG_SENT",
                        "process_name": "Process_A",
                        "pid": pid,
                        "data": msg_packet,
                        "timestamp": msg_packet["sent_timestamp"],
                    })

                elif action == "STOP":
                    break

            # Check if messages arrived from Process B
            if conn.poll(0.05):
                incoming = conn.recv()
                recv_time = time.time()
                latency_ms = (recv_time - incoming.get("sent_timestamp", recv_time)) * 1000.0
                telemetry_queue.put({
                    "type": "MSG_RECEIVED",
                    "process_name": "Process_A",
                    "pid": pid,
                    "data": incoming,
                    "recv_timestamp": recv_time,
                    "latency_ms": latency_ms,
                })

            time.sleep(0.02)
        except Exception as e:
            telemetry_queue.put({
                "type": "ERROR",
                "process_name": "Process_A",
                "pid": pid,
                "error": str(e),
                "timestamp": time.time(),
            })
            break

    try:
        conn.close()
    except Exception:
        pass

    telemetry_queue.put({
        "type": "STATUS",
        "process_name": "Process_A",
        "pid": pid,
        "status": "STOPPED",
        "timestamp": time.time(),
    })


def pipe_worker_b(
    conn: Connection,
    cmd_queue: mp.Queue,
    telemetry_queue: mp.Queue,
    stop_event: mp.Event,
):
    """
    Worker Process B: Listens on pipe, receives messages, and can send reply/echo.
    Runs at module-level for Windows spawn compatibility.
    """
    pid = os.getpid()
    telemetry_queue.put({
        "type": "STATUS",
        "process_name": "Process_B",
        "pid": pid,
        "status": "STARTED",
        "timestamp": time.time(),
    })

    while not stop_event.is_set():
        try:
            # Check for commands to send across the pipe
            if not cmd_queue.empty():
                cmd = cmd_queue.get_nowait()
                action = cmd.get("action")

                if action == "SEND":
                    payload = cmd.get("payload", "")
                    delay = cmd.get("delay", 0.0)
                    if delay > 0:
                        time.sleep(delay)

                    msg_packet = {
                        "msg_id": str(uuid.uuid4())[:8],
                        "sender": "Process_B",
                        "sender_pid": pid,
                        "receiver": "Process_A",
                        "payload": payload,
                        "sent_timestamp": time.time(),
                    }

                    conn.send(msg_packet)
                    telemetry_queue.put({
                        "type": "MSG_SENT",
                        "process_name": "Process_B",
                        "pid": pid,
                        "data": msg_packet,
                        "timestamp": msg_packet["sent_timestamp"],
                    })

                elif action == "STOP":
                    break

            # Poll for incoming message
            if conn.poll(0.05):
                incoming = conn.recv()
                recv_time = time.time()
                latency_ms = (recv_time - incoming.get("sent_timestamp", recv_time)) * 1000.0
                telemetry_queue.put({
                    "type": "MSG_RECEIVED",
                    "process_name": "Process_B",
                    "pid": pid,
                    "data": incoming,
                    "recv_timestamp": recv_time,
                    "latency_ms": latency_ms,
                })

            time.sleep(0.02)
        except Exception as e:
            telemetry_queue.put({
                "type": "ERROR",
                "process_name": "Process_B",
                "pid": pid,
                "error": str(e),
                "timestamp": time.time(),
            })
            break

    try:
        conn.close()
    except Exception:
        pass

    telemetry_queue.put({
        "type": "STATUS",
        "process_name": "Process_B",
        "pid": pid,
        "status": "STOPPED",
        "timestamp": time.time(),
    })


class PipeSession:
    """
    Manages an active two-process duplex Pipe communication session.
    Provides lifecycle controls, message transmission, and telemetry collection.
    """

    def __init__(self):
        self.conn_a: Optional[Connection] = None
        self.conn_b: Optional[Connection] = None
        self.proc_a: Optional[mp.Process] = None
        self.proc_b: Optional[mp.Process] = None
        self.cmd_queue_a: Optional[mp.Queue] = None
        self.cmd_queue_b: Optional[mp.Queue] = None
        self.telemetry_queue: Optional[mp.Queue] = None
        self.stop_event: Optional[mp.Event] = None
        self.is_running: bool = False
        self.received_messages = []

    def start(self) -> Tuple[bool, str]:
        """Start Process A and Process B connected via duplex Pipe."""
        if self.is_running:
            return False, "Pipe session is already running."

        try:
            self.conn_a, self.conn_b = mp.Pipe(duplex=True)
            self.cmd_queue_a = mp.Queue()
            self.cmd_queue_b = mp.Queue()
            self.telemetry_queue = mp.Queue()
            self.stop_event = mp.Event()

            self.proc_a = mp.Process(
                target=pipe_worker_a,
                args=(self.conn_a, self.cmd_queue_a, self.telemetry_queue, self.stop_event),
                name="Pipe_Process_A",
            )
            self.proc_b = mp.Process(
                target=pipe_worker_b,
                args=(self.conn_b, self.cmd_queue_b, self.telemetry_queue, self.stop_event),
                name="Pipe_Process_B",
            )

            self.proc_a.start()
            self.proc_b.start()
            self.is_running = True

            event_logger.log(
                ipc_type="PIPE",
                severity="SUCCESS",
                message=f"Pipe session started: Process A (PID {self.proc_a.pid}), Process B (PID {self.proc_b.pid})",
                process_name="PipeManager",
            )
            return True, "Pipe session started successfully."
        except Exception as e:
            self.is_running = False
            event_logger.log(
                ipc_type="PIPE",
                severity="ERROR",
                message=f"Failed to start pipe session: {e}",
                process_name="PipeManager",
            )
            return False, str(e)

    def send_message(self, sender: str, payload: str, delay: float = 0.0) -> bool:
        """Send a message from either Process A or Process B."""
        if not self.is_running:
            return False

        cmd = {"action": "SEND", "payload": payload, "delay": delay}
        if sender.upper() in ["A", "PROCESS_A", "PROCESS A"]:
            if self.cmd_queue_a:
                self.cmd_queue_a.put(cmd)
                return True
        else:
            if self.cmd_queue_b:
                self.cmd_queue_b.put(cmd)
                return True
        return False

    def poll_telemetry(self) -> list:
        """Fetch all queued telemetry events and update DB/logger."""
        events = []
        if not self.telemetry_queue:
            return events

        while not self.telemetry_queue.empty():
            try:
                item = self.telemetry_queue.get_nowait()
                events.append(item)

                item_type = item.get("type")
                if item_type == "MSG_SENT":
                    data = item["data"]
                    event_logger.log(
                        ipc_type="PIPE",
                        severity="INFO",
                        message=f"Sent: '{data['payload']}' (ID: {data['msg_id']})",
                        process_name=data["sender"],
                        process_pid=data["sender_pid"],
                    )
                elif item_type == "MSG_RECEIVED":
                    data = item["data"]
                    self.received_messages.append({
                        "msg_id": data["msg_id"],
                        "sender": data["sender"],
                        "receiver": item["process_name"],
                        "payload": data["payload"],
                        "latency_ms": item["latency_ms"],
                        "timestamp": item["recv_timestamp"],
                    })
                    event_logger.log(
                        ipc_type="PIPE",
                        severity="SUCCESS",
                        message=f"Received: '{data['payload']}' in {item['latency_ms']:.2f} ms",
                        process_name=item["process_name"],
                        process_pid=item["pid"],
                    )
                    # Persist message to DB
                    db_instance.log_message(
                        ipc_type="PIPE",
                        sender_name=data["sender"],
                        sender_pid=data.get("sender_pid"),
                        receiver_name=item["process_name"],
                        receiver_pid=item["pid"],
                        payload_preview=data["payload"],
                        payload_size_bytes=len(str(data["payload"]).encode("utf-8")),
                        sent_timestamp=data["sent_timestamp"],
                        recv_timestamp=item["recv_timestamp"],
                        status="DELIVERED",
                    )
                elif item_type == "ERROR":
                    event_logger.log(
                        ipc_type="PIPE",
                        severity="ERROR",
                        message=item["error"],
                        process_name=item["process_name"],
                        process_pid=item["pid"],
                    )
            except Exception:
                break
        return events

    def get_process_status(self) -> Dict[str, Any]:
        """Return current status of both pipe processes."""
        a_alive = self.proc_a.is_alive() if self.proc_a else False
        b_alive = self.proc_b.is_alive() if self.proc_b else False
        return {
            "is_running": self.is_running and (a_alive or b_alive),
            "proc_a": {
                "name": "Process_A",
                "pid": self.proc_a.pid if self.proc_a else None,
                "alive": a_alive,
            },
            "proc_b": {
                "name": "Process_B",
                "pid": self.proc_b.pid if self.proc_b else None,
                "alive": b_alive,
            },
        }

    def stop(self):
        """Cleanly stop both processes and release connection handles."""
        if not self.is_running:
            return

        if self.stop_event:
            self.stop_event.set()

        for proc in [self.proc_a, self.proc_b]:
            if proc and proc.is_alive():
                proc.join(timeout=1.0)
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=0.5)

        for conn in [self.conn_a, self.conn_b]:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        self.is_running = False
        event_logger.log(
            ipc_type="PIPE",
            severity="INFO",
            message="Pipe session stopped and connections closed.",
            process_name="PipeManager",
        )
