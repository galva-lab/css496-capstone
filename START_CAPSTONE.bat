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
start "FastAPI Backend" cmd /k "cd /d "%CAPSTONE%\backend" && python -m uvicorn main:app --reload --host 0.0.0.0 && pause"

REM Wait 3 seconds for FastAPI to start before launching bridge
echo     Waiting for FastAPI to initialize...
timeout /t 3 /nobreak >nul

echo [2/3] Starting RuView bridge...
start "RuView Bridge" cmd /k "cd /d "%RUVIEW%" && python "%CAPSTONE%\backend\ruview_bridge.py" && pause"

REM Wait 2 more seconds for bridge to connect
timeout /t 2 /nobreak >nul

echo [3/3] Opening dashboard...
start "" "%CAPSTONE%\backend\dashboard.html"

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
echo   Press any key to STOP all services...
pause >nul

REM Kill all services when user presses a key
echo.
echo Stopping all services...
taskkill /FI "WINDOWTITLE eq FastAPI Backend" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq RuView Bridge" /T /F >nul 2>&1
echo Done. Goodbye!
timeout /t 2 /nobreak >nul