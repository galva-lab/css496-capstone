# Capstone Project Comprehensive Report

**Project Title:** Privacy-Preserving Multi-Sensor IoT System for Abnormal Restroom Activity Detection Using ESP32-S3 and RuView

**Author:** Nehemiah Brandon Soebroto
**Advisor:** [FILL IN — Advisor Name]
**Sponsor:** [FILL IN — Sponsor / Lab, e.g., Galva Lab]
**Course:** CSS 496/497 — Capstone
**Quarter:** Spring 2026

---

> **Note to author:** This is a grounded draft. The technical sections reflect the system you actually built and the problems you actually solved. The reflection sections are written from those real events — please revise them into your own voice and verify the personal details (advisor, sponsor, career goals) before submitting, since this is graded as original work. Formatting target: 1.5 line spacing, section headings retained.

---

## 1. Project Overview

### 1.1 Project Description and Purpose

This capstone project is a **privacy-preserving monitoring system** that can detect potentially abnormal situations in a sensitive space — a public restroom — *without using any cameras or recording any personal images*. Restrooms are exactly the kind of place where safety monitoring is sometimes needed (medical emergencies, falls, aggressive incidents, vandalism, air-quality hazards) but where conventional camera surveillance is unacceptable for obvious privacy reasons. This project resolves that tension: it watches for *signals* of trouble while remaining structurally incapable of capturing anyone's identity or image.

Explained for a non-specialist: instead of a camera, the system "sees" people the way a bat sees in the dark — by sensing how their bodies disturb ordinary Wi-Fi radio signals already traveling through the room. It pairs that with simple environmental sensors that smell the air and listen for loud noises. A small server collects all of this, combines it, and shows a live dashboard that reads "all normal" or "possible problem" — never a face, never a recording.

Concretely, the system is built from **six ESP32-S3 microcontroller boards** (expanded from an initial four during development):

- **Nodes 1, 2, 3, 5, and 6** run the **RuView Wi-Fi Channel State Information (CSI)** framework. By measuring tiny distortions in Wi-Fi signals, they detect **motion** and **presence** — all without a camera. Their readings are combined by **consensus**, so one noisy board cannot dominate the result.
- **Node 4** is a dedicated **environmental sensing node** carrying an **MQ-135 gas sensor** (air quality / dangerous gas) and a **KY-037 sound sensor** (noise level, e.g., shouting or a crash).

All four nodes transmit over Wi-Fi to a **FastAPI backend server**. The backend performs **sensor fusion** — merging the motion/presence data with the gas/noise data — to produce a single, unified **threat assessment** (Low / Medium / High). A **real-time web dashboard** then displays motion, presence, gas level, sound level, the computed threat level, and the live status of every node. Every reading is also written to a historical log for later analysis.

### 1.2 Problem Statement and Solution Approach

**Problem:** How can a facility monitor a private space for genuine emergencies and abnormal activity *without* the privacy violation, legal exposure, and ethical cost of cameras or microphones that record identifiable content?

**Solution approach:** Replace identity-capturing sensors with *non-identifying* physical signals. Wi-Fi CSI reveals that *a body is moving* in the room without revealing *who*. A gas sensor reveals *dangerous air* without revealing a person. A sound sensor reveals *a loud event* (peak amplitude) without recording or transcribing speech. No single one of these is meaningful on its own, so the system **fuses** them in software: the combination of signals — e.g., motion plus a gas spike plus a loud noise — is what raises a flag. The output is an abstract threat level on a dashboard, not surveillance footage.

### 1.3 Primary Goals and Objectives

1. **Detect human presence and motion** using Wi-Fi CSI sensing across five coordinated nodes (combined by consensus) — no camera.
2. **Collect environmental data** (gas concentration and noise level) from a dedicated sensor node.
3. **Fuse multiple heterogeneous sensor streams** into one unified, real-time threat assessment.
4. **Deliver a complete, demonstrable IoT system** — hardware, networking, backend, data logging, and a live dashboard — that is privacy-preserving end to end.

### 1.4 Target Audience and Users

The primary beneficiaries are **facility operators and safety staff** in settings that have a duty of care but a hard privacy constraint: schools, care facilities, gyms, airports, correctional facilities, and public venues. The end users of the dashboard are the **monitoring staff** who need an at-a-glance "normal vs. attention-needed" signal. More broadly, the project is a reference design for **privacy-by-design IoT** — useful to any engineer who needs situational awareness without surveillance.

### 1.5 Final Project Scope and Features Delivered (Q2)

The delivered system includes:

- Six configured ESP32-S3 devices (five CSI nodes + one environmental node).
- An operational RuView Wi-Fi CSI sensing deployment, bridged into the project backend with **multi-node consensus** aggregation.
- A custom FastAPI backend with sensor-data ingestion, a sensor-fusion engine, threat/alert logic, and node-status reporting.
- A **relative sound-level + spike detector** that flags sudden noise anomalies above a rolling baseline (replacing an earlier, misleadingly-labeled "dB" reading).
- A **coarse occupancy estimator** (exponential smoothing + inactivity decay) with a supporting **calibration toolchain** — a ground-truth logger and an accuracy analyzer for tuning thresholds to a specific room.
- Dual data logging (in-memory for the live dashboard, SQLite for history) plus an occupancy-transition log.
- A real-time web dashboard (motion, presence, gas, sound, threat level, occupancy estimate, per-node status, trend chart).
- A one-click Windows startup automation script that launches the backend, the RuView bridge, and the dashboard together, and cleanly shuts them down.

### 1.6 How the Completed Project Compares to the Initial Plan

The **core vision held remarkably steady**: privacy-preserving, camera-free, multi-sensor, fused threat detection on a live dashboard. The architecture in the final design specification matches what was built. Where reality differed from the plan was almost entirely in the **last-mile integration and robustness** rather than the concept — the unglamorous but defining work of making four wireless devices, a third-party sensing framework, a server, and a browser dashboard all cooperate reliably. Several features that *sounded* like single line items in the plan ("environmental sensing node," "one-click startup") turned out to contain the hardest engineering of the project once hardware, networking, and the host operating system were involved. These are detailed in Sections 4 and 5.

---

## 2. Technical Implementation

### 2.1 Key Technical Requirements

The system had to satisfy several non-negotiable technical requirements:

- **Privacy by construction:** No camera, no image storage, no identifiable audio. The sensing modalities themselves had to be incapable of capturing identity.
- **Real-time operation:** End-to-end latency from a physical event to the dashboard had to be low enough (a few seconds) to be useful for live monitoring.
- **Multi-source, heterogeneous ingestion:** The backend had to accept data from two very different producers — a Node.js-based RuView CSI pipeline and HTTP-posting Arduino firmware — and normalize them into one schema.
- **Sensor fusion:** Independent sensor streams had to be combined into a single threat decision, with the fusion preferring the most authoritative source for each field.
- **Resilience:** Wireless devices drop, DHCP addresses change, and a backend may be down. The system had to degrade gracefully rather than hang or crash.
- **Reproducible deployment:** A non-expert operator had to be able to start and stop the entire multi-process system without using a terminal.

### 2.2 Design and Architecture

The system follows a clean **layered, message-passing architecture** with well-separated responsibilities, which made each piece independently testable and debuggable:

```
  HARDWARE LAYER
  ESP32 #1/2/3/5/6 (RuView CSI)      ESP32 #4 (MQ-135 gas + KY-037 sound)
        │  UDP CSI frames                    │  HTTP POST JSON
        ▼                                    │
  BRIDGE LAYER                               │
  ruview_bridge.py                           │
   • spawns rf-scan.js (RuView)              │
   • reader thread parses CSI → latest_frame │
   • consensus across all CSI boards         │
   • POSTs to backend every 2 s              │
        │                                    │
        └─────────────┬──────────────────────┘
                      ▼   POST /sensor-data
  BACKEND LAYER  (FastAPI — main.py)
   • latest_by_source[]  (per-source latest reading)
   • fuse_latest()       (merge CSI + environmental)
   • get_occupancy_alerts() (threat level + alerts)
   • SQLite + in-memory logging
        │   GET /latest, /logs, /nodes
        ▼
  PRESENTATION LAYER  (dashboard.html)
   • polls /latest (2 s), /logs (4 s), /nodes
   • occupancy banner, sensor cards, Chart.js trend, log table
```

**Key design choices and why they were appropriate:**

- **Source-keyed latest-reading store.** The backend keeps a dictionary `latest_by_source` with one slot per producer (`wifi_csi`, `esp32_node3`, `esp32_node4`). This decouples producers entirely — each node posts on its own schedule, and fusion simply reads whatever is most recent. Adding a fifth sensor would be a one-line change.
- **Fusion that prefers the authoritative source.** `fuse_latest()` takes motion/presence from the CSI nodes and gas/sound from the environmental node, falling back gracefully when a source is absent. This honored the principle that each sensor "owns" the fields it is actually qualified to report.
- **A dedicated bridge process** (`ruview_bridge.py`) rather than embedding RuView logic in the backend. RuView is a Node.js tool; isolating it behind a small Python bridge with its own reader thread kept the FastAPI server clean and let the two evolve independently.
- **Stateless polling dashboard.** The dashboard is a single self-contained HTML/JS file that polls REST endpoints. This avoided a build toolchain and a websocket server — appropriate for a demonstrable capstone where simplicity and "just open the file" deployment mattered.
- **Dual storage.** A capped in-memory list serves the live dashboard quickly, while SQLite (`sensor_logs.db`) retains full history for analysis — separating "hot" and "cold" data paths.

### 2.3 Technologies and Tools

| Technology | Role | Why chosen |
|---|---|---|
| **ESP32-S3** | Sensor/edge nodes | Cheap, Wi-Fi-capable, enough ADC channels and compute for CSI and analog sensing |
| **RuView + ESP-IDF 5.5** | Wi-Fi CSI sensing framework | Provides camera-free motion/presence sensing — the privacy core of the project |
| **Arduino IDE / C++** | Environmental node firmware | Fast path to reliable ADC sampling and HTTP posting on the ESP32 |
| **Python + FastAPI** | Backend server & fusion | Minimal, modern, async-capable REST framework; rapid to build and easy to read |
| **SQLite** | Historical logging | Zero-configuration embedded database; ships with Python |
| **HTML/CSS/JavaScript + Chart.js** | Dashboard | No build step; runs in any browser; Chart.js gives clean trend visualization |
| **Node.js** | Runs RuView's `rf-scan.js` | Required by the RuView framework |
| **Windows Batch + PowerShell** | One-click deployment | Native orchestration of the multi-process system on the target OS |
| **Git/GitHub + VS Code** | Version control & development | Standard professional toolchain; full project history |

These choices consistently favored **simplicity and demonstrability** over heavyweight infrastructure — a deliberate decision for a single-developer capstone where reliability and the ability to explain every line mattered more than scaling to thousands of users.

### 2.4 Testing and Validation (Q2)

Validation was primarily **empirical and instrument-driven**, appropriate for a hardware-in-the-loop system where unit tests cannot exercise a physical sensor:

- **Serial-monitor instrumentation.** The firmware emits a debug line every cycle (`[DBG] rawGas=… gas=… soundPeak=… soundScore=…`). This was the single most valuable validation tool — it let me observe the *raw* and *processed* values simultaneously and confirm, with real numbers, whether a sensor was behaving. For example, validating the sound fix meant clapping and watching `soundPeak` jump from a ~130 baseline to 1252 and 2932.
- **Endpoint verification.** Backend endpoints were validated directly (`GET /` returning `{"status":"backend running"}`, `/latest`, `/nodes`) from the browser and from the ESP32's HTTP response codes (watching `HTTP 200` vs. `HTTP -1`).
- **End-to-end smoke test.** The acceptance test was the full pipeline: a physical action (motion, clap, gas source) producing a visible change on the dashboard within seconds, with the corresponding row appearing in the SQLite log.
- **Static checks.** Python modules were syntax-validated, and the deployment script's paths were verified to resolve to existing files before relying on it.

### 2.5 Final-Stage Technical Adjustments and Improvements (Q2)

In the final stages, several robustness and code-quality improvements were made after a structured code review:

- **Sound sampling redesigned** from a blocking 300 ms-per-2 s window to continuous per-loop peak-hold sampling, then calibrated with a noise-floor offset and a widened scale (Section 4 details the full debugging arc).
- **Network resilience:** HTTP connect/read timeouts were added to the firmware so an unreachable backend can no longer stall the device's main loop.
- **Bounded memory:** the in-memory reading buffer was capped (full history still persists to SQLite) to prevent unbounded growth on a long-running server.
- **Configuration hygiene:** Wi-Fi credentials were extracted from the firmware into a git-ignored `arduino_secrets.h` (with a committed `.example` template); the empty `requirement.txt` was populated; and the deployment script was made path-portable using `%~dp0` instead of a hard-coded user path.
- **Honest data flow:** a placeholder that misrepresented one signal as another (using a breathing-rate estimate as a stand-in for sound) was removed so the fused output only reflects real measurements.
- **Sound reframed as a relative spike, not fake decibels.** The KY-037 is uncalibrated, so the misleading "dB" label was dropped in favor of a relative level plus a **spike detector** that flags readings jumping above a rolling room baseline — an honest, anomaly-oriented signal that also feeds the threat level. (A dead absolute threshold of `sound_level >= 70`, which could never fire on the real scale, was replaced in the process.)
- **Coarse occupancy estimator with calibration tooling.** A smoothing-plus-decay estimator turns the fused signals into an Empty / Occupied / Busy / Crowded level — honestly framed as an *estimate*, not an exact head count — backed by a `calibration_logger` / `calibration_analyzer` pair for measuring accuracy and tuning thresholds to a specific room.
- **Multi-node CSI consensus.** The bridge was upgraded from reading only the *first* CSI board to aggregating *all* boards by consensus (median/trimmed for presence and count, voting for motion), so a single noisy node is outvoted rather than amplified. The system was also expanded from three to five CSI boards.

### 2.6 Most Challenging Technical Aspects and Their Resolution (Q2)

The three hardest technical problems — the sound-sensor sampling bug, the cross-device networking failure, and the deployment shutdown bug — are analyzed in depth in Section 4, because each was as much a *debugging-process* lesson as a technical one.

---

## 3. Development Process Reflection

### 3.1 Approach to Project Management and Development

The project was organized around **vertical slices that each produced something observable**. Rather than building all firmware, then all backend, then all dashboard, I prioritized getting a *thin end-to-end path* working first — one sensor value traveling from an ESP32, through the backend, onto the dashboard — and then thickened it. This meant that at almost every stage there was a running system to test against, which is essential for hardware work where bugs hide at the seams between components.

Work was tracked in Git with incremental commits (e.g., weekly milestones such as "occupancy tracking, auto-start batch script, updated dashboard"), giving a clear history of how the system grew.

### 3.2 How the Project Evolved from the Initial Concept

The concept — privacy-preserving, fused, camera-free detection — was stable from the start. What *evolved* was my understanding of where the difficulty actually lived. Early on, I assumed the intellectual core would be the sensing science (CSI, fusion algorithms). In practice, the science was largely provided by RuView and the fusion logic was straightforward; the real engineering turned out to be **integration and robustness** — making heterogeneous devices, a third-party framework, and the host OS cooperate without silent failures. The project matured from "make it work once" to "make it work reliably and start with one click."

### 3.3 Key Decision Points and Rationale

- **Bridge vs. rewrite.** I chose to *bridge* RuView through a small Python adapter rather than reimplement CSI sensing. Rationale: reuse the proven framework and spend my effort on the parts that were genuinely mine (fusion, backend, dashboard, deployment).
- **REST + polling vs. websockets.** I chose simple HTTP polling for the dashboard. Rationale: zero build tooling, trivial to demo, and entirely sufficient at a 2-second cadence.
- **SQLite vs. a server database.** I chose SQLite for zero-config embedded persistence. Rationale: no external dependency to install or run during a demo.
- **Source-keyed fusion that prefers the real sensor.** Rationale: correctness — never let a placeholder value overwrite a genuine measurement.

### 3.4 Significant Changes, Refinements, and Pivots

The most significant refinement was the **sound-sensing pipeline**, which was redesigned twice (Section 4). A second meaningful pivot was in **deployment**: the one-click script's shutdown logic had to be completely re-implemented once I discovered that the modern Windows Terminal host invalidated the original window-title-based approach. Neither was a change of *goal* — both were changes of *technique* forced by evidence.

### 3.5 Feedback and Insights That Influenced Direction

A structured **code review** late in the project surfaced a cluster of issues that, individually, were easy to dismiss but collectively mattered: an empty requirements file, an unbounded in-memory list, hard-coded secrets, a misleading data substitution, and a fragile deployment path. Acting on that review measurably improved the professionalism and reproducibility of the deliverable, and reinforced a lasting lesson: **a working demo is not the same as a finished engineering artifact.**

---

## 4. Challenge Analysis and Problem-Solving

This section documents the most significant challenges. Each is presented as a root-cause investigation because the *method* of solving them was as important as the fix.

### 4.1 Challenge 1 — The Sound Sensor That Couldn't Hear a Clap

**The symptom.** The KY-037 sound reading was effectively stuck at a low value (~6 on the dashboard). Clapping or playing loud music produced no reaction, yet slowly changing the volume produced a slow drift. The sensor appeared broken.

**Problem-solving process.** Rather than swapping hardware or guessing, I followed a disciplined root-cause investigation. I first decoded what "stuck at 6" meant numerically: it corresponded to a peak-to-peak amplitude of roughly 40 ADC counts — the ambient noise floor — meaning the measured signal was not responding to loud sound at all. I then enumerated competing hypotheses (wrong ADC pin for the board, wiring to the digital output instead of analog, and sampling-window blindness) and eliminated them with evidence: confirming the board was an ESP32-S3 (so the pin was valid with Wi-Fi active) and that the wiring used the analog output.

The decisive evidence came from the firmware's own serial debug line. A clap produced `soundPeak=970` — a large, healthy swing — but only *occasionally*. That was the tell.

**Root cause.** The original sampling routine listened for only **300 ms once every 2 seconds**. A clap is a ~30 ms transient, so roughly 85% of the time the code was simply not listening when the sound occurred. The sensor was fine; the *sampling strategy* was deaf to transients.

**The fix — and a revealing regression.** I rewrote sampling to run **continuously on every loop iteration**, holding the loudest peak-to-peak value seen within each reporting interval. After flashing, the value went to **zero** — a worse symptom. Investigation showed this was *not* a new sensor problem but a coupling I had introduced: the device's HTTP POST was failing (`HTTP -1`) against an unreachable backend, and that failing call blocked the main loop for the full connection-timeout (~2 s). With the loop blocked, the new continuous sampler got exactly one sample per window, so max equaled min and the peak-to-peak was zero. I added a short HTTP connect/read timeout so a dead backend could no longer starve sampling. The values immediately returned, and a single clap now registered every time.

**Final calibration.** With real data in hand (claps reaching 1252–2932), I subtracted a measured noise floor (~130) so a quiet room reads near zero, and widened the scale so loud events have headroom instead of all saturating at the maximum.

**Deeper insight.** This was the most instructive bug of the project. It taught me that in embedded systems, **timing and sampling strategy are first-class correctness concerns** — a perfectly good sensor is useless if you sample it wrong — and that **fixes can introduce coupling bugs**, so each change must be re-validated against real evidence, not assumed correct.

### 4.2 Challenge 2 — `HTTP -1`: When Two Devices Can't Find Each Other

**The symptom.** Every POST from the environmental node returned `HTTP -1`; the dashboard never received its data.

**Problem-solving process.** I traced the failure across the network boundary. The ESP32 reported its own IP as `10.0.0.220` while trying to reach the backend at a previously hard-coded `10.0.0.145:8000`. Both were on the same subnet, so routing was fine — the backend simply wasn't answering at that address.

**Root cause.** A combination of classic IoT networking pitfalls: **DHCP address drift** (the backend machine's address was not guaranteed to remain `.145`), the backend needing to bind to `0.0.0.0` (not just `127.0.0.1`) to be reachable by other devices, and **Windows Firewall** commonly blocking inbound connections on the server port.

**Resolution and alternatives considered.** The immediate resolution was operational (confirm the backend's current IP, bind to all interfaces, allow the port). The deeper, defensive resolution — and the more valuable one — was the HTTP timeout added in Challenge 1, which ensured that even when the backend *is* unreachable, the device fails fast and keeps functioning rather than freezing. An alternative I considered was service discovery (mDNS) to eliminate hard-coded IPs entirely; I judged it out of scope for the timeline but noted it as a clear future improvement (Section 6).

**Deeper insight.** Distributed systems fail at the boundaries, and those failures are often *environmental* (DHCP, firewall, binding) rather than in your code. The lesson was to **instrument the boundary** (the `HTTP 200` vs. `HTTP -1` log was what made this tractable) and to **design for the remote side being absent.**

### 4.3 Challenge 3 — The One-Click Script That Wouldn't Close Its Own Windows

**The symptom.** The startup script launched the backend and bridge in separate windows correctly, but pressing a key to stop everything left those windows running. The shutdown silently did nothing.

**Problem-solving process.** The shutdown used `taskkill /FI "WINDOWTITLE eq ..."` to find and close the service windows by title. I first suspected the window title was getting a suffix appended. But inspecting the *live* processes revealed the true owner of the windows: **`WindowsTerminal`**, not `cmd.exe`.

**Root cause.** On Windows 11, **Windows Terminal is the default console host**. Under it, the `cmd`/`python` processes run inside a pseudo-console and have **no classic window title of their own** for `taskkill`'s `WINDOWTITLE` filter to match. The original approach could never have worked on this OS configuration — it was matching against a window-title concept that no longer applies.

**Resolution.** I rewrote the shutdown to identify the service processes by their **command line** instead of their window title — querying `Win32_Process` for the `cmd.exe` instances whose command line contained `uvicorn` or `ruview_bridge`, and tree-killing them (`/T`) so child processes (uvicorn's reload worker, the bridge's Node subprocess) are also terminated and the terminal tab closes. I restricted the match to `cmd.exe` specifically so the query could never accidentally kill the helper running it. Crucially, I **verified the fix against the actually-running windows** before declaring it done — it cleanly terminated all four processes.

**Deeper insight.** A technique can be silently invalidated by a platform change you didn't make. The lesson was twofold: **identify resources by something intrinsic (the command line) rather than something incidental (a window title)**, and **verify against live state** rather than trusting that a plausible command worked.

### 4.4 Challenge 4 — Why the Wi-Fi Sensing Reported a Crowd in an Empty Room (A Five-Layer Trace)

**The symptom.** The dashboard's presence/occupancy never matched reality. An empty room showed presence scores of 8–16 and a constant "4 people," with motion always "detected." Tuning the backend thresholds changed nothing.

**Problem-solving process — building a tool instead of guessing.** Rather than keep nudging thresholds, I wrote a **calibration logger** that recorded the model's prediction alongside hand-labeled ground truth, and an **analyzer** that asked the key question: does *any* sensor signal actually separate "empty" from "occupied"? The result was damning but clarifying. Across 76 samples:

- Presence read *higher* when empty (median **15.8**) than with one person (**11.8**).
- `n_persons` was a constant **4** at every real occupancy.
- Motion was **100%** always.

No signal tracked occupancy — so **no threshold could ever work.** The problem was upstream of everything I controlled, so I traced the data backward through all five layers:

1. **Dashboard** — faithfully displaying the backend value.
2. **Backend fusion** — faithfully passing the bridge value.
3. **Bridge** — faithfully forwarding RuView's value.
4. **RuView's `rf-scan.js`** — reading its source, I found it does not *compute* presence/people; it merely **unpacks bytes from a UDP packet** the ESP32 boards send. The numbers originate on the boards.
5. **The ESP32 RuView firmware** — reading its `edge_processing.c`, I found the real algorithm: `n_persons` is `subcarrier_energy_count / 2`, **hard-clamped to [1, 4]**, so it can never report 0 and saturates at 4 in any reflective room; presence is the **raw motion-energy**, gated by an **adaptive baseline learned over the first ~60 seconds after boot**.

**Root cause.** Two compounding firmware realities: (a) the people-count is a crude clamped heuristic *structurally incapable* of counting; and (b) the presence baseline had been learned **while the room was occupied during setup**, poisoning the definition of "empty." A red flag confirmed the diagnosis — the firmware's own UI expects presence in a 0–1 range, but we were seeing 8–16.

**Resolution.** I first **ruled out a synthetic-data build**: the firmware has a mock-CSI test mode, so I confirmed from the serial boot log and `sdkconfig` that real CSI was enabled and no mock generator was running. Then I **re-ran the firmware's calibration correctly** — rebooting each board with the room genuinely empty and still for the full ~60-second window — and verified on the serial console that empty now read presence ≈ 0 and a person read ≈ 9. A further subtlety emerged during multi-board testing: boards calibrated **alone** (a quiet channel) read high when run **all together**, because five simultaneous CSI streams congest the Wi-Fi channel. Calibration therefore had to be done **under real operating conditions**, with every board streaming. Finally, isolating the boards one by one revealed a **single faulty board** (node 3) that stayed noisy while the others were clean — absorbed by the consensus fusion, which outvotes one bad node.

**Deeper insight.** This was the deepest investigation of the project and its most valuable lesson: **a number on a screen can be wrong five layers away from where you're looking**, and the only way to find it is to trace the data to its true origin rather than tune the surface. It also taught me the honest limits of a borrowed component — RuView delivers solid *presence/motion* sensing once calibrated, but its *people-counting* is a heuristic unsuitable for accurate occupancy, which is a limitation worth documenting rather than papering over. And calibration must reflect the **real operating environment**, not a convenient idealized one.

### 4.5 What I Would Do Differently

Across these challenges, the common thread is that **the environment — sampling timing, the network, the OS host, the RF channel — was the real adversary, not the algorithm.** With hindsight I would (1) instrument every component boundary *from the start* rather than adding logging reactively, (2) write down a hypothesis and the evidence that would falsify it before changing code, (3) trace a suspicious value all the way to its origin instead of tuning where it surfaces, and (4) prefer intrinsic identifiers and fail-fast defaults everywhere. These habits turned hours of potential guesswork into targeted, evidence-driven fixes.

---

## 5. Learning and Professional Growth

### 5.1 New Technical Skills and Knowledge Acquired

This project pushed me across an unusually wide stack:

- **Embedded systems & signal sampling:** ADC sampling on the ESP32, peak-to-peak amplitude measurement, the critical relationship between sampling rate/window and what you can actually measure, and sensor calibration (noise floors, scaling).
- **Wi-Fi CSI sensing:** integrating and interpreting a CSI framework (RuView) to extract presence and motion without cameras — including reading its firmware to understand how the vitals are actually computed, and learning the practical realities of CSI (adaptive baselines, channel congestion across multiple boards, sensitivity to the access point and board placement).
- **Multi-sensor calibration & evaluation:** building a ground-truth logging/analysis loop to measure whether a signal actually separates classes, and using it to tune (and to *disprove*) thresholds with evidence.
- **Backend & API development:** building a real REST API with FastAPI, designing a clean ingestion/fusion schema, and using threading for a concurrent reader loop.
- **Data engineering:** dual hot/cold storage with an in-memory buffer and SQLite persistence.
- **Front-end visualization:** a polling dashboard with live charts.
- **Networking in practice:** DHCP behavior, binding to interfaces, firewalls, HTTP timeouts, and diagnosing cross-device failures.
- **Systems automation:** orchestrating a multi-process system with Batch and PowerShell, including process-tree management on modern Windows.
- **Disciplined debugging:** root-cause investigation as a repeatable method.

### 5.2 How the Project Challenged My Existing Capabilities

The project repeatedly forced me to operate at the **seams between domains** I had previously studied in isolation — where firmware meets networking meets a server meets an OS. Most of the hardest bugs lived precisely where one domain handed off to another (a sensor read interrupted by a network call; a process killed by an OS host). Reasoning across those boundaries, and resisting the urge to apply quick fixes before understanding the root cause, was the biggest stretch.

### 5.3 Connection to Coursework and Theoretical Concepts

The project was a practical synthesis of core CS coursework: **operating systems** (processes, concurrency, the console host), **computer networks** (IP, DHCP, HTTP, client/server), **embedded/architecture** concepts (ADC, sampling, microcontrollers), **databases** (schema design, SQLite), and **software engineering** (layered architecture, separation of concerns, version control, code review). It turned abstract concepts — "a process tree," "a sampling window," "binding to an interface" — into things I had to reason about to make a real system work.

### 5.4 Impact on Professional Interests and Career Goals

> *[FILL IN / personalize — example below, edit to your real goals]*

This project sharpened my interest in **systems-level and IoT/embedded engineering** — the discipline of making physical devices, networks, and software cooperate reliably. I found the integration and debugging work genuinely satisfying, which points me toward roles in embedded systems, backend/infrastructure, or IoT product development. *(Adjust this paragraph to reflect your actual career direction.)*

### 5.5 Biggest Takeaways

The lessons most likely to stay with me: **integration is where real engineering happens**, **evidence beats intuition when debugging**, and **a demo that works once is only halfway to a deliverable** — robustness, configuration hygiene, and reproducible deployment are what separate a prototype from a professional artifact.

---

## 6. Key Insights and Future Directions

### 6.1 Three Most Important Takeaways

1. **Sampling and timing are correctness, not details.** The defining bug of the project was a perfectly functional sensor made useless by a flawed sampling window. In any system that touches the physical world, *how and when you measure* is as important as *what you measure*.
2. **Debug from the root cause, with instrumented evidence.** Every major problem yielded quickly once I stopped guessing and started observing the actual data at component boundaries. The serial debug line and the `HTTP 200/-1` codes were worth more than any amount of speculation.
3. **Robustness and reproducibility are features.** Timeouts, bounded memory, secret hygiene, intrinsic identifiers, and one-click deployment were not "extra" — they were what turned a fragile demo into a system someone else could run.

### 6.2 What I Found Most Meaningful

The most rewarding moments were the **clean root-cause resolutions** — watching a single clap finally spike the sound reading every time after understanding *why* it hadn't, and watching the stuck service windows close cleanly after discovering *why* the original approach was doomed. Turning a confusing, frustrating symptom into a precise, explained fix is the part of engineering I find most satisfying.

### 6.3 How This Project Shaped My Professional Development

I developed concrete, portfolio-ready skills in embedded sampling, REST backend design, sensor fusion, and cross-device networking — and, just as importantly, a **repeatable debugging discipline** I can carry into any system. I also practiced communicating technical decisions clearly, which this very report exercises.

### 6.4 Ways I'll Apply These Insights in Future Work

I will **instrument boundaries before I need to**, **state and falsify hypotheses before editing code**, and **default to fail-fast, well-configured, reproducible setups** rather than retrofitting robustness after a demo. These are habits, not one-off fixes, and they generalize far beyond this project.

### 6.5 Advice for Anyone Continuing or Building on This Project

- **Eliminate hard-coded IPs** with service discovery (mDNS/Bonjour) so devices find the backend automatically across DHCP changes.
- **Make thresholds configurable** (the project now uses a `.env` for occupancy thresholds) and keep the backend and dashboard reading from one source of truth.
- **Do not trust RuView's `n_persons` for counting** — it is clamped to [1, 4] and saturates in any real room. Use **presence/motion** (after proper calibration) as "someone is active," and treat exact head-counting as out of reach for this firmware.
- **Calibrate CSI under real operating conditions** — every board streaming, the room genuinely empty for the full ~60-second window. Calibrating one board at a time gives a baseline that fails the moment all boards run together (channel congestion).
- **Prefer a fixed router over a phone hotspot** as the CSI reference (hotspots move, power-save, and vary their traffic), and **spread the boards out** rather than clustering them, so they provide independent coverage instead of redundant, mutually-interfering readings.
- **Verify every fix against live state**, especially anything touching the OS, the network, or the RF channel.

### 6.6 Potential Improvements and Extensions Beyond the Course

- **Better occupancy than the firmware heuristic:** the coarse estimator (smoothing + decay) and calibration tooling are built; the natural next step is a learned model (a small classifier trained on the calibration logs) to push past RuView's clamped `n_persons` toward genuine counting — or distributing the boards around the room for true spatial coverage.
- **WebSocket push** to replace polling for lower-latency, lower-overhead dashboard updates.
- **Authentication and TLS** on the backend for any real deployment beyond a closed lab network.
- **Cross-platform deployment** (a containerized backend; a non-Windows launcher) for portability.
- **A mobile/responsive dashboard** and push notifications for on-call staff.
- **Time-series retention policies** and analytics on the historical log (peak-hours, anomaly baselines).

### 6.7 How This Could Be Used or Expanded in a Real-World Setting

In a real deployment, a facilities or safety operations team could run this as a **privacy-compliant situational-awareness layer** across multiple rooms, with per-room threat tiles, configurable alert thresholds per location, and integration into an existing incident-response workflow (paging, ticketing). Its privacy-by-design nature is a genuine commercial differentiator in regulated environments where cameras are prohibited.

### 6.8 Advice for Future Capstone Students

- **Get a thin end-to-end slice working first**, then thicken it. A running system to test against is invaluable, especially with hardware.
- **Instrument early.** Add debug output at every boundary before you have a bug — it is the cheapest insurance you will ever buy.
- **Expect the integration to be the project.** The individual technologies are usually well-documented; the difficulty lives where they meet.
- **Don't confuse "it worked once" with "it's done."** Budget real time for robustness, configuration, and deployment.

### 6.9 What I Would Do Differently With More Time or Resources

With more time I would add **automated, hardware-in-the-loop test harnesses** (replaying captured sensor streams against the backend) to catch regressions like the sound-sampling coupling bug automatically; implement **service discovery** to remove networking friction entirely; and run a **structured evaluation** of detection accuracy against staged scenarios to quantify the system's real-world reliability.

---

## Appendix A — System Architecture Diagram

*(See the layered diagram in Section 2.2. For the poster/presentation, render this as the central figure: four nodes → bridge/backend (sensor fusion) → threat level → dashboard.)*

## Appendix B — Representative Code

**Sensor fusion (backend `main.py`):**
```python
def fuse_latest():
    csi   = latest_by_source.get("wifi_csi") or {}
    node4 = latest_by_source.get("esp32_node4") or {}
    return {
        "motion":         csi.get("motion", False),
        "presence_score": csi.get("presence_score", 0),
        "csi_nodes":      csi.get("csi_nodes", 0),
        "sound_level":    node4.get("sound_level") if node4 else csi.get("sound_level", 0),
        "gas_level":      node4.get("gas_level")   if node4 else csi.get("gas_level", 0),
        "source": "fused",
    }
```

**Multi-node CSI consensus (bridge `ruview_bridge.py`):** instead of trusting one board, presence uses a trimmed value (drop the single noisiest board), people-count uses the median, and motion requires agreement from at least two boards — so a single noisy node is outvoted, not amplified.

**Transient-safe sound sampling (firmware), after redesign:**
```cpp
// Sample every loop iteration; hold the loudest peak-to-peak per interval.
int s = analogRead(SOUND_PIN);
if (s < soundMin) soundMin = s;
if (s > soundMax) soundMax = s;
// ...every 2 s:
int rawSoundPeak = soundMax - soundMin;   // captures a clap at any instant
```

## Appendix C — Selected Validation Evidence

**Serial log confirming the sound fix (a clap spikes the reading):**
```
[DBG] rawGas=1625 gas=163 soundPeak=1252 soundScore=120   <- clap detected
[DBG] rawGas=1608 gas=156 soundPeak=2932 soundScore=120   <- clap detected
[OK] Gas: 156 | Sound Score: 120 | HTTP 200               <- backend reachable
```

**Calibration analysis proving the CSI presence signal was unusable (before re-calibration):**
```
Presence score by actual occupancy:
  0 people: median = 15.81   <- empty reads HIGHER than occupied
  1 people: median = 11.76
  2 people: median = 12.13
CSI n_persons: constant 4.00 at every occupancy   <- clamped heuristic
DIAGNOSIS: no signal cleanly separates empty from occupied.
```

**CSI presence after correct empty-room calibration (board serial console):**
```
adaptive_ctrl: medium tick: ... motion=0.00 presence=0.00   <- room empty
adaptive_ctrl: medium tick: ... motion=1.00 presence=9.06   <- person present
```

## Appendix D — Tools Used

ESP32-S3 (×6) · MQ-135 · KY-037 · RuView · ESP-IDF 5.5 (`idf.py` build/flash/monitor) · Arduino IDE · Python · FastAPI · SQLite · HTML/CSS/JavaScript · Chart.js · Node.js · Windows Batch/PowerShell · Git/GitHub · Visual Studio Code · custom calibration tooling (`calibration_logger.py`, `calibration_analyzer.py`).
