"""
people_count_history.py
-----------------------
Logs occupancy TRANSITIONS (when the level changes) to data/occupancy_log.csv,
and exposes recent history. Recording only on change keeps the log small and
meaningful instead of writing a row every couple of seconds.
"""

import csv
import os
from datetime import datetime

_DATA = os.path.join(os.path.dirname(__file__), "..", "data")
_LOG = os.path.join(_DATA, "occupancy_log.csv")
_FIELDS = [
    "timestamp", "estimated_count", "occupancy_level",
    "raw_estimate", "smoothed",
    "motion", "presence_score", "sound_spike", "gas_level",
]

_last_level = None


def record(estimate: dict, reading: dict) -> bool:
    """Append a row only when the occupancy level changes. Returns True if written."""
    global _last_level
    level = estimate.get("occupancy_level")
    if level == _last_level:
        return False
    _last_level = level

    os.makedirs(_DATA, exist_ok=True)
    is_new = not os.path.exists(_LOG)
    with open(_LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS)
        if is_new:
            w.writeheader()
        w.writerow({
            "timestamp":       datetime.now().isoformat(),
            "estimated_count": estimate.get("estimated_count"),
            "occupancy_level": level,
            "raw_estimate":    estimate.get("raw_estimate"),
            "smoothed":        estimate.get("smoothed"),
            "motion":          reading.get("motion"),
            "presence_score":  reading.get("presence_score"),
            "sound_spike":     reading.get("sound_spike"),
            "gas_level":       reading.get("gas_level"),
        })
    return True


def recent(n: int = 50):
    """Return the last n occupancy transitions (most recent last)."""
    if not os.path.exists(_LOG):
        return []
    with open(_LOG) as f:
        rows = list(csv.DictReader(f))
    return rows[-n:]
