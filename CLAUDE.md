# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Privacy-preserving IoT restroom safety monitor. Six ESP32-S3 nodes stream Wi-Fi CSI + gas/sound sensor data to a FastAPI backend, which fuses readings into a threat level shown on a polling web dashboard. No cameras, no identity data. See `AGENTS.md` for the full architecture reference.

## Commands

### Run the backend

```powershell
cd backend
backend\venv\Scripts\activate   # Windows
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Run the RuView bridge (separate terminal, from `backend/`)

```powershell
python ruview_bridge.py
```

### Run without hardware (simulator)

```powershell
python esp32/sensor_sender.py   # POSTs random data to /sensor-data every 5 s
```

### One-click start (Windows)

```bat
START_CAPSTONE.bat
```

### Install dependencies

```powershell
pip install -r requirement.txt   # note: singular "requirement", not "requirements"
```

### Calibration workflow

```powershell
python scripts/calibration_logger.py   # collect ground-truth labels while system runs
python scripts/calibration_analyzer.py # print accuracy + suggest .env thresholds
```

## Architecture

The system has four layers (hardware → bridge → backend → dashboard), with all state crossing layer boundaries as JSON over HTTP:

- **Bridge** (`backend/ruview_bridge.py`): spawns RuView's `rf-scan.js`, reads UDP CSI frames, builds per-board consensus, POSTs to `/sensor-data` every 2 s.
- **Backend** (`backend/main.py`): receives all posts into `latest_by_source` dict (one slot per source), calls `fuse_latest()` on each request to merge CSI + environmental data, writes every reading to SQLite (`data/sensor_logs.db`) and a 500-entry in-memory ring.
- **Occupancy** (`backend/people_counter.py`): EMA smoother + decay; reads tuning from `backend/.env` at import time (no `python-dotenv` — custom parser). Re-read requires restart.
- **Dashboard** (`backend/dashboard.html`): static HTML file opened as `file://`. Polls `/latest` (2 s) and `/logs` (4 s). No build step.

## Key Files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app, sensor fusion, SQLite, threat alerts |
| `backend/people_counter.py` | Occupancy EMA + decay logic |
| `backend/ruview_bridge.py` | CSI bridge; hard-coded constants at top of file |
| `backend/.env` | Occupancy tuning (copy from `.env.example`; restart to apply) |
| `requirement.txt` | Python deps (root level, singular name) |
| `Arduino script/esp32_node3_sensors/esp32_node3_sensors.ino` | Environmental node firmware |

## Critical Gotchas

- **Dependency file is `requirement.txt`** (singular) at the repo root, not inside `backend/`.
- **RuView `n_persons` is clamped `[1, 4]` and cannot report 0.** Never treat it as an accurate head count.
- **Sound is not calibrated dB.** The backend uses a rolling-baseline spike detector, not absolute thresholds.
- **CSI baseline is learned at boot.** If the room is occupied during the first ~60 s, the "empty" baseline will be wrong permanently until reboot with the room clear.
- **`serverIP` in the Arduino sketch is hard-coded.** If the backend machine's IP changes, the node fails silently with `HTTP -1`.
- **There is no test suite.** Validate changes by running the simulator or live hardware and hitting `/`, `/latest`, `/nodes` in a browser.
