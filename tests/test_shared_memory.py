"""
Unit and Integration Tests for Shared Memory Handler
"""

import time
import pytest
from ipc.shared_memory_handler import SharedMemorySession, MAGIC_BYTES


def test_shared_memory_lifecycle():
    """Test allocation and safe deallocation of shared memory block."""
    session = SharedMemorySession(size=1024, synchronized=True)
    success, msg = session.start()
    assert success is True
    assert session.shm is not None
    assert session.shm_name is not None

    time.sleep(0.4)
    status = session.get_process_status()
    assert status["is_running"] is True
    assert status["writer"]["alive"] is True
    assert status["reader"]["alive"] is True

    session.stop()
    time.sleep(0.5)
    status_after = session.get_process_status()
    assert status_after["is_running"] is False
    assert session.shm is None


def test_shared_memory_synchronized_write_read():
    """Test synchronized write and read cycle through shared memory."""
    session = SharedMemorySession(size=2048, synchronized=True)
    session.start()
    time.sleep(0.4)

    test_data = "SHARED_RAM_PAYLOAD_ABC_999"
    written = session.write_data(test_data)
    assert written is True

    # Poll until reader picks up the data
    read_success = False
    start = time.time()
    while time.time() - start < 4.0:
        session.poll_telemetry()
        if session.read_history:
            last_read = session.read_history[-1]
            if last_read["payload"] == test_data:
                read_success = True
                assert last_read["synchronized"] is True
                assert last_read["corrupted"] is False
                assert last_read["latency_ms"] >= 0.0
                break
        time.sleep(0.1)

    assert read_success is True, "Reader process failed to read from shared memory"

    # Inspect raw buffer
    buf_info = session.inspect_raw_buffer(max_bytes=64)
    assert buf_info["header"] is not None
    assert buf_info["header"]["magic"] == MAGIC_BYTES.decode("ascii")

    session.stop()


def test_shared_memory_unsynchronized_mode():
    """Test that unsynchronized mode runs and signals unsynchronized state."""
    session = SharedMemorySession(size=2048, synchronized=False)
    session.start()
    time.sleep(0.4)

    test_data = "RACE_CONDITION_SIMULATION_BURST"
    written = session.write_data(test_data)
    assert written is True

    read_found = False
    start = time.time()
    while time.time() - start < 4.0:
        session.poll_telemetry()
        if session.read_history:
            read_found = True
            assert session.read_history[-1]["synchronized"] is False
            break
        time.sleep(0.1)

    assert read_found is True
    session.stop()
