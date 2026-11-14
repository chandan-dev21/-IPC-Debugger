"""
Unit and Integration Tests for Deadlock Detector and Simulation Lab
"""

import time
import pytest
from debugging.deadlock_detector import ResourceAllocationGraph, DeadlockLabSession


def test_rag_cycle_detection():
    """Test graph cycle detection algorithm for circular wait."""
    rag = ResourceAllocationGraph()

    # P1 holds Lock A, P2 holds Lock B
    rag.set_allocation("Lock_A", "Process_1")
    rag.set_allocation("Lock_B", "Process_2")

    # No cycle yet
    has_deadlock, cycle = rag.detect_deadlock()
    assert has_deadlock is False
    assert len(cycle) == 0

    # P1 requests Lock B
    rag.set_request("Process_1", "Lock_B")
    has_deadlock, cycle = rag.detect_deadlock()
    assert has_deadlock is False

    # P2 requests Lock A -> Circular Wait Cycle!
    rag.set_request("Process_2", "Lock_A")
    has_deadlock, cycle = rag.detect_deadlock()
    assert has_deadlock is True
    assert len(cycle) > 0


def test_deadlock_simulation_with_timeout_resolution():
    """Test controlled deadlock execution: circular wait occurs and safely times out without freezing."""
    session = DeadlockLabSession(timeout=1.5)
    success, msg = session.run_simulation(prevent_deadlock=False)
    assert success is True

    # Poll during execution: should detect deadlock within ~1.0s
    start = time.time()
    deadlock_seen = False
    while time.time() - start < 4.0:
        state = session.poll_telemetry()
        if state["deadlock_detected"]:
            deadlock_seen = True
        if state.get("resolved") and not state.get("is_running"):
            break
        time.sleep(0.2)

    assert deadlock_seen is True, "Deadlock detection failed to recognize circular wait"
    assert session.resolved is True, "Deadlock failed to resolve safely via timeout"
    session.stop()


def test_deadlock_prevention_ordered_locks():
    """Test that strict lock ordering prevents deadlock."""
    session = DeadlockLabSession(timeout=2.0)
    success, msg = session.run_simulation(prevent_deadlock=True)
    assert success is True

    start = time.time()
    while time.time() - start < 4.0:
        state = session.poll_telemetry()
        if not state.get("is_running"):
            break
        time.sleep(0.2)

    # In prevention mode, circular wait should NEVER occur
    assert session.deadlock_detected is False
    session.stop()
