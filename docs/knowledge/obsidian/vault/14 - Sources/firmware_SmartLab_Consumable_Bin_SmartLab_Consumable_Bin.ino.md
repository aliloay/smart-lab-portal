---
type: "source-mirror"
source_kind: "source-code"
source_path: "firmware/SmartLab_Consumable_Bin/SmartLab_Consumable_Bin.ino"
source_hash: "57be653f9cd68f9e4f9a03bffcdad399b8a8c31c7ebcf023667e832143ed8f4c"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `firmware/SmartLab_Consumable_Bin/SmartLab_Consumable_Bin.ino` - edit the original in the repository, not this note.

Systems: [[Consumables bin]]

## Related
- [[docs_ROBOTICS_LAB_ARCHITECTURE.md]] - mentioned by docs
- [[tools_bringup_README.md]] - mentioned by docs

```ino
// ===========================================================================
// SMART LAB - CONSUMABLE BIN NODE (Robotics Lab, System 3)      ESP32 #2
// ===========================================================================
// One weighing bin: removable bin -> plate -> 1 kg load cell -> fixed base.
// HX711 -> ESP32 -> 16x2 I2C LCD, and over Wi-Fi to the portal:
//   - STABLE masses           POST /api/inventory/measurements
//   - heartbeat every 30 s    POST /api/access/heartbeat
// The portal turns stable mass steps into withdrawals/refills and, once the
// bin's calibration (empty-bin mass, unit mass) has been MEASURED and
// entered, estimates the quantity; it replies with it for the LCD.
//
// Two calibrations, kept apart:
//   1. Load cell (here, Serial commands, stored in flash):
//        tare        - platform empty -> zero
//        cal <g>     - a known reference mass on the platform -> scale
//        show        - current raw / scale / mass
//        avg <n>     - mean and spread of n raw samples (known-mass tests)
//        stream      - toggle: every HX711 sample as "CSV,lc,..." (noise,
//                      drift, settling, step response); portal reporting
//                      pauses while streaming so test loads are not stock
//   2. Bin (in the portal, Inventory): empty-bin mass, unit mass, noise.
// Every reading / send / HTTP round trip / Wi-Fi change is also printed as a
// "CSV,..." line (tools/bringup/README.md) for the measurement log.
// This firmware reports the mass on the PLATFORM in grams (bin included).
//
// STATUS (2026-10-10): pins 32/33 like the reusable bin; precision pipeline new - VERIFY on hardware.
// Earlier note: Values marked VERIFY come
// from the noise and settling tests in docs/ROBOTICS_LAB_ARCHITECTURE.md.
// ===========================================================================
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Preferences.h>
#include "HX711.h"
#include <algorithm>

#include "secrets.h"        // WIFI_SSID, WIFI_PASS, DEVICE_KEY (gitignored)

// --- network ------------------------------------------------------------------
const char *BACKEND_IP = "192.168.1.200";
constexpr uint16_t BACKEND_PORT = 8000;
// BENCH = the bring-up bench (home); its data stays apart from the lab's.
// Set "LAB_01" when the bin is installed in the Robotics Lab.
const char *LAB_ID    = "LAB_01";      // Robotics Lab (was BENCH, which the portal does not have)
const char *DEVICE_ID = "BIN_NODE_1";
const char *BIN_CODE  = "BIN-R10K";            // must exist in the portal (Inventory)
const char *FIRMWARE  = "bin-0.3";
const IPAddress LOCAL_IP(192, 168, 1, 153), GATEWAY(192, 168, 1, 1),
                SUBNET(255, 255, 255, 0);

// --- pins -----------------------------------------------------------------------
constexpr uint8_t HX_DT_PIN  = 32;   // same wiring as the reusable bin
constexpr uint8_t HX_SCK_PIN = 33;
constexpr uint8_t I2C_SDA = 21, I2C_SCL = 22;   // LCD

// --- measurement (small parts: resistors, LEDs, capacitors) ---------------------
// Pipeline per HX711 sample (~10/s): median of the last 5 (drops spikes) ->
// moving average of AVG_N -> grams. A real step (> STEP_RESET_G) restarts the
// average so the display follows at once instead of sliding for 2 s.
// The LCD and the portal get the value only through a deadband, so the last
// digit does not flicker. All values VERIFY with "avg 100" on the real bin.
constexpr float    MAX_LOAD_G      = 1000.0;    // load cell rated capacity; not its calibration factor
constexpr uint8_t  MEDIAN_N        = 5;         // spike filter
constexpr uint8_t  AVG_N           = 20;        // ~2 s of samples at 10 Hz
constexpr float    STEP_RESET_G    = 0.5;       // a jump this big = something added / removed
constexpr float    DISPLAY_DEADBAND_G = 0.04;   // shown value moves only beyond this
constexpr float    STABLE_SNAP_G   = 0.02;      // ... or, once stable, beyond this
constexpr float    STABLE_BAND_G   = 0.08;      // spread of the window to call it stable
constexpr uint32_t STABLE_TIME_MS  = 1500;      // ... held for this long
constexpr float    SEND_DELTA_G    = 0.05;      // report a stable value that moved this much
// Zero: at power-on (after BOOT_SETTLE_MS) a reading below BOOT_ZERO_MAX_G is
// drift and becomes the new zero; above it, items are on the platform and the
// saved zero is kept (zeroing would hide them). While the platform is EMPTY and
// stable, the zero follows slow drift (zero tracking); a removed part is a step,
// never tracked.
constexpr uint32_t BOOT_SETTLE_MS  = 4000;
constexpr float    BOOT_ZERO_MAX_G = 2.0;
constexpr float    ZERO_TRACK_BAND_G = 0.25;    // only this close to zero
constexpr float    ZERO_TRACK_RATE = 0.02;      // fraction of the error corrected per sample
// Loaded drift (bin-0.3, 2026-10-18). Measured: with the resistor cup on, the reading crept
// 134.80 -> 134.50 g in 15 min after power-on (one resistor = 0.21 g, so 30 read as 29).
// While the reading stays STABLE the zero follows that slow creep, at most DRIFT_RATE_G_PER_S.
// Taking or adding parts always breaks stability (a 0.21 g step vs the 0.08 g band), and the
// value it settles on afterwards is accepted as the new reference - never "corrected" back.
// A restart keeps the last saved reading when the power-on reading is within RESTART_KEEP_MAX_G
// of it (creep while off); a bigger difference is a real change and is kept as measured.
// Trade-off (owner's choice): one part taken while the bin is OFF is not seen; the portal's
// bin calibration (tare) re-anchors the count to a confirmed number.
constexpr float    DRIFT_RATE_G_PER_S = 0.003;  // 0.18 g/min - 9x the measured creep
constexpr float    DRIFT_FOLLOW_MAX_G = 0.30;   // farther than this = not drift: take it as is
constexpr float    STEP_ACCEPT_G      = 0.12;   // settles this far from the reference = parts moved
                                                // (one resistor 0.21 g; filtered noise ~0.015 g)
constexpr float    RESTART_KEEP_MAX_G = 0.30;   // ~1.5 resistors
constexpr uint32_t MASS_SAVE_MIN_MS   = 60000;  // flash write at most once a minute ...
constexpr float    MASS_SAVE_DELTA_G  = 0.05;   // ... and only when the reading moved this much
constexpr uint32_t KEEPALIVE_MS    = 1000;      // or every 1 s: the portal books a change once two readings agree
constexpr uint32_t HEARTBEAT_MS    = 30000;
constexpr uint32_t HTTP_TIMEOUT_MS = 2500;

HX711 scale;
Preferences prefs;
LiquidCrystal_I2C *lcd = nullptr;
uint8_t lcdAddr = 0;

float    scaleFactor = 0;          // counts per gram; 0 = not calibrated
long     zeroOffset  = 0;
float    massG = NAN;              // filtered reading (grams)
float    shownG = NAN;             // what the LCD / portal see (deadband)
long     medBuf[MEDIAN_N]; uint8_t medN = 0, medI = 0;
double   avgBuf[AVG_N];   uint8_t avgN = 0, avgI = 0;
bool     stable = false;
float    windowMin = NAN, windowMax = NAN;
uint32_t windowStart = 0;
float    lastSentG = NAN;
uint32_t lastSentMs = 0, lastHeartbeatMs = 0;
bool     netOk = false;
bool     streaming = false;        // "stream": raw samples out, portal paused
String   itemName = "";
uint32_t lastSampleMs = 0;         // last HX711 sample (heartbeat "hx711": answering recently)
float    anchorG = NAN;            // accepted loaded reading the zero is held to while stable
bool     followStable = false;     // stable since anchorG was taken
uint32_t lastFollowMs = 0;
double   zeroTrimCounts = 0;       // fractional counts not yet moved into zeroOffset
float    savedMassG = NAN;         // last reading saved in flash (restart reference)
uint32_t lastMassSaveMs = 0;
const char *bootAnchor = "none";   // what the power-on check did (heartbeat)
long     qtyEst = -1, qtyErr = -1;

// --- I2C: find the LCD instead of assuming its address --------------------------
void scanI2c() {
  Serial.println("[I2C] Scanning...");
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.printf("[I2C] Device at 0x%02X\n", a);
      // PCF8574 (0x20-0x27) and PCF8574A (0x38-0x3F) are the usual LCD backpacks.
      bool backpack = (a >= 0x20 && a <= 0x27) || (a >= 0x38 && a <= 0x3F);
      if (backpack && !lcdAddr) lcdAddr = a;
    }
  }
  if (lcdAddr) Serial.printf("[I2C] Using 0x%02X for the LCD\n", lcdAddr);
  else Serial.println("[I2C] No LCD backpack found - running without the display");
}

void lcdShow(const String &l1, const String &l2) {
  if (!lcd) return;
  lcd->clear();
  lcd->setCursor(0, 0); lcd->print(l1.substring(0, 16));
  lcd->setCursor(0, 1); lcd->print(l2.substring(0, 16));
}

void drawLcd() {
  String l1 = itemName.length() ? itemName : String(BIN_CODE);
  String l2;
  if (scaleFactor == 0)      l2 = "NOT CALIBRATED";
  else if (isnan(massG) || isnan(shownG)) l2 = "SETTLING...";
  else if (massG > MAX_LOAD_G) l2 = "OVER 1000 g!";
  else {
    float v = fabs(shownG) < 0.005f ? 0.0f : shownG;   // no "-0.00"
    l2 = String(v, 2) + " g";
    if (qtyEst >= 0) l2 += " ~" + String(qtyEst);
    if (!stable) l2 += " ..";
  }
  if (!netOk && l2.length() <= 14) l2 += " !";
  lcdShow(l1, l2);
}

// --- load cell ------------------------------------------------------------------
void loadCalibration() {
  prefs.begin("bin", true);
  scaleFactor = prefs.getFloat("scale", 0);
  zeroOffset  = prefs.getLong("offset", 0);
  savedMassG  = prefs.getFloat("mass", NAN);
  prefs.end();
  if (scaleFactor != 0) {
    scale.set_scale(scaleFactor);
    scale.set_offset(zeroOffset);
    Serial.printf("[CAL] Loaded: scale %.3f counts/g, offset %ld\n", scaleFactor, zeroOffset);
  } else {
    Serial.println("[CAL] Not calibrated: 'tare' with the platform empty, then 'cal <grams>'");
  }
}

void saveCalibration() {
  prefs.begin("bin", false);
  prefs.putFloat("scale", scaleFactor);
  prefs.putLong("offset", zeroOffset);
  prefs.end();
}

static long medianRaw() {
  long t[MEDIAN_N];
  memcpy(t, medBuf, sizeof(long) * medN);
  std::sort(t, t + medN);
  return t[medN / 2];
}

// Saved together: the zero as it is now (drift followed) and the reading it gives.
void saveMassReference(float g) {
  prefs.begin("bin", false);
  prefs.putLong("offset", zeroOffset);
  prefs.putFloat("mass", g);
  prefs.end();
  savedMassG = g;
  lastMassSaveMs = millis();
}

// Called on every sample (see the constants above); acts only on a stable, loaded platform.
void followLoadedDrift(uint32_t now) {
  if (!stable || isnan(massG) || fabs(massG) < BOOT_ZERO_MAX_G) { followStable = false; return; }
  // After a moment of instability only a real step moves the reference: a wobble that settles
  // within STEP_ACCEPT_G of it keeps it (re-anchoring on every wobble let the creep through -
  // measured on the bench 2026-10-18: +0.1 g in 4 min, then a false "2 taken").
  bool settledAfterStep = !followStable && !isnan(anchorG) && fabs(massG - anchorG) >= STEP_ACCEPT_G;
  if (!followStable && !settledAfterStep && !isnan(anchorG) && fabs(massG - anchorG) <= DRIFT_FOLLOW_MAX_G) {
    followStable = true;                   // same load as before the wobble: keep following
    lastFollowMs = now;
    return;
  }
  if (settledAfterStep || isnan(anchorG) || fabs(massG - anchorG) > DRIFT_FOLLOW_MAX_G) {
    anchorG = massG;                       // settled after a change: this is the new reference
    followStable = true;
    lastFollowMs = now;
    Serial.printf("CSV,anchor,%lu,%.3f\n", (unsigned long)now, anchorG);
    return;
  }
  double dt = (now - lastFollowMs) / 1000.0;
  lastFollowMs = now;
  double maxStep = DRIFT_RATE_G_PER_S * dt;
  double corr = std::max(-maxStep, std::min(maxStep, (double)(massG - anchorG)));
  zeroTrimCounts += corr * scaleFactor;     // reading too high -> zero up, and the reverse
  long whole = (long)zeroTrimCounts;
  if (whole) { zeroOffset += whole; zeroTrimCounts -= whole; scale.set_offset(zeroOffset); }
  if ((isnan(savedMassG) || fabs(anchorG - savedMassG) >= MASS_SAVE_DELTA_G || whole) &&
      now - lastMassSaveMs >= MASS_SAVE_MIN_MS) saveMassReference(anchorG);
}

void resetFilter() { medN = medI = avgN = avgI = 0; windowMin = windowMax = NAN; stable = false; }

// One HX711 sample -> filtered grams. Non-blocking: returns at once when no
// new sample is ready (the HX711 makes ~10 per second).
void readScale() {
  if (!scale.is_ready()) return;
  long raw = scale.read();
  lastSampleMs = millis();
  medBuf[medI] = raw; medI = (medI + 1) % MEDIAN_N; if (medN < MEDIAN_N) medN++;
  if (scaleFactor == 0) return;
  double g = (medianRaw() - (double)zeroOffset) / scaleFactor;

  // A real step restarts the average (fast response); noise does not.
  if (avgN > 0) {
    double mean = 0; for (uint8_t i = 0; i < avgN; i++) mean += avgBuf[i]; mean /= avgN;
    if (fabs(g - mean) > STEP_RESET_G) { avgN = avgI = 0; windowMin = windowMax = NAN; }
  }
  avgBuf[avgI] = g; avgI = (avgI + 1) % AVG_N; if (avgN < AVG_N) avgN++;
  double sum = 0; for (uint8_t i = 0; i < avgN; i++) sum += avgBuf[i];
  massG = sum / avgN;

  if (massG > MAX_LOAD_G) {
    stable = false;
    windowMin = windowMax = NAN;
    Serial.printf("[SCALE][OVERLOAD] %.2f g exceeds the %.0f g cell rating; not reporting\n",
                  massG, MAX_LOAD_G);
    return;
  }
  uint32_t now = millis();
  // Stability: the filtered value stays within STABLE_BAND_G for STABLE_TIME_MS.
  if (isnan(windowMin) || max(windowMax, massG) - min(windowMin, massG) > STABLE_BAND_G) {
    windowMin = windowMax = massG;          // moved: start a new window
    windowStart = now;
  } else {
    windowMin = min(windowMin, massG);
    windowMax = max(windowMax, massG);
  }
  stable = avgN >= AVG_N && now - windowStart >= STABLE_TIME_MS;

  // Zero tracking: empty platform, stable, a hair off zero -> nudge the zero.
  if (stable && fabs(massG) < ZERO_TRACK_BAND_G) {
    long shift = lround(massG * scaleFactor * ZERO_TRACK_RATE);
    if (shift) { zeroOffset += shift; scale.set_offset(zeroOffset); }
  }
  followLoadedDrift(now);
  // Deadband: while moving, the shown value only follows a real change; once
  // stable it settles onto the reading (within STABLE_SNAP_G), so the screen is
  // calm AND exact (measured noise of the filtered value: about +-0.015 g).
  if (isnan(shownG) || fabs(massG - shownG) >= DISPLAY_DEADBAND_G ||
      (stable && fabs(massG - shownG) >= STABLE_SNAP_G)) shownG = massG;
  static uint32_t lastLog = 0;
  if (now - lastLog >= 500) {
    lastLog = now;
    Serial.printf("CSV,mass,%lu,%.3f,%.2f,%d\n", (unsigned long)now, massG, shownG, stable ? 1 : 0);
  }
}

// Power-on zero: drift is zeroed, items on the platform are kept.
void bootZero() {
  if (scaleFactor == 0) { Serial.println("[ZERO] Not calibrated - 'tare' empty, then 'cal <grams>'"); return; }
  Serial.printf("[ZERO] Letting the load cell settle %lu ms...\n", (unsigned long)BOOT_SETTLE_MS);
  uint32_t t0 = millis();
  while (millis() - t0 < BOOT_SETTLE_MS) { if (scale.is_ready()) scale.read(); delay(5); }
  if (!scale.wait_ready_timeout(1000)) { Serial.println("[ZERO][FAIL] HX711 not ready"); return; }
  double raw = scale.read_average(30);
  double g = (raw - zeroOffset) / scaleFactor;
  if (fabs(g) < BOOT_ZERO_MAX_G) {
    zeroOffset = lround(raw);
    scale.set_offset(zeroOffset);
    saveCalibration();
    bootAnchor = "empty";
    Serial.printf("[ZERO] Platform empty: %.2f g of drift -> zero (saved)\n", g);
  } else if (!isnan(savedMassG) && fabs(g - savedMassG) <= RESTART_KEEP_MAX_G) {
    // Same load as before the restart, crept a little: keep the reading (and so the count).
    zeroOffset += lround((g - savedMassG) * scaleFactor);
    scale.set_offset(zeroOffset);
    saveCalibration();
    bootAnchor = "kept";
    Serial.printf("[ZERO] %.2f g at power-on, %.2f g before the restart: %+.2f g of creep corrected "
                  "(reading kept)\n", g, savedMassG, g - savedMassG);
  } else {
    bootAnchor = isnan(savedMassG) ? "no_reference" : "changed";
    Serial.printf("[ZERO] %.2f g on the platform at power-on: items present - saved zero kept%s\n", g,
                  isnan(savedMassG) ? "" : " (differs from before the restart: kept as measured)");
  }
}

// n raw samples: mean and standard deviation (Welford), raw and in grams.
void averageSamples(int n) {
  double mean = 0, m2 = 0;
  int got = 0;
  for (int i = 0; i < n; i++) {
    if (!scale.wait_ready_timeout(500)) break;
    double x = (double)scale.read();
    got++;
    double d = x - mean;
    mean += d / got;
    m2 += d * (x - mean);
  }
  if (got < 2) { Serial.println("[AVG] HX711 not answering"); return; }
  double sd = sqrt(m2 / (got - 1));
  double g = scaleFactor != 0 ? (mean - zeroOffset) / scaleFactor : NAN;
  double sdg = scaleFactor != 0 ? sd / fabs(scaleFactor) : NAN;
  Serial.printf("CSV,avg,%lu,%d,%.1f,%.1f,%.3f,%.3f\n", (unsigned long)millis(), got, mean, sd, g, sdg);
  Serial.printf("[AVG] %d samples: raw %.1f (sd %.1f) -> %.3f g (sd %.3f g)\n", got, mean, sd, g, sdg);
}

void handleSerial() {
  static String line;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c != '\n') { if (line.length() < 32) line += c; continue; }
    line.trim();
    if (line == "tare") {
      scale.set_scale(1);
      scale.tare(20);
      zeroOffset = scale.get_offset();
      if (scaleFactor != 0) scale.set_scale(scaleFactor);
      saveCalibration();
      resetFilter();
      anchorG = NAN; followStable = false; zeroTrimCounts = 0;
      saveMassReference(NAN);              // the old restart reference no longer applies
      Serial.printf("[CAL] Zero set (offset %ld)\n", zeroOffset);
    } else if (line.startsWith("cal ")) {
      float g = line.substring(4).toFloat();
      if (g <= 0 || g > MAX_LOAD_G) {
        Serial.printf("[CAL] Usage: cal <known reference mass in grams, 0 < g <= %.0f>\n", MAX_LOAD_G);
      }
      else {
        scale.set_scale(1);
        float raw = scale.get_units(40);       // counts above zero (4 s average)
        scaleFactor = raw / g;
        scale.set_scale(scaleFactor);
        saveCalibration();
        resetFilter();
        anchorG = NAN; followStable = false; zeroTrimCounts = 0;
        saveMassReference(NAN);
        Serial.printf("[CAL] %.2f g -> scale %.3f counts/g (saved)\n", g, scaleFactor);
      }
    } else if (line == "show") {
      Serial.printf("[CAL] raw %ld, offset %ld, scale %.3f, mass %.2f g, %s\n",
                    (long)scale.read_average(10), zeroOffset, scaleFactor, massG,   // read_average() is a float here
                    stable ? "stable" : "settling");
    } else if (line == "stream") {
      streaming = !streaming;
      Serial.printf("[STREAM] %s\n", streaming
                    ? "on - every HX711 sample as CSV,lc,<ms>,<raw>,<grams>; portal reporting paused"
                    : "off - portal reporting resumed");
    } else if (line.startsWith("avg ")) {
      averageSamples(constrain(line.substring(4).toInt(), 2, 500));
    } else if (line.length()) {
      Serial.println("[CMD] tare | cal <grams> | show | avg <n> | stream");
    }
    line = "";
  }
}

// --- network --------------------------------------------------------------------
String post(const char *path, const String &body, int *code) {
  *code = -1;
  if (WiFi.status() != WL_CONNECTED) return "";
  WiFiClient client;
  HTTPClient http;
  if (!http.begin(client, String("http://") + BACKEND_IP + ":" + BACKEND_PORT + "/api" + path)) return "";
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  uint32_t t0 = millis();
  *code = http.POST(body);
  Serial.printf("CSV,http,%lu,%s,%d,%lu\n", (unsigned long)millis(), path, *code,
                (unsigned long)(millis() - t0));
  String reply = *code == 200 ? http.getString() : String();
  http.end();
  return reply;
}

long jsonLong(const String &s, const char *key) {
  int i = s.indexOf(String("\"") + key + "\":");
  if (i < 0) return -1;
  i += strlen(key) + 3;
  if (s.startsWith("null", i)) return -1;
  return s.substring(i).toInt();
}

String jsonStr(const String &s, const char *key) {
  int i = s.indexOf(String("\"") + key + "\":\"");
  if (i < 0) return "";
  i += strlen(key) + 4;
  int j = s.indexOf('"', i);
  return j > i ? s.substring(i, j) : "";
}

void sendMass() {
  String body = String("{\"device_uid\":\"") + DEVICE_ID + "\",\"readings\":[{\"bin_code\":\"" +
                BIN_CODE + "\",\"mass_g\":" + String(shownG, 2) + "}]}";
  int code;
  String reply = post("/inventory/measurements", body, &code);
  netOk = code == 200;
  if (!netOk) { Serial.printf("[NET] measurement not recorded (HTTP %d)\n", code); return; }
  lastSentG = shownG;
  lastSentMs = millis();
  if (reply.indexOf("\"known\":false") >= 0) {
    Serial.printf("[NET] The portal has no bin %s - create it under Inventory\n", BIN_CODE);
    return;
  }
  itemName = jsonStr(reply, "item_name");
  qtyEst = jsonLong(reply, "qty_est");
  qtyErr = jsonLong(reply, "qty_err");
  String tx = jsonStr(reply, "transaction");
  Serial.printf("CSV,sent,%lu,%.3f,%ld,%s\n", (unsigned long)millis(), massG, qtyEst, tx.c_str());
  Serial.printf("[BIN] %.2f g sent%s%s\n", massG,
                qtyEst >= 0 ? (String(" ~") + qtyEst + " pcs").c_str() : "",
                tx.length() ? (String(" -> ") + tx).c_str() : "");
}

void sendHeartbeat() {
  String body = String("{\"device_uid\":\"") + DEVICE_ID + "\",\"lab_id\":\"" + LAB_ID +
                "\",\"device_type\":\"SENSOR_NODE\",\"firmware_version\":\"" + FIRMWARE +
                "\",\"ip_address\":\"" + WiFi.localIP().toString() + "\",\"components\":{" +
                // answering recently - is_ready() alone is false most of the time, because every
                // sample is read the moment it is ready (it reported false while weighing fine)
                "\"hx711\":" + (lastSampleMs && millis() - lastSampleMs < 2000 ? "true" : "false") +
                ",\"uptime_s\":" + String(millis() / 1000) +
                ",\"boot_reading\":\"" + bootAnchor + "\"" +
                ",\"calibrated\":" + (scaleFactor != 0 ? "true" : "false") +
                ",\"lcd\":" + (lcd ? "true" : "false") + "}}";
  int code;
  post("/access/heartbeat", body, &code);
  netOk = code == 200;
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
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== SMART LAB - CONSUMABLE BIN NODE (System 3) ===");
  Serial.printf("firmware %s, device %s, lab %s, bin %s\n", FIRMWARE, DEVICE_ID, LAB_ID, BIN_CODE);
  // Initialize and tare the scale before the optional LCD. A display or I2C
  // issue must not prevent the load cell from starting and reporting readings.
  Serial.printf("[SCALE] Starting HX711 on DT=%u, SCK=%u\n", HX_DT_PIN, HX_SCK_PIN);
  // Match the reusable bin: do not reset here. HX711's default reset reads a
  // sample with no timeout and can freeze startup before the LCD is refreshed.
  scale.begin(HX_DT_PIN, HX_SCK_PIN, true, false);
  Serial.println("[SCALE] HX711 begin returned");
  loadCalibration();
  bootZero();
  resetFilter();

  Wire.begin(I2C_SDA, I2C_SCL);
  scanI2c();
  if (lcdAddr) {
    lcd = new LiquidCrystal_I2C(lcdAddr, 16, 2);
    Serial.println("[LCD] Initializing display at detected address");
    lcd->init();
    lcd->backlight();
    Serial.println("[LCD] Display initialized");
  }
  drawLcd();

  WiFi.mode(WIFI_STA);
  WiFi.config(LOCAL_IP, GATEWAY, SUBNET, GATEWAY);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) delay(250);
  Serial.printf("[WIFI] %s\n", WiFi.status() == WL_CONNECTED
                ? WiFi.localIP().toString().c_str() : "not connected yet - will retry");
}

void loop() {
  static uint32_t lastDraw = 0;
  ensureWifi();
  handleSerial();
  if (streaming) {                 // measurement mode: raw samples only
    if (scale.is_ready()) {
      long raw = scale.read();
      lastSampleMs = millis();
      float g = scaleFactor != 0 ? (raw - zeroOffset) / scaleFactor : NAN;
      Serial.printf("CSV,lc,%lu,%ld,%.3f\n", (unsigned long)millis(), raw, g);
    }
    if (lastHeartbeatMs == 0 || millis() - lastHeartbeatMs > HEARTBEAT_MS) sendHeartbeat();
    if (millis() - lastDraw > 1000) { lastDraw = millis(); lcdShow(BIN_CODE, "STREAMING"); }
    return;
  }
  readScale();
  if (lastHeartbeatMs == 0 || millis() - lastHeartbeatMs > HEARTBEAT_MS) sendHeartbeat();
  if (stable && !isnan(massG) &&
      (isnan(lastSentG) || fabs(shownG - lastSentG) >= SEND_DELTA_G || millis() - lastSentMs > KEEPALIVE_MS)) {
    sendMass();
  }
  if (millis() - lastDraw > 500) { lastDraw = millis(); drawLcd(); }
}

```
