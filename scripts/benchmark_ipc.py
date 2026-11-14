"""
IPC Performance Benchmark Suite
Automated stress testing and latency/throughput profiling across:
- multiprocessing.Pipe
- multiprocessing.Queue
- multiprocessing.shared_memory (Synchronized)
- multiprocessing.shared_memory (Unsynchronized)
"""

import os
import sys
import time
import statistics
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipc.pipe_handler import PipeSession
from ipc.queue_handler import QueueSession
from ipc.shared_memory_handler import SharedMemorySession
from database.db_manager import db_instance

NUM_SAMPLES = 40
PAYLOAD = "BENCHMARK_PAYLOAD_TEST_DATA_BLOCK_OS_CAPSTONE_2026"
PAYLOAD_SIZE = len(PAYLOAD.encode("utf-8"))


def benchmark_pipe() -> dict:
    print("\n[1/4] Benchmarking multiprocessing.Pipe...")
    session = PipeSession()
    session.start()
    time.sleep(0.5)

    latencies = []
    start_total = time.time()

    for i in range(NUM_SAMPLES):
        msg = f"{PAYLOAD}_{i+1}"
        session.send_message("A", msg, delay=0.0)
        # Wait for receipt
        t0 = time.time()
        while time.time() - t0 < 1.0:
            session.poll_telemetry()
            if len(session.received_messages) > len(latencies):
                latencies.append(session.received_messages[-1]["latency_ms"])
                break
            time.sleep(0.005)

    duration = time.time() - start_total
    session.stop()

    valid_lats = latencies if latencies else [0.0]
    return {
        "mechanism": "multiprocessing.Pipe",
        "samples": len(valid_lats),
        "min_latency_ms": min(valid_lats),
        "avg_latency_ms": statistics.mean(valid_lats),
        "median_latency_ms": statistics.median(valid_lats),
        "max_latency_ms": max(valid_lats),
        "total_time_sec": duration,
        "throughput_msgs_per_sec": len(valid_lats) / duration if duration > 0 else 0,
        "throughput_kb_per_sec": (len(valid_lats) * PAYLOAD_SIZE / 1024.0) / duration if duration > 0 else 0,
    }


def benchmark_queue() -> dict:
    print("[2/4] Benchmarking multiprocessing.Queue...")
    session = QueueSession(maxsize=100)
    session.start()
    time.sleep(0.5)

    items = [f"{PAYLOAD}_{i+1}" for i in range(NUM_SAMPLES)]
    start_total = time.time()
    session.produce(items, interval=0.001)

    # Wait for consumer to process all
    start_wait = time.time()
    while time.time() - start_wait < 5.0:
        session.poll_telemetry()
        if session.total_received >= NUM_SAMPLES:
            break
        time.sleep(0.01)

    duration = time.time() - start_total
    session.stop()

    latencies = [m["latency_ms"] for m in session.received_messages if m.get("latency_ms") is not None]
    valid_lats = latencies if latencies else [0.0]
    return {
        "mechanism": "multiprocessing.Queue",
        "samples": len(valid_lats),
        "min_latency_ms": min(valid_lats),
        "avg_latency_ms": statistics.mean(valid_lats),
        "median_latency_ms": statistics.median(valid_lats),
        "max_latency_ms": max(valid_lats),
        "total_time_sec": duration,
        "throughput_msgs_per_sec": len(valid_lats) / duration if duration > 0 else 0,
        "throughput_kb_per_sec": (len(valid_lats) * PAYLOAD_SIZE / 1024.0) / duration if duration > 0 else 0,
    }


def benchmark_shared_memory(synchronized: bool) -> dict:
    mode_str = "Synchronized (Lock)" if synchronized else "Unsynchronized"
    print(f"[{3 if synchronized else 4}/4] Benchmarking SharedMemory [{mode_str}]...")
    session = SharedMemorySession(size=4096, synchronized=synchronized)
    session.start()
    time.sleep(0.5)

    latencies = []
    start_total = time.time()

    for i in range(NUM_SAMPLES):
        msg = f"{PAYLOAD}_{i+1}"
        session.write_data(msg, delay=0.0)
        t0 = time.time()
        while time.time() - t0 < 1.0:
            session.poll_telemetry()
            if len(session.read_history) > len(latencies):
                latencies.append(session.read_history[-1]["latency_ms"])
                break
            time.sleep(0.005)

    duration = time.time() - start_total
    session.stop()

    valid_lats = latencies if latencies else [0.0]
    name = f"SharedMemory ({mode_str})"
    return {
        "mechanism": name,
        "samples": len(valid_lats),
        "min_latency_ms": min(valid_lats),
        "avg_latency_ms": statistics.mean(valid_lats),
        "median_latency_ms": statistics.median(valid_lats),
        "max_latency_ms": max(valid_lats),
        "total_time_sec": duration,
        "throughput_msgs_per_sec": len(valid_lats) / duration if duration > 0 else 0,
        "throughput_kb_per_sec": (len(valid_lats) * PAYLOAD_SIZE / 1024.0) / duration if duration > 0 else 0,
    }


def main():
    print("=" * 65)
    print("        IPC DEBUGGER: QUANTITATIVE BENCHMARK HARNESS        ")
    print(f"  Samples: {NUM_SAMPLES} per IPC mechanism | Payload Size: {PAYLOAD_SIZE} bytes")
    print("=" * 65)

    results = []
    results.append(benchmark_pipe())
    results.append(benchmark_queue())
    results.append(benchmark_shared_memory(synchronized=True))
    results.append(benchmark_shared_memory(synchronized=False))

    df = pd.DataFrame(results)
    print("\n" + "=" * 65)
    print("                      BENCHMARK RESULTS                      ")
    print("=" * 65)
    formatters = {
        "min_latency_ms": "{:.3f} ms".format,
        "avg_latency_ms": "{:.3f} ms".format,
        "median_latency_ms": "{:.3f} ms".format,
        "max_latency_ms": "{:.3f} ms".format,
        "throughput_msgs_per_sec": "{:.1f} msg/s".format,
        "throughput_kb_per_sec": "{:.2f} KB/s".format,
    }
    print(df[["mechanism", "avg_latency_ms", "max_latency_ms", "throughput_msgs_per_sec", "throughput_kb_per_sec"]].to_string(index=False))

    # Save results to CSV
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "benchmark_results.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[Saved CSV] {csv_path}")

    # Generate Plotly comparison chart
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["mechanism"],
        y=df["avg_latency_ms"],
        name="Average Latency (ms)",
        marker_color=["#38bdf8", "#10b981", "#f59e0b", "#ef4444"],
    ))
    fig.update_layout(
        title="IPC Mechanism Latency Benchmark Comparison",
        xaxis_title="IPC Mechanism",
        yaxis_title="Average Latency (ms) [Lower is Better]",
        template="plotly_dark",
    )
    chart_html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "benchmark_chart.html")
    fig.write_html(chart_html_path)
    print(f"[Saved Chart HTML] {chart_html_path}")
    print("Benchmark run complete!")


if __name__ == "__main__":
    main()
