// ===========================================================================
// SMART LAB - ENVIRONMENT NODE (Robotics Lab, System 2)        ESP32 #1
// ===========================================================================
// Senses only. It never actuates anything and is not a certified fire,
// gas or safety system: the MQ-2 and the flame sensor are INDICATORS, and
// the emergency input only WATCHES an existing safety signal through an
// optocoupler.
//
// Reports to the portal (laptop, 192.168.1.200:8000) over the lab Wi-Fi:
//   - heartbeat every 30 s           POST /api/access/heartbeat
//   - readings every 30 s, and AT ONCE when a hazard state changes
//                                    POST /api/access/telemetry
// The server timestamps every reading (UTC) and raises / clears the hazard
// alerts. Only sensors marked present below are reported; a missing or
// failing sensor is never replaced by a made-up value.
//
// STATUS: written against the design in docs/ROBOTICS_LAB_ARCHITECTURE.md
// (section I) and compiled; NOT yet run on hardware. Every value marked
// VERIFY must be checked on the actual module before it is trusted.
//
// BRING-UP: sensors are enabled ONE AT A TIME (HAS_* below), in the order
// DHT22 -> MQ-2 -> flame -> PIR -> leak. An enabled input with nothing
// connected floats and reports false hazards, so a sensor is enabled only
// once it is wired and its output level has been measured.
// Every reading, state change, HTTP round trip and Wi-Fi change is also
// printed as a "CSV,..." line (see tools/bringup/README.md) for the
// measurement log; tools/bringup/serial_log.py saves them with timestamps.
// ===========================================================================
#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>

// WIFI_SSID, WIFI_PASS and DEVICE_KEY live in secrets.h (gitignored).
#include "secrets.h"

// --- network -----------------------------------------------------------------
const char *BACKEND_IP = "192.168.1.200";
constexpr uint16_t BACKEND_PORT = 8000;
// BENCH = the bring-up bench (home); its data stays apart from the lab's.
// Set "LAB_01" when the node is installed in the Robotics Lab.
const char *LAB_ID    = "BENCH";
const char *DEVICE_ID = "ENV_LAB01";
const char *FIRMWARE  = "env-0.2";
// Fixed address, like the door boards: the plan in the architecture doc.
const IPAddress LOCAL_IP(192, 168, 1, 152), GATEWAY(192, 168, 1, 1),
                SUBNET(255, 255, 255, 0);

constexpr uint32_t REPORT_PERIOD_MS    = 30000;
constexpr uint32_t HEARTBEAT_PERIOD_MS = 30000;
constexpr uint32_t HTTP_TIMEOUT_MS     = 2500;

// --- pins (ADC1 / input-only pins; no strapping pins 0, 2, 12, 15) -----------
constexpr uint8_t DHT_PIN       = 4;
constexpr uint8_t MQ2_DO_PIN    = 34;   // through a divider if DO swings to 5 V (VERIFY)
constexpr uint8_t FLAME_DO_PIN  = 32;   // module powered at 3.3 V
constexpr uint8_t LEAK_DO_PIN   = 33;   // module powered at 3.3 V
constexpr uint8_t PIR_PIN       = 27;   // HC-SR501 OUT (VERIFY it is 3.3 V)
constexpr uint8_t EMERGENCY_PIN = 26;   // optocoupler output, pulled up

// --- which sensors are actually fitted (unfitted = never reported) -----------
// Bring-up stage 1: DHT22 only. Enable the next one after it is wired and
// its output level is measured (README, "Before connecting anything").
constexpr bool HAS_DHT = true, HAS_MQ2 = false, HAS_FLAME = false,
               HAS_LEAK = false, HAS_PIR = false, HAS_EMERGENCY = false;

// --- the level that means "detected" on each module (VERIFY each one) -------
// Common LM393-comparator modules (MQ-2, flame, rain/leak) pull DO LOW when
// they trigger; HC-SR501 drives OUT HIGH on motion; the optocoupler input
// reads LOW when the emergency signal is active. Confirm with a multimeter.
constexpr int MQ2_ACTIVE = LOW, FLAME_ACTIVE = LOW, LEAK_ACTIVE = LOW,
              PIR_ACTIVE = HIGH, EMERGENCY_ACTIVE = LOW;

// A state must hold this long before it counts (filters glitches).
constexpr uint32_t STATE_DEBOUNCE_MS = 500;
// MQ-2 heater warm-up: its output is not reported until this has passed.
// VERIFY: measure how long DO takes to settle after power-up.
constexpr uint32_t MQ2_WARMUP_MS = 120000;
// DHT22: at most one read every 2 s (sensor limit).
constexpr uint32_t DHT_PERIOD_MS = 2500;

DHT dht(DHT_PIN, DHT22);

// ---------------------------------------------------------------------------
struct StateInput {
  const char *metric;
  uint8_t pin;
  int activeLevel;
  bool present;
  bool state;            // debounced: true = detected
  bool candidate;
  uint32_t candidateSince;
};

StateInput inputs[] = {
  {"smoke",      MQ2_DO_PIN,    MQ2_ACTIVE,       HAS_MQ2,       false, false, 0},
  {"flame",      FLAME_DO_PIN,  FLAME_ACTIVE,     HAS_FLAME,     false, false, 0},
  {"water_leak", LEAK_DO_PIN,   LEAK_ACTIVE,      HAS_LEAK,      false, false, 0},
  {"motion",     PIR_PIN,       PIR_ACTIVE,       HAS_PIR,       false, false, 0},
  {"emergency",  EMERGENCY_PIN, EMERGENCY_ACTIVE, HAS_EMERGENCY, false, false, 0},
};
constexpr size_t INPUT_COUNT = sizeof(inputs) / sizeof(inputs[0]);

float    lastTemp = NAN, lastHum = NAN;
bool     dhtOk = false;
uint8_t  dhtFailures = 0;
uint32_t lastDhtMs = 0, lastReportMs = 0, lastHeartbeatMs = 0;
bool     reportDue = true;                 // send at the next chance

String backendUrl(const char *path) {
  return String("http://") + BACKEND_IP + ":" + BACKEND_PORT + "/api" + path;
}

bool postJson(const char *path, const String &body) {
  if (WiFi.status() != WL_CONNECTED) return false;
  WiFiClient client;
  HTTPClient http;
  if (!http.begin(client, backendUrl(path))) return false;
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  uint32_t t0 = millis();
  int code = http.POST(body);
  uint32_t rtt = millis() - t0;
  http.end();
  // Round trip node -> portal -> node, for the network measurements.
  Serial.printf("CSV,http,%lu,%s,%d,%lu\n", (unsigned long)millis(), path, code, (unsigned long)rtt);
  if (code != 200) Serial.printf("[NET] %s -> HTTP %d\n", path, code);
  return code == 200;
}

bool mq2Ready() { return millis() > MQ2_WARMUP_MS; }

// --- sensors ------------------------------------------------------------------
void readDht() {
  if (!HAS_DHT || millis() - lastDhtMs < DHT_PERIOD_MS) return;
  lastDhtMs = millis();
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (isnan(t) || isnan(h)) {
    Serial.printf("CSV,dht_fail,%lu\n", (unsigned long)millis());
    // Three failures in a row = the sensor is reported faulty and its
    // values are no longer sent (the portal then shows them as stale).
    if (++dhtFailures >= 3 && dhtOk) {
      dhtOk = false;
      Serial.println("[DHT] Read failing - temperature/humidity not reported");
    }
    return;
  }
  dhtFailures = 0;
  Serial.printf("CSV,dht,%lu,%.2f,%.2f\n", (unsigned long)millis(), t, h);
  if (!dhtOk) Serial.println("[DHT] Reading");
  dhtOk = true;
  lastTemp = t;
  lastHum = h;
}

void pollInputs() {
  uint32_t now = millis();
  for (auto &in : inputs) {
    if (!in.present) continue;
    bool raw = digitalRead(in.pin) == in.activeLevel;
    if (raw != in.candidate) { in.candidate = raw; in.candidateSince = now; }
    if (in.candidate != in.state && now - in.candidateSince >= STATE_DEBOUNCE_MS) {
      in.state = in.candidate;
      bool warming = strcmp(in.metric, "smoke") == 0 && !mq2Ready();
      Serial.printf("[STATE] %s -> %s%s\n", in.metric, in.state ? "DETECTED" : "normal",
                    warming ? " (MQ-2 warming up - not reported yet)" : "");
      Serial.printf("CSV,state,%lu,%s,%d\n", (unsigned long)now, in.metric, in.state ? 1 : 0);
      if (!warming) reportDue = true;      // a hazard change goes out at once
    }
  }
}

// --- reports -------------------------------------------------------------------
void addReading(String &body, bool &first, const char *metric, float value, const char *unit) {
  if (!first) body += ',';
  first = false;
  body += String("{\"metric\":\"") + metric + "\",\"value\":" + String(value, 2) +
          ",\"unit\":\"" + unit + "\"}";
}

void sendReadings() {
  String body = String("{\"device_uid\":\"") + DEVICE_ID + "\",\"lab_id\":\"" + LAB_ID +
                "\",\"readings\":[";
  bool first = true;
  if (HAS_DHT && dhtOk) {
    addReading(body, first, "temperature", lastTemp, "C");
    addReading(body, first, "humidity", lastHum, "%");
  }
  for (auto &in : inputs) {
    if (!in.present) continue;
    if (strcmp(in.metric, "smoke") == 0 && !mq2Ready()) continue;
    addReading(body, first, in.metric, in.state ? 1 : 0, "state");
  }
  body += "]}";
  if (first) return;                        // nothing measurable to send
  if (postJson("/access/telemetry", body)) {
    reportDue = false;
    lastReportMs = millis();
  }
  // On failure reportDue stays set: the current states go out as soon as
  // the network is back. Values during an outage are not back-dated.
}

void sendHeartbeat() {
  String body = String("{\"device_uid\":\"") + DEVICE_ID + "\",\"lab_id\":\"" + LAB_ID +
                "\",\"device_type\":\"SENSOR_NODE\",\"firmware_version\":\"" + FIRMWARE +
                "\",\"ip_address\":\"" + WiFi.localIP().toString() + "\",\"components\":{" +
                "\"dht22\":" + (HAS_DHT ? (dhtOk ? "true" : "false") : "null") +
                ",\"mq2_ready\":" + (HAS_MQ2 ? (mq2Ready() ? "true" : "false") : "null") + "}}";
  postJson("/access/heartbeat", body);
  lastHeartbeatMs = millis();
}

// Logs every connect / disconnect (reconnect behaviour and time).
void logWifi() {
  static bool was = false;
  bool now = WiFi.status() == WL_CONNECTED;
  if (now == was) return;
  was = now;
  if (now) Serial.printf("CSV,wifi,%lu,connected,%d\n", (unsigned long)millis(), (int)WiFi.RSSI());
  else     Serial.printf("CSV,wifi,%lu,disconnected,0\n", (unsigned long)millis());
}

void ensureWifi() {
  static uint32_t lastTry = 0;
  logWifi();
  if (WiFi.status() == WL_CONNECTED || millis() - lastTry < 10000) return;
  lastTry = millis();
  Serial.println("[WIFI] Reconnecting...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("=================================================");
  Serial.println(" SMART LAB - ENVIRONMENT NODE (System 2)");
  Serial.printf(" firmware %s, device %s, lab %s\n", FIRMWARE, DEVICE_ID, LAB_ID);
  Serial.println(" Indicators only - not a certified safety system.");
  Serial.println("=================================================");

  for (auto &in : inputs) {
    if (!in.present) continue;
    // GPIO34-39 have no internal pull-ups; the modules drive these lines.
    pinMode(in.pin, in.pin >= 34 ? INPUT : (in.pin == EMERGENCY_PIN ? INPUT_PULLUP : INPUT));
    in.state = in.candidate = digitalRead(in.pin) == in.activeLevel;
    in.candidateSince = millis();
    Serial.printf("[INIT] %-10s GPIO%-2u start: %s\n", in.metric, in.pin,
                  in.state ? "DETECTED" : "normal");
  }
  if (HAS_DHT) dht.begin();
  if (HAS_MQ2) Serial.printf("[INIT] MQ-2 warm-up: smoke not reported for %lu s\n",
                             (unsigned long)(MQ2_WARMUP_MS / 1000));

  WiFi.mode(WIFI_STA);
  WiFi.config(LOCAL_IP, GATEWAY, SUBNET, GATEWAY);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) { delay(250); Serial.print('.'); }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    WiFi.setSleep(false);
    Serial.printf("[WIFI] Connected: %s -> portal %s:%u\n",
                  WiFi.localIP().toString().c_str(), BACKEND_IP, BACKEND_PORT);
  } else {
    Serial.println("[WIFI][WARN] Not connected yet - will keep trying.");
  }
}

void loop() {
  ensureWifi();
  readDht();
  pollInputs();
  // The first heartbeat goes before the first readings: it is what
  // registers this node (type SENSOR_NODE) with the portal.
  if (lastHeartbeatMs == 0 || millis() - lastHeartbeatMs > HEARTBEAT_PERIOD_MS) sendHeartbeat();
  if (reportDue || millis() - lastReportMs > REPORT_PERIOD_MS) sendReadings();
  delay(20);
}
