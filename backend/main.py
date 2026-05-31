import csv
import os
import sqlite3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

fake_database = []

# Latest reading per source
latest_by_source = {
    "wifi_csi":    None,
    "esp32_node3": None,
    "esp32_node4": None,
}

# ── Presence (signal) Tracking ─────────────────────────────────
# Simple, honest presence flag: signal disturbance detected right now.
occupancy = {
    "presence_detected": False,
}

# Thresholds
SOUND_SPIKE_THRESHOLD = 70  # dB level considered a high instantaneous sound

def update_occupancy(motion: bool, sound_level: int):
    """Update simple presence flag based on current motion (CSI disturbance).
    Do not track sessions, durations, or exits.
    """
    occupancy["presence_detected"] = bool(motion)

def get_occupancy_alerts(gas: int, motion: bool, sound_level: int, presence_score: float = 0):
    """Generate alerts based on raw sensor readings (no session/duration logic).
    Keeps gas-based alerts and a raw sound-level threshold check.
    """
    alerts = []
    threat = "low"

    # Immediate sound threshold
    if sound_level >= SOUND_SPIKE_THRESHOLD:
        alerts.append(f"High sound level detected ({sound_level} dB)")
        threat = "high"

    # Gas-based alerts
    if gas >= 400:
        alerts.append("Dangerous gas level detected")
        threat = "high"
    elif gas >= 250:
        alerts.append("Poor air quality detected")
        if threat == "low":
            threat = "medium"

    # Motion + gas immediate anomaly (no duration requirement)
    if motion and gas >= 300:
        alerts.append("Motion + gas anomaly detected")
        if threat != "high":
            threat = "high"

    return {"threat_level": threat, "alerts": alerts}

# ── Sensor fusion ──────────────────────────────────────────────
def fuse_latest():
    csi   = latest_by_source.get("wifi_csi") or {}
    node3 = latest_by_source.get("esp32_node3") or {}
    return {
        "motion":         csi.get("motion", False),
        "presence_score": csi.get("presence_score", 0),
        "heart_rate":     csi.get("heart_rate", 0),
        "n_persons":      csi.get("n_persons", 0),
        "rssi":           csi.get("rssi", 0),
        "sound_level":    node3.get("sound_level") if node3 else csi.get("sound_level", 0),
        "gas_level":      node3.get("gas_level")   if node3 else csi.get("gas_level", 0),
        "source": "fused",
    }

def get_db_path():
    os.makedirs("../data", exist_ok=True)
    return os.path.join("../data", "sensor_logs.db")

def init_db():
    conn = sqlite3.connect(get_db_path())
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sensor_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            source TEXT,
            motion INTEGER,
            sound_level INTEGER,
            gas_level INTEGER,
            presence_score REAL,
            heart_rate INTEGER,
            rssi INTEGER,
            threat_level TEXT,
            alerts TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def save_to_db(data):
    conn = sqlite3.connect(get_db_path())
    conn.execute(
        """
        INSERT INTO sensor_logs (
            timestamp, source, motion, sound_level, gas_level,
            presence_score, heart_rate, rssi,
            threat_level, alerts
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            data.get("timestamp"),
            data.get("source", "unknown"),
            1 if data.get("motion") else 0,
            data.get("sound_level"),
            data.get("gas_level"),
            data.get("presence_score"),
            data.get("heart_rate"),
            data.get("rssi"),
            data.get("analysis", {}).get("threat_level"),
            "; ".join(data.get("analysis", {}).get("alerts", []))
        ]
    )
    conn.commit()
    conn.close()

# ── Endpoints ──────────────────────────────────────────────────
@app.get("/")
def home():
    return {"status": "backend running"}

@app.post("/sensor-data")
def receive_sensor_data(data: dict):
    data["timestamp"] = datetime.now().isoformat()
    source = data.get("source", "unknown")
    if source in latest_by_source:
        latest_by_source[source] = data

    fused = fuse_latest()
    fused["timestamp"] = data["timestamp"]

    motion      = fused.get("motion", False)
    sound_level = fused.get("sound_level", 0) or 0
    gas_level   = fused.get("gas_level", 0) or 0

    # Update occupancy tracker
    update_occupancy(motion, sound_level)

    # Attach occupancy snapshot to reading
    fused["occupancy"] = {
        "presence_detected": occupancy.get("presence_detected", False),
    }

    # Generate occupancy-aware alerts
    analysis = get_occupancy_alerts(gas_level, motion, sound_level, fused.get("presence_score"))
    fused["analysis"] = analysis

    fake_database.append(fused)
    save_to_db(fused)

    print(f"[{source}] motion={motion} presence={occupancy.get('presence_detected')} ps={fused.get('presence_score')} sound={sound_level} gas={gas_level} threat={analysis['threat_level']}")

    return {
        "status": "received",
        "stored_items": len(fake_database),
        "data": fused
    }

@app.get("/logs")
def get_logs():
    return fake_database

@app.get("/latest")
def get_latest():
    if not fake_database:
        return {"message": "No data yet"}
    return fake_database[-1]



@app.get("/nodes")
def get_nodes():
    return {
        source: {
            "connected":   data is not None,
            "last_seen":   data.get("timestamp")  if data else None,
            "gas_level":   data.get("gas_level")   if data else None,
            "sound_level": data.get("sound_level") if data else None,
            "motion":      data.get("motion")      if data else None,
        }
        for source, data in latest_by_source.items()
    }
