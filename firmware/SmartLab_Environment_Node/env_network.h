// ===========================================================================
// NETWORK - Wi-Fi and (later) the portal, on their own task (core 0).
// Nothing here can stall the sensors: loop() never waits on the network.
//
// LOCAL TEST MODE (env_config.h): Wi-Fi connects and reconnects, nothing is sent.
// Backend mode (phase 9) reuses the portal's EXISTING endpoints, the same
// ones the earlier env-0.2 draft used - no new API:
//   POST /api/access/heartbeat   device registration + component health
//   POST /api/access/telemetry   readings: temperature, humidity and the
//                                hazard states smoke / flame / motion (0/1)
// The portal timestamps what it receives; per-channel flame, PIR zones and
// MQ raw values need a portal change first, agreed before it is made.
// ===========================================================================
#pragma once
#include <WiFi.h>
#include <HTTPClient.h>
#include <stdarg.h>

// --- what the network task may read, copied from loop() under a lock -------
struct Published {
  bool  dhtFitted, dhtValid;  float tempC, humPct;
  bool  pirFitted[2], pirOnline[2], motion[2];
  bool  mqFitted, mqReady, mqFault, gasDo;  uint8_t gasLevel;
  bool  flameFitted, flameAny;
};
portMUX_TYPE pubMux = portMUX_INITIALIZER_UNLOCKED;
Published    pub;

void publish(uint32_t now) {
  Published p;
  p.dhtFitted = fit.dht;   p.dhtValid = dhtValid(now);
  p.tempC = dhtS.tempC;    p.humPct = dhtS.humPct;
  for (int i = 0; i < 2; i++) {
    p.pirFitted[i] = *pirs[i].fitted;
    p.pirOnline[i] = pirs[i].health == H_ONLINE;
    p.motion[i]    = pirs[i].motion;
  }
  p.mqFitted = fit.mq;  p.mqReady = mq.health == H_READY;  p.mqFault = mq.health == H_FAULT;
  p.gasLevel = mq.level;  p.gasDo = fit.mqDo && mq.doStable;
  p.flameFitted = flameAnyFitted();  p.flameAny = flameAny();
  portENTER_CRITICAL(&pubMux);
  pub = p;
  portEXIT_CRITICAL(&pubMux);
}

// --- a small fixed-size JSON writer (no String, no heap growth) -------------
struct JsonBuf {
  char  *b;
  size_t cap, len = 0;
  bool   overflow = false;
  JsonBuf(char *buf, size_t c) : b(buf), cap(c) { b[0] = 0; }
  void add(const char *fmt, ...) {
    if (overflow) return;
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(b + len, cap - len, fmt, ap);
    va_end(ap);
    if (n < 0 || (size_t)n >= cap - len) { overflow = true; len = cap - 1; b[len] = 0; }
    else len += n;
  }
};

// --- HTTP (network task only; timeouts so it can never hang) ----------------
int postJson(const char *path, const char *body) {
  if (WiFi.status() != WL_CONNECTED) return -1;
  char url[96];
  snprintf(url, sizeof(url), "http://%s:%u/api%s", BACKEND_HOST, BACKEND_PORT, path);
  WiFiClient client;
  HTTPClient http;
  if (!http.begin(client, url)) return -1;
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  uint32_t t0 = millis();
  int code = http.POST((uint8_t *)body, strlen(body));
  uint32_t rtt = millis() - t0;
  http.end();
  // Round trip node -> portal -> node, for the network measurements.
  Serial.printf("CSV,http,%lu,%s,%d,%lu\n", (unsigned long)millis(), path, code, (unsigned long)rtt);
  if (code != 200) Serial.printf("[NET] %s -> HTTP %d\n", path, code);
  return code;
}

bool sendHeartbeat() {
  Published p;
  portENTER_CRITICAL(&pubMux); p = pub; portEXIT_CRITICAL(&pubMux);
  char body[400];
  JsonBuf j(body, sizeof(body));
  j.add("{\"device_uid\":\"%s\",\"lab_id\":\"%s\",\"device_type\":\"SENSOR_NODE\","
        "\"firmware_version\":\"env-%s\",\"ip_address\":\"%s\",\"components\":{",
        DEVICE_ID, LAB_ID, FIRMWARE_VERSION, WiFi.localIP().toString().c_str());
  // null = not fitted, so the portal does not report it as broken.
  j.add("\"dht22\":%s", p.dhtFitted ? (p.dhtValid ? "true" : "false") : "null");
  j.add(",\"mq_1\":%s", p.mqFitted ? (p.mqFault ? "false" : "true") : "null");
  j.add(",\"pir_1\":%s", p.pirFitted[0] ? "true" : "null");
  j.add(",\"pir_2\":%s", p.pirFitted[1] ? "true" : "null");
  j.add(",\"flame\":%s}}", p.flameFitted ? "true" : "null");
  return !j.overflow && postJson("/access/heartbeat", body) == 200;
}

// Readings in the portal's existing format. Only sensors that are fitted
// AND trustworthy right now are sent - never a placeholder value.
bool sendEnvironmentSnapshot() {
  Published p;
  portENTER_CRITICAL(&pubMux); p = pub; portEXIT_CRITICAL(&pubMux);
  char body[512];
  JsonBuf j(body, sizeof(body));
  j.add("{\"device_uid\":\"%s\",\"lab_id\":\"%s\",\"readings\":[", DEVICE_ID, LAB_ID);
  int n = 0;
  auto reading = [&](const char *metric, float v, const char *unit) {
    j.add("%s{\"metric\":\"%s\",\"value\":%.2f,\"unit\":\"%s\"}", n++ ? "," : "", metric, v, unit);
  };
  if (p.dhtValid) { reading("temperature", p.tempC, "C"); reading("humidity", p.humPct, "%"); }
  if (p.mqReady)  reading("smoke", (p.gasLevel >= GAS_WARNING || p.gasDo) ? 1 : 0, "state");
  if (p.flameFitted) reading("flame", p.flameAny ? 1 : 0, "state");
  if (p.pirOnline[0] || p.pirOnline[1])
    reading("motion", ((p.pirOnline[0] && p.motion[0]) || (p.pirOnline[1] && p.motion[1])) ? 1 : 0, "state");
  j.add("]}");
  if (n == 0) return true;                 // nothing trustworthy to send yet
  return !j.overflow && postJson("/access/telemetry", body) == 200;
}

// An event in backend mode = send the current states now (the portal raises
// and clears its alerts on the state change). In local mode the event has
// already been printed by emitEvent().
bool sendEnvironmentEvent(const EnvEvent &) { return sendEnvironmentSnapshot(); }

// --- the task -------------------------------------------------------------------
void netTask(void *) {
  uint32_t lastTry = 0, lastBeat = 0, lastSnap = 0, lastFail = 0;
  bool firstTry = true, urgent = false;
  for (;;) {
    uint32_t now = millis();
    if (WIFI_ENABLED && WiFi.status() != WL_CONNECTED &&
        (firstTry || now - lastTry >= WIFI_RECONNECT_INTERVAL_MS)) {
      firstTry = false;
      lastTry = now;
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASS);    // returns at once; connects in the background
    }
    if (!LOCAL_TEST_MODE && WiFi.status() == WL_CONNECTED) {
      EnvEvent e;
      while (eventQueue && xQueueReceive(eventQueue, &e, 0) == pdTRUE) urgent = true;
      if (lastBeat == 0 || now - lastBeat >= HEARTBEAT_INTERVAL_MS) {
        sendHeartbeat();
        lastBeat = millis();
      }
      // Safety change: at once (and again next round if the portal missed it).
      // A failed send (portal down, Wi-Fi gone) waits SEND_RETRY_MS instead of
      // hammering the portal every loop.
      bool retryOk = lastFail == 0 || now - lastFail >= SEND_RETRY_MS;
      if (retryOk && (urgent || lastSnap == 0 || now - lastSnap >= SNAPSHOT_INTERVAL_MS)) {
        if (sendEnvironmentSnapshot()) { urgent = false; lastSnap = millis(); lastFail = 0; }
        else lastFail = millis();
      }
    }
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

// Wi-Fi changes, seen from loop(): one event per change.
void wifiWatch(uint32_t now) {
  static bool was = false;
  bool up = WiFi.status() == WL_CONNECTED;
  if (up == was) return;
  was = up;
  if (up) {
    Serial.printf("CSV,wifi,%lu,connected,%d\n", (unsigned long)now, (int)WiFi.RSSI());
    Serial.printf("[WIFI] Connected  IP: %s  RSSI: %d dBm\n", WiFi.localIP().toString().c_str(), (int)WiFi.RSSI());
    emitEvent(EV_WIFI_CONNECTED, "wifi", WiFi.RSSI());
  } else {
    Serial.printf("CSV,wifi,%lu,disconnected,0\n", (unsigned long)now);
    emitEvent(EV_WIFI_DISCONNECTED, "wifi");
  }
}

void networkBegin() {
  if (!WIFI_ENABLED) return;
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(false);           // the task does it, on its own schedule
  WiFi.config(LOCAL_IP, GATEWAY, SUBNET, GATEWAY);
  WiFi.setSleep(false);                   // lower latency; the node is mains-powered
  xTaskCreatePinnedToCore(netTask, "net", 8192, nullptr, 1, nullptr, 0);
}
