"""
calibration_logger.py
----------------------
Collect ground-truth vs predicted occupancy while the system is running.

It polls the backend, shows the current estimate and sensor readings, and asks
you how many people are ACTUALLY present. Each answer is saved with the sensor
data to data/calibration_log.csv, which calibration_analyzer.py then uses to
measure accuracy and suggest threshold tuning.

Usage:
  1. Start the full system (START_CAPSTONE.bat) so the backend is live.
  2. Run:  python calibration_logger.py
  3. Each prompt: type the real number of people present, or 'q' to quit.

No external dependencies (uses urllib).
"""

import csv
import json
import os
import time
import urllib.request

BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
DATA = os.path.join(os.path.dirname(__file__), "..", "data")
LOG = os.path.join(DATA, "calibration_log.csv")
FIELDS = [
    "timestamp", "actual_count", "predicted_count", "occupancy_level",
    "motion", "presence_score", "n_persons", "sound_level", "sound_spike", "gas_level",
]


def get_latest():
    with urllib.request.urlopen(f"{BACKEND}/latest", timeout=3) as r:
        return json.load(r)


def main():
    os.makedirs(DATA, exist_ok=True)
    is_new = not os.path.exists(LOG)
    print("Calibration logger")
    print(f"  backend: {BACKEND}")
    print("  Type the ACTUAL number of people present, or 'q' to quit.\n")

    with open(LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if is_new:
            w.writeheader()
            f.flush()

        while True:
            try:
                d = get_latest()
            except Exception as e:
                print(f"  (can't reach backend at {BACKEND}: {e})")
                time.sleep(2)
                continue

            if d.get("message"):
                print("  (no data yet — is the system sending readings?)")
                time.sleep(2)
                continue

            people = d.get("people", {})
            pred = people.get("estimated_count")
            level = people.get("occupancy_level")
            print(f"Prediction: {pred} ({level}) | "
                  f"motion={d.get('motion')} presence={d.get('presence_score')} "
                  f"n_persons={d.get('n_persons')} sound_spike={d.get('sound_spike')} "
                  f"gas={d.get('gas_level')}")

            ans = input("  Actual people present? > ").strip().lower()
            if ans in ("q", "quit", "exit"):
                break
            if not ans.isdigit():
                print("  (enter a whole number, or q)\n")
                continue

            w.writerow({
                "timestamp":       d.get("timestamp"),
                "actual_count":    int(ans),
                "predicted_count": pred,
                "occupancy_level": level,
                "motion":          d.get("motion"),
                "presence_score":  d.get("presence_score"),
                "n_persons":       d.get("n_persons"),
                "sound_level":     d.get("sound_level"),
                "sound_spike":     d.get("sound_spike"),
                "gas_level":       d.get("gas_level"),
            })
            f.flush()
            print("  saved.\n")

    print(f"\nDone. Wrote to {LOG}")


if __name__ == "__main__":
    main()
