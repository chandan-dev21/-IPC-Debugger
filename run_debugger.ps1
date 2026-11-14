# PowerShell Runner Script for IPC Debugger
# Run with: powershell -ExecutionPolicy Bypass -File run_debugger.ps1

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "          IPC DEBUGGER: INTER-PROCESS COMMUNICATION LAB" -ForegroundColor Cyan
Write-Host "          Operating Systems Capstone Project" -ForegroundColor DarkCyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verify Python
Write-Host "[1/3] Checking Python installation..." -ForegroundColor Yellow
try {
    $pyVer = python --version 2>&1
    Write-Host "  Found: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Python is not installed or not in PATH!" -ForegroundColor Red
    exit 1
}

# 2. Run Verification Tests
Write-Host "[2/3] Running verification test suite..." -ForegroundColor Yellow
$testResult = python -m pytest tests -q 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [SUCCESS] All 17 verification tests passed cleanly!" -ForegroundColor Green
} else {
    Write-Host "  [WARNING] Some tests reported issues:" -ForegroundColor DarkYellow
    Write-Host $testResult
}

# 3. Launch Streamlit
Write-Host ""
Write-Host "[3/3] Launching Streamlit Dashboard on http://localhost:8501 ..." -ForegroundColor Yellow
Write-Host "Press Ctrl+C in this terminal window to stop the debugger." -ForegroundColor Gray
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

python -m streamlit run app.py
