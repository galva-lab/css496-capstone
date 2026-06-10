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
_last_count = None
_last_heartbeat = 0.0
_HEARTBEAT_SEC = 60   # force a row every 60 s even if nothing changed


def record(estimate: dict, reading: dict) -> bool:
    """Append a row when the occupancy level OR estimated count changes,
    plus a heartbeat row every HEARTBEAT_SEC seconds.  Returns True if written.
    """
    global _last_level, _last_count, _last_heartbeat
    level = estimate.get("occupancy_level")
    count = estimate.get("estimated_count")
    now = datetime.now().timestamp()

    changed = (level != _last_level) or (count != _last_count)
    heartbeat = (now - _last_heartbeat) >= _HEARTBEAT_SEC

    if not changed and not heartbeat:
        return False

    _last_level = level
    _last_count = count
    if changed or heartbeat:
        _last_heartbeat = now

    os.makedirs(_DATA, exist_ok=True)
    is_new = not os.path.exists(_LOG)
    with open(_LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS)
        if is_new:
            w.writeheader()
        w.writerow({
            "timestamp":       datetime.now().isoformat(),
            "estimated_count": count,
            "occupancy_level": level,
            "raw_estimate":    estimate.get("raw_estimate"),
            "smoothed":        estimate.get("smoothed"),
            "motion":          reading.get("motion"),
            "presence_score":  reading.get("presence_score"),
            "sound_spike":     reading.get("sound_spike"),
            "gas_level":       reading.get("gas_level"),
        })
        f.flush()          # ensure row hits disk immediately
    return True


def recent(n: int = 50):
    """Return the last n occupancy transitions (most recent last)."""
    if not os.path.exists(_LOG):
        return []
    with open(_LOG) as f:
        rows = list(csv.DictReader(f))
    return rows[-n:]
