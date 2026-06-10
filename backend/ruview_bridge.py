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
# Per-board presence score that counts as "active". Your empty room reads noisy
# and high (3-15), so this MUST be tuned to your environment — raise it until an
# empty room stops triggering. Use scripts/calibration_logger.py to find it.
# SYNC with people_counter.py PRESENCE_OCCUPIED so motion only fires when
# someone is genuinely present.
PRESENCE_THRESH = 7.0
# Consensus: how many boards must agree before we declare motion. With multiple
# boards this outvotes single-board noise (the key to "more nodes = reliable").
MOTION_MIN_NODES = 2
# ────────────────────────────────────────────────────────────────────────────

# Shared state updated by the reader thread
latest_frame = {
    "motion": False,
    "presence_score": 0.0,
    "breathing_rate": 0,
    "heart_rate": 0,
    "n_persons": 0,
    "rssi": 0,
    "csi_nodes": 0,          # how many CSI boards reported in the latest frame
}
frame_lock = threading.Lock()

# Only True once rf-scan.js delivers at least one real CSI frame.
# Guards against posting stale defaults when no ESP32 is connected.
has_csi_data = False


def read_ruview(proc):
    """Reads JSON lines from rf-scan.js --json output and updates latest_frame."""
    global has_csi_data
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

            # Aggregate across all CSI boards using CONSENSUS so one noisy board
            # can't cause false detections. (Plain MAX/OR amplifies noise — that
            # is exactly why presence looked random and occupancy stuck high.)
            #   motion    -> only when >= MOTION_MIN_NODES boards agree
            #   presence  -> drop the single highest (noisiest) board when >=3
            #   n_persons -> median, robust to one outlier board
            #   vitals    -> from the board seeing the strongest presence
            per_presence, per_persons = [], []
            motion_votes  = 0
            best_presence = -1.0
            breathing_rate = heart_rate = rssi = 0

            for nd in nodes:
                v   = nd.get("vitals") or {}
                ps  = v.get("presenceScore", 0.0) or 0.0
                npp = v.get("nPersons", 0) or 0
                me  = v.get("motionEnergy", 0) or 0

                per_presence.append(ps)
                per_persons.append(npp)
                if me > 0 or ps >= PRESENCE_THRESH:
                    motion_votes += 1
                if ps > best_presence:
                    best_presence  = ps
                    breathing_rate = v.get("breathingRate", 0) or 0
                    heart_rate     = v.get("heartrate", 0) or 0
                    rssi           = nd.get("rssi", 0) or 0

            n = len(nodes)
            motion = motion_votes >= min(MOTION_MIN_NODES, n)

            # Trimmed presence: ignore the single noisiest board when we have >=3.
            per_presence.sort(reverse=True)
            presence_score = per_presence[1] if n >= 3 else per_presence[0]

            # Median people-count: a lone board hallucinating a crowd is outvoted.
            per_persons.sort()
            n_persons = per_persons[n // 2]

            with frame_lock:
                latest_frame.update({
                    "motion":          motion,
                    "presence_score":  round(presence_score, 2),
                    "breathing_rate":  round(breathing_rate),
                    "heart_rate":      round(heart_rate),
                    "n_persons":       n_persons,
                    "rssi":            rssi,
                    "csi_nodes":       n,
                })
            has_csi_data = True

        except json.JSONDecodeError:
            pass  # skip non-JSON lines (startup messages)
        except Exception as e:
            print(f"[bridge] Reader error: {e}")


def post_to_backend():
    """Reads latest frame and POSTs to FastAPI backend."""
    if not has_csi_data:
        print("[bridge] No CSI data yet — skipping POST (no ESP32 connected)")
        return

    with frame_lock:
        frame = dict(latest_frame)

    payload = {
        "motion":      frame["motion"],
        # This CSI node has no microphone or gas sensor. Those readings come from
        # the environmental sensor node (source "esp32_node4"), and the backend's
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
        "csi_nodes":      frame["csi_nodes"],
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
    print("  RuView -> FastAPI Bridge")
    print(f"  Backend : {BACKEND_URL}")
    print(f"  UDP port: {RUVIEW_PORT}")
    print(f"  Interval: every {UPDATE_INTERVAL}s")
    print("=" * 55)
    print("[bridge] Starting rf-scan.js...")

    # Start rf-scan.js as a subprocess with JSON output
    # rf-scan.js lives in the external RuView framework directory.
    rf_scan_path = r"C:\Users\Branm\OneDrive\Documents\School\Spring 26\CSS 496\Ruview\RuView\scripts\rf-scan.js"
    proc = subprocess.Popen(
        ["node", rf_scan_path, "--port", str(RUVIEW_PORT), "--json"],
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
