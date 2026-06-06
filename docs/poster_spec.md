# Capstone Poster — Content Spec

Privacy-Preserving Multi-Sensor IoT System for Abnormal Restroom Activity Detection

This is a paste-ready blueprint. Each section gives you the **heading** + the exact
**text/bullets** to use, plus what **visual** goes with it. Keep body text as short
phrases/bullets — the rubric penalizes prose ("Poster does not focus on words only").

---

## Poster meta

- **Size / orientation:** 48 in wide × 36 in tall, **landscape** (matches both UW example posters).
- **Fonts (rubric-required minimums):** Title > 72 pt · Headings > 40 pt · Body > 28 pt · Captions > 24 pt.
- **Color theme (UW Bothell):** Purple `#4B2E83`, Gold `#B7A57A`, white background, dark text.
  Use the purple band for the header and section title bars; gold accents.
- **Layout grid:** Header band across the top, then **3 columns** below
  (Left = context, Center = the system, Right = results). No empty gaps — the rubric
  explicitly docks "unnecessary empty spaces."

```
+-------------------------------------------------------------------------+
|  HEADER BAND: Title / Presenter · Advisor · Sponsor · Quarter   [W logo] |
+----------------------+--------------------------------+-----------------+
| LEFT COLUMN          | CENTER COLUMN                  | RIGHT COLUMN    |
| 1. Overview &        | 3. SYSTEM ARCHITECTURE         | 6. Results /    |
|    Motivation        |    (big diagram - centerpiece) |    Dashboard    |
| 2. Goals             | 4. How It Works (methodology)  | 7. Privacy by   |
|                      | 5. Hardware & Tech Stack       |    Design (call) |
|                      |                                | 8. Conclusion / |
|                      |                                |    Future Work  |
+----------------------+--------------------------------+-----------------+
```

---

## Header band (REQUIRED items — Technical Content, 50 pts)

The rubric requires ALL of: **title, your name, advisor name, sponsor, date.** Fill the brackets.

- **Title (>72pt):** Privacy-Preserving Multi-Sensor IoT System for Abnormal Restroom Activity Detection
- **Subtitle:** Camera-Free Monitoring Using ESP32-S3 + RuView Wi-Fi CSI Sensing
- **Line under title:** Presenter: Nehemiah Brandon Soebroto  |  Advisor: [ADVISOR NAME]  |  Sponsor: [SPONSOR — Galva Lab?]  |  Spring 2026
- **Top-right:** UW / UW Bothell "W" logo.

---

## 1. Overview & Motivation  (Technical Content — the "why")

**Heading:** Overview

- Restrooms are **privacy-critical** spaces where emergencies — falls, medical events,
  aggressive activity — can go unnoticed.
- Cameras are **unacceptable** there for privacy reasons.
- **This system monitors for abnormal activity using NO cameras and NO images** —
  only Wi-Fi signal disturbances and environmental readings.
- Built by extending the **RuView** Wi-Fi sensing framework with custom backend,
  environmental sensing, fusion, and a live dashboard.

*Visual:* a small "no-camera" icon (camera with a slash) to make the privacy angle pop.

---

## 2. Goals  (Technical Content)

**Heading:** Goals

- Detect **presence & motion** via Wi-Fi CSI (no cameras).
- Collect **gas & noise** environmental data.
- **Fuse** multiple sensors into one **threat assessment**.
- **Real-time** monitoring dashboard.
- **Log** historical data for later analysis.
- Demonstrate a **complete IoT system** end-to-end.

---

## 3. SYSTEM ARCHITECTURE  (centerpiece — Organization + Professionalism)

**Heading:** System Architecture

This is the most important graphic. Draw a **left-to-right, 3-layer data-flow diagram**.
Use boxes + arrows + small icons. Layers:

**Layer 1 — Sensing (left):**
- Group box "Wi-Fi CSI Sensing" containing **3 boxes**: `ESP32-S3 Node #1`, `#2`, `#3`
  — caption: "RuView CSI: motion, presence, activity"
- Separate box "Environmental Node": `ESP32-S3 Node #4` with `MQ-135 Gas` + `KY-037 Sound`

**Arrows:** all four nodes → labeled **"Wi-Fi"** → Layer 2.

**Layer 2 — Processing (center):**
- `RuView Bridge` (CSI → JSON)  →  `FastAPI Backend`
- Inside/after backend: `Sensor Fusion Engine`  →  `Threat Assessment (Low / Med / High)`
- Side branch: `CSV + SQLite Logging`

**Arrows:** Backend → Layer 3.

**Layer 3 — Output (right):**
- `Real-Time Dashboard` box — caption: "motion · presence · gas · sound · threat · device status"

```
[Node#1 CSI]\
[Node#2 CSI] >--Wi-Fi--> [RuView Bridge] --> [FastAPI Backend] --> [Dashboard]
[Node#3 CSI]/                                      |  \
[Node#4 Gas+Sound] --Wi-Fi-----------------------> |   [Sensor Fusion -> Threat Level]
                                                    \-> [CSV + SQLite Logging]
```

*Tip:* color the 3 CSI nodes one color and the environmental node a second color so the
two sensing modalities read at a glance.

---

## 4. How It Works  (Technical Content — Methodology)

**Heading:** How It Works

- **Wi-Fi CSI sensing (Nodes 1–3):** RuView reads disturbances in Wi-Fi Channel State
  Information → motion, presence, and activity estimates. *No image capture.*
- **Environmental sensing (Node 4):** MQ-135 measures gas/air quality; KY-037 measures
  sound level (peak-to-peak, continuously sampled).
- **Sensor fusion (backend):** combines all sources → **threat level + alerts**
  (e.g., high sound + gas spike → possible incident).
- **Real-time + logged:** dashboard polls every 2 s; every reading saved to SQLite/CSV.

*Visual:* 3 small numbered icons (Wi-Fi waves · gas/sound gauge · merge arrows → shield).

---

## 5. Hardware & Tech Stack  (Professionalism)

**Heading:** Hardware & Tools

- **Hardware:** 4 × ESP32-S3 · MQ-135 gas sensor · KY-037 sound sensor · power banks
- **Sensing:** RuView framework · ESP-IDF 5.5 · Arduino IDE
- **Backend:** Python · FastAPI · SQLite
- **Frontend:** HTML / CSS / JavaScript (Chart.js)
- **Tooling:** GitHub · VS Code · one-click `.bat` deployment

*Visual:* a neat icon row (like the "Technology" block in the Learn Databases poster).

---

## 6. Results / Live Dashboard  (Creativity + Comprehension)

**Heading:** Results

- **Screenshot of your real dashboard** — biggest visual on the right. Annotate 2–3 parts:
  threat banner, sensor cards (gas/sound/motion), trend chart.
- Bullets:
  - All 4 nodes connect and stream over Wi-Fi.
  - Fusion produces **Low / Medium / High** threat levels with alerts.
  - Dashboard updates in **real time (~2 s)**.
  - **5,000+** readings logged to SQLite/CSV for analysis.
  - **One-click startup** launches the whole system.

*This screenshot is your strongest "it actually works" proof — make it large and clear.*

---

## 7. Privacy by Design  (differentiator — make it a callout box)

**Heading:** Privacy by Design

A bold highlighted box (gold border):
- ❌ No cameras  ❌ No images  ❌ No personal data
- ✅ Only Wi-Fi signal disturbances + environmental readings

*This is your project's signature — give it visual emphasis.*

---

## 8. Conclusion & Future Work  (Technical Content — Application/Originality)

**Heading:** Conclusion & Future Work

- **Achieved:** a complete, working IoT pipeline integrating hardware, networking,
  backend fusion, logging, and real-time visualization — **without cameras**.
- **Application:** restrooms, locker rooms, eldercare, or any privacy-sensitive space
  needing safety monitoring.
- **Future work:**
  - **Occupancy / entry detection** (count people and flag when more enter).
  - ML-based anomaly detection on logged data.
  - Multi-room scaling.

---

## Rubric coverage check

| Criterion (pts) | Where it's earned on the poster |
|---|---|
| Technical Content (50) | Header required fields · Overview motivation · Methodology · Conclusion application/originality |
| Organization (15) | 3-column flow, architecture diagram, clear section bars, no empty gaps |
| Professionalism (15) | Custom diagram + dashboard screenshot (NOT printed slides), tech-stack row |
| Creativity (10) | Icons, color-coded nodes, annotated dashboard, privacy callout |
| Comprehension (10) | Big fonts (72/40/28/24), image–text balance, glanceable at a few feet |

---

## What I still need from you (required by rubric)

1. **Advisor name** — required field, can't be blank.
2. **Sponsor** — is it **Galva Lab** (your GitHub org) or someone else?
3. Confirm **presenter name** (Nehemiah Brandon Soebroto?) and **quarter** (Spring 2026?).
4. A **dashboard screenshot** to drop into section 6.
