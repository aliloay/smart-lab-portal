// PN532 (HW-147 V3) in I2C mode, OUTSIDE the bin: the deliberate
// "this item" scan. Diagnostics first: the reader must answer with its
// firmware version, otherwise NFC is reported unavailable (never assumed).
// A UID identifies an ITEM's sticker; it authenticates nobody.
#pragma once
#include <Arduino.h>

class Adafruit_PN532;

struct NfcScan {
  String uid;          // hex, no separators, e.g. 04A1B2C3D4E5F6
  uint8_t uidLength;   // 4 or 7 bytes for ISO14443A
  uint32_t atMs;       // millis() of the detection
};

class NFCManager {
 public:
  bool begin();                      // Wire must already be started
  bool available() const { return _ok; }
  uint32_t firmwareVersion() const { return _fw; }
  // Looks for a tag every NFC_POLL_INTERVAL_MS (each look waits at most
  // NFC_READ_TIMEOUT_MS). Returns true once per NEW scan; the same UID within
  // NFC_DUPLICATE_MS is ignored.
  bool poll(NfcScan *out);
  void printStatus();

 private:
  Adafruit_PN532 *_pn = nullptr;
  bool _ok = false;
  uint32_t _fw = 0, _lastPollMs = 0, _lastUidMs = 0, _failures = 0;
  String _lastUid;
};
