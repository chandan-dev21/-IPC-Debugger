"""
Unit Tests for Bottleneck Detector
"""

import pytest
from debugging.bottleneck_detector import BottleneckDetector


def test_latency_bottleneck_detection():
    detector = BottleneckDetector(latency_threshold_ms=20.0)

    # Test normal latency
    normal_msgs = [{"latency_ms": 5.0}, {"latency_ms": 12.0}]
    reports = detector.analyze_message_latencies(normal_msgs)
    assert len(reports) == 0

    # Test latency spike
    spike_msgs = [{"latency_ms": 10.0}, {"latency_ms": 65.0}]
    reports = detector.analyze_message_latencies(spike_msgs)
    assert len(reports) > 0
    assert reports[0].severity == "CRITICAL"
    assert "Latency" in reports[0].category


def test_queue_backlog_bottleneck_detection():
    detector = BottleneckDetector(backlog_threshold=5, timeout_threshold=3)

    # Under threshold
    reports = detector.analyze_queue_health(backlog=2, capacity=20, empty_timeouts=1)
    assert len(reports) == 0

    # Backlog exceeded
    reports = detector.analyze_queue_health(backlog=8, capacity=20, empty_timeouts=0)
    assert len(reports) == 1
    assert reports[0].category == "Queue Backlog"

    # Timeouts exceeded
    reports_timeout = detector.analyze_queue_health(backlog=0, capacity=20, empty_timeouts=4)
    assert len(reports_timeout) == 1
    assert reports_timeout[0].category == "Consumer Starvation"


def test_lock_wait_bottleneck_detection():
    detector = BottleneckDetector(lock_wait_threshold_ms=40.0)

    # Normal wait
    report = detector.analyze_synchronization(lock_wait_ms=15.0)
    assert report is None

    # Excessive wait
    report = detector.analyze_synchronization(lock_wait_ms=90.0)
    assert report is not None
    assert report.severity == "WARNING"
