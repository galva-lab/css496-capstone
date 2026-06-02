# Privacy-Preserving Multi-Sensor IoT System for Abnormal Restroom Activity Detection

A real-time restroom safety monitoring system using four ESP32-S3 devices, Wi-Fi CSI sensing, environmental sensors, and a live web dashboard — all without cameras or personal data collection.

## What It Does

This system detects unusual activity in restroom environments while fully preserving user privacy. Instead of cameras, it uses **Wi-Fi Channel State Information (CSI)** — disturbances in Wi-Fi signals caused by physical movement — combined with gas and sound sensors to assess whether something abnormal is happening. All sensor data streams to a FastAPI backend that fuses the readings into a unified threat level and displays them on a real-time dashboard.

- **Detects motion and presence** from Wi-Fi signal disturbances (no cameras)
- **Measures air quality** with an MQ-135 gas sensor
- **Monitors sound levels** with a KY-037 sound sensor
- **Fuses all sensor inputs** into a low / medium / high threat assessment
- **Displays live readings** on a web dashboard with per-device status
- **Logs historical data** to SQLite for analysis

## Stack

| Layer | Tech |
|---|---|
| Hardware | 4 × ESP32-S3, MQ-135 gas sensor, KY-037 sound sensor |
| Wi-Fi Sensing | RuView Wi-Fi CSI framework |
| Firmware | ESP-IDF 5.5 + Arduino IDE |
| Backend | FastAPI + Python 3.11 + SQLite |
| Dashboard | HTML / CSS / JavaScript (served by FastAPI) |
| Startup | One-click `START_CAPSTONE.bat` automation |

## System Architecture

```
ESP32-S3 Node #1  ──┐
ESP32-S3 Node #2  ──┤  Wi-Fi CSI (motion / presence)
ESP32-S3 Node #3  ──┤
                    ├──► FastAPI Backend (port 8000)
ESP32-S3 Node #4  ──┘  Gas + Sound sensors    │
                                               ├─ Sensor fusion engine
                                               ├─ SQLite data logging
                                               └─ Real-time web dashboard
```

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### One-Click Start (Windows)

```bat
START_CAPSTONE.bat
```

Launches the backend server and opens the dashboard automatically.

## Hardware Components

| Component | Role |
|---|---|
| ESP32-S3 Node #1 | RuView Wi-Fi CSI sensing |
| ESP32-S3 Node #2 | RuView Wi-Fi CSI sensing |
| ESP32-S3 Node #3 | RuView Wi-Fi CSI sensing |
| ESP32-S3 Node #4 | MQ-135 gas sensor + KY-037 sound sensor |

## Key Goals

- Detect presence and motion using Wi-Fi CSI without cameras
- Collect gas and noise environmental measurements
- Fuse multiple sensor sources into a single threat assessment
- Monitor all data in real time through a web dashboard
- Store historical logs for later analysis
- Demonstrate a complete IoT pipeline: hardware → networking → backend → visualization
