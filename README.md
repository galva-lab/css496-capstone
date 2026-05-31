# Privacy-Preserving Multi-Sensor IoT System for Abnormal Restroom Activity Detection

This capstone project builds a privacy-preserving restroom monitoring system using four ESP32-S3 devices and the RuView Wi-Fi sensing framework.

## Project Overview

- Three ESP32-S3 nodes run RuView Wi-Fi Channel State Information (CSI) sensing to detect motion, presence, and estimate activity from Wi-Fi signal disturbances.
- A fourth ESP32-S3 node collects environmental data with an MQ-135 gas sensor and a KY-037 sound sensor.
- All sensor data is transmitted over Wi-Fi to a FastAPI backend server.
- The backend fuses Wi-Fi CSI data with environmental sensing to generate a unified threat assessment.
- A real-time web dashboard displays motion, presence, gas, sound, occupancy, and device status.
- The system preserves privacy by avoiding cameras and the collection of personal images.

## System Components

- ESP32-S3 Node #1: RuView Wi-Fi CSI sensing
- ESP32-S3 Node #2: RuView Wi-Fi CSI sensing
- ESP32-S3 Node #3: RuView Wi-Fi CSI sensing
- ESP32-S3 Node #4: MQ-135 gas sensor + KY-037 sound sensor
- FastAPI backend server
- Sensor fusion engine
- CSV data logging system
- Real-time web dashboard
- One-click startup automation script

## Key Goals

- Detect presence and motion using Wi-Fi CSI
- Collect gas and noise environmental measurements
- Fuse multiple sensor sources into a threat assessment
- Monitor data in real time through a dashboard
- Store historical logs for later analysis
- Demonstrate a complete IoT system integrating hardware, networking, backend, and visualization

## Tools and Technologies

- Hardware: 4 × ESP32-S3 boards, MQ-135 gas sensor, KY-037 sound sensor, breadboards, jumper wires, USB cables, power banks
- Software: RuView, ESP-IDF 5.5, Arduino IDE, Python, FastAPI, HTML/CSS/JavaScript, GitHub, Visual Studio Code
