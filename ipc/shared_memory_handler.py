"""
Shared Memory Communication Handler
Implements inter-process communication using multiprocessing.shared_memory.SharedMemory.
Demonstrates synchronized read/write with multiprocessing.Lock vs unsynchronized race conditions.
"""

import os
import time
import struct
import logging
from typing import Dict, Any, Optional, Tuple
import multiprocessing as mp
from multiprocessing import shared_memory

from debugging.event_logger import event_logger
from database.db_manager import db_instance

logger = logging.getLogger("IPC_SharedMemoryHandler")

# Header Format: Magic (4s), Sequence (I), Timestamp (d), Length (I) -> 4 + 4 + 8 + 4 = 20 bytes
HEADER_FORMAT = ">4sIdI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAGIC_BYTES = b"IPCS"
SHM_BUFFER_SIZE = 4096


def shm_writer_worker(
    shm_name: str,
    lock: Optional[mp.Lock],
    cmd_queue: mp.Queue,
    telemetry_queue: mp.Queue,
    stop_event: mp.Event,
    synchronized: bool,
):
    """
    Writer Process: Writes structured data into the named shared memory block.
    Runs at module-level for Windows spawn compatibility.
    """
    pid = os.getpid()
    telemetry_queue.put({
        "type": "STATUS",
        "process_name": "SHM_Writer",
        "pid": pid,
        "status": "STARTED",
        "timestamp": time.time(),
    })

    try:
        shm = shared_memory.SharedMemory(name=shm_name)
    except Exception as e:
        telemetry_queue.put({
            "type": "ERROR",
            "process_name": "SHM_Writer",
            "pid": pid,
            "error": f"Failed to attach shared memory: {e}",
            "timestamp": time.time(),
        })
        return

    seq = 0

    while not stop_event.is_set():
        try:
            if not cmd_queue.empty():
                cmd = cmd_queue.get_nowait()
                action = cmd.get("action")

                if action == "WRITE":
                    payload = str(cmd.get("payload", ""))
                    seq += 1
                    data_bytes = payload.encode("utf-8")
                    data_len = len(data_bytes)

                    if data_len > (SHM_BUFFER_SIZE - HEADER_SIZE):
                        data_bytes = data_bytes[: (SHM_BUFFER_SIZE - HEADER_SIZE)]
                        data_len = len(data_bytes)

                    now = time.time()
                    header = struct.pack(HEADER_FORMAT, MAGIC_BYTES, seq, now, data_len)

                    if synchronized and lock:
                        lock_wait_start = time.time()
                        lock.acquire()
                        lock_acquire_time = time.time()
                        lock_wait_ms = (lock_acquire_time - lock_wait_start) * 1000.0

                        telemetry_queue.put({
                            "type": "LOCK_ACQUIRED",
                            "process_name": "SHM_Writer",
                            "pid": pid,
                            "lock_wait_ms": lock_wait_ms,
                            "timestamp": lock_acquire_time,
                        })

                        try:
                            # Write header followed by payload
                            shm.buf[:HEADER_SIZE] = header
                            shm.buf[HEADER_SIZE : HEADER_SIZE + data_len] = data_bytes

                            # Optional write delay
                            write_delay = cmd.get("delay", 0.0)
                            if write_delay > 0:
                                time.sleep(write_delay)
                        finally:
                            lock.release()
                            telemetry_queue.put({
                                "type": "LOCK_RELEASED",
                                "process_name": "SHM_Writer",
                                "pid": pid,
                                "timestamp": time.time(),
                            })
                    else:
                        # UNSYNCHRONIZED MODE: Simulate torn write / race condition
                        # Write partially, sleep, then write rest
                        half = data_len // 2
                        shm.buf[:HEADER_SIZE] = header
                        shm.buf[HEADER_SIZE : HEADER_SIZE + half] = data_bytes[:half]
                        time.sleep(0.05)  # Window for reader to read torn/corrupted state!
                        shm.buf[HEADER_SIZE + half : HEADER_SIZE + data_len] = data_bytes[half:]

                    telemetry_queue.put({
                        "type": "SHM_WRITTEN",
                        "process_name": "SHM_Writer",
                        "pid": pid,
                        "seq": seq,
                        "payload": payload,
                        "size_bytes": data_len,
                        "timestamp": now,
                        "synchronized": synchronized,
                    })

                elif action == "STOP":
                    break

            time.sleep(0.02)
        except Exception as e:
            telemetry_queue.put({
                "type": "ERROR",
                "process_name": "SHM_Writer",
                "pid": pid,
                "error": str(e),
                "timestamp": time.time(),
            })
            break

    try:
        shm.close()
    except Exception:
        pass

    telemetry_queue.put({
        "type": "STATUS",
        "process_name": "SHM_Writer",
        "pid": pid,
        "status": "STOPPED",
        "timestamp": time.time(),
    })


def shm_reader_worker(
    shm_name: str,
    lock: Optional[mp.Lock],
    cmd_queue: mp.Queue,
    telemetry_queue: mp.Queue,
    stop_event: mp.Event,
    synchronized: bool,
):
    """
    Reader Process: Reads structured data from shared memory block.
    Runs at module-level for Windows spawn compatibility.
    """
    pid = os.getpid()
    telemetry_queue.put({
        "type": "STATUS",
        "process_name": "SHM_Reader",
        "pid": pid,
        "status": "STARTED",
        "timestamp": time.time(),
    })

    try:
        shm = shared_memory.SharedMemory(name=shm_name)
    except Exception as e:
        telemetry_queue.put({
            "type": "ERROR",
            "process_name": "SHM_Reader",
            "pid": pid,
            "error": f"Failed to attach shared memory: {e}",
            "timestamp": time.time(),
        })
        return

    last_seen_seq = -1

    while not stop_event.is_set():
        try:
            if not cmd_queue.empty():
                cmd = cmd_queue.get_nowait()
                if cmd.get("action") == "STOP":
                    break

            # Check if there is data
            is_new = False
            raw_header = None
            raw_payload = b""
            read_time = time.time()
            lock_wait_ms = 0.0

            if synchronized and lock:
                lock_wait_start = time.time()
                lock.acquire()
                lock_acquire_time = time.time()
                lock_wait_ms = (lock_acquire_time - lock_wait_start) * 1000.0

                try:
                    raw_header = bytes(shm.buf[:HEADER_SIZE])
                    magic, seq, write_time, data_len = struct.unpack(HEADER_FORMAT, raw_header)
                    if magic == MAGIC_BYTES and seq > last_seen_seq:
                        raw_payload = bytes(shm.buf[HEADER_SIZE : HEADER_SIZE + data_len])
                        last_seen_seq = seq
                        is_new = True
                except Exception:
                    pass
                finally:
                    lock.release()
            else:
                # UNSYNCHRONIZED: Read immediately without lock
                try:
                    raw_header = bytes(shm.buf[:HEADER_SIZE])
                    magic, seq, write_time, data_len = struct.unpack(HEADER_FORMAT, raw_header)
                    if magic == MAGIC_BYTES and seq > last_seen_seq:
                        raw_payload = bytes(shm.buf[HEADER_SIZE : HEADER_SIZE + data_len])
                        last_seen_seq = seq
                        is_new = True
                except Exception:
                    pass

            if is_new:
                recv_time = time.time()
                latency_ms = (recv_time - write_time) * 1000.0
                try:
                    decoded = raw_payload.decode("utf-8")
                    corrupted = False
                except UnicodeDecodeError:
                    decoded = str(raw_payload)
                    corrupted = True

                telemetry_queue.put({
                    "type": "SHM_READ",
                    "process_name": "SHM_Reader",
                    "pid": pid,
                    "seq": seq,
                    "payload": decoded,
                    "write_timestamp": write_time,
                    "read_timestamp": recv_time,
                    "latency_ms": latency_ms,
                    "lock_wait_ms": lock_wait_ms,
                    "synchronized": synchronized,
                    "corrupted": corrupted,
                })

            time.sleep(0.03)
        except Exception as e:
            telemetry_queue.put({
                "type": "ERROR",
                "process_name": "SHM_Reader",
                "pid": pid,
                "error": str(e),
                "timestamp": time.time(),
            })
            break

    try:
        shm.close()
    except Exception:
        pass

    telemetry_queue.put({
        "type": "STATUS",
        "process_name": "SHM_Reader",
        "pid": pid,
        "status": "STOPPED",
        "timestamp": time.time(),
    })


class SharedMemorySession:
    """
    Manages an active Shared Memory session with Reader and Writer processes.
    Demonstrates synchronized vs race-condition modes.
    """

    def __init__(self, size: int = SHM_BUFFER_SIZE, synchronized: bool = True):
        self.size = size
        self.synchronized = synchronized
        self.shm: Optional[shared_memory.SharedMemory] = None
        self.shm_name: Optional[str] = None
        self.lock: Optional[mp.Lock] = None
        self.cmd_queue_writer: Optional[mp.Queue] = None
        self.cmd_queue_reader: Optional[mp.Queue] = None
        self.telemetry_queue: Optional[mp.Queue] = None
        self.stop_event: Optional[mp.Event] = None
        self.proc_writer: Optional[mp.Process] = None
        self.proc_reader: Optional[mp.Process] = None
        self.is_running: bool = False
        self.read_history = []

    def start(self, synchronized: Optional[bool] = None) -> Tuple[bool, str]:
        """Create shared memory block and launch Reader and Writer processes."""
        if self.is_running:
            return False, "Shared memory session already active."

        if synchronized is not None:
            self.synchronized = synchronized

        try:
            # Allocate shared memory with unique name
            self.shm = shared_memory.SharedMemory(create=True, size=self.size)
            self.shm_name = self.shm.name
            # Initialize buffer with zero bytes
            self.shm.buf[:] = b"\x00" * self.size

            self.lock = mp.Lock() if self.synchronized else None
            self.cmd_queue_writer = mp.Queue()
            self.cmd_queue_reader = mp.Queue()
            self.telemetry_queue = mp.Queue()
            self.stop_event = mp.Event()

            self.proc_writer = mp.Process(
                target=shm_writer_worker,
                args=(
                    self.shm_name,
                    self.lock,
                    self.cmd_queue_writer,
                    self.telemetry_queue,
                    self.stop_event,
                    self.synchronized,
                ),
                name="SHM_Writer_Proc",
            )

            self.proc_reader = mp.Process(
                target=shm_reader_worker,
                args=(
                    self.shm_name,
                    self.lock,
                    self.cmd_queue_reader,
                    self.telemetry_queue,
                    self.stop_event,
                    self.synchronized,
                ),
                name="SHM_Reader_Proc",
            )

            self.proc_writer.start()
            self.proc_reader.start()
            self.is_running = True
            self.read_history.clear()

            mode_str = "SYNCHRONIZED (with Lock)" if self.synchronized else "UNSYNCHRONIZED (Race Condition Mode)"
            event_logger.log(
                ipc_type="SHARED_MEM",
                severity="SUCCESS",
                message=f"Shared memory block '{self.shm_name}' ({self.size} bytes) created in {mode_str}. Writer PID: {self.proc_writer.pid}, Reader PID: {self.proc_reader.pid}",
                process_name="SHMManager",
            )
            return True, f"Shared memory session started in {mode_str}."
        except Exception as e:
            self.is_running = False
            self.cleanup()
            event_logger.log(
                ipc_type="SHARED_MEM",
                severity="ERROR",
                message=f"Failed to start shared memory session: {e}",
                process_name="SHMManager",
            )
            return False, str(e)

    def write_data(self, payload: str, delay: float = 0.0) -> bool:
        """Command the writer process to write data into shared memory."""
        if not self.is_running or not self.cmd_queue_writer:
            return False

        self.cmd_queue_writer.put({
            "action": "WRITE",
            "payload": payload,
            "delay": delay,
        })
        return True

    def inspect_raw_buffer(self, max_bytes: int = 128) -> Dict[str, Any]:
        """Directly inspect raw bytes from the shared memory block for GUI visualization."""
        if not self.shm:
            return {"hex": "", "text": "", "header": None}

        try:
            raw = bytes(self.shm.buf[:max_bytes])
            hex_view = " ".join(f"{b:02X}" for b in raw)
            # Replace non-printable characters with dots
            text_view = "".join(chr(b) if 32 <= b <= 126 else "." for b in raw)

            header_info = None
            if len(raw) >= HEADER_SIZE:
                try:
                    magic, seq, ts, length = struct.unpack(HEADER_FORMAT, raw[:HEADER_SIZE])
                    header_info = {
                        "magic": magic.decode("ascii", errors="replace"),
                        "sequence": seq,
                        "timestamp": ts,
                        "data_length": length,
                    }
                except Exception:
                    pass

            return {
                "hex": hex_view,
                "text": text_view,
                "header": header_info,
                "total_size": self.size,
                "shm_name": self.shm_name,
            }
        except Exception as e:
            return {"error": str(e)}

    def poll_telemetry(self) -> list:
        """Harvest events from the telemetry queue."""
        events = []
        if not self.telemetry_queue:
            return events

        while not self.telemetry_queue.empty():
            try:
                item = self.telemetry_queue.get_nowait()
                events.append(item)
                item_type = item.get("type")

                if item_type == "SHM_WRITTEN":
                    event_logger.log(
                        ipc_type="SHARED_MEM",
                        severity="INFO",
                        message=f"Written #{item['seq']}: '{item['payload']}' ({item['size_bytes']} bytes, synched={item['synchronized']})",
                        process_name=item["process_name"],
                        process_pid=item["pid"],
                    )
                elif item_type == "SHM_READ":
                    self.read_history.append(item)
                    severity = "WARNING" if item.get("corrupted") else "SUCCESS"
                    msg = f"Read #{item['seq']}: '{item['payload']}' in {item['latency_ms']:.2f} ms"
                    if item.get("corrupted"):
                        msg += " [DATA CORRUPTION DETECTED!]"

                    event_logger.log(
                        ipc_type="SHARED_MEM",
                        severity=severity,
                        message=msg,
                        process_name=item["process_name"],
                        process_pid=item["pid"],
                    )
                    # Persist message to DB
                    db_instance.log_message(
                        ipc_type="SHARED_MEM",
                        sender_name="SHM_Writer",
                        sender_pid=None,
                        receiver_name="SHM_Reader",
                        receiver_pid=item["pid"],
                        payload_preview=item["payload"],
                        payload_size_bytes=len(str(item["payload"]).encode("utf-8")),
                        sent_timestamp=item["write_timestamp"],
                        recv_timestamp=item["read_timestamp"],
                        status="DELIVERED" if not item.get("corrupted") else "CORRUPTED",
                    )
                elif item_type == "LOCK_ACQUIRED":
                    event_logger.log(
                        ipc_type="SHARED_MEM",
                        severity="INFO",
                        message=f"Lock acquired after {item['lock_wait_ms']:.2f} ms wait",
                        process_name=item["process_name"],
                        process_pid=item["pid"],
                    )
                elif item_type == "LOCK_RELEASED":
                    event_logger.log(
                        ipc_type="SHARED_MEM",
                        severity="INFO",
                        message="Lock released",
                        process_name=item["process_name"],
                        process_pid=item["pid"],
                    )
                elif item_type == "ERROR":
                    event_logger.log(
                        ipc_type="SHARED_MEM",
                        severity="ERROR",
                        message=item["error"],
                        process_name=item["process_name"],
                        process_pid=item["pid"],
                    )
            except Exception:
                break
        return events

    def get_process_status(self) -> Dict[str, Any]:
        """Return reader and writer process status."""
        w_alive = self.proc_writer.is_alive() if self.proc_writer else False
        r_alive = self.proc_reader.is_alive() if self.proc_reader else False
        return {
            "is_running": self.is_running and (w_alive or r_alive),
            "shm_name": self.shm_name,
            "synchronized": self.synchronized,
            "writer": {
                "name": "SHM_Writer",
                "pid": self.proc_writer.pid if self.proc_writer else None,
                "alive": w_alive,
            },
            "reader": {
                "name": "SHM_Reader",
                "pid": self.proc_reader.pid if self.proc_reader else None,
                "alive": r_alive,
            },
        }

    def cleanup(self):
        """Close handles and unlink shared memory block."""
        if self.shm:
            try:
                self.shm.close()
            except Exception:
                pass
            try:
                self.shm.unlink()
            except Exception:
                pass
            self.shm = None
            self.shm_name = None

    def stop(self):
        """Cleanly stop processes and release shared memory block."""
        if not self.is_running:
            return

        if self.stop_event:
            self.stop_event.set()

        for proc in [self.proc_writer, self.proc_reader]:
            if proc and proc.is_alive():
                proc.join(timeout=1.0)
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=0.5)

        self.cleanup()
        self.is_running = False
        event_logger.log(
            ipc_type="SHARED_MEM",
            severity="INFO",
            message="Shared memory session stopped and memory block unlinked.",
            process_name="SHMManager",
        )
