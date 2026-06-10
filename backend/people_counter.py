"""
people_counter.py
-----------------
Occupancy ESTIMATOR for the multi-sensor system (adapted to the FastAPI backend).

HONEST FRAMING (read before trusting the number):
  This produces a COARSE occupancy estimate, not an exact head count. The
  sensors available — Wi-Fi CSI motion/presence (+ RuView's n_persons), a
  RELATIVE sound spike, and a mostly-inactive gas reading — cannot reliably
  tell 3 people from 4. What they CAN do well is estimate a level
  (Empty / Occupied / Busy / Crowded) and track when occupancy rises or falls.

  Treat `occupancy_level` as the trustworthy output and `estimated_count` as a
  smoothed best-guess.

How this avoids the classic people-counting failure modes:
  * Overcounting on a transient spike  -> EMA temporal smoothing of the estimate
  * "Stuck" count after people leave    -> decay toward 0 when activity stops
  * Jumpy output                        -> rounded, smoothed integer

Tuning lives in backend/.env (see .env.example). State is kept in module-level
`_state` between calls (one monitored space).
"""

import os
import time


def _load_env():
    """Minimal .env reader (no external dependency). Real environment variables
    take precedence over the .env file."""
    path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())


_load_env()


def _f(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return float(default)


# ── Tunable config (overridable via backend/.env) ───────────────────────────
PRESENCE_OCCUPIED = _f("PRESENCE_OCCUPIED", 7.0)   # presence_score => at least 1 person
                                                     # (raised because empty room reads ~5-6)
PRESENCE_BUSY     = _f("PRESENCE_BUSY", 14.0)      # strong disturbance => likely >1
                                                     # (default very high because 1 active person
                                                     #  can already score 10-15)
SMOOTHING_ALPHA   = _f("SMOOTHING_ALPHA", 0.4)     # EMA weight for newest reading (0..1)
DECAY_AFTER_SEC   = _f("DECAY_AFTER_SEC", 8)       # idle seconds before estimate decays
DECAY_STEP        = _f("DECAY_STEP", 1.0)          # drop per inactive update
MAX_COUNT         = int(_f("MAX_COUNT", 5))

# (max_count_inclusive, label) — coarse levels are the honest output
LEVELS = [
    (0, "Empty"),
    (1, "Occupied"),
    (3, "Busy"),
    (MAX_COUNT, "Crowded"),
]

_state = {
    "smoothed": 0.0,
    "last_activity": 0.0,
}


def _level_for(count: int) -> str:
    for ceiling, label in LEVELS:
        if count <= ceiling:
            return label
    return LEVELS[-1][1]


def _raw_estimate(motion, presence_score, n_persons, sound_spike):
    """Instantaneous, un-smoothed estimate from a single reading.

    CRITICAL: RuView's n_persons is hard-clamped to [1, 4] and structurally
    incapable of reporting 0.  We therefore do NOT trust it as standalone
    evidence — it is only used as a refinement when motion or presence_score
    already proves someone is actually in the room.

    Additionally, a single very active person can drive presence_score just as
    high as two quiet people.  We therefore only declare >1 person when there
    is MULTI-MODAL evidence (motion + high presence + sound spike), keeping
    the estimator honest about its limitations.
    """
    # Genuine presence: do NOT trust motion as standalone evidence.
    # CSI "motion" is noisy — an empty room can still read motionEnergy > 0
    # when the adaptive baseline drifts.  We therefore require a strong enough
    # presence_score (the more reliable signal) to declare someone is here.
    genuine_presence = presence_score >= PRESENCE_OCCUPIED or sound_spike

    if not genuine_presence:
        base = 0
    elif presence_score >= PRESENCE_BUSY and sound_spike:
        # Multi-modal consensus: strong CSI disturbance + loud noise
        # is the ONLY combination we trust for >1 person.
        base = max(2, min(n_persons, MAX_COUNT)) if n_persons else 2
    elif presence_score >= PRESENCE_BUSY:
        # High presence but no sound spike = 1 very active person.
        base = 1
    else:
        # Weak / moderate presence: exactly 1 person.
        base = 1

    return base


def update(reading: dict) -> dict:
    """Take a fused sensor reading and return the occupancy estimate.

    Maintains exponential smoothing + inactivity decay between calls so the
    estimate ignores momentary spikes and falls back to Empty when the room
    goes quiet.
    """
    now = time.time()
    motion         = bool(reading.get("motion"))
    presence_score = float(reading.get("presence_score") or 0)
    n_persons      = int(reading.get("n_persons") or 0)
    sound_spike    = bool(reading.get("sound_spike"))

    raw = _raw_estimate(motion, presence_score, n_persons, sound_spike)
    active = sound_spike or presence_score >= PRESENCE_OCCUPIED or raw > 0

    if active:
        _state["last_activity"] = now
        # Exponential smoothing toward the newest raw estimate.
        _state["smoothed"] = (SMOOTHING_ALPHA * raw +
                              (1 - SMOOTHING_ALPHA) * _state["smoothed"])
    elif now - _state["last_activity"] >= DECAY_AFTER_SEC:
        # Sustained inactivity: decay toward zero so the count can't get stuck.
        _state["smoothed"] = max(0.0, _state["smoothed"] - DECAY_STEP)

    count = max(0, min(int(round(_state["smoothed"])), MAX_COUNT))
    return {
        "estimated_count": count,
        "occupancy_level": _level_for(count),
        "raw_estimate":    raw,
        "smoothed":        round(_state["smoothed"], 2),
    }


def reset():
    """Clear state (for tests or a fresh deployment)."""
    _state["smoothed"] = 0.0
    _state["last_activity"] = 0.0
