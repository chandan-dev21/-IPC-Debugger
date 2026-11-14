"""
Bottleneck Detector and Performance Profiler
Analyzes communication latency, queue backlogs, and synchronization delays against configurable criteria.
"""

import time
from typing import Any


class BottleneckReport:
    """Diagnostic report highlighting communication delays and resource bottlenecks."""

    def __init__(
        self,
        category: str,
        severity: str,  # HEALTHY, WARNING, CRITICAL
        title: str,
        description: str,
        observed_value: Any,
        threshold_value: Any,
        metric_unit: str,
        recommendation: str,
    ):
        self.category = category
        self.severity = severity
        self.title = title
        self.description = description
        self.observed_value = observed_value
        self.threshold_value = threshold_value
        self.metric_unit = metric_unit
        self.recommendation = recommendation
        self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "observed_value": self.observed_value,
            "threshold_value": self.threshold_value,
            "metric_unit": self.metric_unit,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp,
        }


class BottleneckDetector:
    """
    Evaluates real-time IPC telemetry to detect performance bottlenecks.
    Detection Criteria:
    - High Latency: Delivery latency > latency_threshold_ms.
    - Queue Saturation: Backlog > backlog_threshold or utilization > 75%.
    - Consumer Starvation / Empty Timeouts: Timeouts > timeout_threshold.
    - Lock Contention: Lock wait time > lock_wait_threshold_ms.
    """

    def __init__(
        self,
        latency_threshold_ms: float = 25.0,
        backlog_threshold: int = 5,
        timeout_threshold: int = 3,
        lock_wait_threshold_ms: float = 50.0,
    ):
        self.latency_threshold_ms = latency_threshold_ms
        self.backlog_threshold = backlog_threshold
        self.timeout_threshold = timeout_threshold
        self.lock_wait_threshold_ms = lock_wait_threshold_ms

    def analyze_message_latencies(self, messages: list[dict[str, Any]]) -> list[BottleneckReport]:
        """Analyze recent message transmissions for unusual latency spikes."""
        reports = []
        if not messages:
            return reports

        latencies = [m["latency_ms"] for m in messages if m.get("latency_ms") is not None]
        if not latencies:
            return reports

        avg_lat = sum(latencies) / len(latencies)
        max_lat = max(latencies)

        if max_lat > self.latency_threshold_ms * 2:
            reports.append(
                BottleneckReport(
                    category="Latency",
                    severity="CRITICAL",
                    title="Extreme Latency Spike Detected",
                    description=(
                        f"Maximum transmission latency reached {max_lat:.2f} ms, "
                        f"which is more than double the threshold ({self.latency_threshold_ms:.2f} ms)."
                    ),
                    observed_value=round(max_lat, 2),
                    threshold_value=self.latency_threshold_ms,
                    metric_unit="ms",
                    recommendation="Inspect OS process scheduling, CPU throttling, or heavy payload serialization overhead.",
                )
            )
        elif avg_lat > self.latency_threshold_ms:
            reports.append(
                BottleneckReport(
                    category="Latency",
                    severity="WARNING",
                    title="Elevated Average Latency",
                    description=(
                        f"Average transmission latency is {avg_lat:.2f} ms, "
                        f"exceeding the baseline threshold ({self.latency_threshold_ms:.2f} ms)."
                    ),
                    observed_value=round(avg_lat, 2),
                    threshold_value=self.latency_threshold_ms,
                    metric_unit="ms",
                    recommendation="Optimize inter-process buffer sizes or reduce payload sizes to decrease IPC overhead.",
                )
            )

        return reports

    def analyze_queue_health(
        self,
        backlog: int,
        capacity: int,
        empty_timeouts: int,
    ) -> list[BottleneckReport]:
        """Inspect message queue depth and consumer balance."""
        reports = []
        utilization = (backlog / capacity) * 100.0 if capacity > 0 else 0.0

        if backlog >= self.backlog_threshold or utilization >= 75.0:
            severity = "CRITICAL" if utilization >= 90.0 else "WARNING"
            reports.append(
                BottleneckReport(
                    category="Queue Backlog",
                    severity=severity,
                    title="Queue Producer-Consumer Imbalance",
                    description=(
                        f"Queue backlog is {backlog} items ({utilization:.1f}% capacity). "
                        f"Producer rate is outpacing consumer processing capacity."
                    ),
                    observed_value=backlog,
                    threshold_value=self.backlog_threshold,
                    metric_unit="messages",
                    recommendation="Scale consumer worker count, decrease consumer per-item delay, or increase queue buffer size.",
                )
            )

        if empty_timeouts >= self.timeout_threshold:
            reports.append(
                BottleneckReport(
                    category="Consumer Starvation",
                    severity="WARNING",
                    title="Consumer Underutilization / Starvation",
                    description=(
                        f"Consumer experienced {empty_timeouts} empty queue timeouts waiting for messages."
                    ),
                    observed_value=empty_timeouts,
                    threshold_value=self.timeout_threshold,
                    metric_unit="timeouts",
                    recommendation="Evaluate producer frequency or employ event-based signaling instead of busy timeout polling.",
                )
            )

        return reports

    def analyze_synchronization(self, lock_wait_ms: float) -> BottleneckReport | None:
        """Inspect lock contention and wait durations."""
        if lock_wait_ms > self.lock_wait_threshold_ms:
            return BottleneckReport(
                category="Synchronization",
                severity="WARNING",
                title="Lock Contention Bottleneck",
                description=(
                    f"Process waited {lock_wait_ms:.2f} ms to acquire synchronization lock "
                    f"(Threshold: {self.lock_wait_threshold_ms:.2f} ms)."
                ),
                observed_value=round(lock_wait_ms, 2),
                threshold_value=self.lock_wait_threshold_ms,
                metric_unit="ms",
                recommendation="Minimize critical section holding time or adopt lock-free ring buffers in shared memory.",
            )
        return None

    def get_criteria_explanation(self) -> dict[str, Any]:
        """Return clear explanations of the configured detection criteria."""
        return {
            "latency": {
                "threshold": f"{self.latency_threshold_ms} ms",
                "criterion": "Flagged if average or peak message delivery time exceeds threshold.",
                "rationale": "High latency indicates I/O blocking, context-switching overhead, or scheduling delays.",
            },
            "queue_backlog": {
                "threshold": f"{self.backlog_threshold} messages",
                "criterion": "Flagged if queued unconsumed messages exceed threshold or capacity > 75%.",
                "rationale": "Unconsumed messages indicate the consumer process is slower than producer arrival rate.",
            },
            "consumer_timeouts": {
                "threshold": f"{self.timeout_threshold} timeouts",
                "criterion": "Flagged when consumer idle timeout counter exceeds threshold.",
                "rationale": "High idle timeouts indicate idle consumer processes wasting scheduling resources.",
            },
            "lock_contention": {
                "threshold": f"{self.lock_wait_threshold_ms} ms",
                "criterion": "Flagged when waiting for mutual exclusion lock exceeds threshold.",
                "rationale": "Excessive lock wait indicates a process holding the lock too long, blocking peer processes.",
            },
        }


# Singleton instance
bottleneck_detector = BottleneckDetector()
