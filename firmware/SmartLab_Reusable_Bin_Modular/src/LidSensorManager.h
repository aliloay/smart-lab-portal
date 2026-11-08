// Reed switch on the lid: LID_UNKNOWN until the first debounced reading
// (or when the reed is not fitted), then LID_OPEN / LID_CLOSED. A servo
// command never counts as "the lid opened" - only this sensor does.
#pragma once
#include <Arduino.h>

enum class LidState : uint8_t { LID_UNKNOWN, LID_OPEN, LID_CLOSED };
const char *lidStateName(LidState s);

class LidSensorManager {
 public:
  void begin();
  void update();                          // call every loop()
  LidState state() const { return _state; }
  bool fitted() const { return _fitted; }
  // Returns true once per change (for logging / events).
  bool takeChange(LidState *now);
  void printStatus();

 private:
  bool _fitted = false, _changed = false;
  int _rawLevel = -1;
  uint32_t _rawSince = 0;
  LidState _state = LidState::LID_UNKNOWN;
};
