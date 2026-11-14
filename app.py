"""
IPC Debugger - Inter-Process Communication Debugging and Visualization Tool
Futuristic Command Center UI & Diagnostic Console
"""

import os
import sys
import textwrap
import time
from datetime import datetime
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import db_instance
from debugging.bottleneck_detector import bottleneck_detector
from debugging.deadlock_detector import DeadlockLabSession
from debugging.event_logger import event_logger
from ipc.pipe_handler import PipeSession
from ipc.queue_handler import QueueSession
from ipc.shared_memory_handler import SharedMemorySession
from utils.process_manager import ProcessManager

# ---------------------------------------------------------
# Page Configuration & Sci-Fi Command Center Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="IPC // DEBUGGER — Command Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Command Center Theme CSS
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700;800&family=Orbitron:wght@600;800;900&display=swap');

    /* Main Core Layout & Tech Grid Background */
    .stApp {
        background-color: #080D18 !important;
        background-image: 
            linear-gradient(rgba(0, 217, 255, 0.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 217, 255, 0.025) 1px, transparent 1px);
        background-size: 32px 32px;
        color: #F1F5F9;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0B1220 !important;
        border-right: 1px solid #263449;
    }
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
        gap: 0.6rem;
    }

    /* Headings */
    h1, h2, h3, h4, h5, h6 {
        color: #F1F5F9 !important;
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    
    .hud-title {
        font-family: 'Orbitron', 'Inter', sans-serif;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        background: linear-gradient(135deg, #FFFFFF 0%, #00D9FF 70%, #2563EB 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        padding: 0;
    }

    /* Top Command Center HUD Banner */
    .command-header-hud {
        background: rgba(17, 24, 39, 0.85);
        backdrop-filter: blur(12px);
        border: 1px solid #263449;
        border-left: 4px solid #00D9FF;
        border-radius: 6px;
        padding: 16px 22px;
        margin-bottom: 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }
    
    .hud-beacon {
        display: inline-block;
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background-color: #00E5A8;
        box-shadow: 0 0 10px #00E5A8;
        animation: pulse-beacon 2s infinite;
        margin-right: 8px;
    }
    @keyframes pulse-beacon {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 229, 168, 0.7); }
        70% { transform: scale(1.1); box-shadow: 0 0 0 8px rgba(0, 229, 168, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 229, 168, 0); }
    }

    .hud-beacon-red {
        display: inline-block;
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background-color: #FF4560;
        box-shadow: 0 0 10px #FF4560;
        animation: pulse-red 1.2s infinite;
        margin-right: 8px;
    }
    @keyframes pulse-red {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 69, 96, 0.8); }
        70% { transform: scale(1.1); box-shadow: 0 0 0 10px rgba(255, 69, 96, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 69, 96, 0); }
    }

    /* Metric Cards */
    .metric-card-hud {
        background: #111827;
        border: 1px solid #263449;
        border-radius: 6px;
        padding: 16px 20px;
        position: relative;
        overflow: hidden;
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card-hud:hover {
        border-color: #00D9FF;
        box-shadow: 0 6px 18px rgba(0, 217, 255, 0.12);
        transform: translateY(-2px);
    }
    .metric-accent-line {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
    }
    .metric-label-hud {
        font-family: 'Inter', sans-serif;
        color: #94A3B8;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
    }
    .metric-val-hud {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.85rem;
        font-weight: 700;
        color: #F1F5F9;
        letter-spacing: -0.02em;
    }

    /* Process Badge Styles */
    .process-hud-badge {
        background: #172235;
        border: 1px solid #263449;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 12px;
        position: relative;
    }
    .badge-status-pill {
        display: inline-block;
        padding: 3px 8px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        font-weight: 700;
        border-radius: 4px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .pill-running {
        background: rgba(0, 229, 168, 0.12);
        color: #00E5A8;
        border: 1px solid #00E5A8;
    }
    .pill-stopped {
        background: rgba(255, 69, 96, 0.12);
        color: #FF4560;
        border: 1px solid #FF4560;
    }
    .pill-active-cyan {
        background: rgba(0, 217, 255, 0.12);
        color: #00D9FF;
        border: 1px solid #00D9FF;
    }

    /* Terminal Console Window */
    .terminal-hud {
        background-color: #050811;
        border: 1px solid #263449;
        border-top: 3px solid #2563EB;
        border-radius: 6px;
        padding: 14px 18px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
        max-height: 300px;
        overflow-y: auto;
        color: #CBD5E1;
        box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.7);
    }
    .terminal-row {
        margin-bottom: 4px;
        line-height: 1.45;
        display: flex;
        gap: 8px;
    }
    .t-time { color: #64748B; font-weight: 500; }
    .t-info { color: #00D9FF; }
    .t-success { color: #00E5A8; }
    .t-warn { color: #FFB020; }
    .t-error { color: #FF4560; }
    .t-proc { color: #8B5CF6; font-weight: 600; }

    /* Button Enhancements */
    .stButton>button {
        background-color: #172235;
        color: #F1F5F9;
        border: 1px solid #263449;
        border-radius: 5px;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 0.85rem;
        letter-spacing: 0.03em;
        transition: all 0.2s ease;
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover {
        background-color: #1E2E48;
        border-color: #00D9FF;
        color: #00D9FF;
        box-shadow: 0 0 12px rgba(0, 217, 255, 0.2);
    }
    .stButton>button:active {
        transform: scale(0.98);
    }

    /* Form Inputs & Sliders */
    div[data-testid="stTextInput"] input {
        background-color: #0B1220 !important;
        border: 1px solid #263449 !important;
        color: #F1F5F9 !important;
        border-radius: 5px;
        font-family: 'JetBrains Mono', monospace;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: #00D9FF !important;
        box-shadow: 0 0 8px rgba(0, 217, 255, 0.2) !important;
    }
    
    div[data-testid="stSelectbox"] div[data-baseweb="select"] {
        background-color: #0B1220 !important;
        border: 1px solid #263449 !important;
        border-radius: 5px;
        color: #F1F5F9 !important;
    }

    /* Table Container Styling */
    div[data-testid="stDataFrame"] {
        border: 1px solid #263449;
        border-radius: 6px;
        background-color: #0B1220;
    }

    /* Custom Radio Navigation */
    div[data-testid="stRadio"] > div {
        background: transparent;
        gap: 6px;
    }
    div[data-testid="stRadio"] label {
        background: #111827;
        border: 1px solid #263449;
        border-radius: 5px;
        padding: 8px 14px;
        margin-bottom: 2px;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    div[data-testid="stRadio"] label:hover {
        border-color: #00D9FF;
        background: #172235;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Session State Initialization (Preserving Working Handlers)
# ---------------------------------------------------------
if "pipe_session" not in st.session_state:
    st.session_state.pipe_session = PipeSession()

if "queue_session" not in st.session_state:
    st.session_state.queue_session = QueueSession(maxsize=30)

if "shm_session" not in st.session_state:
    st.session_state.shm_session = SharedMemorySession(size=2048, synchronized=True)

if "deadlock_session" not in st.session_state:
    st.session_state.deadlock_session = DeadlockLabSession(timeout=3.5)

if "proc_manager" not in st.session_state:
    st.session_state.proc_manager = ProcessManager()

if "latency_threshold" not in st.session_state:
    st.session_state.latency_threshold = 25.0

if "backlog_threshold" not in st.session_state:
    st.session_state.backlog_threshold = 5


# Poll all background telemetry queues
st.session_state.pipe_session.poll_telemetry()
st.session_state.queue_session.poll_telemetry()
st.session_state.shm_session.poll_telemetry()
deadlock_graph_state = st.session_state.deadlock_session.poll_telemetry()


# ---------------------------------------------------------
# Sidebar Redesign: Futuristic Command Navigation
# ---------------------------------------------------------
with st.sidebar:
    # Sidebar Header
    st.markdown(
        """
        <div style="padding: 10px 4px 18px 4px; border-bottom: 1px solid #263449; margin-bottom: 12px;">
            <div style="display:flex; align-items:center; gap:10px;">
                <div style="background: rgba(0, 217, 255, 0.15); border: 1px solid #00D9FF; width: 34px; height: 34px; border-radius: 6px; display:flex; align-items:center; justify-content:center; color:#00D9FF; font-weight:800; font-family:'Orbitron';">
                    ⚡
                </div>
                <div>
                    <div style="font-family:'Orbitron', sans-serif; font-size:1.1rem; font-weight:800; letter-spacing:0.08em; color:#F1F5F9;">
                        IPC <span style="color:#00D9FF;">//</span> DEBUGGER
                    </div>
                    <div style="font-family:'JetBrains Mono', monospace; font-size:0.65rem; color:#94A3B8; letter-spacing:0.1em; text-transform:uppercase;">
                        OPERATING SYSTEM INTELLIGENCE
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='font-family:\"JetBrains Mono\", monospace; font-size:0.7rem; color:#94A3B8; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:4px;'>CONSOLE NAVIGATION</div>",
        unsafe_allow_html=True,
    )

    menu_option = st.radio(
        "Console Navigation",
        [
            "System Overview",
            "Pipes Lab",
            "Message Queues Lab",
            "Shared Memory Lab",
            "Deadlock & Bottleneck Lab",
            "Metrics & History",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-family:\"JetBrains Mono\", monospace; font-size:0.7rem; color:#94A3B8; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px;'>DIAGNOSTIC CONTROLS</div>",
        unsafe_allow_html=True,
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 Sync", use_container_width=True, help="Force refresh telemetry from OS processes"):
            st.rerun()
    with col_btn2:
        if st.button("🛑 Abort All", use_container_width=True, help="Emergency abort: Terminate all active child processes"):
            st.session_state.pipe_session.stop()
            st.session_state.queue_session.stop()
            st.session_state.shm_session.stop()
            st.session_state.deadlock_session.stop()
            event_logger.log("SYSTEM", "WARNING", "Emergency manual abort: All IPC workers killed.")
            st.rerun()

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-family:\"JetBrains Mono\", monospace; font-size:0.7rem; color:#94A3B8; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px;'>PROFILING THRESHOLDS</div>",
        unsafe_allow_html=True,
    )
    st.session_state.latency_threshold = st.slider(
        "Latency Alert (ms)", min_value=5.0, max_value=200.0, value=25.0, step=5.0
    )
    st.session_state.backlog_threshold = st.slider(
        "Queue Backlog Alert", min_value=1, max_value=20, value=5, step=1
    )
    bottleneck_detector.latency_threshold_ms = st.session_state.latency_threshold
    bottleneck_detector.backlog_threshold = st.session_state.backlog_threshold

    # Sidebar Bottom System Health Indicator
    st.markdown(
        """
        <div style="margin-top: 24px; padding: 12px; background: #0E1726; border: 1px solid #263449; border-radius: 6px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <span style="font-family:'JetBrains Mono', monospace; font-size:0.7rem; color:#94A3B8;">SUBSYSTEM:</span>
                <span style="font-family:'JetBrains Mono', monospace; font-size:0.7rem; color:#00E5A8; font-weight:700;">WIN_SPAWN_OK</span>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <span style="font-family:'JetBrains Mono', monospace; font-size:0.7rem; color:#94A3B8;">PROCESS ENGINE:</span>
                <span style="font-family:'JetBrains Mono', monospace; font-size:0.7rem; color:#00D9FF;">X86_64 MULTIPROC</span>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-family:'JetBrains Mono', monospace; font-size:0.7rem; color:#94A3B8;">AUDIT STORE:</span>
                <span style="font-family:'JetBrains Mono', monospace; font-size:0.7rem; color:#8B5CF6;">SQLITE_ACTIVE</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Reusable UI Component Helpers
# ---------------------------------------------------------
def render_main_hud_header(subtitle: str = "INTER-PROCESS COMMUNICATION CONTROL CENTER"):
    """Renders the top command center header."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.markdown(
        f"""
        <div class="command-header-hud">
            <div>
                <div style="display:flex; align-items:center;">
                    <span class="hud-beacon"></span>
                    <span style="font-family:'Orbitron', sans-serif; font-size:1.35rem; font-weight:800; letter-spacing:0.06em; color:#F1F5F9;">
                        IPC DEBUGGER
                    </span>
                    <span style="color:#263449; margin: 0 12px;">|</span>
                    <span style="font-family:'JetBrains Mono', monospace; font-size:0.75rem; color:#00E5A8; font-weight:700; letter-spacing:0.08em;">
                        SYSTEM STATUS: ONLINE
                    </span>
                </div>
                <div style="font-family:'JetBrains Mono', monospace; font-size:0.72rem; color:#94A3B8; margin-top:4px; letter-spacing:0.05em;">
                    {subtitle}
                </div>
            </div>
            <div style="text-align:right;">
                <div style="font-family:'JetBrains Mono', monospace; font-size:0.8rem; color:#00D9FF; font-weight:700;">
                    {now_str}
                </div>
                <div style="font-family:'JetBrains Mono', monospace; font-size:0.68rem; color:#94A3B8; margin-top:2px;">
                    ARCHITECTURE: WINDOWS MULTIPROCESSING
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: Any, accent_color: str = "#00D9FF", icon: str = "◈"):
    """Generates an elevated HUD metric card."""
    return f"""
    <div class="metric-card-hud">
        <div class="metric-accent-line" style="background: {accent_color}; box-shadow: 0 0 10px {accent_color};"></div>
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div class="metric-label-hud">{label}</div>
            <span style="color: {accent_color}; font-size: 0.9rem;">{icon}</span>
        </div>
        <div class="metric-val-hud" style="color: #F1F5F9;">{value}</div>
    </div>
    """


def render_process_badge_hud(name: str, pid: Any, alive: bool):
    """Renders a process state module with PID and status pill."""
    if alive:
        return f"""
        <div class="process-hud-badge" style="border-left: 3px solid #00E5A8;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:700; color:#F1F5F9; font-size:0.9rem;">{name}</span>
                <span class="badge-status-pill pill-running">ONLINE</span>
            </div>
            <div style="font-family:'JetBrains Mono', monospace; font-size:0.75rem; color:#94A3B8; margin-top:6px;">
                OS_PID: <b style="color:#00D9FF;">{pid}</b> | STATE: <span style="color:#00E5A8;">DISPATCHED</span>
            </div>
        </div>
        """
    else:
        return f"""
        <div class="process-hud-badge" style="border-left: 3px solid #263449; opacity: 0.85;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:600; color:#94A3B8; font-size:0.9rem;">{name}</span>
                <span class="badge-status-pill pill-stopped">OFFLINE</span>
            </div>
            <div style="font-family:'JetBrains Mono', monospace; font-size:0.75rem; color:#64748B; margin-top:6px;">
                OS_PID: <span style="color:#64748B;">NONE</span> | STATE: STANDBY
            </div>
        </div>
        """


def render_terminal_logs_hud(filter_type: str = "ALL"):
    """Renders high-tech monospace terminal logging console."""
    recent_events = event_logger.get_recent(40, filter_type=filter_type)
    if not recent_events:
        st.markdown(
            """
            <div class="terminal-hud">
                <div class="terminal-row">
                    <span class="t-time">[00:00:00]</span>
                    <span class="t-info">[INFO]</span>
                    <span>System kernel ready. Awaiting IPC telemetry stream...</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    html_lines = []
    for ev in recent_events:
        sev = ev["severity"]
        cls = "t-info"
        if sev == "SUCCESS":
            cls = "t-success"
        elif sev == "WARNING":
            cls = "t-warn"
        elif sev == "ERROR":
            cls = "t-error"

        line = (
            f"<div class='terminal-row'>"
            f"<span class='t-time'>[{ev['time_str']}]</span>"
            f"<span class='{cls}'>[{ev['severity']}]</span>"
            f"<span class='t-proc'>{ev['process_name']}:</span>"
            f"<span>{ev['message']}</span>"
            f"</div>"
        )
        html_lines.append(line)

    content = "".join(html_lines)
    st.markdown(f"<div class='terminal-hud'>{content}</div>", unsafe_allow_html=True)


def _sanitize_svg(svg_code: str) -> str:
    """
    Sanitize SVG markup by dedenting and stripping leading/trailing whitespace from each line.
    Prevents Streamlit Markdown / CommonMark from treating indented lines as <pre><code> blocks.
    """
    dedented = textwrap.dedent(svg_code).strip()
    return "\n".join(line.strip() for line in dedented.splitlines() if line.strip())


def render_cinematic_architecture_svg():
    """Generates the centerpiece futuristic IPC Architecture HUD Visualization."""
    svg = """
    <svg width="100%" height="260" viewBox="0 0 960 260" xmlns="http://www.w3.org/2000/svg" style="background:#080D18; border:1px solid #263449; border-radius:6px; box-shadow: 0 4px 20px rgba(0,0,0,0.6);">
        <defs>
            <marker id="cyan-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 8 5 L 0 9 z" fill="#00D9FF" />
            </marker>
            <marker id="green-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 8 5 L 0 9 z" fill="#00E5A8" />
            </marker>
            <marker id="purple-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 8 5 L 0 9 z" fill="#8B5CF6" />
            </marker>
            <linearGradient id="cyan-glow" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#00D9FF" stop-opacity="0.8"/>
                <stop offset="100%" stop-color="#2563EB" stop-opacity="0.8"/>
            </linearGradient>
            <linearGradient id="purple-glow" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#8B5CF6" stop-opacity="0.8"/>
                <stop offset="100%" stop-color="#00D9FF" stop-opacity="0.8"/>
            </linearGradient>
        </defs>

        <!-- Background HUD Grid Elements -->
        <line x1="20" y1="20" x2="28" y2="20" stroke="#00D9FF" stroke-width="2" />
        <line x1="20" y1="20" x2="20" y2="28" stroke="#00D9FF" stroke-width="2" />
        <line x1="940" y1="20" x2="932" y2="20" stroke="#00D9FF" stroke-width="2" />
        <line x1="940" y1="20" x2="940" y2="28" stroke="#00D9FF" stroke-width="2" />
        <line x1="20" y1="240" x2="28" y2="240" stroke="#00D9FF" stroke-width="2" />
        <line x1="20" y1="240" x2="20" y2="232" stroke="#00D9FF" stroke-width="2" />
        <line x1="940" y1="240" x2="932" y2="240" stroke="#00D9FF" stroke-width="2" />
        <line x1="940" y1="240" x2="940" y2="232" stroke="#00D9FF" stroke-width="2" />

        <!-- 1. PIPES SUB-SYSTEM -->
        <rect x="30" y="30" width="280" height="200" rx="6" fill="#111827" stroke="#263449" stroke-width="1.2" />
        <rect x="30" y="30" width="280" height="30" rx="6" fill="#172235" />
        <text x="45" y="50" fill="#00D9FF" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="bold">◈ PIPES [DUPLEX STREAM]</text>
        <circle cx="290" cy="45" r="4" fill="#00D9FF" />

        <rect x="45" y="80" width="65" height="55" rx="4" fill="#172235" stroke="#00D9FF" stroke-width="1" />
        <text x="52" y="105" fill="#F1F5F9" font-family="'Inter', sans-serif" font-size="11" font-weight="bold">PROC A</text>
        <text x="52" y="120" fill="#00D9FF" font-family="'JetBrains Mono', monospace" font-size="8">PORT 1</text>

        <rect x="135" y="75" width="70" height="65" rx="4" fill="#0B1220" stroke="#263449" stroke-width="1.5" />
        <text x="142" y="98" fill="#F1F5F9" font-family="'JetBrains Mono', monospace" font-size="9" font-weight="bold">KERNEL</text>
        <text x="140" y="112" fill="#00D9FF" font-family="'JetBrains Mono', monospace" font-size="8">BYTE_STREAM</text>
        <line x1="145" y1="125" x2="195" y2="125" stroke="#00D9FF" stroke-dasharray="2,2" stroke-width="1" />

        <rect x="230" y="80" width="65" height="55" rx="4" fill="#172235" stroke="#00D9FF" stroke-width="1" />
        <text x="237" y="105" fill="#F1F5F9" font-family="'Inter', sans-serif" font-size="11" font-weight="bold">PROC B</text>
        <text x="237" y="120" fill="#00D9FF" font-family="'JetBrains Mono', monospace" font-size="8">PORT 2</text>

        <line x1="110" y1="98" x2="133" y2="98" stroke="#00D9FF" stroke-width="2" marker-end="url(#cyan-arrow)" />
        <line x1="205" y1="98" x2="228" y2="98" stroke="#00D9FF" stroke-width="2" marker-end="url(#cyan-arrow)" />
        <line x1="230" y1="118" x2="207" y2="118" stroke="#00E5A8" stroke-width="1.5" stroke-dasharray="3,3" marker-end="url(#green-arrow)" />
        <line x1="135" y1="118" x2="112" y2="118" stroke="#00E5A8" stroke-width="1.5" stroke-dasharray="3,3" marker-end="url(#green-arrow)" />
        
        <text x="45" y="165" fill="#94A3B8" font-family="'JetBrains Mono', monospace" font-size="9">Channel: OS Kernel Pipe Buffer</text>
        <text x="45" y="180" fill="#94A3B8" font-family="'JetBrains Mono', monospace" font-size="9">Mode: Full Duplex Point-to-Point</text>
        <text x="45" y="195" fill="#00D9FF" font-family="'JetBrains Mono', monospace" font-size="9">Latency Benchmark: ~7.78 ms</text>

        <!-- 2. MESSAGE QUEUES SUB-SYSTEM -->
        <rect x="340" y="30" width="280" height="200" rx="6" fill="#111827" stroke="#263449" stroke-width="1.2" />
        <rect x="340" y="30" width="280" height="30" rx="6" fill="#172235" />
        <text x="355" y="50" fill="#00E5A8" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="bold">◈ MESSAGE QUEUE [FIFO]</text>
        <circle cx="600" cy="45" r="4" fill="#00E5A8" />

        <rect x="355" y="80" width="65" height="55" rx="4" fill="#172235" stroke="#00E5A8" stroke-width="1" />
        <text x="360" y="105" fill="#F1F5F9" font-family="'Inter', sans-serif" font-size="10" font-weight="bold">PRODUCER</text>
        <text x="367" y="120" fill="#00E5A8" font-family="'JetBrains Mono', monospace" font-size="8">TX_NODE</text>

        <rect x="445" y="75" width="70" height="65" rx="4" fill="#0B1220" stroke="#00E5A8" stroke-width="1.2" />
        <text x="450" y="95" fill="#F1F5F9" font-family="'JetBrains Mono', monospace" font-size="9" font-weight="bold">QUEUE BUF</text>
        <rect x="452" y="103" width="12" height="18" fill="#172235" stroke="#263449" />
        <rect x="466" y="103" width="12" height="18" fill="#00E5A8" />
        <rect x="480" y="103" width="12" height="18" fill="#00E5A8" />
        <text x="452" y="132" fill="#94A3B8" font-family="'JetBrains Mono', monospace" font-size="7">FIFO SLOTS</text>

        <rect x="540" y="80" width="65" height="55" rx="4" fill="#172235" stroke="#00E5A8" stroke-width="1" />
        <text x="545" y="105" fill="#F1F5F9" font-family="'Inter', sans-serif" font-size="10" font-weight="bold">CONSUMER</text>
        <text x="552" y="120" fill="#00E5A8" font-family="'JetBrains Mono', monospace" font-size="8">RX_NODE</text>

        <line x1="420" y1="105" x2="443" y2="105" stroke="#00E5A8" stroke-width="2" marker-end="url(#green-arrow)" />
        <line x1="515" y1="105" x2="538" y2="105" stroke="#00E5A8" stroke-width="2" marker-end="url(#green-arrow)" />

        <text x="355" y="165" fill="#94A3B8" font-family="'JetBrains Mono', monospace" font-size="9">Buffer: Semaphore Bounded FIFO</text>
        <text x="355" y="180" fill="#94A3B8" font-family="'JetBrains Mono', monospace" font-size="9">Throughput: ~33.8 msgs/sec</text>
        <text x="355" y="195" fill="#00E5A8" font-family="'JetBrains Mono', monospace" font-size="9">Backlog & Starvation Monitored</text>

        <!-- 3. SHARED MEMORY SUB-SYSTEM -->
        <rect x="650" y="30" width="280" height="200" rx="6" fill="#111827" stroke="#263449" stroke-width="1.2" />
        <rect x="650" y="30" width="280" height="30" rx="6" fill="#172235" />
        <text x="665" y="50" fill="#8B5CF6" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="bold">◈ SHARED MEMORY [ZERO-COPY]</text>
        <circle cx="910" cy="45" r="4" fill="#8B5CF6" />

        <rect x="665" y="80" width="60" height="55" rx="4" fill="#172235" stroke="#8B5CF6" stroke-width="1" />
        <text x="674" y="105" fill="#F1F5F9" font-family="'Inter', sans-serif" font-size="11" font-weight="bold">WRITER</text>
        <text x="677" y="120" fill="#8B5CF6" font-family="'JetBrains Mono', monospace" font-size="8">PROC 1</text>

        <rect x="745" y="72" width="90" height="70" rx="4" fill="#0B1220" stroke="#8B5CF6" stroke-width="1.5" />
        <text x="752" y="93" fill="#F1F5F9" font-family="'JetBrains Mono', monospace" font-size="9" font-weight="bold">SHARED RAM</text>
        <text x="755" y="107" fill="#00D9FF" font-family="'JetBrains Mono', monospace" font-size="8">4096B BLOCK</text>
        <rect x="752" y="115" width="76" height="16" rx="2" fill="#172235" stroke="#8B5CF6" />
        <text x="756" y="127" fill="#8B5CF6" font-family="'JetBrains Mono', monospace" font-size="8">MUTEX LOCK</text>

        <rect x="855" y="80" width="60" height="55" rx="4" fill="#172235" stroke="#8B5CF6" stroke-width="1" />
        <text x="864" y="105" fill="#F1F5F9" font-family="'Inter', sans-serif" font-size="11" font-weight="bold">READER</text>
        <text x="867" y="120" fill="#8B5CF6" font-family="'JetBrains Mono', monospace" font-size="8">PROC 2</text>

        <line x1="725" y1="102" x2="743" y2="102" stroke="#8B5CF6" stroke-width="2" marker-end="url(#purple-arrow)" />
        <line x1="835" y1="102" x2="853" y2="102" stroke="#8B5CF6" stroke-width="2" marker-end="url(#purple-arrow)" />

        <text x="665" y="165" fill="#94A3B8" font-family="'JetBrains Mono', monospace" font-size="9">Access: Direct Physical RAM Mapping</text>
        <text x="665" y="180" fill="#94A3B8" font-family="'JetBrains Mono', monospace" font-size="9">Synchronization: mp.Lock Guarded</text>
        <text x="665" y="195" fill="#8B5CF6" font-family="'JetBrains Mono', monospace" font-size="9">Demonstrates Race Conditions & Torn Writes</text>
    </svg>
    """
    return _sanitize_svg(svg)


def render_rag_svg_hud(allocations: dict[str, str], requests: dict[str, str], has_deadlock: bool):
    """Generates the Resource Allocation Graph (RAG) visualization."""
    cycle_banner = ""
    if has_deadlock:
        cycle_banner = """
        <rect x="150" y="8" width="300" height="26" rx="4" fill="rgba(255, 69, 96, 0.2)" stroke="#FF4560" stroke-width="1.5" />
        <circle cx="166" cy="21" r="5" fill="#FF4560" />
        <text x="180" y="25" fill="#FF4560" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="bold">CIRCULAR WAIT DETECTED: DEADLOCK</text>
        """

    # Dynamic Allocation Edges (Lock -> Process)
    alloc_svg = ""
    for lock, proc in allocations.items():
        if "A" in lock and "1" in proc:
            alloc_svg += '<path d="M 270 58 Q 180 62 145 92" fill="none" stroke="#00E5A8" stroke-width="2.5" marker-end="url(#rag-green)" />'
            alloc_svg += '<text x="175" y="66" fill="#00E5A8" font-family="\'JetBrains Mono\', monospace" font-size="10" font-weight="bold">HELD_BY</text>'
        elif "B" in lock and "2" in proc:
            alloc_svg += '<path d="M 330 170 Q 420 166 455 135" fill="none" stroke="#00E5A8" stroke-width="2.5" marker-end="url(#rag-green)" />'
            alloc_svg += '<text x="375" y="172" fill="#00E5A8" font-family="\'JetBrains Mono\', monospace" font-size="10" font-weight="bold">HELD_BY</text>'
        elif "A" in lock and "2" in proc:
            alloc_svg += '<path d="M 330 58 Q 420 62 455 92" fill="none" stroke="#00E5A8" stroke-width="2.5" marker-end="url(#rag-green)" />'
        elif "B" in lock and "1" in proc:
            alloc_svg += '<path d="M 270 170 Q 180 166 145 135" fill="none" stroke="#00E5A8" stroke-width="2.5" marker-end="url(#rag-green)" />'

    # Dynamic Request Edges (Process -> Lock)
    req_svg = ""
    for proc, lock in requests.items():
        if "1" in proc and "B" in lock:
            req_svg += '<path d="M 145 135 Q 180 175 268 178" fill="none" stroke="#FF4560" stroke-width="2.5" stroke-dasharray="4,3" marker-end="url(#rag-red)" />'
            req_svg += '<text x="160" y="165" fill="#FF4560" font-family="\'JetBrains Mono\', monospace" font-size="10" font-weight="bold">WAITING_FOR</text>'
        elif "2" in proc and "A" in lock:
            req_svg += '<path d="M 455 92 Q 420 52 332 50" fill="none" stroke="#FF4560" stroke-width="2.5" stroke-dasharray="4,3" marker-end="url(#rag-red)" />'
            req_svg += '<text x="375" y="60" fill="#FF4560" font-family="\'JetBrains Mono\', monospace" font-size="10" font-weight="bold">WAITING_FOR</text>'

    svg = f"""
    <svg width="100%" height="240" viewBox="0 0 600 240" xmlns="http://www.w3.org/2000/svg" style="background:#080D18; border:1px solid #263449; border-radius:6px;">
        <defs>
            <marker id="rag-green" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 8 5 L 0 9 z" fill="#00E5A8" />
            </marker>
            <marker id="rag-red" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 8 5 L 0 9 z" fill="#FF4560" />
            </marker>
        </defs>

        {cycle_banner}

        <!-- Process 1 Node (Circle) -->
        <circle cx="120" cy="115" r="34" fill="#111827" stroke="#00D9FF" stroke-width="2" />
        <text x="96" y="115" fill="#F1F5F9" font-family="'Inter', sans-serif" font-size="11" font-weight="bold">PROC 1</text>
        <text x="100" y="130" fill="#00D9FF" font-family="'JetBrains Mono', monospace" font-size="8">THREAD P1</text>

        <!-- Process 2 Node (Circle) -->
        <circle cx="480" cy="115" r="34" fill="#111827" stroke="#00D9FF" stroke-width="2" />
        <text x="456" y="115" fill="#F1F5F9" font-family="'Inter', sans-serif" font-size="11" font-weight="bold">PROC 2</text>
        <text x="460" y="130" fill="#00D9FF" font-family="'JetBrains Mono', monospace" font-size="8">THREAD P2</text>

        <!-- Lock A Node (Square) -->
        <rect x="270" y="32" width="60" height="42" rx="4" fill="#172235" stroke="#8B5CF6" stroke-width="2" />
        <text x="282" y="56" fill="#F1F5F9" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="bold">LOCK A</text>

        <!-- Lock B Node (Square) -->
        <rect x="270" y="155" width="60" height="42" rx="4" fill="#172235" stroke="#8B5CF6" stroke-width="2" />
        <text x="282" y="180" fill="#F1F5F9" font-family="'JetBrains Mono', monospace" font-size="11" font-weight="bold">LOCK B</text>

        <!-- Edges -->
        {alloc_svg}
        {req_svg}
    </svg>
    """
    return _sanitize_svg(svg)


# ---------------------------------------------------------
# VIEW 1: System Overview (Command Center Centerpiece)
# ---------------------------------------------------------
if menu_option == "System Overview":
    render_main_hud_header("SYSTEM OVERVIEW // ARCHITECTURE & PERFORMANCE TELEMETRY")

    metrics = db_instance.get_metrics_summary()

    # 4 Major Premium Metric Cards
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            render_metric_card("TOTAL MESSAGES TRANSFERRED", metrics["total_messages"], "#00D9FF", "⇄"),
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            render_metric_card("SUCCESSFULLY DELIVERED", metrics["delivered"], "#00E5A8", "✓"),
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            render_metric_card("AVERAGE LATENCY", f"{metrics['avg_latency_ms']} ms", "#2563EB", "◷"),
            unsafe_allow_html=True,
        )
    with m4:
        deadlock_color = "#FF4560" if metrics["deadlocks_detected"] > 0 else "#94A3B8"
        st.markdown(
            render_metric_card("DEADLOCKS DETECTED", metrics["deadlocks_detected"], deadlock_color, "⚠"),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
    st.markdown("### ◈ INTER-PROCESS COMMUNICATION TOPOLOGY")
    st.components.v1.html(
        render_cinematic_architecture_svg(),
        height=280,
        scrolling=False,
    )

    col_left, col_right = st.columns([1.1, 0.9])

    with col_left:
        st.markdown("### ◈ IPC MECHANISMS MATRIX")
        st.markdown(
            """
            | Primitive | Kernel Mechanism | Data Transfer | Synchronization | Primary Failure Mode |
            | :--- | :--- | :--- | :--- | :--- |
            | **Pipes** | Kernel Byte-Stream Buffer | Serialized 2-Copy (User $\\to$ Kernel $\\to$ User) | Implicit Kernel Blocking | Broken Pipe, Blocking `recv` |
            | **Message Queues** | Thread-safe Semaphore Queue | Discrete Packets via Feeder Thread | Built-in Process Lock | Backpressure, Queue Saturation |
            | **Shared Memory** | Direct Virtual RAM Mapping | **Zero-Copy Direct Access** | Explicit (`mp.Lock` required) | **Race Conditions, Torn Writes, Deadlocks** |
            """
        )

    with col_right:
        st.markdown("### ◈ REAL-TIME BOTTLENECK DIAGNOSTICS")
        recent_msgs = db_instance.get_recent_messages(limit=30)
        reports = bottleneck_detector.analyze_message_latencies(recent_msgs)

        if reports:
            for rep in reports:
                icon = "⚠️" if rep.severity == "WARNING" else "🚨"
                border_col = "#FFB020" if rep.severity == "WARNING" else "#FF4560"
                st.markdown(
                    f"""
                    <div style="background:#111827; border:1px solid {border_col}; border-left:4px solid {border_col}; padding:14px; border-radius:5px; margin-bottom:10px;">
                        <div style="font-weight:700; color:#F1F5F9; font-size:0.9rem;">{icon} {rep.title} ({rep.category})</div>
                        <div style="font-size:0.8rem; color:#94A3B8; margin-top:4px;">{rep.description}</div>
                        <div style="font-family:'JetBrains Mono', monospace; font-size:0.75rem; color:#00D9FF; margin-top:6px;">ACTION: {rep.recommendation}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                """
                <div style="background:#111827; border:1px solid #263449; border-left:4px solid #00E5A8; padding:16px; border-radius:5px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span class="hud-beacon"></span>
                        <span style="font-weight:700; color:#00E5A8;">SYSTEM TELEMETRY NOMINAL</span>
                    </div>
                    <div style="font-size:0.8rem; color:#94A3B8; margin-top:6px;">
                        No communication latency bottlenecks or buffer overflows detected under current operational thresholds.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------
# VIEW 2: Pipes Lab (Futuristic Dedicated Workspace)
# ---------------------------------------------------------
elif menu_option == "Pipes Lab":
    render_main_hud_header("PIPES SIMULATION LAB // DUPLEX POINT-TO-POINT STREAM")

    pipe_sess: PipeSession = st.session_state.pipe_session
    status = pipe_sess.get_process_status()

    # Process A and Process B Status Panels
    c_proc1, c_proc2, c_controls = st.columns([1, 1, 1.2])

    with c_proc1:
        st.markdown(
            render_process_badge_hud(
                "Process A (Sender / Port 1)",
                status["proc_a"]["pid"],
                status["proc_a"]["alive"],
            ),
            unsafe_allow_html=True,
        )

    with c_proc2:
        st.markdown(
            render_process_badge_hud(
                "Process B (Receiver / Port 2)",
                status["proc_b"]["pid"],
                status["proc_b"]["alive"],
            ),
            unsafe_allow_html=True,
        )

    with c_controls:
        st.markdown(
            "<div style='font-family:\"JetBrains Mono\", monospace; font-size:0.75rem; color:#94A3B8; margin-bottom:6px;'>SESSION CONTROL</div>",
            unsafe_allow_html=True,
        )
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if not status["is_running"]:
                if st.button("▶ Start Engine", key="start_pipe", use_container_width=True):
                    success, msg = pipe_sess.start()
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun()
            else:
                if st.button("⏹ Stop Engine", key="stop_pipe", use_container_width=True):
                    pipe_sess.stop()
                    st.rerun()
        with btn_col2:
            st.markdown(
                f"""
                <div style="background:#172235; border:1px solid #263449; border-radius:5px; padding:7px 12px; text-align:center;">
                    <div style="font-size:0.65rem; color:#94A3B8; font-family:'JetBrains Mono';">DELIVERED</div>
                    <div style="font-size:1.1rem; color:#00D9FF; font-weight:700; font-family:'JetBrains Mono';">{len(pipe_sess.received_messages)} msgs</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Message Transmission Form & Bus Diagram
    col_input, col_sim = st.columns([1.6, 1.4])

    with col_input:
        st.markdown("### ◈ TRANSMIT PAYLOAD ACROSS DUPLEX PIPE")
        with st.form("pipe_send_form", clear_on_submit=False):
            sender_choice = st.selectbox(
                "Origin Process",
                ["Process_A (Sends to Process_B)", "Process_B (Sends to Process_A)"],
            )
            msg_payload = st.text_input(
                "Payload String",
                value="TELEMETRY_PACKET_VERIFICATION_TOKEN_X7",
            )
            sim_delay = st.slider(
                "Inject Transmission Delay / Latency (seconds)",
                min_value=0.0,
                max_value=1.5,
                value=0.0,
                step=0.05,
                help="Simulate heavy serialization or network lag across pipe buffers.",
            )
            submit = st.form_submit_button("🚀 Dispatch Message Across Pipe", use_container_width=True)

            if submit:
                if not status["is_running"]:
                    st.error("Cannot dispatch: Process session is currently offline. Click '▶ Start Engine'.")
                else:
                    sender_key = "A" if "Process_A" in sender_choice else "B"
                    sent = pipe_sess.send_message(sender_key, msg_payload, delay=sim_delay)
                    if sent:
                        st.info("Payload dispatched into pipe buffer.")
                        time.sleep(0.1 + sim_delay)
                        pipe_sess.poll_telemetry()
                        st.rerun()

    with col_sim:
        st.markdown("### ◈ DUPLEX PIPE BUS TOPOLOGY")
        channel_color = "#00D9FF" if status["is_running"] else "#263449"
        pulse_tag = "CONNECTED (DUPLEX)" if status["is_running"] else "CHANNEL CLOSED"
        st.markdown(
            f"""
            <div style="background:#080D18; border:1px solid #263449; border-radius:6px; padding:20px 16px; text-align:center;">
                <div style="display:flex; justify-content:space-around; align-items:center; margin-bottom:14px;">
                    <div style="background:#111827; padding:12px 18px; border-radius:5px; border:1px solid #00D9FF;">
                        <div style="font-weight:700; color:#F1F5F9; font-size:0.9rem;">PROCESS A</div>
                        <div style="font-family:'JetBrains Mono'; font-size:0.75rem; color:#00D9FF;">PID: {status['proc_a']['pid'] or 'OFF'}</div>
                    </div>
                    <div style="color:{channel_color}; font-size:1.8rem; font-weight:bold; letter-spacing:4px;">⇄</div>
                    <div style="background:#172235; padding:12px 18px; border-radius:5px; border:1px solid {channel_color};">
                        <div style="font-weight:700; color:#00D9FF; font-size:0.9rem;">KERNEL BUFFER</div>
                        <div style="font-family:'JetBrains Mono'; font-size:0.75rem; color:#94A3B8;">OS PIPE STREAM</div>
                    </div>
                    <div style="color:{channel_color}; font-size:1.8rem; font-weight:bold; letter-spacing:4px;">⇄</div>
                    <div style="background:#111827; padding:12px 18px; border-radius:5px; border:1px solid #00D9FF;">
                        <div style="font-weight:700; color:#F1F5F9; font-size:0.9rem;">PROCESS B</div>
                        <div style="font-family:'JetBrains Mono'; font-size:0.75rem; color:#00D9FF;">PID: {status['proc_b']['pid'] or 'OFF'}</div>
                    </div>
                </div>
                <div style="font-family:'JetBrains Mono', monospace; font-size:0.8rem; color:#94A3B8;">
                    CHANNEL STATUS: <span style="color:{'#00E5A8' if status['is_running'] else '#FF4560'}; font-weight:700;">{pulse_tag}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Received Messages & History
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.markdown("### ◈ PIPE TRANSMISSION AUDIT LOG")
    if pipe_sess.received_messages:
        df_pipe = pd.DataFrame(pipe_sess.received_messages)
        df_pipe["timestamp_str"] = df_pipe["timestamp"].apply(
            lambda t: time.strftime("%H:%M:%S", time.localtime(t))
        )
        st.dataframe(
            df_pipe[["msg_id", "sender", "receiver", "payload", "latency_ms", "timestamp_str"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No messages received in current session yet. Dispatch messages above to populate audit log.")

    # Console
    st.markdown("### ◈ PIPES DEBUGGING CONSOLE")
    render_terminal_logs_hud(filter_type="PIPE")


# ---------------------------------------------------------
# VIEW 3: Message Queues Lab (Producer - Consumer)
# ---------------------------------------------------------
elif menu_option == "Message Queues Lab":
    render_main_hud_header("MESSAGE QUEUES LAB // PRODUCER - CONSUMER BUFFER DYNAMICS")

    q_sess: QueueSession = st.session_state.queue_session
    q_status = q_sess.get_process_status()

    # Process Status Row
    c1, c2, c3 = st.columns([1, 1, 1.2])

    with c1:
        st.markdown(
            render_process_badge_hud(
                "Producer Process (TX)",
                q_status["producer"]["pid"],
                q_status["producer"]["alive"],
            ),
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            render_process_badge_hud(
                "Consumer Process (RX)",
                q_status["consumer"]["pid"],
                q_status["consumer"]["alive"],
            ),
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            "<div style='font-family:\"JetBrains Mono\", monospace; font-size:0.75rem; color:#94A3B8; margin-bottom:6px;'>QUEUE CONTROLS</div>",
            unsafe_allow_html=True,
        )
        b1, b2 = st.columns(2)
        with b1:
            if not q_status["is_running"]:
                if st.button("▶ Start Queue", key="start_q", use_container_width=True):
                    success, msg = q_sess.start()
                    if success:
                        st.success(msg)
                    st.rerun()
            else:
                if st.button("⏹ Stop Queue", key="stop_q", use_container_width=True):
                    q_sess.stop()
                    st.rerun()
        with b2:
            st.markdown(
                f"""
                <div style="background:#172235; border:1px solid #263449; border-radius:5px; padding:7px 12px; text-align:center;">
                    <div style="font-size:0.65rem; color:#94A3B8; font-family:'JetBrains Mono';">QUEUE BACKLOG</div>
                    <div style="font-size:1.1rem; color:{'#FFB020' if q_status['backlog'] > 5 else '#00E5A8'}; font-weight:700; font-family:'JetBrains Mono';">{q_status['backlog']} items</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Queue Metrics HUD Meter
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(render_metric_card("TOTAL PRODUCED", q_status["total_sent"], "#00E5A8", "📦"), unsafe_allow_html=True)
    with m2:
        st.markdown(render_metric_card("TOTAL CONSUMED", q_status["total_received"], "#00D9FF", "📥"), unsafe_allow_html=True)
    with m3:
        capacity = q_status["maxsize"]
        pct = (q_status["backlog"] / capacity * 100) if capacity else 0
        st.markdown(render_metric_card("QUEUE SATURATION", f"{pct:.1f}%", "#2563EB", "☷"), unsafe_allow_html=True)
    with m4:
        st.markdown(render_metric_card("EMPTY TIMEOUTS", q_sess.empty_timeout_count, "#FFB020", "⏱"), unsafe_allow_html=True)

    # Progress Bar Meter
    st.progress(min(1.0, max(0.0, q_status["backlog"] / (q_status["maxsize"] or 1))))

    # Transmission and Delays Controls
    col_prod, col_cons = st.columns(2)

    with col_prod:
        st.markdown("### ◈ PRODUCER BURST GENERATOR")
        with st.form("produce_form"):
            burst_count = st.slider("Burst Message Count", 1, 10, 3)
            prefix = st.text_input("Message Payload Prefix", "JOB_DISPATCH_TASK")
            prod_interval = st.slider("Production Interval (seconds)", 0.0, 0.5, 0.05, 0.05)
            prod_submit = st.form_submit_button("📦 Enqueue Message Burst", use_container_width=True)

            if prod_submit:
                if not q_status["is_running"]:
                    st.error("Please start the queue session first.")
                else:
                    items = [f"{prefix}_{i+1}" for i in range(burst_count)]
                    q_sess.produce(items, interval=prod_interval)
                    time.sleep(0.1)
                    q_sess.poll_telemetry()
                    st.rerun()

    with col_cons:
        st.markdown("### ◈ CONSUMER DELAY (BOTTLENECK INJECTOR)")
        cons_delay = st.slider(
            "Consumer Processing Delay per Message (seconds)",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.05,
            help="Simulate a slow consumer to demonstrate queue backlog accumulation and backpressure.",
        )
        if st.button("⚡ Apply Consumer Delay Bottleneck", use_container_width=True):
            if q_status["is_running"]:
                q_sess.set_consumer_delay(cons_delay)
                st.success(f"Consumer delay configured to {cons_delay}s.")
            else:
                st.error("Start queue session first.")

    # Bottleneck Analysis for Queue
    q_reports = bottleneck_detector.analyze_queue_health(
        backlog=q_status["backlog"],
        capacity=q_status["maxsize"],
        empty_timeouts=q_sess.empty_timeout_count,
    )
    if q_reports:
        st.markdown("### ⚠️ DETECTED QUEUE BOTTLENECKS")
        for r in q_reports:
            st.warning(f"**{r.title}**: {r.description}\n\n*Action:* {r.recommendation}")

    # History Table
    st.markdown("### ◈ CONSUMED MESSAGES AUDIT LOG")
    if q_sess.received_messages:
        df_q = pd.DataFrame(q_sess.received_messages[-20:])
        st.dataframe(
            df_q[["sequence", "msg_id", "payload", "latency_ms"]],
            use_container_width=True,
            hide_index=True,
        )

    # Console
    st.markdown("### ◈ MESSAGE QUEUE DEBUGGING CONSOLE")
    render_terminal_logs_hud(filter_type="QUEUE")


# ---------------------------------------------------------
# VIEW 4: Shared Memory Lab (Purple/Cyan Sci-Fi Workspace)
# ---------------------------------------------------------
elif menu_option == "Shared Memory Lab":
    render_main_hud_header("SHARED MEMORY LAB // ZERO-COPY MEMORY & SYNCHRONIZATION")

    shm_sess: SharedMemorySession = st.session_state.shm_session
    shm_status = shm_sess.get_process_status()

    # Process Cards
    c1, c2, c3 = st.columns([1, 1, 1.2])

    with c1:
        st.markdown(
            render_process_badge_hud(
                "Writer Process (SHM_TX)",
                shm_status["writer"]["pid"],
                shm_status["writer"]["alive"],
            ),
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            render_process_badge_hud(
                "Reader Process (SHM_RX)",
                shm_status["reader"]["pid"],
                shm_status["reader"]["alive"],
            ),
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            "<div style='font-family:\"JetBrains Mono\", monospace; font-size:0.75rem; color:#94A3B8; margin-bottom:6px;'>SHARED RAM CONTROLS</div>",
            unsafe_allow_html=True,
        )
        sync_mode = st.toggle("Enable Lock Synchronization (mp.Lock)", value=shm_sess.synchronized)

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if not shm_status["is_running"]:
                if st.button("▶ Allocate SHM", key="start_shm", use_container_width=True):
                    success, msg = shm_sess.start(synchronized=sync_mode)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun()
            else:
                if st.button("⏹ Unlink SHM", key="stop_shm", use_container_width=True):
                    shm_sess.stop()
                    st.rerun()
        with col_b2:
            mode_badge = (
                '<span class="badge-status-pill pill-running">LOCKED (MUTEX)</span>'
                if shm_sess.synchronized
                else '<span class="badge-status-pill pill-stopped">RACE CONDITION MODE</span>'
            )
            st.markdown(f"Mode: {mode_badge}", unsafe_allow_html=True)

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Writer Control & Memory Hex Inspector
    col_write, col_hex = st.columns([1.2, 1.8])

    with col_write:
        st.markdown("### ◈ WRITE TO DIRECT VIRTUAL RAM")
        with st.form("shm_write_form"):
            payload_str = st.text_input("Data String", "SYSTEM_KERNEL_CRITICAL_PAYLOAD_X99")
            w_delay = st.slider("Simulate Critical Section Hold (seconds)", 0.0, 1.0, 0.0, 0.05)
            w_submit = st.form_submit_button("💾 Commit Write to RAM", use_container_width=True)

            if w_submit:
                if not shm_status["is_running"]:
                    st.error("Please allocate shared memory session first.")
                else:
                    shm_sess.write_data(payload_str, delay=w_delay)
                    time.sleep(0.1 + w_delay)
                    shm_sess.poll_telemetry()
                    st.rerun()

        if not shm_sess.synchronized:
            st.warning(
                "⚠️ **Race Condition Demonstration Active**: Without a lock, concurrent reader access during "
                "a multi-part write will cause dirty reads or torn data."
            )

    with col_hex:
        st.markdown("### ◈ MEMORY DUMP INSPECTOR (HEX & ASCII DUMP)")
        buf_data = shm_sess.inspect_raw_buffer(max_bytes=96)
        if buf_data.get("header"):
            h = buf_data["header"]
            st.markdown(
                f"""
                <div style="background:#080D18; border:1px solid #263449; border-radius:5px; padding:10px 14px; margin-bottom:8px; font-family:'JetBrains Mono', monospace; font-size:0.75rem;">
                    MAGIC: <b style="color:#00D9FF;">{h['magic']}</b> | SEQ: <b style="color:#00E5A8;">#{h['sequence']}</b> | 
                    LEN: <b style="color:#8B5CF6;">{h['data_length']}B</b> | BLOCK: <span style="color:#94A3B8;">{buf_data.get('shm_name')}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.code(f"HEX DUMP (First 96 Bytes):\n{buf_data['hex']}\n\nASCII VIEW:\n{buf_data['text']}", language="text")
        else:
            st.info("Buffer empty or session offline. Click '▶ Allocate SHM' to inspect RAM buffer.")

    # Reader History
    st.markdown("### ◈ READER PROCESS RECEIPT LOG")
    if shm_sess.read_history:
        df_shm = pd.DataFrame(shm_sess.read_history[-15:])
        st.dataframe(
            df_shm[["seq", "payload", "latency_ms", "lock_wait_ms", "synchronized", "corrupted"]],
            use_container_width=True,
            hide_index=True,
        )

    # Console
    st.markdown("### ◈ SHARED MEMORY DEBUGGING CONSOLE")
    render_terminal_logs_hud(filter_type="SHARED_MEM")


# ---------------------------------------------------------
# VIEW 5: Deadlock & Bottleneck Lab (Diagnostic Console)
# ---------------------------------------------------------
elif menu_option == "Deadlock & Bottleneck Lab":
    render_main_hud_header("DEADLOCK & BOTTLENECK LAB // RAG GRAPH & COFFMAN CONDITION ANALYSIS")

    deadlock_sess: DeadlockLabSession = st.session_state.deadlock_session
    graph_state = deadlock_sess.poll_telemetry()

    c_demo1, c_demo2 = st.columns([1.2, 1])

    with c_demo1:
        st.markdown("### ◈ CONTROLLED DEADLOCK DEMONSTRATION")
        st.markdown(
            """
            - **Process 1** acquires `Lock A`, sleeps 0.4s, then requests `Lock B`.
            - **Process 2** acquires `Lock B`, sleeps 0.4s, then requests `Lock A`.
            - **Result**: $P_1 \\rightarrow L_B \\rightarrow P_2 \\rightarrow L_A \\rightarrow P_1$ (Circular Wait Deadlock).
            - **Safety Guarantee**: Bounded timeouts are used; application will **never freeze**.
            """
        )

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("🚨 Simulate Deadlock (Circular Wait)", use_container_width=True):
                success, msg = deadlock_sess.run_simulation(prevent_deadlock=False)
                if success:
                    st.info(msg)
                time.sleep(0.5)
                st.rerun()

        with col_b2:
            if st.button("🛡️ Run with Lock Ordering (Prevention)", use_container_width=True):
                success, msg = deadlock_sess.run_simulation(prevent_deadlock=True)
                if success:
                    st.success(msg)
                time.sleep(0.5)
                st.rerun()

    with c_demo2:
        st.markdown("### ◈ DEADLOCK DIAGNOSTIC STATE")
        if graph_state.get("deadlock_detected"):
            cycle_str = " ➔ ".join(graph_state["cycle"])
            st.markdown(
                f"""
                <div style="background: rgba(255, 69, 96, 0.1); border: 1px solid #FF4560; border-left: 4px solid #FF4560; padding:16px; border-radius:5px;">
                    <div style="display:flex; align-items:center;">
                        <span class="hud-beacon-red"></span>
                        <span style="font-family:'Orbitron', sans-serif; font-size:1.1rem; color:#FF4560; font-weight:800;">DEADLOCK DETECTED!</span>
                    </div>
                    <div style="font-family:'JetBrains Mono', monospace; font-size:0.8rem; color:#F1F5F9; margin-top:8px;">
                        CIRCULAR WAIT CYCLE: <b style="color:#FF4560;">{cycle_str}</b>
                    </div>
                    <div style="font-size:0.75rem; color:#94A3B8; margin-top:4px;">
                        Both processes are blocked in mutual resource starvation. Breaking safely via timeout...
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif graph_state.get("resolved") and not graph_state.get("is_running"):
            st.markdown(
                """
                <div style="background: rgba(0, 229, 168, 0.1); border: 1px solid #00E5A8; border-left: 4px solid #00E5A8; padding:14px; border-radius:5px;">
                    <span style="font-family:'Orbitron', sans-serif; color:#00E5A8; font-weight:700;">✓ SCENARIO SAFELY RESOLVED</span>
                    <div style="font-size:0.78rem; color:#94A3B8; margin-top:4px;">
                        All resource locks safely released. No orphan processes remain active.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div style="background:#111827; border:1px solid #263449; padding:14px; border-radius:5px;">
                    <span style="font-family:'JetBrains Mono', monospace; color:#00D9FF; font-weight:700;">STANDBY</span>
                    <div style="font-size:0.78rem; color:#94A3B8; margin-top:4px;">
                        No active circular wait detected in Resource Allocation Graph.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Resource Allocation Graph (RAG) Visualization
    st.markdown("### ◈ LIVE RESOURCE ALLOCATION GRAPH (RAG)")
    rag_svg = render_rag_svg_hud(
        allocations=graph_state.get("allocations", {}),
        requests=graph_state.get("requests", {}),
        has_deadlock=graph_state.get("deadlock_detected", False),
    )

    c_graph, c_explain = st.columns([1.5, 1])
    with c_graph:
        st.components.v1.html(
            rag_svg,
            height=260,
            scrolling=False,
        )

    with c_explain:
        st.markdown("### ◈ GRAPH NOTATION & COFFMAN CONDITIONS")
        st.markdown(
            """
            - 🟢 **Solid Green Arrow ($L \\rightarrow P$):** Allocation edge. Lock is held by process.
            - 🔴 **Dashed Red Arrow ($P \\rightarrow L$):** Request edge. Process blocked waiting for lock.
            - **Cycle Condition:** A directed cycle in a single-unit resource graph is a necessary and sufficient condition for Deadlock.
            
            **The Four Coffman Conditions:**
            1. **Mutual Exclusion:** Locks are non-shareable.
            2. **Hold & Wait:** $P_1$ holds $L_A$ while requesting $L_B$.
            3. **No Preemption:** Neither process can seize locks.
            4. **Circular Wait:** $P_1 \\rightarrow L_B \\rightarrow P_2 \\rightarrow L_A \\rightarrow P_1$.
            """
        )

    # Console
    st.markdown("### ◈ DEADLOCK & SYNCHRONIZATION CONSOLE")
    render_terminal_logs_hud(filter_type="DEADLOCK")


# ---------------------------------------------------------
# VIEW 6: Metrics & History (Futuristic Analytics Console)
# ---------------------------------------------------------
elif menu_option == "Metrics & History":
    render_main_hud_header("METRICS & HISTORY // AUDIT LOGS & QUANTITATIVE TELEMETRY")

    metrics = db_instance.get_metrics_summary()

    # 4 Metric Cards
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(render_metric_card("TOTAL TRANSMISSIONS", metrics["total_messages"], "#00D9FF", "📊"), unsafe_allow_html=True)
    with m2:
        st.markdown(render_metric_card("AVERAGE LATENCY", f"{metrics['avg_latency_ms']} ms", "#2563EB", "◷"), unsafe_allow_html=True)
    with m3:
        st.markdown(render_metric_card("MINIMUM LATENCY", f"{metrics['min_latency_ms']} ms", "#00E5A8", "▼"), unsafe_allow_html=True)
    with m4:
        st.markdown(render_metric_card("MAXIMUM LATENCY", f"{metrics['max_latency_ms']} ms", "#FF4560", "▲"), unsafe_allow_html=True)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Plotly Visualizations with Custom Sci-Fi Theme
    all_msgs = db_instance.get_recent_messages(limit=100)
    if all_msgs:
        df_all = pd.DataFrame(all_msgs)

        col_chart1, col_chart2 = st.columns(2)

        custom_plotly_layout = {
            "paper_bgcolor": "#080D18",
            "plot_bgcolor": "#0B1220",
            "font": {"family": "JetBrains Mono, Inter, monospace", "color": "#F1F5F9", "size": 11},
            "xaxis": {"gridcolor": "#263449", "zerolinecolor": "#263449"},
            "yaxis": {"gridcolor": "#263449", "zerolinecolor": "#263449"},
        }

        with col_chart1:
            st.markdown("### ◈ MESSAGE LATENCY PROFILE (ms)")
            fig_lat = px.line(
                df_all,
                x="id",
                y="latency_ms",
                color="ipc_type",
                markers=True,
                title="Delivery Latency per Transmission",
                color_discrete_map={"PIPE": "#00D9FF", "QUEUE": "#00E5A8", "SHARED_MEM": "#8B5CF6"},
                labels={"id": "Message Sequence ID", "latency_ms": "Latency (ms)"},
            )
            fig_lat.add_hline(
                y=st.session_state.latency_threshold,
                line_dash="dash",
                line_color="#FF4560",
                annotation_text=f"Alert Threshold ({st.session_state.latency_threshold}ms)",
            )
            fig_lat.update_layout(**custom_plotly_layout)
            st.plotly_chart(fig_lat, use_container_width=True)

        with col_chart2:
            st.markdown("### ◈ TRANSMISSIONS BY IPC MECHANISM")
            fig_bar = px.histogram(
                df_all,
                x="ipc_type",
                color="ipc_type",
                title="Mechanism Distribution",
                color_discrete_map={"PIPE": "#00D9FF", "QUEUE": "#00E5A8", "SHARED_MEM": "#8B5CF6"},
            )
            fig_bar.update_layout(**custom_plotly_layout)
            st.plotly_chart(fig_bar, use_container_width=True)

    # SQLite Database Table Viewer
    st.markdown("### ◈ PERSISTENT SQLITE TRANSMISSION AUDIT STORE")
    if all_msgs:
        df_disp = pd.DataFrame(all_msgs)
        st.dataframe(
            df_disp[
                [
                    "id",
                    "iso_time",
                    "ipc_type",
                    "sender_name",
                    "receiver_name",
                    "payload_preview",
                    "latency_ms",
                    "status",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        # CSV Download Button
        csv_data = df_disp.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Export Transmission History to CSV",
            data=csv_data,
            file_name="ipc_debugger_metrics.csv",
            mime="text/csv",
        )
    else:
        st.info("No recorded messages in the database yet. Run experiments in the lab tabs to collect metrics.")

    # Clear History Control
    if st.button("🗑 Clear All Historical Telemetry & Events"):
        db_instance.clear_all()
        event_logger.clear()
        st.success("Database and telemetry history cleared.")
        st.rerun()
