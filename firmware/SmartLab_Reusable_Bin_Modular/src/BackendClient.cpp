#include "BackendClient.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "config.h"
#include "secrets.h"
#include "Log.h"

static String num(float g) { return isnan(g) ? String("null") : String(g, 1); }

String BackendClient::request(const char *method, const String &path, const String &body, int *code) {
  *code = -1;
  if (WiFi.status() != WL_CONNECTED) { _lastOk = false; _lastCode = -1; return ""; }
  WiFiClient client;
  HTTPClient h;
  String url = String("http://") + BACKEND_HOST + ":" + BACKEND_PORT + path;
  if (!h.begin(client, url)) { _lastOk = false; return ""; }
  h.setConnectTimeout(HTTP_TIMEOUT_MS);
  h.setTimeout(HTTP_TIMEOUT_MS);
  h.addHeader("X-Device-Key", DEVICE_KEY);
  uint32_t t0 = millis();
  if (strcmp(method, "POST") == 0) {
    h.addHeader("Content-Type", "application/json");
    *code = h.POST(body);
  } else {
    *code = h.GET();
  }
  String reply = *code > 0 ? h.getString() : String();
  h.end();
  _lastCode = *code;
  _lastOk = *code == 200;
  if (*code != 200) LOG("BACKEND", "%s %s -> %d (%lu ms)%s", method, path.c_str(), *code,
                        (unsigned long)(millis() - t0), *code == 401 ? " - device key refused" : "");
  return *code == 200 ? reply : String();
}

bool BackendClient::heartbeat(const HeartbeatInfo &i) {
  JsonDocument d;
  d["device_uid"] = DEVICE_ID;
  d["lab_id"] = LAB_ID;
  d["device_type"] = "SENSOR_NODE";
  d["firmware_version"] = FIRMWARE_VERSION;
  d["ip_address"] = WiFi.localIP().toString();
  JsonObject c = d["components"].to<JsonObject>();
  c["reusable_bin"] = true;               // how the portal finds the lab's bin node
  c["hx711"] = i.hx711;
  c["scale_calibrated"] = i.calibrated;
  c["pn532"] = i.pn532;
  c["lcd"] = i.lcd;
  c["servo_calibrated"] = i.servoCalibrated;
  c["servo_locked_out"] = i.servoLocked;
  if (i.reedFitted && i.lidState) c["lid_closed"] = i.lidState == 2; else c["lid_closed"] = nullptr;
  c["rfid"] = i.rfidStatus;
  c["mode"] = i.mode;
  c["fault"] = i.fault;
  String body;
  serializeJson(d, body);
  int code;
  request("POST", PATH_HEARTBEAT, body, &code);
  return code == 200;
}

ScanReply BackendClient::scan(const String &uid, float massDeltaG, const String &extraJson) {
  ScanReply r;
  String body = String("{\"device_uid\":\"") + DEVICE_ID + "\",\"nfc_uid\":\"" + uid + "\"" +
                (isnan(massDeltaG) ? String("") : ",\"mass_delta_g\":" + num(massDeltaG)) +
                (extraJson.length() ? "," + extraJson : String("")) + "}";
  String reply = request("POST", PATH_NFC_SCAN, body, &r.httpCode);
  JsonDocument d;
  if (r.httpCode != 200 || deserializeJson(d, reply)) return r;
  r.ok = true;
  r.action = d["action"] | "";
  r.lcd1 = d["lcd1"] | "";
  r.lcd2 = d["lcd2"] | "";
  r.assetTag = d["asset_tag"] | "";
  r.weightCheck = d["weight_check"] | "";
  LOG("BACKEND", "scan %s -> %s (%s / %s)%s%s", uid.c_str(), r.action.c_str(), r.lcd1.c_str(), r.lcd2.c_str(),
      r.weightCheck.length() ? ", weight " : "", r.weightCheck.c_str());
  return r;
}

CompleteReply BackendClient::returnDone(const String &uid, bool opened, bool closed,
                                        float beforeG, float afterG, const String &extraJson) {
  CompleteReply r;
  String body = String("{\"device_uid\":\"") + DEVICE_ID + "\",\"nfc_uid\":\"" + uid +
                "\",\"lid_opened\":" + (opened ? "true" : "false") +
                ",\"lid_closed\":" + (closed ? "true" : "false") +
                ",\"mass_before_g\":" + num(beforeG) + ",\"mass_after_g\":" + num(afterG) +
                (extraJson.length() ? "," + extraJson : String("")) + "}";
  String reply = request("POST", PATH_RETURN_DONE, body, &r.httpCode);
  JsonDocument d;
  if (r.httpCode != 200 || deserializeJson(d, reply)) return r;
  r.ok = true;
  r.recorded = d["recorded"] | false;
  r.lcd1 = d["lcd1"] | "";
  r.lcd2 = d["lcd2"] | "";
  r.weightCheck = d["weight_check"] | "";
  LOG("BACKEND", "return %s -> %s (%s / %s)", uid.c_str(), r.recorded ? "RECORDED" : "NOT recorded",
      r.lcd1.c_str(), r.lcd2.c_str());
  return r;
}

BinCommand BackendClient::nextCommand() {
  BinCommand c;
  int code;
  String reply = request("GET", String(PATH_COMMAND_NEXT) + "?device_uid=" + DEVICE_ID, "", &code);
  JsonDocument d;
  if (code != 200 || deserializeJson(d, reply) || d["id"].isNull()) return c;
  c.present = true;
  c.id = d["id"] | -1L;
  c.command = d["command"] | "";
  JsonVariantConst args = d["args"];
  c.intent = args["intent"] | (d["intent"] | "");
  c.assetTag = args["asset_tag"] | (d["asset_tag"] | "");
  LOG("BACKEND", "command #%ld %s %s %s", c.id, c.command.c_str(), c.intent.c_str(), c.assetTag.c_str());
  return c;
}

void BackendClient::commandStatus(long id, const char *status, const char *step, const char *message) {
  char path[96];
  snprintf(path, sizeof(path), PATH_COMMAND_STATUS, id);
  JsonDocument d;
  d["device_uid"] = DEVICE_ID;
  d["status"] = status;
  d["step"] = step;
  d["message"] = message;
  String body;
  serializeJson(d, body);
  int code;
  request("POST", path, body, &code);
}
