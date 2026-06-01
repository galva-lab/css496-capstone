"""
ruview_bridge.py
----------------
Bridges RuView ESP32 Wi-Fi CSI data to the Capstone FastAPI backend.

How it works:
  1. Runs rf-scan.js --json in the background (reads from ESP32 over UDP)
  2. Parses each JSON frame from RuView
  3. Maps CSI data → backend format (motion, sound_level, gas_level)
  4. POSTs to FastAPI every UPDATE_INTERVAL seconds

Usage:
  python ruview_bridge.py

"""

import subprocess
import json
import requests
import time
import threading

# ── Config ──────────────────────────────────────────────────────────────────
BACKEND_URL     = "http://127.0.0.1:8000/sensor-data"
RUVIEW_PORT     = 5005          # UDP port ESP32 sends to
UPDATE_INTERVAL = 2             # seconds between FastAPI POSTs
PRESENCE_THRESH = 1.5           # presence score above this = motion detected
# ────────────────────────────────────────────────────────────────────────────

# Shared state updated by the reader thread
latest_frame = {
    "motion": False,
    "presence_score": 0.0,
    "breathing_rate": 0,
    "heart_rate": 0,
    "n_persons": 0,
    "rssi": 0,
}
frame_lock = threading.Lock()


def read_ruview(proc):
    """Reads JSON lines from rf-scan.js --json output and updates latest_frame."""
    print("[bridge] RuView reader thread started...")
    for raw_line in proc.stdout:
        line = raw_line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            nodes = data.get("nodes", [])
            if not nodes:
                continue

            # Use the first node's data
            node = nodes[0]
            vitals = node.get("vitals") or {}
            classification = node.get("classification") or {}

            presence_score  = vitals.get("presenceScore", 0.0) or 0.0
            breathing_rate  = vitals.get("breathingRate", 0) or 0
            heart_rate      = vitals.get("heartrate", 0) or 0
            n_persons       = vitals.get("nPersons", 0) or 0
            motion_detected = (vitals.get("motionEnergy", 0) or 0) > 0
            rssi            = node.get("rssi", 0) or 0

            # Motion = presence score above threshold OR motion flag
            motion = motion_detected or (presence_score >= PRESENCE_THRESH)

            with frame_lock:
                latest_frame.update({
                    "motion":          motion,
                    "presence_score":  round(presence_score, 2),
                    "breathing_rate":  round(breathing_rate),
                    "heart_rate":      round(heart_rate),
                    "n_persons":       n_persons,
                    "rssi":            rssi,
                })

        except json.JSONDecodeError:
            pass  # skip non-JSON lines (startup messages)
        except Exception as e:
            print(f"[bridge] Reader error: {e}")


def post_to_backend():
    """Reads latest frame and POSTs to FastAPI backend."""
    with frame_lock:
        frame = dict(latest_frame)

    payload = {
        "motion":      frame["motion"],
        # This CSI node has no microphone or gas sensor. Those readings come from
        # the environmental sensor node (source "esp32_node3"), and the backend's
        # fuse_latest() prefers that node's values. Send 0 here so we never
        # overwrite a real sensor reading with a CSI stand-in.
        "sound_level": 0,
        "gas_level":   0,
        # Wi-Fi CSI sensing fields
        "breathing_rate": frame["breathing_rate"],
        "presence_score": frame["presence_score"],
        "heart_rate":     frame["heart_rate"],
        "n_persons":      frame["n_persons"],
        "rssi":           frame["rssi"],
        "source":         "wifi_csi",
    }

    try:
        response = requests.post(BACKEND_URL, json=payload, timeout=3)
        print(f"[bridge] POST → {payload}")
        print(f"[bridge] Response: {response.json()}")
    except requests.exceptions.ConnectionError:
        print("[bridge] ⚠ FastAPI not reachable — is it running?")
    except Exception as e:
        print(f"[bridge] POST error: {e}")


def main():
    print("=" * 55)
    print("  RuView → FastAPI Bridge")
    print(f"  Backend : {BACKEND_URL}")
    print(f"  UDP port: {RUVIEW_PORT}")
    print(f"  Interval: every {UPDATE_INTERVAL}s")
    print("=" * 55)
    print("[bridge] Starting rf-scan.js...")

    # Start rf-scan.js as a subprocess with JSON output
    proc = subprocess.Popen(
        ["node", "scripts/rf-scan.js", "--port", str(RUVIEW_PORT), "--json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )

    # Reader thread updates latest_frame continuously
    reader = threading.Thread(target=read_ruview, args=(proc,), daemon=True)
    reader.start()

    print("[bridge] Waiting for ESP32 data...")
    time.sleep(3)  # give rf-scan.js time to start receiving

    # Main loop: POST to backend every UPDATE_INTERVAL seconds
    try:
        while True:
            post_to_backend()
            time.sleep(UPDATE_INTERVAL)
    except KeyboardInterrupt:
        print("\n[bridge] Stopped by user.")
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
