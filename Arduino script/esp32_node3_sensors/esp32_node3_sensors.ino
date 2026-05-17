/*
  ESP32 #3 — Gas + Sound Sensor Node
  CSS 496 Capstone

  Sensors:
    MQ-135  → GPIO34 (air quality / gas)
    KY-037  → GPIO35 (sound level / noise)

  Wiring:
    MQ-135:  VCC → 5V, GND → GND, AOUT → GPIO34
    KY-037:  VCC → 3.3V, GND → GND, A0  → GPIO35

  Sends HTTP POST to FastAPI every 2 seconds.
  Make sure FastAPI backend is running first.
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── Config ────────────────────────────────────────────────
const char* ssid       = "lucky plaza";
const char* password   = "homesweethome2";
const char* serverIP   = "10.0.0.145";
const int   serverPort = 8000;

const int GAS_PIN   = 5;   // MQ-135 analog out
const int SOUND_PIN = 4;   // KY-037 analog out

const int SEND_INTERVAL_MS = 2000;
// ──────────────────────────────────────────────────────────

// MQ-135 warmup — sensor needs ~30s to stabilize
const int WARMUP_SECONDS = 30;

unsigned long lastSend = 0;

// Rolling average for smoother readings
const int SAMPLE_COUNT = 10;
int gasSamples[SAMPLE_COUNT];
int soundSamples[SAMPLE_COUNT];
int sampleIndex = 0;

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println("\n=== ESP32 #3 — Gas + Sound Node ===");
  Serial.printf("Gas pin:   GPIO%d (MQ-135)\n", GAS_PIN);
  Serial.printf("Sound pin: GPIO%d (KY-037)\n", SOUND_PIN);

  // Analog resolution: 12-bit (0-4095)
  analogReadResolution(12);

  // Connect to WiFi
  Serial.printf("\nConnecting to %s", ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  Serial.printf("IP address: %s\n", WiFi.localIP().toString().c_str());
  Serial.printf("Posting to: http://%s:%d/sensor-data\n\n", serverIP, serverPort);

  // Warmup MQ-135
  Serial.printf("Warming up MQ-135 sensor (%d seconds)...\n", WARMUP_SECONDS);
  for (int i = WARMUP_SECONDS; i > 0; i--) {
    Serial.printf("  %d seconds remaining...\r", i);
    delay(1000);
  }
  Serial.println("\nSensor ready!");

  // Init sample arrays
  for (int i = 0; i < SAMPLE_COUNT; i++) {
    gasSamples[i] = 0;
    soundSamples[i] = 0;
  }
}

int readGasLevel() {
  // MQ-135: higher analog value = more gas/pollution
  // Map 12-bit ADC (0-4095) to 0-500 range matching backend expectations
  int raw = analogRead(GAS_PIN);
  gasSamples[sampleIndex % SAMPLE_COUNT] = raw;

  // Rolling average
  long sum = 0;
  for (int i = 0; i < SAMPLE_COUNT; i++) sum += gasSamples[i];
  int avg = sum / SAMPLE_COUNT;

  return map(avg, 1800, 4095, 0, 120);
}

int readSoundLevel() {
  // KY-037: analog output varies with sound amplitude
  // Take multiple quick samples to catch peaks
  int peak = 0;
  for (int i = 0; i < 50; i++) {
    int val = analogRead(SOUND_PIN);
    if (val > peak) peak = val;
    delayMicroseconds(200);
  }

  soundSamples[sampleIndex % SAMPLE_COUNT] = peak;

  long sum = 0;
  for (int i = 0; i < SAMPLE_COUNT; i++) sum += soundSamples[i];
  int avg = sum / SAMPLE_COUNT;

  // Map to 0-120 dB-like scale
  return map(avg, 0, 4095, 0, 120);
}

void sendData(int gasLevel, int soundLevel) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Disconnected — reconnecting...");
    WiFi.reconnect();
    delay(2000);
    return;
  }

  HTTPClient http;
  String url = String("http://") + serverIP + ":" + serverPort + "/sensor-data";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  // Build JSON payload
  StaticJsonDocument<256> doc;
  doc["source"]      = "esp32_node3";
  doc["gas_level"]   = gasLevel;
  doc["sound_level"] = soundLevel;
  doc["motion"]      = false;   // No motion sensing on this node

  String body;
  serializeJson(doc, body);

  int httpCode = http.POST(body);

  if (httpCode == 200) {
    Serial.printf("[OK] Gas: %d | Sound: %d dB | HTTP %d\n",
                  gasLevel, soundLevel, httpCode);
  } else {
    Serial.printf("[ERR] HTTP %d — is FastAPI running?\n", httpCode);
  }

  http.end();
}

void loop() {
  unsigned long now = millis();

  if (now - lastSend >= SEND_INTERVAL_MS) {
    lastSend = now;

    int gas   = readGasLevel();
    int sound = readSoundLevel();

    sampleIndex++;

    sendData(gas, sound);
  }
}
