#include "LidSensorManager.h"
#include "config.h"
#include "Log.h"

const char *lidStateName(LidState s) {
  return s == LidState::LID_OPEN ? "LID OPEN" : s == LidState::LID_CLOSED ? "LID CLOSED" : "LID UNKNOWN";
}

void LidSensorManager::begin() {
  pinMode(PIN_REED, INPUT_PULLUP);       // reed between the pin and GND
  _fitted = true;
  _rawLevel = digitalRead(PIN_REED);
  _rawSince = millis();
  LOG("REED", "Reed on GPIO%u (pull-up; '%s' level = closed - VERIFY on the bin)", PIN_REED,
      REED_LEVEL_WHEN_CLOSED == LOW ? "LOW" : "HIGH");
}

void LidSensorManager::update() {
  if (!_fitted) return;
  int level = digitalRead(PIN_REED);
  uint32_t now = millis();
  if (level != _rawLevel) { _rawLevel = level; _rawSince = now; return; }
  if (now - _rawSince < REED_DEBOUNCE_MS) return;
  LidState s = level == REED_LEVEL_WHEN_CLOSED ? LidState::LID_CLOSED : LidState::LID_OPEN;
  if (s != _state) {
    _state = s;
    _changed = true;
    LOG("REED", "%s", lidStateName(s));
  }
}

bool LidSensorManager::takeChange(LidState *now) {
  if (!_changed) return false;
  _changed = false;
  if (now) *now = _state;
  return true;
}

void LidSensorManager::printStatus() {
  LOG("REED", "%s (pin level %s)", lidStateName(_state), _rawLevel == LOW ? "LOW" : _rawLevel == HIGH ? "HIGH" : "?");
}
