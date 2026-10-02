// ===========================================================================
// SMART LAB - REUSABLE BIN NODE (Robotics Lab, System 4)        ESP32 #3
// ===========================================================================
// PN532 (outside the bin) reads the NTAG213 sticker of an item; the portal
// decides; an MG90S servo presses the bin's own push-to-open button
// (PRESS - HOLD - RELEASE); a reed switch confirms the lid opened and
// closed. The servo is not part of any weighing path.
//
//   RETURN:   scan a checked-out item -> portal says OPEN_FOR_RETURN ->
//             lid open, item in, lid closed -> POST /reusable/complete
//   CHECKOUT: chosen in the portal -> this node fetches an OPEN_LID request
//             (only while idle) -> lid opens -> the person scans the item's
//             tag -> the portal checks it is the chosen item
//
// An NFC UID identifies an item; it authenticates nobody.
//
// STATUS: compiled, NOT yet run on hardware. Servo angles, hold time and
// the reed polarity are VERIFY values: set them on the actual bin.
// ===========================================================================
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_PN532.h>
#include <LiquidCrystal_I2C.h>
#include <ESP32Servo.h>

#include "secrets.h"        // WIFI_SSID, WIFI_PASS, DEVICE_KEY (gitignored)

// --- network ------------------------------------------------------------------
const char *BACKEND_IP = "192.168.1.200";
constexpr uint16_t BACKEND_PORT = 8000;
const char *LAB_ID    = "LAB_01";
const char *DEVICE_ID = "REUSE_BIN_1";
const char *FIRMWARE  = "reuse-0.1";
const IPAddress LOCAL_IP(192, 168, 1, 154), GATEWAY(192, 168, 1, 1),
                SUBNET(255, 255, 255, 0);

// --- pins -----------------------------------------------------------------------
constexpr uint8_t I2C_SDA = 21, I2C_SCL = 22;   // PN532 (0x24) + LCD on one bus
constexpr uint8_t SERVO_PIN = 13;
constexpr uint8_t REED_PIN  = 27;               // to GND through the reed, pulled up

// --- mechanism (VERIFY on the actual bin) ---------------------------------------
constexpr int      HOME_ANGLE   = 0;
constexpr int      PRESS_ANGLE  = 60;
constexpr uint32_t PRESS_RAMP_MS = 250;         // time to reach the press angle
constexpr uint32_t OPEN_HOLD_MS  = 8000;        // lid held open for the item
constexpr uint32_t LID_OPEN_TIMEOUT_MS  = 2000; // reed must show OPEN by then
constexpr uint32_t LID_CLOSE_TIMEOUT_MS = 6000; // and CLOSED after release
constexpr bool     HAS_REED = true;
constexpr int      REED_LID_CLOSED_LEVEL = LOW; // magnet at the reed = lid closed

constexpr uint32_t SCAN_REPEAT_MS  = 3000;      // same tag again within this = ignored
constexpr uint32_t COMMAND_POLL_MS = 2000;
constexpr uint32_t HEARTBEAT_MS    = 30000;
constexpr uint32_t HTTP_TIMEOUT_MS = 2500;

Adafruit_PN532 nfc(255, 255, &Wire);            // IRQ / RESET not wired
LiquidCrystal_I2C *lcd = nullptr;
Servo servo;
bool pn532Ok = false;
String lastUid;
uint32_t lastUidMs = 0, lastPollMs = 0, lastHeartbeatMs = 0, idleScreenAt = 0;

// --- helpers --------------------------------------------------------------------
void lcdShow(const String &l1, const String &l2) {
  Serial.printf("[LCD] %s | %s\n", l1.c_str(), l2.c_str());
  if (!lcd) return;
  lcd->clear();
  lcd->setCursor(0, 0); lcd->print(l1.substring(0, 16));
  lcd->setCursor(0, 1); lcd->print(l2.substring(0, 16));
}

void idleScreen() { lcdShow("SMART BIN", pn532Ok ? "SCAN AN ITEM" : "READER OFFLINE"); }

bool lidClosed() { return !HAS_REED || digitalRead(REED_PIN) == REED_LID_CLOSED_LEVEL; }

bool waitLid(bool wantClosed, uint32_t timeoutMs) {
  if (!HAS_REED) { delay(300); return true; }    // not verifiable without the reed
  uint32_t t0 = millis();
  while (millis() - t0 < timeoutMs) {
    if (lidClosed() == wantClosed) return true;
    delay(20);
  }
  return false;
}

void moveServo(int from, int to) {
  int steps = 10;
  for (int i = 1; i <= steps; i++) {
    servo.write(from + (to - from) * i / steps);
    delay(PRESS_RAMP_MS / steps);
  }
}

// One PRESS - HOLD - RELEASE cycle. Reports what the reed saw.
void lidCycle(bool *opened, bool *closed) {
  moveServo(HOME_ANGLE, PRESS_ANGLE);
  *opened = waitLid(false, LID_OPEN_TIMEOUT_MS);
  if (*opened) delay(OPEN_HOLD_MS);
  moveServo(PRESS_ANGLE, HOME_ANGLE);
  *closed = waitLid(true, LID_CLOSE_TIMEOUT_MS);
  Serial.printf("[LID] opened=%d closed=%d\n", *opened, *closed);
}

String http(const char *method, const String &path, const String &body, int *code) {
  *code = -1;
  if (WiFi.status() != WL_CONNECTED) return "";
  WiFiClient client;
  HTTPClient h;
  if (!h.begin(client, String("http://") + BACKEND_IP + ":" + BACKEND_PORT + "/api" + path)) return "";
  h.setConnectTimeout(HTTP_TIMEOUT_MS);
  h.setTimeout(HTTP_TIMEOUT_MS);
  h.addHeader("X-Device-Key", DEVICE_KEY);
  if (strcmp(method, "POST") == 0) {
    h.addHeader("Content-Type", "application/json");
    *code = h.POST(body);
  } else {
    *code = h.GET();
  }
  String reply = *code == 200 ? h.getString() : String();
  h.end();
  return reply;
}

String jsonStr(const String &s, const char *key) {
  int i = s.indexOf(String("\"") + key + "\":\"");
  if (i < 0) return "";
  i += strlen(key) + 4;
  int j = s.indexOf('"', i);
  return j > i ? s.substring(i, j) : "";
}

long jsonLong(const String &s, const char *key) {
  int i = s.indexOf(String("\"") + key + "\":");
  return i < 0 ? -1 : s.substring(i + strlen(key) + 3).toInt();
}

// --- flows ----------------------------------------------------------------------
void handleScan(const String &uid) {
  int code;
  String reply = http("POST", "/reusable/scan",
                      String("{\"device_uid\":\"") + DEVICE_ID + "\",\"nfc_uid\":\"" + uid + "\"}", &code);
  if (code != 200) { lcdShow("NO CONNECTION", "TRY AGAIN"); idleScreenAt = millis() + 3000; return; }
  String action = jsonStr(reply, "action");
  lcdShow(jsonStr(reply, "lcd1"), jsonStr(reply, "lcd2"));
  if (action == "OPEN_FOR_RETURN") {
    bool opened, closed;
    lidCycle(&opened, &closed);
    String done = http("POST", "/reusable/complete",
                       String("{\"device_uid\":\"") + DEVICE_ID + "\",\"nfc_uid\":\"" + uid +
                       "\",\"lid_opened\":" + (opened ? "true" : "false") +
                       ",\"lid_closed\":" + (closed ? "true" : "false") + "}", &code);
    if (code == 200) lcdShow(jsonStr(done, "lcd1"), jsonStr(done, "lcd2"));
    else lcdShow("NOT RECORDED", "CALL STAFF");
  }
  idleScreenAt = millis() + 3000;
}

void progress(long id, const char *status, const char *step, const char *msg) {
  int code;
  http("POST", String("/access/commands/") + id + "/progress",
       String("{\"device_uid\":\"") + DEVICE_ID + "\",\"status\":\"" + status +
       "\",\"step\":\"" + step + "\",\"message\":\"" + msg + "\"}", &code);
}

void pollCommand() {
  int code;
  String reply = http("GET", String("/access/commands/next?device_uid=") + DEVICE_ID, "", &code);
  if (code != 200 || reply.indexOf("\"id\":") < 0) return;
  long id = jsonLong(reply, "id");
  if (jsonStr(reply, "command") != "OPEN_LID") {
    progress(id, "FAILED", "UNKNOWN_COMMAND", "Not a bin request");
    return;
  }
  String item = jsonStr(reply, "asset_tag");
  lcdShow("TAKE " + item, "THEN SCAN IT");
  progress(id, "RUNNING", "OPENING", "Opening the lid");
  bool opened, closed;
  lidCycle(&opened, &closed);
  if (!opened) progress(id, "FAILED", "LID_NOT_OPENED", "The lid did not open");
  else progress(id, "RUNNING", closed ? "LID_CLOSED" : "LID_LEFT_OPEN",
                "Waiting for the item's tag");          // the scan completes it
  lcdShow("SCAN " + item, "TO CONFIRM");
  idleScreenAt = millis() + 15000;
}

void sendHeartbeat() {
  int code;
  http("POST", "/access/heartbeat",
       String("{\"device_uid\":\"") + DEVICE_ID + "\",\"lab_id\":\"" + LAB_ID +
       "\",\"device_type\":\"SENSOR_NODE\",\"firmware_version\":\"" + FIRMWARE +
       "\",\"ip_address\":\"" + WiFi.localIP().toString() + "\",\"components\":{" +
       "\"reusable_bin\":true,\"pn532\":" + (pn532Ok ? "true" : "false") +
       ",\"lid_closed\":" + (HAS_REED ? (lidClosed() ? "true" : "false") : "null") + "}}", &code);
  lastHeartbeatMs = millis();
}

void ensureWifi() {
  static uint32_t lastTry = 0;
  if (WiFi.status() == WL_CONNECTED || millis() - lastTry < 10000) return;
  lastTry = millis();
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== SMART LAB - REUSABLE BIN NODE (System 4) ===");
  pinMode(REED_PIN, INPUT_PULLUP);
  servo.attach(SERVO_PIN);
  servo.write(HOME_ANGLE);

  Wire.begin(I2C_SDA, I2C_SCL);
  uint8_t lcdAddr = 0;
  for (uint8_t a = 1; a < 127; a++) {             // scan: never assume addresses
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.printf("[I2C] Device at 0x%02X%s\n", a, a == 0x24 ? " (PN532)" : "");
      bool backpack = (a >= 0x20 && a <= 0x27 && a != 0x24) || (a >= 0x38 && a <= 0x3F);
      if (backpack && !lcdAddr) lcdAddr = a;
    }
  }
  if (lcdAddr) { lcd = new LiquidCrystal_I2C(lcdAddr, 16, 2); lcd->init(); lcd->backlight(); }

  delay(1000);                                    // PN532 needs time after power-up
  nfc.begin();
  for (int i = 0; i < 5 && !pn532Ok; i++) {
    uint32_t fw = nfc.getFirmwareVersion();
    pn532Ok = fw != 0;
    if (pn532Ok) { nfc.SAMConfig(); Serial.printf("[NFC] PN532 firmware %lu.%lu\n", (fw >> 16) & 0xFF, (fw >> 8) & 0xFF); }
    else delay(200);
  }
  if (!pn532Ok) Serial.println("[NFC][FAIL] PN532 not answering");

  WiFi.mode(WIFI_STA);
  WiFi.config(LOCAL_IP, GATEWAY, SUBNET, GATEWAY);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) delay(250);
  Serial.printf("[WIFI] %s\n", WiFi.status() == WL_CONNECTED
                ? WiFi.localIP().toString().c_str() : "not connected yet");
  idleScreen();
}

void loop() {
  ensureWifi();
  if (lastHeartbeatMs == 0 || millis() - lastHeartbeatMs > HEARTBEAT_MS) sendHeartbeat();
  if (idleScreenAt && millis() > idleScreenAt) { idleScreenAt = 0; idleScreen(); }

  if (pn532Ok) {
    uint8_t uid[7], len = 0;
    if (nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &len, 150)) {
      String hex;
      for (uint8_t i = 0; i < len; i++) { char b[3]; snprintf(b, 3, "%02X", uid[i]); hex += b; }
      if (hex != lastUid || millis() - lastUidMs > SCAN_REPEAT_MS) {   // anti-repeat
        lastUid = hex;
        lastUidMs = millis();
        Serial.printf("[NFC] Tag %s\n", hex.c_str());
        handleScan(hex);
      }
    }
  }
  if (!idleScreenAt && millis() - lastPollMs > COMMAND_POLL_MS) {
    lastPollMs = millis();
    pollCommand();
  }
}
