"""
Message Queue Communication Handler
Implements inter-process communication using multiprocessing.Queue.
Demonstrates producer-consumer architecture, queue backlog, empty timeouts, and backpressure.
"""

import os
import time
import uuid
import queue
import logging
from typing import Dict, Any, Optional, Tuple
import multiprocessing as mp

from debugging.event_logger import event_logger
from database.db_manager import db_instance

logger = logging.getLogger("IPC_QueueHandler")


def queue_producer_worker(
    data_queue: mp.Queue,
    cmd_queue: mp.Queue,
    telemetry_queue: mp.Queue,
    stop_event: mp.Event,
):
    """
    Producer Process: Enqueues messages with payload and metadata into the data queue.
    Runs at module-level for Windows spawn compatibility.
    """
    pid = os.getpid()
    telemetry_queue.put({
        "type": "STATUS",
        "process_name": "Producer",
        "pid": pid,
        "status": "STARTED",
        "timestamp": time.time(),
    })

    while not stop_event.is_set():
        try:
            if not cmd_queue.empty():
                cmd = cmd_queue.get_nowait()
                action = cmd.get("action")

                if action == "PRODUCE":
                    items = cmd.get("items", [])
                    interval = cmd.get("interval", 0.0)

                    for idx, payload in enumerate(items):
                        if stop_event.is_set():
                            break

                        msg_packet = {
                            "msg_id": str(uuid.uuid4())[:8],
                            "sequence": idx + 1,
                            "sender": "Producer",
                            "sender_pid": pid,
                            "receiver": "Consumer",
                            "payload": payload,
                            "sent_timestamp": time.time(),
                        }

                        # Attempt to put message into queue with timeout for full queue detection
                        try:
                            data_queue.put(msg_packet, timeout=1.0)
                            telemetry_queue.put({
                                "type": "MSG_PRODUCED",
                                "process_name": "Producer",
                                "pid": pid,
                                "data": msg_packet,
                                "timestamp": msg_packet["sent_timestamp"],
                            })
                        except queue.Full:
                            telemetry_queue.put({
                                "type": "QUEUE_FULL",
                                "process_name": "Producer",
                                "pid": pid,
                                "data": msg_packet,
                                "timestamp": time.time(),
                            })

                        if interval > 0:
                            time.sleep(interval)

                elif action == "STOP":
                    break

            time.sleep(0.02)
        except Exception as e:
            telemetry_queue.put({
                "type": "ERROR",
                "process_name": "Producer",
                "pid": pid,
                "error": str(e),
                "timestamp": time.time(),
            })
            break

    telemetry_queue.put({
        "type": "STATUS",
        "process_name": "Producer",
        "pid": pid,
        "status": "STOPPED",
        "timestamp": time.time(),
    })


def queue_consumer_worker(
    data_queue: mp.Queue,
    cmd_queue: mp.Queue,
    telemetry_queue: mp.Queue,
    stop_event: mp.Event,
):
    """
    Consumer Process: Dequeues messages, simulates processing delay, and reports latency.
    Runs at module-level for Windows spawn compatibility.
    """
    pid = os.getpid()
    telemetry_queue.put({
        "type": "STATUS",
        "process_name": "Consumer",
        "pid": pid,
        "status": "STARTED",
        "timestamp": time.time(),
    })

    consumer_delay = 0.0

    while not stop_event.is_set():
        try:
            # Check for config updates (e.g. adjust processing delay)
            if not cmd_queue.empty():
                cmd = cmd_queue.get_nowait()
                if cmd.get("action") == "SET_DELAY":
                    consumer_delay = cmd.get("delay", 0.0)
                elif cmd.get("action") == "STOP":
                    break

            # Attempt to dequeue with a 0.2s timeout
            try:
                msg = data_queue.get(timeout=0.2)
                recv_time = time.time()

                # Simulate configurable consumer processing delay (bottleneck demonstration)
                if consumer_delay > 0:
                    time.sleep(consumer_delay)

                latency_ms = (recv_time - msg.get("sent_timestamp", recv_time)) * 1000.0

                telemetry_queue.put({
                    "type": "MSG_CONSUMED",
                    "process_name": "Consumer",
                    "pid": pid,
                    "data": msg,
                    "recv_timestamp": recv_time,
                    "latency_ms": latency_ms,
                    "processing_delay": consumer_delay,
                })
            except queue.Empty:
                # Periodic empty queue timeout notification
                telemetry_queue.put({
                    "type": "QUEUE_EMPTY",
                    "process_name": "Consumer",
                    "pid": pid,
                    "timestamp": time.time(),
                })

            time.sleep(0.01)
        except Exception as e:
            telemetry_queue.put({
                "type": "ERROR",
                "process_name": "Consumer",
                "pid": pid,
                "error": str(e),
                "timestamp": time.time(),
            })
            break

    telemetry_queue.put({
        "type": "STATUS",
        "process_name": "Consumer",
        "pid": pid,
        "status": "STOPPED",
        "timestamp": time.time(),
    })


class QueueSession:
    """
    Manages an active Producer-Consumer Message Queue session.
    Tracks backlog, messages sent/received, delivery latencies, and queue health.
    """

    def __init__(self, maxsize: int = 50):
        self.maxsize = maxsize
        self.data_queue: Optional[mp.Queue] = None
        self.cmd_queue_producer: Optional[mp.Queue] = None
        self.cmd_queue_consumer: Optional[mp.Queue] = None
        self.telemetry_queue: Optional[mp.Queue] = None
        self.stop_event: Optional[mp.Event] = None
        self.proc_producer: Optional[mp.Process] = None
        self.proc_consumer: Optional[mp.Process] = None
        self.is_running: bool = False

        self.total_sent: int = 0
        self.total_received: int = 0
        self.received_messages = []
        self.empty_timeout_count: int = 0

    def start(self) -> Tuple[bool, str]:
        """Start the Producer and Consumer processes."""
        if self.is_running:
            return False, "Queue session already active."

        try:
            self.data_queue = mp.Queue(maxsize=self.maxsize)
            self.cmd_queue_producer = mp.Queue()
            self.cmd_queue_consumer = mp.Queue()
            self.telemetry_queue = mp.Queue()
            self.stop_event = mp.Event()

            self.proc_producer = mp.Process(
                target=queue_producer_worker,
                args=(self.data_queue, self.cmd_queue_producer, self.telemetry_queue, self.stop_event),
                name="Queue_Producer",
            )
            self.proc_consumer = mp.Process(
                target=queue_consumer_worker,
                args=(self.data_queue, self.cmd_queue_consumer, self.telemetry_queue, self.stop_event),
                name="Queue_Consumer",
            )

            self.proc_producer.start()
            self.proc_consumer.start()
            self.is_running = True
            self.total_sent = 0
            self.total_received = 0
            self.empty_timeout_count = 0

            event_logger.log(
                ipc_type="QUEUE",
                severity="SUCCESS",
                message=f"Queue session started (Capacity: {self.maxsize}). Producer PID: {self.proc_producer.pid}, Consumer PID: {self.proc_consumer.pid}",
                process_name="QueueManager",
            )
            return True, "Queue session started successfully."
        except Exception as e:
            self.is_running = False
            event_logger.log(
                ipc_type="QUEUE",
                severity="ERROR",
                message=f"Failed to start queue session: {e}",
                process_name="QueueManager",
            )
            return False, str(e)

    def produce(self, items: list, interval: float = 0.0) -> bool:
        """Command the producer to send items into the queue."""
        if not self.is_running or not self.cmd_queue_producer:
            return False

        self.cmd_queue_producer.put({
            "action": "PRODUCE",
            "items": items,
            "interval": interval,
        })
        self.total_sent += len(items)
        return True

    def set_consumer_delay(self, delay_sec: float) -> bool:
        """Dynamically configure consumer processing delay to simulate bottleneck."""
        if not self.is_running or not self.cmd_queue_consumer:
            return False

        self.cmd_queue_consumer.put({"action": "SET_DELAY", "delay": delay_sec})
        return True

    def get_backlog(self) -> int:
        """Compute message backlog (sent minus received)."""
        backlog = self.total_sent - self.total_received
        return max(0, backlog)

    def poll_telemetry(self) -> list:
        """Harvest telemetry messages and update event log & database."""
        events = []
        if not self.telemetry_queue:
            return events

        while not self.telemetry_queue.empty():
            try:
                item = self.telemetry_queue.get_nowait()
                events.append(item)
                item_type = item.get("type")

                if item_type == "MSG_PRODUCED":
                    data = item["data"]
                    event_logger.log(
                        ipc_type="QUEUE",
                        severity="INFO",
                        message=f"Produced #{data['sequence']}: '{data['payload']}'",
                        process_name=item["process_name"],
                        process_pid=item["pid"],
                    )
                elif item_type == "MSG_CONSUMED":
                    data = item["data"]
                    self.total_received += 1
                    self.received_messages.append({
                        "msg_id": data["msg_id"],
                        "sequence": data["sequence"],
                        "payload": data["payload"],
                        "latency_ms": item["latency_ms"],
                        "timestamp": item["recv_timestamp"],
                    })
                    event_logger.log(
                        ipc_type="QUEUE",
                        severity="SUCCESS",
                        message=f"Consumed #{data['sequence']}: '{data['payload']}' (Latency: {item['latency_ms']:.2f} ms)",
                        process_name=item["process_name"],
                        process_pid=item["pid"],
                    )
                    # Persist message to DB
                    db_instance.log_message(
                        ipc_type="QUEUE",
                        sender_name="Producer",
                        sender_pid=data.get("sender_pid"),
                        receiver_name="Consumer",
                        receiver_pid=item["pid"],
                        payload_preview=data["payload"],
                        payload_size_bytes=len(str(data["payload"]).encode("utf-8")),
                        sent_timestamp=data["sent_timestamp"],
                        recv_timestamp=item["recv_timestamp"],
                        status="DELIVERED",
                    )
                elif item_type == "QUEUE_FULL":
                    event_logger.log(
                        ipc_type="QUEUE",
                        severity="WARNING",
                        message="Queue capacity reached! Backpressure detected on producer.",
                        process_name=item["process_name"],
                        process_pid=item["pid"],
                    )
                elif item_type == "QUEUE_EMPTY":
                    self.empty_timeout_count += 1
                    if self.empty_timeout_count % 10 == 0:  # Avoid log flooding
                        event_logger.log(
                            ipc_type="QUEUE",
                            severity="WARNING",
                            message="Queue empty timeout: consumer waiting for data.",
                            process_name=item["process_name"],
                            process_pid=item["pid"],
                        )
                elif item_type == "ERROR":
                    event_logger.log(
                        ipc_type="QUEUE",
                        severity="ERROR",
                        message=item["error"],
                        process_name=item["process_name"],
                        process_pid=item["pid"],
                    )
            except Exception:
                break
        return events

    def get_process_status(self) -> Dict[str, Any]:
        """Return status for producer and consumer processes."""
        prod_alive = self.proc_producer.is_alive() if self.proc_producer else False
        cons_alive = self.proc_consumer.is_alive() if self.proc_consumer else False
        return {
            "is_running": self.is_running and (prod_alive or cons_alive),
            "backlog": self.get_backlog(),
            "total_sent": self.total_sent,
            "total_received": self.total_received,
            "maxsize": self.maxsize,
            "producer": {
                "name": "Producer",
                "pid": self.proc_producer.pid if self.proc_producer else None,
                "alive": prod_alive,
            },
            "consumer": {
                "name": "Consumer",
                "pid": self.proc_consumer.pid if self.proc_consumer else None,
                "alive": cons_alive,
            },
        }

    def stop(self):
        """Safely terminate producer and consumer processes."""
        if not self.is_running:
            return

        if self.stop_event:
            self.stop_event.set()

        for proc in [self.proc_producer, self.proc_consumer]:
            if proc and proc.is_alive():
                proc.join(timeout=1.0)
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=0.5)

        # Close queues
        for q in [self.data_queue, self.cmd_queue_producer, self.cmd_queue_consumer, self.telemetry_queue]:
            if q:
                try:
                    q.close()
                except Exception:
                    pass

        self.is_running = False
        event_logger.log(
            ipc_type="QUEUE",
            severity="INFO",
            message="Queue session stopped and worker processes terminated.",
            process_name="QueueManager",
        )
