# AGENTS.md — AI Coding Agent Reference

> This file is for AI coding agents working on this repository. It assumes no prior knowledge of the project.

---

## Project Overview

This is a **privacy-preserving multi-sensor IoT system** that detects abnormal activity in a sensitive space (a public restroom) without using cameras or capturing any personal images. It is the author's CSS 496/497 Capstone project.

**How it works in one sentence:** Six ESP32-S3 microcontrollers stream Wi-Fi CSI motion/presence data and environmental gas/sound readings to a FastAPI backend, which fuses them into a unified threat level and displays everything on a live web dashboard.

**Key principle — privacy by construction:** The sensing modalities (Wi-Fi signal disturbance, gas concentration, noise amplitude) are structurally incapable of capturing identity. The dashboard shows abstract threat levels and sensor readings, never images or recordings.

---

## Technology Stack

| Layer | Technology | Files / Notes |
|---|---|---|
| **Hardware** | 6 × ESP32-S3 | 5 CSI nodes + 1 environmental node |
| **Wi-Fi Sensing** | RuView (ESP-IDF 5.5) | External framework; bridge connects it |
| **Environmental Firmware** | Arduino C++ | `Arduino script/esp32_node3_sensors/esp32_node3_sensors.ino` |
| **Backend** | Python 3.11+ · FastAPI · SQLite | `backend/main.py` and helpers |
| **Bridge** | Python + Node.js | `backend/ruview_bridge.py` spawns `rf-scan.js` |
| **Dashboard** | HTML / CSS / JavaScript (Chart.js) | `backend/dashboard.html` (static file, polls REST) |
| **Simulator** | Python | `esp32/sensor_sender.py` (random data for testing) |
| **Calibration Tools** | Python (stdlib only) | `scripts/calibration_logger.py`, `calibration_analyzer.py` |
| **Startup** | Windows Batch + PowerShell | `START_CAPSTONE.bat` |

---

## Directory Structure

```
.
├── backend/                    # FastAPI server + bridge + dashboard
│   ├── main.py                 # FastAPI app: ingestion, fusion, alerts, SQLite
│   ├── people_counter.py       # Coarse occupancy estimator (EMA + decay)
│   ├── people_count_history.py # Logs occupancy transitions to CSV
│   ├── ruview_bridge.py        # Bridges RuView Node.js → FastAPI POSTs
│   ├── dashboard.html          # Self-contained polling dashboard
│   ├── .env                    # Occupancy tuning (gitignored)
│   └── .env.example            # Template for .env
├── dashboard/                  # Simple Python polling client (less used)
│   └── app.py
├── esp32/                      # Test/simulator scripts
│   └── sensor_sender.py        # Random sensor simulator
├── scripts/                    # Calibration toolchain
│   ├── calibration_logger.py   # Collect ground-truth occupancy labels
│   └── calibration_analyzer.py # Measure accuracy & suggest thresholds
├── Arduino script/             # Environmental node firmware
│   └── esp32_node3_sensors/
│       ├── esp32_node3_sensors.ino
│       ├── arduino_secrets.h         # Wi-Fi creds (gitignored)
│       └── arduino_secrets.h.example # Template
├── data/                       # Runtime data (DBs, CSVs)
│   ├── sensor_logs.db          # SQLite full history
│   ├── occupancy_log.csv       # Occupancy transition log
│   └── calibration_log.csv     # Ground-truth calibration data
├── docs/                       # Documentation & diagrams
│   ├── Capstone_Final_Report.md
│   ├── poster_spec.md
│   └── data_flow_diagram.html
├── START_CAPSTONE.bat          # One-click Windows launcher
├── requirement.txt             # Python deps (singular name, not "requirements")
└── README.md
```

---

## How to Run the System

### One-Click Start (Windows)

```bat
START_CAPSTONE.bat
```

This script:
1. Starts the FastAPI backend (`uvicorn main:app --reload --host 0.0.0.0` from `backend/`)
2. Waits 3 seconds
3. Starts the RuView bridge (`python ruview_bridge.py`)
4. Opens `backend/dashboard.html` in the default browser
5. Waits for a keypress, then cleanly shuts down all processes via PowerShell

**Prerequisites checked by the script:** Python and Node.js must be on `PATH`.

### Manual Start

```bash
cd backend

# 1. Install deps
pip install -r ../requirement.txt

# 2. Start FastAPI
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 3. In another terminal, start the RuView bridge
python ruview_bridge.py

# 4. Open backend/dashboard.html in a browser
```

### Backend-only / Simulator Mode

If you don't have the ESP32 hardware, use the random simulator:

```bash
python esp32/sensor_sender.py
```

This POSTs random data to `http://127.0.0.1:8000/sensor-data` every 5 seconds.

---

## Architecture & Data Flow

The system uses a **layered, message-passing architecture**:

```
  HARDWARE LAYER
  ESP32 #1-3,5,6 (RuView CSI)      ESP32 #4 (MQ-135 gas + KY-037 sound)
        │  UDP CSI frames                    │  HTTP POST JSON
        ▼                                    │
  BRIDGE LAYER                               │
  ruview_bridge.py                           │
   • spawns rf-scan.js (RuView)              │
   • reader thread parses CSI → latest_frame │
   • consensus across all CSI boards         │
   • POSTs to backend every 2 s              │
        │                                    │
        └─────────────┬──────────────────────┘
                      ▼   POST /sensor-data
  BACKEND LAYER  (FastAPI — main.py)
   • latest_by_source[]  (per-source latest reading)
   • fuse_latest()       (merge CSI + environmental)
   • get_occupancy_alerts() (threat level + alerts)
   • SQLite + in-memory logging
        │   GET /latest, /logs, /nodes
        ▼
  PRESENTATION LAYER  (dashboard.html)
   • polls /latest (2 s), /logs (4 s), /nodes
```

**Key design choices:**
- `latest_by_source` decouples producers. Each node posts on its own schedule. Adding a new source is a one-line change.
- `fuse_latest()` prefers the authoritative source per field: motion/presence from CSI, gas/sound from the environmental node.
- The bridge is a separate process so the Node.js-dependent RuView logic never touches the FastAPI server.
- The dashboard is a static HTML file that polls REST endpoints — no WebSocket server, no build step.

---

## Key Backend Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Health check |
| `/sensor-data` | POST | Ingestion endpoint for all sensor nodes |
| `/latest` | GET | Most recent fused reading |
| `/logs` | GET | Last 500 in-memory readings |
| `/nodes` | GET | Per-source connectivity status (30-second timeout) |
| `/people-count` | GET | Latest occupancy estimate |
| `/people-history` | GET | Recent occupancy level transitions |

**CORS is fully open** (`allow_origins=["*"]`) because the dashboard is opened as a `file://` URL.

---

## Configuration & Tuning

### Occupancy Estimator (`backend/.env`)

`people_counter.py` reads `backend/.env` with its own minimal parser (no `python-dotenv` dependency). Copy `.env.example` to `.env` and tune:

```env
PRESENCE_OCCUPIED=3.0   # presence_score above this => at least 1 person
PRESENCE_BUSY=6.0       # strong disturbance => likely >1 person
SMOOTHING_ALPHA=0.4     # EMA weight for newest reading (lower = smoother)
DECAY_AFTER_SEC=8       # idle seconds before estimate decays toward 0
DECAY_STEP=1.0          # drop per inactive update
MAX_COUNT=5             # maximum reportable occupancy
```

**How to tune correctly:** Do NOT guess thresholds. Use the calibration toolchain:

1. Start the full system.
2. Run `python scripts/calibration_logger.py` and type the actual number of people present at each prompt.
3. Run `python scripts/calibration_analyzer.py` to see exact-match accuracy, mean absolute error, and a suggested threshold.

### RuView Bridge (`backend/ruview_bridge.py`)

Hard-coded constants at the top of the file (no config file):

```python
BACKEND_URL     = "http://127.0.0.1:8000/sensor-data"
RUVIEW_PORT     = 5005          # UDP port ESP32 sends to
UPDATE_INTERVAL = 2             # seconds between POSTs
PRESENCE_THRESH = 3.0           # per-board presence score that counts as "active"
MOTION_MIN_NODES = 2            # boards that must agree before declaring motion
```

### Environmental Node Firmware

`Arduino script/esp32_node3_sensors/esp32_node3_sensors.ino` contains:
- Hard-coded `serverIP` — must match the backend machine's current IP.
- `SOUND_NOISE_FLOOR = 130` — measured ambient baseline; re-measure if room/mic changes.
- `SEND_INTERVAL_MS = 2000` — reporting cadence.

**Wi-Fi credentials** live in `arduino_secrets.h` (gitignored). There is an `arduino_secrets.h.example` template.

---

## Data Storage

| Store | Path | Purpose |
|---|---|---|
| SQLite | `data/sensor_logs.db` | Full history of every fused reading |
| In-memory | `backend/main.py` `fake_database` | Last 500 readings for fast dashboard polling (`MAX_RECORDS = 500`) |
| CSV | `data/occupancy_log.csv` | Only records when occupancy *level* changes (keeps log small) |
| CSV | `data/calibration_log.csv` | Ground-truth labels + predictions for threshold tuning |

SQLite schema (`sensor_logs` table):
```sql
id, timestamp, source, motion, sound_level, gas_level,
presence_score, heart_rate, rssi, threat_level, alerts
```

---

## Code Style & Conventions

- **Python:** No linter/formatter is configured. Follow the existing style:
  - Two spaces before inline comments.
  - ASCII section dividers (`# ── Section ───────────────────────────────`).
  - Docstrings are honest about limitations (e.g., "coarse estimate, not an exact head count").
  - Module-level dictionaries are used for runtime state (`_state`, `latest_by_source`, `sound_state`).
- **Firmware (Arduino/C++):** `Serial.printf` debug lines start with `[DBG]` for raw values and `[OK]` for successful posts. Keep the timeout short (`http.setConnectTimeout(800)`) so a dead backend cannot stall the loop.
- **Dashboard (HTML/JS):** Self-contained single file. No build step. Uses Chart.js CDN. Polling intervals are 2 s for `/latest` and 4 s for `/logs`.

---

## Testing & Validation

There is **no automated test suite** (no `pytest`, no `unittest`). Validation is empirical and hardware-in-the-loop:

1. **Serial-monitor instrumentation:** The firmware emits `[DBG] rawGas=… gas=… soundPeak=… soundScore=…` every cycle. This is the primary debugging tool.
2. **Endpoint verification:** Hit `/`, `/latest`, `/nodes` from a browser or `curl`.
3. **End-to-end smoke test:** A physical action (clap, motion, gas source) produces a visible dashboard change within seconds, with a corresponding SQLite row.
4. **Calibration toolchain:** The only quantitative accuracy measurement available.

**When modifying code, always verify against live state** — especially anything touching the OS, network, or RF channel.

---

## Known Limitations & Honest Engineering Notes

Read these before making changes or trusting outputs:

1. **RuView `n_persons` is not a real people count.** The firmware heuristic is hard-clamped to `[1, 4]` and structurally incapable of reporting 0. The coarse occupancy estimator (`people_counter.py`) treats it as weak evidence and relies on EMA smoothing + decay.
2. **Sound is relative, not calibrated decibels.** The KY-037 has no dB calibration. The backend uses a rolling-baseline **spike detector** (`detect_sound_spike`) instead of absolute thresholds.
3. **CSI presence requires proper calibration.** The firmware learns an adaptive baseline during the first ~60 seconds after boot. If the room is occupied during that window, "empty" will read high forever. Recalibrate with the room genuinely empty and all boards streaming.
4. **Multi-node consensus is essential.** With 5 CSI boards, one noisy board is outvoted. The bridge uses trimmed presence (drop the noisiest board), median people-count, and voting for motion.
5. **Hard-coded IP addresses.** The ESP32 firmware has a static `serverIP`. If the backend machine's DHCP address changes, the node will fail with `HTTP -1`. mDNS/service discovery is noted as future work.
6. **CORS is fully open.** The dashboard is opened as a local file. Do not deploy this backend on an open network without adding authentication and TLS.

---

## Security Considerations

- **No authentication or authorization** on any endpoint.
- **No TLS/HTTPS** — all traffic is plain HTTP over a local Wi-Fi network.
- **Wi-Fi credentials** in `arduino_secrets.h` are gitignored, but the file itself is plain text on disk.
- **CORS allows all origins.**
- **Privacy guarantee:** The system never captures cameras, images, microphones, or speech. It only forwards numerical sensor readings (motion flag, presence score, gas ppm index, sound amplitude).

For any deployment beyond a closed lab network, add:
1. Backend authentication (API keys or session auth).
2. TLS on the backend and ideally on the ESP32 (often impractical; at minimum isolate the IoT VLAN).
3. Restrict CORS to known origins.

---

## Dependency File

`requirement.txt` (singular, not `requirements.txt`):

```
fastapi>=0.110.0
uvicorn>=0.29.0
requests>=2.31.0
```

There is no `pyproject.toml`, `setup.py`, `package.json`, `Cargo.toml`, or other package manifest.

---

## Adding a New Sensor Node

To add a new source (e.g., a fifth sensor type):

1. **Firmware / Bridge:** Have the new node POST to `/sensor-data` with a unique `"source"` string and the fields it measures.
2. **Backend (`main.py`):**
   - Add the source key to `latest_by_source` (line 26).
   - Update `fuse_latest()` to read the new fields, preferring the authoritative source.
   - Update `get_occupancy_alerts()` if the new sensor should influence threat level.
3. **Dashboard (`dashboard.html`):**
   - Add a card or badge for the new reading.
   - Update `fetchLatest()` to render the new value.
4. **SQLite (`init_db()` / `save_to_db()`):** Add columns if needed, or store the new data in the existing `alerts` / flexible fields.

Because the backend uses source-keyed fusion, the change is usually localized to `latest_by_source`, `fuse_latest()`, and the dashboard HTML.

---

## Contact / Authorship

This is a single-developer academic capstone. For questions about design decisions, see `docs/Capstone_Final_Report.md`, which contains detailed root-cause analyses of the major bugs and engineering trade-offs.
