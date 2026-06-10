import csv
import os
import sqlite3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from datetime import datetime

import people_counter
import people_count_history

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Recent readings kept in memory for /logs and /latest. Capped so a long-running
# server doesn't grow unbounded — full history still lives in SQLite (sensor_logs.db).
MAX_RECORDS = 500
fake_database = []

# Latest reading per source
latest_by_source = {
    "wifi_csi":    None,
    "esp32_node4": None,
}

# ── Presence (signal) Tracking ─────────────────────────────────
# Simple, honest presence flag: signal disturbance detected right now.
occupancy = {
    "presence_detected": False,
}

# ── Sound spike detection (relative to a rolling baseline) ──────────────
# The KY-037 reports a RELATIVE amplitude, not calibrated decibels. So instead
# of an absolute dB threshold, we flag a SPIKE: a reading well above the room's
# recent baseline. This auto-adapts to any room. Tune the constants below.
SOUND_BASELINE_WINDOW = 15   # number of recent readings that define "normal"
SOUND_SPIKE_MARGIN    = 6    # how far above baseline a reading must jump to spike
SOUND_SPIKE_MIN       = 8    # ignore readings below this (noise floor, never a spike)

sound_history = []                          # recent sound levels (rolling window)
sound_state   = {"baseline": 0, "spike": False}

def update_occupancy(motion: bool, sound_level: int):
    """Update simple presence flag based on current motion (CSI disturbance).
    Do not track sessions, durations, or exits.
    """
    occupancy["presence_detected"] = bool(motion)

def detect_sound_spike(sound_level: int) -> dict:
    """Flag a spike when sound jumps above the room's rolling baseline.
    Baseline is the average of the PREVIOUS readings, so a single loud event
    (clap, shout) stands out instead of needing a fixed, uncalibrated dB cutoff.
    """
    baseline = sum(sound_history) / len(sound_history) if sound_history else 0
    spike = (sound_level >= SOUND_SPIKE_MIN) and (sound_level - baseline >= SOUND_SPIKE_MARGIN)

    sound_history.append(sound_level)
    if len(sound_history) > SOUND_BASELINE_WINDOW:
        del sound_history[:-SOUND_BASELINE_WINDOW]

    return {"baseline": round(baseline, 1), "spike": spike}

def get_occupancy_alerts(gas: int, motion: bool, sound_level: int, sound_spike: bool = False, presence_score: float = 0):
    """Generate alerts from current readings. Sound uses a relative SPIKE
    (a sudden jump above the room baseline) rather than an absolute level,
    because the KY-037 is not calibrated to real decibels.
    """
    alerts = []
    threat = "low"

    def escalate(level):
        nonlocal threat
        rank = {"low": 0, "medium": 1, "high": 2}
        if rank[level] > rank[threat]:
            threat = level

    # Sudden sound spike above the room baseline = anomaly
    if sound_spike:
        alerts.append(f"Sound spike detected (level {sound_level}, above baseline)")
        escalate("medium")
        if motion:
            alerts.append("Motion + sound spike - possible disturbance")
            escalate("high")

    # Gas-based alerts
    if gas >= 400:
        alerts.append("Dangerous gas level detected")
        escalate("high")
    elif gas >= 250:
        alerts.append("Poor air quality detected")
        escalate("medium")

    # Motion + gas immediate anomaly (no duration requirement)
    if motion and gas >= 300:
        alerts.append("Motion + gas anomaly detected")
        escalate("high")

    return {"threat_level": threat, "alerts": alerts}

# ── Sensor fusion ──────────────────────────────────────────────
def fuse_latest():
    csi   = latest_by_source.get("wifi_csi") or {}
    node4 = latest_by_source.get("esp32_node4") or {}
    return {
        "motion":         csi.get("motion", False),
        "presence_score": csi.get("presence_score", 0),
        "heart_rate":     csi.get("heart_rate", 0),
        "n_persons":      csi.get("n_persons", 0),
        "rssi":           csi.get("rssi", 0),
        "csi_nodes":      csi.get("csi_nodes", 0),
        "sound_level":    node4.get("sound_level") if node4 else csi.get("sound_level", 0),
        "gas_level":      node4.get("gas_level")   if node4 else csi.get("gas_level", 0),
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

    # Update sound spike state only when fresh sound data arrives (node 4),
    # so the same value isn't re-evaluated on every CSI post.
    if source == "esp32_node4":
        sound_state.update(detect_sound_spike(sound_level))

    # Update occupancy tracker
    update_occupancy(motion, sound_level)

    # Attach occupancy + sound snapshot to reading
    fused["occupancy"] = {
        "presence_detected": occupancy.get("presence_detected", False),
    }
    fused["sound_baseline"] = sound_state["baseline"]
    fused["sound_spike"]    = sound_state["spike"]

    # Occupancy estimate (smoothed + decaying — see people_counter.py)
    fused["people"] = people_counter.update(fused)
    people_count_history.record(fused["people"], fused)

    # Generate occupancy-aware alerts
    analysis = get_occupancy_alerts(gas_level, motion, sound_level, sound_state["spike"], fused.get("presence_score"))
    fused["analysis"] = analysis

    fake_database.append(fused)
    if len(fake_database) > MAX_RECORDS:
        del fake_database[:-MAX_RECORDS]  # keep only the most recent MAX_RECORDS
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



NODE_TIMEOUT_SECONDS = 30

@app.get("/nodes")
def get_nodes():
    now = datetime.now()
    result = {}
    for source, data in latest_by_source.items():
        if data is None:
            connected = False
        else:
            try:
                last_seen = datetime.fromisoformat(data["timestamp"])
                connected = (now - last_seen).total_seconds() < NODE_TIMEOUT_SECONDS
            except Exception:
                connected = False
        result[source] = {
            "connected":   connected,
            "last_seen":   data.get("timestamp")  if data else None,
            "gas_level":   data.get("gas_level")   if data else None,
            "sound_level": data.get("sound_level") if data else None,
            "motion":      data.get("motion")      if data else None,
        }
    return result

@app.get("/people-count")
def people_count():
    """Latest occupancy estimate (coarse — see people_counter.py)."""
    if not fake_database:
        return {"estimated_count": 0, "occupancy_level": "Empty"}
    return fake_database[-1].get("people", {"estimated_count": 0, "occupancy_level": "Empty"})

@app.get("/people-history")
def people_history():
    """Recent occupancy transitions (level changes over time)."""
    return people_count_history.recent()


@app.get("/export-csv")
def export_csv(limit: int = 0):
    """Export the full SQLite history as a downloadable CSV.
    Set ?limit=N to cap the number of rows (most recent first).
    """
    import io

    conn = sqlite3.connect(get_db_path())
    cursor = conn.execute("SELECT * FROM sensor_logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    if limit > 0:
        rows = rows[:limit]
    rows.reverse()  # chronological order in the file

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "timestamp", "source", "motion", "sound_level", "gas_level",
        "presence_score", "heart_rate", "rssi", "threat_level", "alerts"
    ])
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sensor_logs_export.csv"}
    )
