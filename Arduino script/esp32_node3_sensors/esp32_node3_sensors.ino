#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "lucky plaza";
const char* password = "homesweethome2";
const char* serverIP = "10.0.0.145";
const int serverPort = 8000;

const int GAS_PIN = 4;
const int SOUND_PIN = 5;

unsigned long lastSend = 0;
const int SEND_INTERVAL_MS = 2000;

int readSoundPeak() {
  int minVal = 4095;
  int maxVal = 0;

  unsigned long start = millis();

  while (millis() - start < 300) {
    int val = analogRead(SOUND_PIN);

    if (val < minVal) minVal = val;
    if (val > maxVal) maxVal = val;
  }

  return maxVal - minVal;
}

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
  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();

    int rawGas = analogRead(GAS_PIN);
    int rawSoundPeak = readSoundPeak();

    int gasLevel = map(rawGas, 1200, 2500, 0, 500);
    gasLevel = constrain(gasLevel, 0, 500);

    int soundLevel = map(rawSoundPeak, 0, 800, 0, 120);
    soundLevel = constrain(soundLevel, 0, 120);

    Serial.printf("[DBG] rawGas=%d gas=%d soundPeak=%d soundScore=%d\n",
                  rawGas, gasLevel, rawSoundPeak, soundLevel);

    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;

      String url = String("http://") + serverIP + ":" + serverPort + "/sensor-data";
      http.begin(url);
      http.addHeader("Content-Type", "application/json");

      String body = "{";
      body += "\"source\":\"esp32_node3\",";
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