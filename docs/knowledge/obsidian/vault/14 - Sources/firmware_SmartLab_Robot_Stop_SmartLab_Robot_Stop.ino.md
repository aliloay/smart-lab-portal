---
type: "source-mirror"
source_kind: "source-code"
source_path: "firmware/SmartLab_Robot_Stop/SmartLab_Robot_Stop.ino"
source_hash: "05813d1196c10c2c21ff7a435e10eacca90ba0249696ba2ec011c693707a2adc"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `firmware/SmartLab_Robot_Stop/SmartLab_Robot_Stop.ino` - edit the original in the repository, not this note.

Systems: [[Robots (read-only)]]

## Related
- [[docs_ROBOT_CONTROL.md]] - mentioned by docs

```ino
// ===========================================================================
// SMART LAB - UR5e STOP RELAY                                 ROBOT_STOP 0.1.0
// ===========================================================================
// Portal STOP that works while the UR5e stays in LOCAL mode, whoever drives it
// (pendant jogging, Freedrive, another person's program or PC). In Local mode
// the controller ignores network stop commands; it always obeys its own
// SAFEGUARD STOP input. Two relay contacts (one per channel, SI0 and SI1) are
// wired in place of that input's factory jumpers:
//
//   relay ENERGISED  = contacts closed = input at 24 V = robot may run (RUN)
//   relay RELEASED   = contacts open   = safeguard stop        (STOP)
//
// So a portal STOP, an unplugged ESP32 or a dead relay coil all stop the robot
// (fail-safe direction). Wi-Fi or portal loss KEEPS the last state (a network
// hiccup must not stop someone's work) - the portal shows the relay offline.
//
// The ESP32 asks the portal every 200 ms: GET /api/robots/stop-relay/poll
// with its own device key; the answer is the portal's STOP latch for the
// robot. It never decides on its own and has no "run" button.
// NOT a safety-rated emergency stop. The pendant E-stop stays the E-stop.
//
// Board: ESP32 Dev Module (WROOM-32), esp32 core 3.x. No extra libraries.
// Wiring + commissioning: README.md in this folder, docs/ROBOT_CONTROL.md.
// ===========================================================================
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include "secrets.h"     // WIFI_SSID, WIFI_PASS, DEVICE_KEY (gitignored)

static const char *FW = "robot_stop-0.1.0";
// --- pins (2-channel 5 V relay module with opto inputs, IN1/IN2) ----------
constexpr int  PIN_RELAY_A = 26;          // channel SI0
constexpr int  PIN_RELAY_B = 27;          // channel SI1
constexpr int  PIN_LED     = 2;           // on = RUN, blinking = STOP, off = no portal yet
constexpr bool RELAY_ACTIVE_LOW = true;   // most HW 2-ch modules: IN low = coil on. CHECK yours (README step 3)
// --- network --------------------------------------------------------------
static const char *BACKEND_HOST = "192.168.1.200";   // the lab laptop
constexpr uint16_t BACKEND_PORT = 8000;
static const IPAddress LOCAL_IP(192, 168, 1, 157), GATEWAY(192, 168, 1, 1), SUBNET(255, 255, 255, 0);
constexpr uint32_t POLL_MS = 200, HTTP_TIMEOUT_MS = 800, WIFI_RETRY_MS = 5000;

Preferences prefs;
bool running = false;          // what the relays do now (true = RUN)
bool everAnswered = false;
uint32_t appliedSeq = 0, lastOkMs = 0, lastPollMs = 0, lastWifiTry = 0, lastDiagMs = 0;
WiFiClient tcp;
HTTPClient http;

void setRelays(bool run) {
  int level = (run ^ RELAY_ACTIVE_LOW) ? HIGH : LOW;
  digitalWrite(PIN_RELAY_A, level);       // both channels together: the controller checks they agree
  digitalWrite(PIN_RELAY_B, level);
  if (run != running) {
    Serial.printf("CSV,relay,%lu,%s\n", (unsigned long)millis(), run ? "RUN" : "STOP");
    prefs.putBool("run", run);            // reboot keeps the last commanded state
  }
  running = run;
}

void wifiWatch(uint32_t now) {
  if (WiFi.status() == WL_CONNECTED || now - lastWifiTry < WIFI_RETRY_MS) return;
  lastWifiTry = now;
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

// One poll. Returns true when the portal answered; the relays follow the answer.
bool pollPortal() {
  if (WiFi.status() != WL_CONNECTED) return false;
  char url[200];
  snprintf(url, sizeof(url), "http://%s:%u/api/robots/stop-relay/poll?relay=%s&applied_seq=%lu&fw=%s&rssi=%d",
           BACKEND_HOST, BACKEND_PORT, running ? "RUN" : "STOP", (unsigned long)appliedSeq, FW, (int)WiFi.RSSI());
  if (!http.begin(tcp, url)) return false;
  http.setReuse(true);                    // keep-alive: one TCP connection, ~20 ms per poll on the LAN
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("X-Device-Key", DEVICE_KEY);
  int code = http.GET();
  bool ok = false;
  if (code == 200) {
    String b = http.getString();
    int s = b.indexOf("\"stop\":");
    int q = b.indexOf("\"seq\":");
    if (s >= 0 && q >= 0) {
      bool stop = b.substring(s + 7, s + 11) == "true";
      setRelays(!stop);
      appliedSeq = (uint32_t)b.substring(q + 6).toInt();
      ok = true;
    }
  } else if (code == 401 || code == 403) {
    Serial.printf("[POLL] refused %d - wrong DEVICE_KEY or ROBOT_STOP_RELAY_UID not set on the portal\n", code);
  }
  http.end();
  return ok;
}

void setup() {
  Serial.begin(115200);
  delay(200);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_RELAY_A, OUTPUT);
  pinMode(PIN_RELAY_B, OUTPUT);
  prefs.begin("robotstop", false);
  bool last = prefs.getBool("run", false);  // first boot ever: STOP until the portal says RUN
  running = !last;                          // force setRelays to write the pins
  setRelays(last);
  Serial.printf("\n%s | relays %s (last commanded) | portal %s:%u | %s\n", FW, last ? "RUN" : "STOP",
                BACKEND_HOST, BACKEND_PORT, LOCAL_IP.toString().c_str());
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);                     // modem sleep adds 100+ ms to every poll
  WiFi.config(LOCAL_IP, GATEWAY, SUBNET);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  lastWifiTry = millis();
}

void loop() {
  uint32_t now = millis();
  wifiWatch(now);
  if (now - lastPollMs >= POLL_MS) {
    lastPollMs = now;
    if (pollPortal()) { lastOkMs = now; everAnswered = true; }
  }
  bool portalOk = everAnswered && now - lastOkMs < 2000;
  digitalWrite(PIN_LED, !portalOk ? LOW : running ? HIGH : ((now / 250) % 2));
  if (now - lastDiagMs >= 10000) {
    lastDiagMs = now;
    Serial.printf("[DIAG] relays=%s portal=%s wifi=%s rssi=%d seq=%lu\n", running ? "RUN" : "STOP",
                  portalOk ? "ok" : "NO ANSWER (holding last state)", WiFi.status() == WL_CONNECTED ? "up" : "down",
                  (int)WiFi.RSSI(), (unsigned long)appliedSeq);
  }
  delay(5);
}

```
