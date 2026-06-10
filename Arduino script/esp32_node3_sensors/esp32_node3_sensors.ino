#include <WiFi.h>
#include <HTTPClient.h>
#include "arduino_secrets.h"   // Wi-Fi credentials (gitignored; see arduino_secrets.h.example)

const char* ssid = SECRET_WIFI_SSID;
const char* password = SECRET_WIFI_PASS;
const char* serverIP = "10.0.0.145";
const int serverPort = 8000;

const int GAS_PIN = 4;
const int SOUND_PIN = 5;

unsigned long lastSend = 0;
const int SEND_INTERVAL_MS = 2000;

// Ambient peak-to-peak in a quiet room (measured ~115-165 counts). Subtracted
// from each reading so silence reads ~0. Re-measure if you change rooms/mic gain.
const int SOUND_NOISE_FLOOR = 130;

// Continuously-updated sound peak tracking, reset each report interval.
// Sampling on every loop iteration means a sudden clap at ANY moment in
// the 2 s window is captured, instead of only during a brief 300 ms listen.
int soundMin = 4095;
int soundMax = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);

  analogReadResolution(12);

  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected");
  Serial.println(WiFi.localIP());
}

void loop() {
  // Sample sound every loop iteration so transients can't slip through a
  // sampling gap. Hold the loudest peak-to-peak seen since the last report.
  int s = analogRead(SOUND_PIN);
  if (s < soundMin) soundMin = s;
  if (s > soundMax) soundMax = s;

  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();

    int rawGas = analogRead(GAS_PIN);
    int rawSoundPeak = soundMax - soundMin;
    soundMin = 4095;   // reset window for the next interval
    soundMax = 0;

    // Subtract the ambient noise floor so a quiet room reads ~0 instead of ~15.
    rawSoundPeak -= SOUND_NOISE_FLOOR;
    if (rawSoundPeak < 0) rawSoundPeak = 0;

    int gasLevel = map(rawGas, 1200, 2500, 0, 500);
    gasLevel = constrain(gasLevel, 0, 500);

    // Scale to a wider 0-3000 range so loud claps (~1200-2900) have headroom
    // instead of all flattening to 120.
    int soundLevel = map(rawSoundPeak, 0, 3000, 0, 120);
    soundLevel = constrain(soundLevel, 0, 120);

    Serial.printf("[DBG] rawGas=%d gas=%d soundPeak=%d soundScore=%d\n",
                  rawGas, gasLevel, rawSoundPeak, soundLevel);

    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;

      String url = String("http://") + serverIP + ":" + serverPort + "/sensor-data";
      http.begin(url);
      http.setConnectTimeout(800);   // don't let an unreachable backend stall the loop (and starve sound sampling)
      http.setTimeout(800);
      http.addHeader("Content-Type", "application/json");

      String body = "{";
      body += "\"source\":\"esp32_node4\",";
      body += "\"gas_level\":" + String(gasLevel) + ",";
      body += "\"sound_level\":" + String(soundLevel) + ",";
      body += "\"motion\":false";
      body += "}";

      int httpCode = http.POST(body);

      Serial.printf("[OK] Gas: %d | Sound Score: %d | HTTP %d\n",
                    gasLevel, soundLevel, httpCode);

      http.end();
    }
  }
}