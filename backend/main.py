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
    "wifi_csi":    None,   # ESP32 #1 + #2 via ruview_bridge
    "esp32_node3": None,   # ESP32 #3 gas + sound
}

def save_to_csv(data):
    file_exists = os.path.isfile("../data/sensor_logs.csv")
    with open("../data/sensor_logs.csv", mode="a", newline="") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow([
                "timestamp", "source",
                "motion", "sound_level", "gas_level",
                "presence_score", "heart_rate", "rssi",
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
            data.get("analysis", {}).get("threat_level"),
            "; ".join(data.get("analysis", {}).get("alerts", []))
        ])

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

def analyze_data(data):
    alerts = []
    motion = data.get("motion", False)
    sound  = data.get("sound_level", 0)
    gas    = data.get("gas_level", 0)
    pres   = data.get("presence_score", 0)
    threat_level = "low"

    if motion and sound >= 80:
        alerts.append("Possible aggressive activity")
        threat_level = "medium"

    if motion and sound >= 100:
        alerts.append("Possible emergency — loud noise detected")
        threat_level = "high"

    if gas >= 250:
        alerts.append("Poor air quality detected")
        if threat_level == "low":
            threat_level = "medium"

    if gas >= 400:
        alerts.append("Dangerous gas level detected")
        threat_level = "high"

    if motion and gas >= 300:
        alerts.append("Motion + gas anomaly — possible incident")
        threat_level = "high"

    return {
        "motion_detected": motion,
        "sound_level":     sound,
        "gas_level":       gas,
        "presence_score":  pres,
        "threat_level":    threat_level,
        "alerts":          alerts
    }

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
    analysis = analyze_data(fused)
    fused["analysis"] = analysis

    fake_database.append(fused)
    save_to_csv(fused)

    print(f"[{source}] gas={fused.get('gas_level')} sound={fused.get('sound_level')} motion={fused.get('motion')} threat={analysis['threat_level']}")

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
