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
set RUVIEW=%~dp0..\Ruview\RuView
REM ─────────────────────────────────────────────

REM Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Make sure Python is installed.
    pause
    exit /b 1
)

REM Check Node.js is available
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Make sure Node.js is installed.
    pause
    exit /b 1
)

echo [1/3] Starting FastAPI backend...
REM /D sets the working dir (handles spaces in the path); the clean window
REM title "Capstone Backend" is what taskkill matches on shutdown.
start "Capstone Backend" /D "%CAPSTONE%backend" cmd /k python -m uvicorn main:app --reload --host 0.0.0.0

REM Wait 3 seconds for FastAPI to start before launching bridge
echo     Waiting for FastAPI to initialize...
timeout /t 3 /nobreak >nul

echo [2/3] Starting RuView bridge...
start "Capstone Bridge" /D "%RUVIEW%" cmd /k python "%CAPSTONE%backend\ruview_bridge.py"

REM Wait 2 more seconds for bridge to connect
timeout /t 2 /nobreak >nul

echo [3/3] Opening dashboard...
start "" "%CAPSTONE%backend\dashboard.html"

echo.
echo ============================================
echo   All services started!
echo.
echo   FastAPI : http://127.0.0.1:8000
echo   Nodes   : http://127.0.0.1:8000/nodes
echo   Latest  : http://127.0.0.1:8000/latest
echo.
echo   Reminder: Plug ESP32 #3 into powerbank!
echo ============================================
echo.
echo   Press any key here to STOP everything
echo   (closes the backend + bridge windows automatically)...
pause >nul

REM Pressing a key lands here. Windows 11 hosts these in Windows Terminal, so the
REM cmd/python processes have no classic window title for taskkill to match.
REM Instead, find the launcher cmd processes by their command line and tree-kill
REM them (/T) — that stops uvicorn's reload worker and the bridge's node child,
REM and the terminal tab closes when its cmd exits. Restricted to cmd.exe so the
REM match can never hit this powershell helper itself.
echo.
echo Stopping all services...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and ($_.CommandLine -match 'uvicorn|ruview_bridge') } | ForEach-Object { taskkill /PID $_.ProcessId /T /F }" >nul 2>&1
echo Done. Goodbye!
timeout /t 2 /nobreak >nul