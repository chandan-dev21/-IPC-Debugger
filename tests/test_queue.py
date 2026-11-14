"""
Unit and Integration Tests for Message Queue Handler
"""

import time
import pytest
from ipc.queue_handler import QueueSession


def test_queue_lifecycle():
    """Test start and stop of Producer and Consumer processes."""
    session = QueueSession(maxsize=20)
    success, msg = session.start()
    assert success is True

    time.sleep(0.4)
    status = session.get_process_status()
    assert status["is_running"] is True
    assert status["producer"]["alive"] is True
    assert status["consumer"]["alive"] is True
    assert status["producer"]["pid"] is not None
    assert status["consumer"]["pid"] is not None

    session.stop()
    time.sleep(0.5)
    status_after = session.get_process_status()
    assert status_after["is_running"] is False


def test_queue_multiple_messages():
    """Test sending multiple messages and verifying producer-consumer throughput."""
    session = QueueSession(maxsize=20)
    session.start()
    time.sleep(0.4)

    test_items = ["Task #1", "Task #2", "Task #3"]
    sent = session.produce(test_items, interval=0.05)
    assert sent is True
    assert session.total_sent == 3

    # Poll until all consumed
    start = time.time()
    while time.time() - start < 4.0:
        session.poll_telemetry()
        if session.total_received >= 3:
            break
        time.sleep(0.1)

    assert session.total_received == 3
    assert len(session.received_messages) == 3
    payloads = [m["payload"] for m in session.received_messages]
    assert payloads == test_items

    # Backlog should now be 0
    assert session.get_backlog() == 0

    session.stop()


def test_queue_backlog_detection():
    """Test that setting consumer delay causes backlog accumulation."""
    session = QueueSession(maxsize=30)
    session.start()
    time.sleep(0.3)

    # Set consumer delay to 0.4s to induce a backlog
    session.set_consumer_delay(0.4)

    # Burst 4 messages quickly
    items = ["Burst A", "Burst B", "Burst C", "Burst D"]
    session.produce(items, interval=0.0)

    # Check immediate backlog before consumer finishes
    time.sleep(0.1)
    session.poll_telemetry()
    backlog = session.get_backlog()
    assert backlog > 0, f"Expected backlog > 0, got {backlog}"

    # Wait for consumer to catch up
    start = time.time()
    while time.time() - start < 4.0:
        session.poll_telemetry()
        if session.total_received >= 4:
            break
        time.sleep(0.2)

    assert session.total_received == 4
    session.stop()
