#include "FaultManager.h"
#include "Log.h"

static const Fault ALL[] = {
  FAULT_HX711_UNAVAILABLE, FAULT_LCD_UNAVAILABLE, FAULT_PN532_UNAVAILABLE, FAULT_RFID_ERROR,
  FAULT_WIFI_DOWN, FAULT_BACKEND_DOWN, FAULT_LID_OPEN_TIMEOUT, FAULT_LID_CLOSE_TIMEOUT,
  FAULT_SERVO_NOT_SET, FAULT_REED_UNKNOWN, FAULT_SCALE_NOT_CALIBRATED,
};

const char *faultName(Fault f) {
  switch (f) {
    case FAULT_HX711_UNAVAILABLE: return "HX711_UNAVAILABLE";
    case FAULT_LCD_UNAVAILABLE:   return "LCD_UNAVAILABLE";
    case FAULT_PN532_UNAVAILABLE: return "PN532_UNAVAILABLE";
    case FAULT_RFID_ERROR:        return "RFID_ERROR";
    case FAULT_WIFI_DOWN:         return "WIFI_DOWN";
    case FAULT_BACKEND_DOWN:      return "BACKEND_DOWN";
    case FAULT_LID_OPEN_TIMEOUT:  return "LID_POSITION_TIMEOUT_OPEN";
    case FAULT_LID_CLOSE_TIMEOUT: return "LID_POSITION_TIMEOUT_CLOSE";
    case FAULT_SERVO_NOT_SET:     return "SERVO_ANGLES_NOT_SET";
    case FAULT_REED_UNKNOWN:      return "LID_STATE_UNKNOWN";
    case FAULT_SCALE_NOT_CALIBRATED: return "SCALE_NOT_CALIBRATED";
    default:                      return "NONE";
  }
}

void FaultManager::set(Fault f, const char *detail) {
  if (_flags & f) return;
  _flags |= f;
  LOG("ERROR", "FAULT %s%s%s", faultName(f), detail ? ": " : "", detail ? detail : "");
}

void FaultManager::clear(Fault f) {
  if (!(_flags & f)) return;
  _flags &= ~f;
  LOG("SYSTEM", "Cleared %s", faultName(f));
}

bool FaultManager::blocksLid() const {
  return _flags & (FAULT_LID_OPEN_TIMEOUT | FAULT_LID_CLOSE_TIMEOUT | FAULT_SERVO_NOT_SET | FAULT_REED_UNKNOWN);
}

String FaultManager::describe() const {
  String s;
  for (Fault f : ALL) if (_flags & f) { if (s.length()) s += ", "; s += faultName(f); }
  return s.length() ? s : String("none");
}

const char *FaultManager::firstName() const {
  for (Fault f : ALL) if (_flags & f) return faultName(f);
  return "NONE";
}
