// Every fault the bin can detect, as flags. Component faults are set at
// start-up / when a part stops answering; lid faults also lock the servo
// out so a failure can never cause repeated movement.
#pragma once
#include <Arduino.h>

enum Fault : uint32_t {
  FAULT_NONE               = 0,
  FAULT_HX711_UNAVAILABLE  = 1u << 0,
  FAULT_LCD_UNAVAILABLE    = 1u << 1,
  FAULT_PN532_UNAVAILABLE  = 1u << 2,
  FAULT_RFID_ERROR         = 1u << 3,   // only when a reader is configured
  FAULT_WIFI_DOWN          = 1u << 4,
  FAULT_BACKEND_DOWN       = 1u << 5,
  FAULT_LID_OPEN_TIMEOUT   = 1u << 6,   // pressed, reed never showed OPEN
  FAULT_LID_CLOSE_TIMEOUT  = 1u << 7,   // released, reed never showed CLOSED
  FAULT_SERVO_NOT_SET      = 1u << 8,   // angles not saved yet
  FAULT_REED_UNKNOWN       = 1u << 9,   // lid state not known at start
  FAULT_SCALE_NOT_CALIBRATED = 1u << 10,
};

class FaultManager {
 public:
  void set(Fault f, const char *detail = nullptr);
  void clear(Fault f);
  bool has(Fault f) const { return _flags & f; }
  uint32_t flags() const { return _flags; }
  // Faults that stop a lid cycle (the rest only degrade it).
  bool blocksLid() const;
  String describe() const;              // "LID_OPEN_TIMEOUT, WIFI_DOWN" or "none"
  const char *firstName() const;
 private:
  uint32_t _flags = 0;
};

const char *faultName(Fault f);
