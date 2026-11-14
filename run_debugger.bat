@echo off
title IPC Debugger - Inter-Process Communication Diagnostic Tool
echo =====================================================================
echo           IPC DEBUGGER: INTER-PROCESS COMMUNICATION LAB
echo           Operating Systems Capstone Project
echo =====================================================================
echo.

echo [1/3] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

echo [2/3] Running verification test suite...
python -m pytest tests -q
if %errorlevel% neq 0 (
    echo [WARNING] Some tests encountered issues. Review test logs.
) else (
    echo [SUCCESS] All 17 verification tests passed cleanly!
)

echo.
echo [3/3] Launching Streamlit Dashboard on http://localhost:8501 ...
echo Press Ctrl+C in this terminal window to stop the debugger.
echo =====================================================================
echo.

python -m streamlit run app.py
pause
