
import multiprocessing as mp
import time

import pytest

from debugging.synchronization import MonitoredLock


def test_lock_acquire_and_release():
    lock = MonitoredLock("Test_Lock")

    assert lock.acquire("Process_A") is True
    assert lock.get_state()["is_held"] is True

    lock.release("Process_A")

    assert lock.get_state()["is_held"] is False


def test_lock_timeout():
    lock = MonitoredLock("Timeout_Lock")

    assert lock.acquire("Process_A") is True

    start = time.perf_counter()
    acquired = lock.acquire("Process_B", timeout=0.1)
    elapsed = time.perf_counter() - start

    assert acquired is False
    assert elapsed >= 0.09

    lock.release("Process_A")


def test_negative_timeout():
    lock = MonitoredLock("Invalid_Lock")

    with pytest.raises(ValueError):
        lock.acquire("Process_A", timeout=-1)


def test_telemetry_history():
    lock = MonitoredLock("History_Lock")

    lock.acquire("Process_A")
    lock.release("Process_A")

    history = lock.get_history()

    actions = [record["action"] for record in history]

    assert "LOCK_REQUESTED" in actions
    assert "LOCK_ACQUIRED" in actions
    assert "LOCK_RELEASED" in actions


def test_holding_duration():
    lock = MonitoredLock("Duration_Lock")

    lock.acquire("Process_A")
    time.sleep(0.05)
    lock.release("Process_A")

    history = lock.get_history()

    released = next(
        record for record in history
        if record["action"] == "LOCK_RELEASED"
    )

    assert released["hold_time_ms"] >= 40


def test_telemetry_queue():
    telemetry_queue = mp.Queue()

    lock = MonitoredLock(
        "Queue_Lock",
        telemetry_queue=telemetry_queue,
    )

    lock.acquire("Process_A")
    lock.release("Process_A")

    records = []

    while not telemetry_queue.empty():
        records.append(telemetry_queue.get(timeout=1))

    actions = [record["action"] for record in records]

    assert "LOCK_REQUESTED" in actions
    assert "LOCK_ACQUIRED" in actions
    assert "LOCK_RELEASED" in actions

    telemetry_queue.close()
    telemetry_queue.join_thread()


def test_history_count():
    lock = MonitoredLock("Count_Lock")

    lock.acquire("Process_A")
    lock.release("Process_A")

    assert len(lock.get_history(count=2)) == 2
    assert len(lock.get_history(count=0)) == 0

    with pytest.raises(ValueError):
        lock.get_history(count=-1)

