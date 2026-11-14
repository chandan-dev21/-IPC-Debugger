"""
Unit and Integration Tests for Pipe Communication Handler
"""

import time
import pytest
from ipc.pipe_handler import PipeSession


def test_pipe_start_and_process_lifecycle():
    """Test that pipe session starts both processes and reports valid PIDs."""
    session = PipeSession()
    success, msg = session.start()
    assert success is True
    assert "started successfully" in msg

    time.sleep(0.5)
    status = session.get_process_status()
    assert status["is_running"] is True
    assert status["proc_a"]["pid"] is not None
    assert status["proc_b"]["pid"] is not None
    assert status["proc_a"]["alive"] is True
    assert status["proc_b"]["alive"] is True

    session.stop()
    time.sleep(0.5)
    status_after = session.get_process_status()
    assert status_after["is_running"] is False


def test_pipe_message_transfer():
    """Test sending a message from Process A to Process B and verifying receipt."""
    session = PipeSession()
    session.start()
    time.sleep(0.4)

    test_payload = "OS_LAB_TEST_MESSAGE_123"
    sent = session.send_message("A", test_payload)
    assert sent is True

    # Poll telemetry to receive message
    received = False
    start_time = time.time()
    while time.time() - start_time < 3.0:
        session.poll_telemetry()
        if session.received_messages:
            last_msg = session.received_messages[-1]
            if last_msg["payload"] == test_payload:
                received = True
                assert last_msg["sender"] == "Process_A"
                assert last_msg["receiver"] == "Process_B"
                assert last_msg["latency_ms"] >= 0.0
                break
        time.sleep(0.1)

    assert received is True, "Process B failed to receive message sent by Process A"
    session.stop()


def test_pipe_bidirectional_transfer():
    """Test bidirectional message transfer: B sends to A."""
    session = PipeSession()
    session.start()
    time.sleep(0.4)

    test_payload = "ECHO_BACK_TO_A"
    sent = session.send_message("B", test_payload)
    assert sent is True

    received = False
    start_time = time.time()
    while time.time() - start_time < 3.0:
        session.poll_telemetry()
        if session.received_messages:
            last_msg = session.received_messages[-1]
            if last_msg["payload"] == test_payload:
                received = True
                assert last_msg["sender"] == "Process_B"
                assert last_msg["receiver"] == "Process_A"
                break
        time.sleep(0.1)

    assert received is True, "Process A failed to receive message from Process B"
    session.stop()
