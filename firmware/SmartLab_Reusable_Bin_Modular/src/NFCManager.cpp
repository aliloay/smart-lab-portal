#include "NFCManager.h"
#include <Wire.h>
#include <Adafruit_PN532.h>
#include "config.h"
#include "DisplayManager.h"
#include "Log.h"

static constexpr uint8_t NO_PIN = 255;   // IRQ and RESET not wired (as on the door)

bool NFCManager::begin() {
  LOG("NFC", "Looking for the PN532 on I2C 0x%02X...", PN532_ADDR);
  if (!i2cPresent(PN532_ADDR)) {
    LOG("ERROR", "PN532 not found at 0x%02X: check S1=ON S2=OFF (I2C mode), VCC, GND, SDA, SCL",
        PN532_ADDR);
    return false;
  }
  _pn = new Adafruit_PN532(NO_PIN, NO_PIN, &Wire);
  _pn->begin();
  _fw = _pn->getFirmwareVersion();
  if (!_fw) {
    LOG("ERROR", "A device answers at 0x%02X but gives no PN532 firmware version", PN532_ADDR);
    return false;
  }
  _pn->SAMConfig();
  _pn->setPassiveActivationRetries(0x01);     // one try per look: the loop stays responsive
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
  if (!_pn->readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &len, NFC_READ_TIMEOUT_MS)) return false;
  String hex;
  for (uint8_t i = 0; i < len; i++) { if (uid[i] < 0x10) hex += '0'; hex += String(uid[i], HEX); }
  hex.toUpperCase();
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
