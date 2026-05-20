import csv
import os
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
}

# ── Occupancy Tracking ─────────────────────────────────────────
occupancy = {
    "occupied":          False,      # is someone currently in the room?
    "entry_time":        None,       # datetime when motion first detected
    "duration_seconds":  0,          # how long they've been there
    "exit_time":         None,       # datetime when they left
    "last_session_sec":  0,          # duration of the last completed session
    "sound_spike_count": 0,          # number of sound spikes during this session
    "sessions_today":    0,          # total sessions logged today
}

# Thresholds
OCCUPANCY_ALERT_SECONDS = 300       # 5 minutes = abnormal stay
SOUND_SPIKE_THRESHOLD   = 70        # dB level that counts as a spike
EXIT_TIMEOUT_SECONDS    = 10        # seconds of no motion before marking exit
last_motion_time        = None      # track when we last saw motion

def update_occupancy(motion: bool, sound_level: int):
    """Update occupancy state based on latest motion and sound readings."""
    global last_motion_time

    now = datetime.now()

    if motion:
        last_motion_time = now

        if not occupancy["occupied"]:
            # Someone just entered
            occupancy["occupied"]          = True
            occupancy["entry_time"]        = now
            occupancy["duration_seconds"]  = 0
            occupancy["sound_spike_count"] = 0
            occupancy["exit_time"]         = None
            print(f"[occupancy] ENTRY detected at {now.strftime('%H:%M:%S')}")

        else:
            # Already occupied — update duration
            if occupancy["entry_time"]:
                occupancy["duration_seconds"] = int(
                    (now - occupancy["entry_time"]).total_seconds()
                )

        # Count sound spikes during session
        if sound_level >= SOUND_SPIKE_THRESHOLD:
            occupancy["sound_spike_count"] += 1
            print(f"[occupancy] Sound spike #{occupancy['sound_spike_count']} detected ({sound_level} dB)")

    else:
        # No motion detected
        if occupancy["occupied"] and last_motion_time:
            seconds_since_motion = (now - last_motion_time).total_seconds()

            if seconds_since_motion >= EXIT_TIMEOUT_SECONDS:
                # Mark as exited
                duration = occupancy["duration_seconds"]
                occupancy["occupied"]         = False
                occupancy["exit_time"]        = now
                occupancy["last_session_sec"] = duration
                occupancy["sessions_today"]  += 1
                print(f"[occupancy] EXIT detected. Duration: {duration}s, Spikes: {occupancy['sound_spike_count']}")

                # Log session to CSV
                log_occupancy_session(duration, occupancy["sound_spike_count"])

def log_occupancy_session(duration_sec: int, sound_spikes: int):
    """Log a completed occupancy session to CSV."""
    os.makedirs("../data", exist_ok=True)
    file_exists = os.path.isfile("../data/occupancy_log.csv")
    with open("../data/occupancy_log.csv", mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "exit_time", "duration_seconds", "duration_minutes",
                "sound_spikes", "abnormal"
            ])
        abnormal = duration_sec >= OCCUPANCY_ALERT_SECONDS or sound_spikes >= 3
        writer.writerow([
            datetime.now().isoformat(),
            duration_sec,
            round(duration_sec / 60, 2),
            sound_spikes,
            abnormal
        ])

def get_occupancy_alerts(duration_sec: int, sound_spikes: int, gas: int, motion: bool):
    """Generate occupancy-aware alerts."""
    alerts = []
    threat = "low"

    if motion and duration_sec >= OCCUPANCY_ALERT_SECONDS:
        alerts.append(f"Prolonged occupancy: {duration_sec // 60}m {duration_sec % 60}s")
        threat = "medium"

    if motion and duration_sec >= OCCUPANCY_ALERT_SECONDS * 2:
        alerts.append("Extended stay — possible incident")
        threat = "high"

    if sound_spikes >= 3 and motion:
        alerts.append(f"Repeated sound spikes detected ({sound_spikes}x)")
        threat = "high" if threat != "high" else threat

    if motion and duration_sec >= OCCUPANCY_ALERT_SECONDS and sound_spikes >= 2:
        alerts.append("Prolonged stay + sound anomaly — investigate")
        threat = "high"

    if gas >= 400:
        alerts.append("Dangerous gas level detected")
        threat = "high"
    elif gas >= 250:
        alerts.append("Poor air quality detected")
        if threat == "low":
            threat = "medium"

    if motion and gas >= 300 and duration_sec >= 60:
        alerts.append("Motion + gas anomaly during occupancy")
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

def save_to_csv(data):
    os.makedirs("../data", exist_ok=True)
    file_exists = os.path.isfile("../data/sensor_logs.csv")
    with open("../data/sensor_logs.csv", mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp", "source", "motion", "sound_level", "gas_level",
                "presence_score", "heart_rate", "rssi",
                "occupancy_duration_sec", "sound_spikes",
                "threat_level", "alerts"
            ])
        writer.writerow([
            data.get("timestamp"),
            data.get("source", "unknown"),
            data.get("motion"),
            data.get("sound_level"),
            data.get("gas_level"),
            data.get("presence_score"),
            data.get("heart_rate"),
            data.get("rssi"),
            data.get("occupancy", {}).get("duration_seconds", 0),
            data.get("occupancy", {}).get("sound_spike_count", 0),
            data.get("analysis", {}).get("threat_level"),
            "; ".join(data.get("analysis", {}).get("alerts", []))
        ])

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
        "occupied":          occupancy["occupied"],
        "duration_seconds":  occupancy["duration_seconds"],
        "sound_spike_count": occupancy["sound_spike_count"],
        "sessions_today":    occupancy["sessions_today"],
        "last_session_sec":  occupancy["last_session_sec"],
        "entry_time":        occupancy["entry_time"].isoformat() if occupancy["entry_time"] else None,
    }

    # Generate occupancy-aware alerts
    analysis = get_occupancy_alerts(
        occupancy["duration_seconds"],
        occupancy["sound_spike_count"],
        gas_level,
        motion
    )
    fused["analysis"] = analysis

    fake_database.append(fused)
    save_to_csv(fused)

    duration = occupancy["duration_seconds"]
    print(f"[{source}] motion={motion} duration={duration}s spikes={occupancy['sound_spike_count']} threat={analysis['threat_level']}")

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

@app.get("/occupancy")
def get_occupancy():
    """Current occupancy state."""
    return {
        "occupied":          occupancy["occupied"],
        "duration_seconds":  occupancy["duration_seconds"],
        "duration_minutes":  round(occupancy["duration_seconds"] / 60, 1),
        "sound_spike_count": occupancy["sound_spike_count"],
        "sessions_today":    occupancy["sessions_today"],
        "last_session_sec":  occupancy["last_session_sec"],
        "entry_time":        occupancy["entry_time"].isoformat() if occupancy["entry_time"] else None,
        "alert_threshold_sec": OCCUPANCY_ALERT_SECONDS,
    }

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
