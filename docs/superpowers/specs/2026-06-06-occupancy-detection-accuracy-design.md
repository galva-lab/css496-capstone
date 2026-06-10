# Occupancy Detection Accuracy — Design Spec

**Date:** 2026-06-06
**Project:** Privacy-Preserving Multi-Sensor IoT Restroom Monitor
**Status:** Draft for review
**Scope decision:** Phase 1 = reliable **Empty vs Occupied** now; Phase 2 = **multi-person** later.

---

## 1. Context

A prior agent (Kimi) re-tuned the occupancy estimator and documented it in
`docs/Capstone_Fix_Report_2026-06-06.md`. The user reported the data felt
inaccurate and asked for an analysis-first pass (no code changes) before any
rework. This spec is the result of that analysis, grounded in **live diagnostics
run against the actual ESP32 hardware** (the host running this codebase is
connected to the nodes in real time), not just historical logs.

---

## 2. Evidence (what is actually true *now*)

### 2.1 Live diagnostic (2026-06-06 ~07:40, backend already running)

Ground truth confirmed by user: **1 person physically in the room.**

| Signal | Live value | Verdict |
|---|---|---|
| `presence_score` | bouncing 2.7 – 8.7 | noisy but usable |
| occupancy output | `Occupied (1)`, stable | ✅ **correct** for the occupied case |
| oscillation into Busy/Crowded | none observed | ✅ multi-person dead code not firing |
| `wifi_csi` + `esp32_node4` | both `connected: true` | nodes online |
| `sound_level` | **0** (confirmed live) | ❌ sound sensor dead |
| `gas_level` | **0** (node4 online, was 220 on Jun 5) | ❌ gas sensor degraded to 0 |
| `n_persons` | **always 4** | ⚠️ firmware artifact, not a count |
| `motion` | always `True` | ⚠️ CSI false-positive; harmless (logic uses presence_score) |
| Empty detection | not validated live | ❓ needs on-site person to step out |

### 2.2 Root causes confirmed by reading source

- **`n_persons` always 4** — `firmware/esp32-csi-node/main/edge_processing.c:481`:
  `n_persons = s_top_k_count / 2`, clamped to `[1, EDGE_MAX_PERSONS]` with
  `EDGE_MAX_PERSONS = 4`. The value is a function of how many subcarriers exceed a
  variance floor, **not** the number of people. It saturates at 4 whenever there
  is CSI energy. RuView already deprecated this (see §5).

- **Sound dead independent of connectivity** — In the Jun 5 calibration log,
  `gas_level = 220` (node4 online and posting) while `sound_level = 0`. So sound
  has *never* worked; it is not a node4-offline problem. Strongest candidates:
  `SOUND_NOISE_FLOOR = 130` over-subtracts (clips to 0), or the KY-037 `AO` pin is
  not wired / unpowered.

- **Multi-person branch is dead code** — `people_counter.py:_raw_estimate`
  declares >1 person only when `presence_score >= PRESENCE_BUSY AND sound_spike`.
  `sound_spike` can never be `True` (sound is always 0), so the branch is
  unreachable.

- **`presence_score` cannot count heads** — From `calibration_log.csv`, a single
  person produces `presence_score` 2–19; two people produce 8–23. The ranges
  overlap completely. No threshold can separate 1 from 2+ on presence alone. The
  existing `calibration_analyzer.py` already detects and reports this.

- **Historical logs are contaminated** — `occupancy_log.csv` and
  `calibration_log.csv` mix pre-fix/post-fix code, corrupted/clean CSI baselines,
  and several restarts. Example: rows at 04:42 show `raw_estimate = 4` (old
  n_persons-trusting logic) that the current code cannot produce. **Aggregate
  accuracy numbers from these files are not trustworthy.**

### 2.3 Key conclusion

In clean, current conditions the system **already does Empty-vs-Occupied
acceptably** for the occupied case. Phase 1 is therefore about **hardening,
honesty, and proof** — not a rebuild. Reliable head-counting above
Empty/Occupied is **not achievable from `presence_score` alone**; it requires a
different person-count source (Phase 2, §5).

---

## 3. Phase 1 — Empty vs Occupied

### 3.1 Goals

1. The system reports **Empty** when the room is empty and **Occupied** when ≥1
   person is present, stably (no flicker, no spurious Busy/Crowded).
2. The output is **honest**: it never emits a level it cannot justify with the
   working sensor (CSI presence).
3. Behavior is **validated live** against ground truth, on a single code version,
   with clean (uncontaminated) logs.

### 3.2 Changes

**A. Quarantine the unjustifiable multi-person output (backend, remote).**
In `people_counter.py`, simplify `_raw_estimate` for Phase 1 so the reportable
level is capped at **Occupied**:
- `genuine_presence` (presence_score ≥ `PRESENCE_OCCUPIED`, or a future sound
  spike) → `1`
- otherwise → `0`
- Remove/guard the `PRESENCE_BUSY + sound_spike` branch so Busy/Crowded are not
  emitted while we cannot substantiate them.
- Keep the existing EMA smoothing + inactivity decay (they work).
- The Busy/Crowded levels and the multi-person logic are **preserved in design**
  for Phase 2 but disabled/guarded, not deleted, with a clear comment pointing to
  this spec.

**B. Boundary hysteresis (backend, remote) — only if §3.3 shows flicker.**
Require `presence_score ≥ PRESENCE_OCCUPIED` for **N consecutive readings**
before declaring Occupied; clear via the existing decay. Default N small (e.g.
2). This is conditional on the empty-room test revealing 0↔1 flicker.

**C. Data hygiene (repo).**
- Archive the contaminated logs (`occupancy_log.csv`, `calibration_log.csv`) to a
  clearly named backup so fresh calibration starts clean.
- Establish the protocol: collect calibration data only **after a clean reboot
  with the room empty**, on **one** code version.

### 3.3 Validation (live, operator-directed)

The only Phase 1 gap left is the **empty-room case**. With an on-site person:
1. Confirm 1-person → `Occupied` (already observed live).
2. Person steps out → confirm the estimate decays to `Empty` within the expected
   window and does **not** false-positive back to Occupied from CSI noise.
3. If false positives appear, raise `PRESENCE_OCCUPIED` and/or apply §3.2-B
   hysteresis, then re-test.
4. Run `calibration_logger.py` for a 0-vs-1 session and confirm
   `calibration_analyzer.py` reports presence cleanly separates empty < occupied.

### 3.4 Firmware diagnostic (needs on-site flash; Phase-1-optional)

Empty/Occupied does not need sound, but the environmental modality is fully dead
and matters for the "restroom safety" anomaly use case. Prepare a ready-to-flash
diagnostic patch to `Arduino script/esp32_node3_sensors/esp32_node3_sensors.ino`:
- Lower `SOUND_NOISE_FLOOR` 130 → ~30.
- Add verbose serial for raw ADC of **both** gas (GPIO 4) and sound (GPIO 5) so
  the operator can tell wiring/power failure from scaling. (Both reading 0 while
  the node is WiFi-connected points to a shared power/ground or ADC issue.)
- Optional: WiFi reconnect watchdog so the node cannot silently drop.

This is staged for whenever the on-site person can flash; it does not block the
backend deliverable.

### 3.5 Out of scope for Phase 1

- Multi-person counting (Phase 2).
- mincut integration into the live pipeline (Phase 2; feasibility already proven,
  §5).
- WebSocket/dashboard rework, mDNS discovery (future work in fix report §8).

---

## 4. Phase 1 Acceptance Criteria

- Room empty → `Empty`; 1 person → `Occupied`, both stable over a multi-minute
  live test with operator-provided ground truth.
- No Busy/Crowded emitted in Phase 1.
- `calibration_analyzer.py` on a fresh 0-vs-1 session reports presence separates
  empty < occupied ("usable").
- Contaminated logs archived; fresh logs are single-version.

---

## 5. Phase 2 — Multi-person (roadmap, de-risked)

**Approach: replace the saturated firmware `n_persons` with RuView's
`scripts/mincut-person-counter.js`** (host-side, no firmware change). It builds a
subcarrier amplitude-correlation graph and uses Stoer-Wagner min-cut to find
independent perturbation groups (≈ persons). It was written specifically to fix
"n_persons always shows 4" (RuView issue #348).

**Feasibility already verified (2026-06-06):**
- It runs on this host (Node v24) against recorded CSI:
  `node scripts/mincut-person-counter.js --replay data/recordings/pretrain-1775182186.csi.jsonl --json`
- Output is a real `personCount` (returned **1**, not the saturated 4) with
  per-node groups. The "always 4" artifact disappears.

**Not yet proven:** that it accurately separates 2/3 people — the available
recordings (`pretrain` "mixed-activity", `overnight`) appear to be single-person.

**Phase 2 plan:**
1. **Capture labeled CSI** with a known head count (1, then 2, then 3 people,
   ~2 min each) — needs on-site coordination. *Cheap to do now while the on-site
   person is available; recommended even before Phase 1 closes.*
2. Tune mincut thresholds (`--corr-threshold`, `--cut-threshold`, `--var-floor`)
   against the labeled captures via `--replay` until counts match ground truth.
3. Integrate: run mincut as the person-count source (e.g. `--forward` to a port
   the bridge reads, or have the bridge consume its JSON), feeding a validated
   count into `people_counter.py`. Re-enable Busy/Crowded levels driven by the
   real count.
4. Re-validate end-to-end with live multi-person tests.

---

## 6. Open items requiring on-site help

| Item | Why on-site | Blocks |
|---|---|---|
| Empty-room live test | someone must leave the room | Phase 1 validation |
| Flash firmware diagnostic | physical access to node4 | Sound/gas recovery |
| Labeled multi-person CSI capture | someone must set head count | Phase 2 validation |

---

## 7. Risks

- **Empty baseline may be high.** If CSI booted while occupied, empty reads high
  until reboot-when-empty. The empty-room test must follow a clean reboot.
- **mincut may not separate real people** even with tuning; if so, the sensor
  geometry (boards must straddle the walking path) or an added modality
  (recovered sound spike for "disturbance", or mmWave) becomes the Phase 2 lever.
  Empty/Occupied (Phase 1) remains valid regardless.
- **Sound/gas may be a hardware fault** (both zero) that a firmware patch cannot
  fix; the diagnostic serial output will disambiguate.
