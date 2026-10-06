#include "RFIDManager.h"
#include "config.h"
#include "Log.h"

const char *rfidStatusName(RfidStatus s) {
  switch (s) {
    case RfidStatus::RFID_AVAILABLE:     return "RFID_AVAILABLE";
    case RfidStatus::RFID_ERROR:         return "RFID_ERROR";
    case RfidStatus::RFID_READING:       return "RFID_READING";
    case RfidStatus::RFID_NO_TAGS:       return "RFID_NO_TAGS";
    case RfidStatus::RFID_TAGS_DETECTED: return "RFID_TAGS_DETECTED";
    default:                             return "RFID_DISABLED";
  }
}

// The one place that knows which reader is fitted. With RFID_NONE: none.
static RfidReader *makeReader() {
#if RFID_READER_MODEL == RFID_NONE
  return nullptr;
#else
#error "RFID_READER_MODEL is set, but makeReader() has no class for it yet (see RFIDManager.h)"
#endif
}

void RFIDManager::begin() {
  _reader = makeReader();
  if (!_reader) {
    _status = RfidStatus::RFID_DISABLED;
    LOG("RFID", "Disabled / not configured (reader model unknown) - the bin works without it");
    return;
  }
  if (_reader->begin()) {
    _status = RfidStatus::RFID_AVAILABLE;
    LOG("RFID", "%s answered", _reader->name());
  } else {
    _status = RfidStatus::RFID_ERROR;
    LOG("ERROR", "RFID reader %s did not answer", _reader->name());
  }
}

bool RFIDManager::startInventory() {
  if (!_reader || _status == RfidStatus::RFID_ERROR || busy()) return false;
  _working.clear();
  _startMs = millis();
  _status = RfidStatus::RFID_READING;
  return true;
}

void RFIDManager::update() {
  if (!busy()) return;
  std::vector<String> ids;
  if (!_reader->readOnce(ids)) {
    _status = RfidStatus::RFID_ERROR;
    _lastValid = false;
    LOG("ERROR", "RFID read failed");
    return;
  }
  uint32_t now = millis();
  for (const String &id : ids) {
    if (_working.add(id)) LOG("RFID", "Tag %s first seen at +%lu ms", id.c_str(), (unsigned long)(now - _startMs));
  }
  if (now - _startMs < RFID_INVENTORY_WINDOW_MS) return;
  _last = _working;
  _lastValid = true;
  _status = _last.size() ? RfidStatus::RFID_TAGS_DETECTED : RfidStatus::RFID_NO_TAGS;
  LOG("RFID", "Inventory after %lu ms: %u tag(s) %s", (unsigned long)RFID_INVENTORY_WINDOW_MS,
      (unsigned)_last.size(), _last.toString().c_str());
}

void RFIDManager::printStatus() {
  LOG("RFID", "%s%s%s", rfidStatusName(_status), _reader ? " - " : "", _reader ? _reader->name() : "");
  if (_lastValid) LOG("RFID", "Last inventory: %s", _last.toString().c_str());
}
