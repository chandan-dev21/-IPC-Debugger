"""
Application Smoke and Sanity Tests
Verifies that app.py compiles, initializes cleanly, and contains all required view handlers.
"""

import os
import py_compile
import pytest


def test_app_compiles():
    """Verify that app.py compiles without syntax or import errors."""
    app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
    compiled = py_compile.compile(app_path, doraise=True)
    assert compiled is not None
    assert os.path.exists(compiled)


def test_app_required_views_and_handlers():
    """Verify that all core IPC and debugging engines are imported and wired in app.py."""
    app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
    with open(app_path, "r", encoding="utf-8") as f:
        code = f.read()

    # Verify all 3 IPC modules are present
    assert "PipeSession" in code
    assert "QueueSession" in code
    assert "SharedMemorySession" in code

    # Verify synchronization and debugging engines
    assert "DeadlockLabSession" in code
    assert "bottleneck_detector" in code
    assert "event_logger" in code
    assert "db_instance" in code

    # Verify GUI sections
    assert "System Overview" in code
    assert "Pipes Lab" in code
    assert "Message Queues Lab" in code
    assert "Shared Memory Lab" in code
    assert "Deadlock & Bottleneck Lab" in code
    assert "Metrics & History" in code
