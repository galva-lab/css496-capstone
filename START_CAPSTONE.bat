@echo off
title CSS 496 Capstone — Sensor System
color 0A

echo.
echo ============================================
echo   CSS 496 Capstone - Wi-Fi Sensor System
echo   Starting all services...
echo ============================================
echo.

REM ── Config ──────────────────────────────────
REM %~dp0 = folder this script lives in (the Capstone root), so paths work
REM regardless of username or where the project is moved. Trailing backslash
REM is included in %~dp0, so do not add another before subfolders.
set CAPSTONE=%~dp0
REM ─────────────────────────────────────────────

REM Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Make sure Python is installed.
    pause
    exit /b 1
)

REM NOTE: This launches the AMPLITUDE bridge (csi_amplitude_bridge.py), which reads
REM raw CSI over UDP directly and derives occupancy from amplitude variance. It does
REM NOT need Node.js / RuView rf-scan. The ESP32 nodes must be flashed with
REM filter_mac set (see provisioning/README_FILTER_MAC.md) so the link is stable.

echo [1/2] Starting FastAPI backend...
REM No --reload: the reloader forks multiprocessing children that orphan and hold
REM port 8000 with stale code/config. Run a single plain worker instead.
start "Capstone Backend" /D "%CAPSTONE%backend" cmd /k python -m uvicorn main:app --host 0.0.0.0 --port 8000

REM Wait for FastAPI to start before launching the bridge
echo     Waiting for FastAPI to initialize...
timeout /t 4 /nobreak >nul

echo [2/2] Starting CSI amplitude bridge (all nodes 1-6)...
start "Capstone Bridge" /D "%CAPSTONE%backend" cmd /k python csi_amplitude_bridge.py --nodes 1 2 3 4 5 6

REM Wait for the bridge to bind UDP 5005 and start posting
timeout /t 2 /nobreak >nul

echo Opening dashboard...
start "" "%CAPSTONE%backend\dashboard.html"

echo.
echo ============================================
echo   All services started!
echo.
echo   FastAPI : http://127.0.0.1:8000
echo   Nodes   : http://127.0.0.1:8000/nodes
echo   Latest  : http://127.0.0.1:8000/latest
echo.
echo   Reminder: ESP32 nodes must be powered and flashed
echo   with filter_mac (BSSID 72:13:01:84:04:59).
echo ============================================
echo.
echo   Press any key here to STOP everything
echo   (closes the backend + bridge windows automatically)...
pause >nul

REM Find the launcher cmd processes by their command line and tree-kill them (/T)
REM so uvicorn and the bridge both stop. Restricted to cmd.exe so the match can
REM never hit this powershell helper itself.
echo.
echo Stopping all services...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and ($_.CommandLine -match 'uvicorn|csi_amplitude_bridge') } | ForEach-Object { taskkill /PID $_.ProcessId /T /F }" >nul 2>&1
echo Done. Goodbye!
timeout /t 2 /nobreak >nul
