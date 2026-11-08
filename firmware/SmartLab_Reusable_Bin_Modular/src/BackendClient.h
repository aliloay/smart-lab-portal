// The Smart Lab portal's REAL bin API (HTTP/JSON, X-Device-Key header).
// Paths are in config.h. The ESP32 never touches the database.
//
//   heartbeat()         POST /api/access/heartbeat     registers / keeps the node online
//   scan(uid, delta)    POST /api/reusable/scan         -> action + LCD text (portal decides)
//   returnDone(...)     POST /api/reusable/complete     after a RETURN lid cycle
//   nextCommand()       GET  /api/access/commands/next  OPEN_LID for a portal checkout
//   commandStatus(...)  POST /api/access/commands/{id}/progress
// Extra fields (local verification, RFID lists) are sent along; today's
// portal ignores fields it does not know, so they are forward-compatible
// and change nothing there.
#pragma once
#include <Arduino.h>

struct ScanReply {
  bool ok = false;            // HTTP 200 with a parsable reply
  int httpCode = -1;
  String action;              // OPEN_FOR_RETURN, CHECKOUT_OK, WRONG_ITEM, NOT_ALLOWED, UNKNOWN
  String lcd1, lcd2, assetTag, assetName, weightCheck;
};

struct CompleteReply {
  bool ok = false, recorded = false;
  int httpCode = -1;
  String lcd1, lcd2, weightCheck;
};

struct BinCommand {
  bool present = false;
  long id = -1;
  String command, intent, assetTag, assetName;
};

struct HeartbeatInfo {
  bool hx711, calibrated, pn532, lcd, reedFitted, servoCalibrated, servoLocked;
  int lidState;               // 0 unknown, 1 open, 2 closed
  const char *rfidStatus, *mode, *fault;
};

class BackendClient {
 public:
  bool heartbeat(const HeartbeatInfo &h);
  ScanReply scan(const String &uid, float massDeltaG, const String &extraJson);
  CompleteReply returnDone(const String &uid, bool lidOpened, bool lidClosed,
                           float beforeG, float afterG, const String &extraJson);
  BinCommand nextCommand();
  void commandStatus(long id, const char *status, const char *step, const char *message);
  // Checkout by weight: the bin weighed before and after (the portal decides).
  CompleteReply checkoutDone(long commandId, bool lidOpened, bool lidClosed, float beforeG, float afterG);
  // A settled change nobody requested (staff are alerted).
  void weightChange(float deltaG, float massG);
  bool reachable() const { return _lastOk; }
  int lastHttpCode() const { return _lastCode; }

 private:
  String request(const char *method, const String &path, const String &body, int *code);
  bool _lastOk = false;
  int _lastCode = -1;
};
