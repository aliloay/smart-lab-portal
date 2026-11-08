#include "NFCManager.h"
#include <Wire.h>
#include <Adafruit_PN532.h>
#include "config.h"
#include "DisplayManager.h"
#include "Log.h"

static constexpr uint8_t NO_PIN = 255;   // IRQ and RESET not wired (as on the door)

bool NFCManager::begin() {
  LOG("NFC", "Looking for the PN532 on I2C 0x%02X (SDA %u, SCL %u)...", PN532_ADDR, PIN_NFC_SDA, PIN_NFC_SCL);
  Wire1.begin(PIN_NFC_SDA, PIN_NFC_SCL, 100000);
  _pn = new Adafruit_PN532(NO_PIN, NO_PIN, &Wire1);
  _pn->begin();
  for (int i = 0; i < 3 && !_fw; i++) { _fw = _pn->getFirmwareVersion(); if (!_fw) delay(200); }
  if (!_fw) {
    LOG("ERROR", "PN532 gives no firmware version on 0x%02X: check S1=ON S2=OFF (I2C mode), VCC 3.3 V, GND, SDA GPIO %u, SCL GPIO %u",
        PN532_ADDR, PIN_NFC_SDA, PIN_NFC_SCL);
    return false;
  }
  _pn->SAMConfig();
  _ok = true;
  LOG("NFC", "PN532 detected: chip PN5%02X, firmware %u.%u", (unsigned)((_fw >> 24) & 0xFF),
      (unsigned)((_fw >> 16) & 0xFF), (unsigned)((_fw >> 8) & 0xFF));
  return true;
}

bool NFCManager::poll(NfcScan *out) {
  if (!_ok) return false;
  uint32_t now = millis();
  if (now - _lastPollMs < NFC_POLL_INTERVAL_MS) return false;
  _lastPollMs = now;
  uint8_t uid[10], len = 0;
  // Exactly the door's read (proven; read Breadboard 1-3 here at 02:20).
  if (!_pn->readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &len, NFC_READ_TIMEOUT_MS)) return false;
  now = millis();
  String hex;
  for (uint8_t i = 0; i < len; i++) { if (uid[i] < 0x10) hex += '0'; hex += String(uid[i], HEX); }
  hex.toUpperCase();
  // Still lying on the reader = the same scan. Lifted for NFC_DUPLICATE_MS = a new scan.
  if (hex == _lastUid && now - _lastUidMs < NFC_DUPLICATE_MS) { _lastUidMs = now; return false; }
  _lastUid = hex;
  _lastUidMs = now;
  out->uid = hex;
  out->uidLength = len;
  out->atMs = now;
  // Only what the reader reports: ISO14443A and the UID length. The exact
  // tag family (NTAG213, MIFARE ...) is not identified from this.
  LOG("NFC", "Tag UID %s (%u-byte UID, ISO14443A) at %lu ms", hex.c_str(), len, (unsigned long)now);
  return true;
}

void NFCManager::printStatus() {
  if (_ok) LOG("NFC", "PN532 OK, firmware %u.%u, last UID %s", (unsigned)((_fw >> 16) & 0xFF),
               (unsigned)((_fw >> 8) & 0xFF), _lastUid.length() ? _lastUid.c_str() : "-");
  else LOG("NFC", "PN532 NOT available");
}
