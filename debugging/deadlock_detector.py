"""
Deadlock Detector and Controlled Simulation Engine
Implements Resource Allocation Graph (RAG) cycle detection and a two-process two-lock controlled demonstration.
Includes bounded timeouts to ensure the application never hangs.
"""

import logging
import multiprocessing as mp
import os
import time
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Lock
from typing import Any, List, Optional

from database.db_manager import db_instance
from debugging.event_logger import event_logger

logger = logging.getLogger("IPC_DeadlockDetector")


class ResourceAllocationGraph:
    """
    Represents the Resource Allocation Graph (RAG) for processes and locks.
    Detects circular wait conditions (deadlock) via cycle detection.
    """

    def __init__(self):
        self.processes: set[str] = set()
        self.locks: set[str] = set()
        # allocations: lock -> process (Lock held by Process)
        self.allocations: dict[str, str] = {}
        # requests: process -> lock (Process waiting for Lock)
        self.requests: dict[str, str] = {}

    def add_process(self, process_name: str):
        self.processes.add(process_name)

    def add_lock(self, lock_name: str):
        self.locks.add(lock_name)

    def set_allocation(self, lock_name: str, process_name: str):
        """Record that process_name currently holds lock_name."""
        self.add_lock(lock_name)
        self.add_process(process_name)
        self.allocations[lock_name] = process_name
        # If it was requesting this lock, clear the request
        if self.requests.get(process_name) == lock_name:
            del self.requests[process_name]

    def set_request(self, process_name: str, lock_name: str):
        """Record that process_name is requesting/waiting for lock_name."""
        self.add_process(process_name)
        self.add_lock(lock_name)
        self.requests[process_name] = lock_name

    def clear_lock(self, lock_name: str):
        """Clear holding allocation for a released lock."""
        if lock_name in self.allocations:
            del self.allocations[lock_name]

    def clear(self):
        self.processes.clear()
        self.locks.clear()
        self.allocations.clear()
        self.requests.clear()

    def detect_deadlock(self) -> tuple[bool, list[str]]:
        """
        Detects if a circular wait (cycle) exists in the Resource Allocation Graph.
        Returns: (has_deadlock, cycle_path)
        """
        # Build directed adjacency list
        # Graph nodes can be processes or locks
        adj: dict[str, list[str]] = {}

        # Edges from Lock -> Process (Allocation)
        for lock, proc in self.allocations.items():
            adj.setdefault(f"Lock:{lock}", []).append(f"Proc:{proc}")

        # Edges from Process -> Lock (Request)
        for proc, lock in self.requests.items():
            adj.setdefault(f"Proc:{proc}", []).append(f"Lock:{lock}")

        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> list[str] | None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    cycle = dfs(neighbor)
                    if cycle:
                        return cycle
                elif neighbor in rec_stack:
                    # Cycle detected! Extract the subpath forming the cycle
                    idx = path.index(neighbor)
                    return path[idx:] + [neighbor]

            path.pop()
            rec_stack.remove(node)
            return None

        all_nodes = list(adj.keys())
        for node in all_nodes:
            if node not in visited:
                cycle = dfs(node)
                if cycle:
                    return True, cycle

        return False, []

    def get_graph_state(self) -> dict[str, Any]:
        """Returns structured graph topology for UI visualization."""
        has_deadlock, cycle = self.detect_deadlock()

        nodes = []
        for p in self.processes:
            nodes.append({"id": f"Proc:{p}", "label": p, "type": "PROCESS"})
        for l in self.locks:
            nodes.append({"id": f"Lock:{l}", "label": l, "type": "LOCK"})

        edges = []
        for lock, proc in self.allocations.items():
            edges.append({
                "from": f"Lock:{lock}",
                "to": f"Proc:{proc}",
                "label": "HELD_BY",
                "type": "ALLOCATION",
            })
        for proc, lock in self.requests.items():
            edges.append({
                "from": f"Proc:{proc}",
                "to": f"Lock:{lock}",
                "label": "WAITING_FOR",
                "type": "REQUEST",
            })

        return {
            "has_deadlock": has_deadlock,
            "cycle": cycle,
            "allocations": dict(self.allocations),
            "requests": dict(self.requests),
            "nodes": nodes,
            "edges": edges,
        }


def deadlock_worker_1(
    lock_a: Lock,
    lock_b: Lock,
    telemetry_queue: Queue,
    timeout: float,
    prevent_deadlock: bool,
):
    """
    Process 1 Worker:
    Acquires Lock A, sleeps briefly, then requests Lock B with bounded timeout.
    """
    pid = os.getpid()
    proc_name = "Process_1"

    telemetry_queue.put({
        "type": "STATUS",
        "process_name": proc_name,
        "pid": pid,
        "status": "STARTED",
        "timestamp": time.time(),
    })

    # Step 1: Request Lock A
    telemetry_queue.put({
        "type": "LOCK_REQUEST",
        "process_name": proc_name,
        "pid": pid,
        "lock_name": "Lock_A",
        "timestamp": time.time(),
    })

    acquired_a = lock_a.acquire(timeout=timeout)
    if not acquired_a:
        telemetry_queue.put({
            "type": "LOCK_TIMEOUT",
            "process_name": proc_name,
            "pid": pid,
            "lock_name": "Lock_A",
            "timestamp": time.time(),
        })
        return

    telemetry_queue.put({
        "type": "LOCK_ACQUIRED",
        "process_name": proc_name,
        "pid": pid,
        "lock_name": "Lock_A",
        "timestamp": time.time(),
    })

    # Deliberate sleep to give Process 2 time to acquire Lock B
    time.sleep(0.4)

    # Step 2: Request Lock B
    telemetry_queue.put({
        "type": "LOCK_REQUEST",
        "process_name": proc_name,
        "pid": pid,
        "lock_name": "Lock_B",
        "timestamp": time.time(),
    })

    acquired_b = lock_b.acquire(timeout=timeout)
    if acquired_b:
        telemetry_queue.put({
            "type": "LOCK_ACQUIRED",
            "process_name": proc_name,
            "pid": pid,
            "lock_name": "Lock_B",
            "timestamp": time.time(),
        })
        # Simulate work
        time.sleep(0.1)
        lock_b.release()
        telemetry_queue.put({
            "type": "LOCK_RELEASED",
            "process_name": proc_name,
            "pid": pid,
            "lock_name": "Lock_B",
            "timestamp": time.time(),
        })
    else:
        telemetry_queue.put({
            "type": "LOCK_TIMEOUT",
            "process_name": proc_name,
            "pid": pid,
            "lock_name": "Lock_B",
            "timestamp": time.time(),
        })

    lock_a.release()
    telemetry_queue.put({
        "type": "LOCK_RELEASED",
        "process_name": proc_name,
        "pid": pid,
        "lock_name": "Lock_A",
        "timestamp": time.time(),
    })


def deadlock_worker_2(
    lock_a: Lock,
    lock_b: Lock,
    telemetry_queue: Queue,
    timeout: float,
    prevent_deadlock: bool,
):
    """
    Process 2 Worker:
    In Deadlock Demo Mode: Acquires Lock B first, sleeps briefly, then requests Lock A (Circular Wait!).
    In Prevention Mode: Follows strict lock hierarchy (Acquires Lock A first, then Lock B).
    """
    pid = os.getpid()
    proc_name = "Process_2"

    telemetry_queue.put({
        "type": "STATUS",
        "process_name": proc_name,
        "pid": pid,
        "status": "STARTED",
        "timestamp": time.time(),
    })

    first_lock = lock_a if prevent_deadlock else lock_b
    first_lock_name = "Lock_A" if prevent_deadlock else "Lock_B"
    second_lock = lock_b if prevent_deadlock else lock_a
    second_lock_name = "Lock_B" if prevent_deadlock else "Lock_A"

    # Step 1: Request First Lock
    telemetry_queue.put({
        "type": "LOCK_REQUEST",
        "process_name": proc_name,
        "pid": pid,
        "lock_name": first_lock_name,
        "timestamp": time.time(),
    })

    acquired_first = first_lock.acquire(timeout=timeout)
    if not acquired_first:
        telemetry_queue.put({
            "type": "LOCK_TIMEOUT",
            "process_name": proc_name,
            "pid": pid,
            "lock_name": first_lock_name,
            "timestamp": time.time(),
        })
        return

    telemetry_queue.put({
        "type": "LOCK_ACQUIRED",
        "process_name": proc_name,
        "pid": pid,
        "lock_name": first_lock_name,
        "timestamp": time.time(),
    })

    # Deliberate sleep
    time.sleep(0.4)

    # Step 2: Request Second Lock
    telemetry_queue.put({
        "type": "LOCK_REQUEST",
        "process_name": proc_name,
        "pid": pid,
        "lock_name": second_lock_name,
        "timestamp": time.time(),
    })

    acquired_second = second_lock.acquire(timeout=timeout)
    if acquired_second:
        telemetry_queue.put({
            "type": "LOCK_ACQUIRED",
            "process_name": proc_name,
            "pid": pid,
            "lock_name": second_lock_name,
            "timestamp": time.time(),
        })
        time.sleep(0.1)
        second_lock.release()
        telemetry_queue.put({
            "type": "LOCK_RELEASED",
            "process_name": proc_name,
            "pid": pid,
            "lock_name": second_lock_name,
            "timestamp": time.time(),
        })
    else:
        telemetry_queue.put({
            "type": "LOCK_TIMEOUT",
            "process_name": proc_name,
            "pid": pid,
            "lock_name": second_lock_name,
            "timestamp": time.time(),
        })

    first_lock.release()
    telemetry_queue.put({
        "type": "LOCK_RELEASED",
        "process_name": proc_name,
        "pid": pid,
        "lock_name": first_lock_name,
        "timestamp": time.time(),
    })


class DeadlockLabSession:
    """
    Coordinates the controlled deadlock simulation and monitoring.
    """

    def __init__(self, timeout: float = 3.5):
        self.timeout = timeout
        self.rag = ResourceAllocationGraph()
        self.lock_a: Lock | None = None
        self.lock_b: Optional[mp.Lock] = None
        self.telemetry_queue: Optional[mp.Queue] = None
        self.proc_1: Optional[mp.Process] = None
        self.proc_2: Optional[mp.Process] = None
        self.is_running: bool = False
        self.prevent_deadlock: bool = False
        self.deadlock_detected: bool = False
        self.deadlock_cycle: List[str] = []
        self.resolved: bool = False

    def run_simulation(self, prevent_deadlock: bool = False) -> tuple[bool, str]:
        """
        Launch the two-process two-lock scenario.
        prevent_deadlock=False: Demonstrates deadlock via circular wait.
        prevent_deadlock=True: Demonstrates prevention via lock ordering hierarchy.
        """
        if self.is_running:
            return False, "Simulation already running."

        self.prevent_deadlock = prevent_deadlock
        self.deadlock_detected = False
        self.deadlock_cycle = []
        self.resolved = False
        self.rag.clear()

        try:
            self.lock_a = mp.Lock()
            self.lock_b = mp.Lock()
            self.telemetry_queue = mp.Queue()

            self.proc_1 = mp.Process(
                target=deadlock_worker_1,
                args=(self.lock_a, self.lock_b, self.telemetry_queue, self.timeout, self.prevent_deadlock),
                name="Deadlock_Proc_1",
            )
            self.proc_2 = mp.Process(
                target=deadlock_worker_2,
                args=(self.lock_a, self.lock_b, self.telemetry_queue, self.timeout, self.prevent_deadlock),
                name="Deadlock_Proc_2",
            )

            self.proc_1.start()
            self.proc_2.start()
            self.is_running = True

            scenario_name = (
                "Deadlock Prevention (Ordered Locks)"
                if self.prevent_deadlock
                else "Controlled Deadlock (Circular Wait)"
            )
            event_logger.log(
                ipc_type="DEADLOCK",
                severity="INFO",
                message=f"Started {scenario_name}. P1 PID: {self.proc_1.pid}, P2 PID: {self.proc_2.pid}. Timeout: {self.timeout}s",
                process_name="DeadlockLab",
            )
            return True, f"Simulation started: {scenario_name}"
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self.is_running = False
            return False, str(exc)

    def poll_telemetry(self) -> dict[str, Any]:
        """Update RAG and detect circular waiting conditions."""
        if not self.telemetry_queue:
            return self.rag.get_graph_state()

        while not self.telemetry_queue.empty():
            try:
                item = self.telemetry_queue.get_nowait()
                itype = item.get("type")
                pname = item.get("process_name")
                pid = item.get("pid")
                lock_name = item.get("lock_name")

                if itype == "LOCK_REQUEST":
                    self.rag.set_request(pname, lock_name)
                    event_logger.log(
                        ipc_type="DEADLOCK",
                        severity="INFO",
                        message=f"{pname} is REQUESTING {lock_name}",
                        process_name=pname,
                        process_pid=pid,
                    )
                elif itype == "LOCK_ACQUIRED":
                    self.rag.set_allocation(lock_name, pname)
                    event_logger.log(
                        ipc_type="DEADLOCK",
                        severity="SUCCESS",
                        message=f"{pname} ACQUIRED {lock_name}",
                        process_name=pname,
                        process_pid=pid,
                    )
                elif itype == "LOCK_RELEASED":
                    self.rag.clear_lock(lock_name)
                    event_logger.log(
                        ipc_type="DEADLOCK",
                        severity="INFO",
                        message=f"{pname} RELEASED {lock_name}",
                        process_name=pname,
                        process_pid=pid,
                    )
                elif itype == "LOCK_TIMEOUT":
                    self.rag.requests.pop(pname, None)
                    event_logger.log(
                        ipc_type="DEADLOCK",
                        severity="WARNING",
                        message=f"{pname} TIMED OUT waiting for {lock_name} (Deadlock broken safely via timeout)",
                        process_name=pname,
                        process_pid=pid,
                    )
                    self.resolved = True
            except Exception:  # noqa: BLE001
                break

        # Check for circular wait in RAG
        has_deadlock, cycle = self.rag.detect_deadlock()
        if has_deadlock and not self.deadlock_detected:
            self.deadlock_detected = True
            self.deadlock_cycle = cycle
            event_logger.log(
                ipc_type="DEADLOCK",
                severity="ERROR",
                message=f"DEADLOCK DETECTED! Circular Wait Condition: {' -> '.join(cycle)}",
                process_name="DeadlockDetector",
            )
            # Log to DB
            db_instance.log_deadlock_incident(
                scenario_type="TWO_PROCESS_TWO_LOCK",
                proc1_name="Process_1",
                proc1_pid=self.proc_1.pid if self.proc_1 else None,
                proc2_name="Process_2",
                proc2_pid=self.proc_2.pid if self.proc_2 else None,
                lock1_name="Lock_A",
                lock2_name="Lock_B",
                status="DETECTED",
                details=f"Circular wait: {' -> '.join(cycle)}",
            )

        # Check process completion
        p1_alive = self.proc_1.is_alive() if self.proc_1 else False
        p2_alive = self.proc_2.is_alive() if self.proc_2 else False

        if not p1_alive and not p2_alive and self.is_running:
            self.is_running = False
            self.resolved = True

        state = self.rag.get_graph_state()
        state["is_running"] = self.is_running
        state["deadlock_detected"] = self.deadlock_detected
        state["cycle"] = self.deadlock_cycle
        state["resolved"] = self.resolved
        return state

    def stop(self):
        """Clean up processes safely."""
        for proc in [self.proc_1, self.proc_2]:
            if proc and proc.is_alive():
                proc.join(timeout=1.0)
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=0.5)

        self.is_running = False
        self.rag.clear()
