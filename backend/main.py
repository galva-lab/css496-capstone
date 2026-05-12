import csv
import os
from fastapi import FastAPI
from datetime import datetime

app = FastAPI()

fake_database = []

def save_to_csv(data):
    file_exists = os.path.isfile("../data/sensor_logs.csv")

    with open("../data/sensor_logs.csv", mode="a", newline="") as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow([
                "timestamp",
                "motion",
                "sound_level",
                "gas_level",
                "threat_level",
                "alerts"
            ])

        writer.writerow([
            data.get("timestamp"),
            data.get("motion"),
            data.get("sound_level"),
            data.get("gas_level"),
            data.get("analysis", {}).get("threat_level"),
            "; ".join(data.get("analysis", {}).get("alerts", []))
        ])

def analyze_data(data):
    alerts = []

    motion = data.get("motion", False)
    sound = data.get("sound_level", 0)
    gas = data.get("gas_level", 0)

    threat_level = "low"

    if motion and sound >= 80:
        alerts.append("Possible aggressive activity")
        threat_level = "medium"

    if gas >= 250:
        alerts.append("Poor air quality detected")
        threat_level = "medium"

    if motion and sound >= 100:
        alerts.append("Possible emergency screaming detected")
        threat_level = "high"

    if gas >= 400:
        alerts.append("Dangerous gas level detected")
        threat_level = "high"

    return {
        "motion_detected": motion,
        "sound_level": sound,
        "gas_level": gas,
        "threat_level": threat_level,
        "alerts": alerts
    }

@app.get("/")
def home():
    return {"status": "backend running"}

@app.post("/sensor-data")
def receive_sensor_data(data: dict):
    data["timestamp"] = datetime.now().isoformat()
    analysis = analyze_data(data)
    data["analysis"] = analysis

    fake_database.append(data)
    save_to_csv(data)

    print("Received:", data)

    return {
        "status": "received",
        "stored_items": len(fake_database),
        "data": data
    }

@app.get("/logs")
def get_logs():
    return fake_database

@app.get("/latest")
def get_latest():
    if len(fake_database) == 0:
        return {"message": "No data yet"}
    return fake_database[-1]