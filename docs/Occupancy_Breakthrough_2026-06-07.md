# Occupancy Detection — Diagnosis & Working Solution

**Date:** 2026-06-07
**Project:** Privacy-Preserving Multi-Sensor IoT Restroom Monitor
**Result:** Empty vs Occupied detection now works (was non-functional).

---

## 1. Starting point: the system could not detect occupancy

Controlled live tests (single calibration, ground-truth from an on-site person)
showed the original CSI pipeline carried **no occupancy information**:

| Condition | presence_score (firmware) |
|---|---|
| EMPTY | mean 7.51, median 6.42, up to **37** |
| OCCUPIED (1 person) | mean 6.90, median 6.58 |

Empty read **higher** than occupied. 40% of samples crossed the threshold in
*both* states. Cohen's d = −0.16 (no separation). The system effectively always
reported "Occupied." Sound and gas sensors read 0 (dead). `n_persons` was always
4 (a firmware artifact: `n_persons = top_k/2`, clamped to 4).

## 2. Root causes (found by reading firmware + controlled experiments)

1. **Promiscuous capture, no MAC filter.** Each CSI frame came from a different
   ambient transmitter, so RSSI swung −34…−75 dB frame-to-frame. The channel
   "signal" was dominated by *which transmitter sent the frame*, not by people.
2. **Firmware presence/motion is phase-based and saturates.** Even after the link
   was stabilized, the firmware `motion` metric was pegged at 1.00 and `presence`
   swung 1…37 in an empty room. CSI phase on the ESP32 is corrupted by CFO/SFO;
   the phase-variance metric is therefore useless here.

## 3. The two fixes

### Fix A — MAC filter (stable link)
Set `filter_mac` in each node's NVS to the AP BSSID (`72:13:01:84:04:59`). Each
node now locks onto one transmitter. **RSSI went from ±41 dB swing to ±1 dB.**
This alone surfaced a faint real signal (Cohen's d: −0.16 → +0.29).
Provisioning: `provisioning/README_FILTER_MAC.md` (USB flash, no network path
exists for this).

### Fix B — host-side amplitude detector (good feature)
`backend/csi_amplitude_bridge.py` replaces the RuView bridge. It reads raw CSI
over UDP, computes the **temporal standard deviation of amplitude** (not phase)
over a sliding window, EMA-smooths it, and maps it to `presence_score` for the
existing backend. Amplitude is robust where ESP32 phase is not.

## 4. Result (live, two nodes, 90 s each)

Single-node validation: **Cohen's d = 0.63, ~85% separation** at the amplitude
threshold. Integrated two-node system, current geometry:

| Condition | presence_score (amplitude, EMA) | Dashboard |
|---|---|---|
| EMPTY (person away) | **8.1 – 8.7** (stable) | Empty |
| OCCUPIED (person at counter, moving) | **12 – 30** | Occupied |

Threshold `PRESENCE_OCCUPIED=9.3`. Transitions both ways are correct and stable.
The journey: **always-Occupied (d=−0.16) → stable link (d=+0.29) → amplitude
detector (clean Empty/Occupied).**

## 5. How to run

```
START_CAPSTONE.bat
```
Launches the backend (no `--reload`) and `csi_amplitude_bridge.py --nodes 1 5`,
opens the dashboard. Requires the nodes flashed with `filter_mac` and powered.
Manual: `uvicorn main:app --host 0.0.0.0 --port 8000` then
`python csi_amplitude_bridge.py --nodes 1 5` from `backend/`.

Config (`backend/.env`): `PRESENCE_OCCUPIED=9.3` (amplitude scale = amp_std×10),
`MAX_COUNT=1` (binary Empty/Occupied). Restart backend to apply.

## 6. Honest limitations

- **Short range with the current clustered geometry** (laptop + 2 nodes + router
  on one counter): detects people *near the counter*, not the whole room. Spread
  the nodes to cover a room; re-calibrate the threshold for the new geometry.
- **Binary Empty/Occupied only.** Head-counting is not reliable with this signal.
- **Threshold is geometry-specific** — recalibrate after moving nodes.
- **Sound/gas sensors are dead** (separate hardware issue, not fixed here).

## 7. Roadmap: multi-person

The credible path is RuView's `scripts/mincut-person-counter.js` (Stoer-Wagner
min-cut on subcarrier correlation; built to fix "n_persons always 4"). It runs on
the host and can `--replay` recorded `.csi.jsonl`. It must be validated against
**labeled multi-person captures** (1/2/3 people) before integration.

## 8. Operational note

Avoid running the backend with `uvicorn --reload`: the reloader forks
`multiprocessing` children that orphan and hold port 8000 with stale code/config
(this caused phantom "Busy" readings during development). Run a single plain
worker. Only one process may bind UDP 5005.
