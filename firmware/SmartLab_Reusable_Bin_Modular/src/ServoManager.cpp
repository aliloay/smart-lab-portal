#include "ServoManager.h"
#include <ESP32Servo.h>
#include <Preferences.h>
#include "config.h"
#include "Log.h"

static Servo g_servo;

const char *servoStateName(ServoState s) {
  switch (s) {
    case ServoState::MOVING_TO_OPEN: return "MOVING_TO_OPEN";
    case ServoState::HOLDING_OPEN:   return "HOLDING_OPEN";
    case ServoState::RELEASING:      return "RELEASING";
    case ServoState::MANUAL:         return "MANUAL";
    default:                         return "SAFE_IDLE";
  }
}

void ServoManager::begin() {
  Preferences p;
  if (p.begin("reusebin", true)) {
    _idle = p.getInt("sv_idle", -1);
    _open = p.getInt("sv_open", -1);
    p.end();
  }
  LOG("SERVO", "Ready on GPIO%u, NOT attached (no movement at boot)", PIN_SERVO);
  if (calibrated()) LOG("SERVO", "Saved angles: idle %d, open %d", _idle, _open);
  else LOG("SERVO", "Angles NOT set yet - lid opening refused until: servo set idle <n> / servo set open <n>");
}

bool ServoManager::moveTo(int angle) {
  angle = constrain(angle, SERVO_SAFE_MIN_ANGLE, SERVO_SAFE_MAX_ANGLE);
  if (!g_servo.attached()) {
    g_servo.attach(PIN_SERVO, SERVO_PULSE_MIN_US, SERVO_PULSE_MAX_US);   // returns a channel number (0 is valid)
    if (!g_servo.attached()) {
      LOG("ERROR", "Servo attach failed on GPIO%u", PIN_SERVO);
      return false;
    }
  }
  g_servo.write(angle);
  _target = angle;
  _since = millis();
  return true;
}

bool ServoManager::open() {
  if (_locked) { LOG("SERVO", "Refused: LOCKED OUT after a fault (servo clear to unlock)"); return false; }
  if (!calibrated()) { LOG("SERVO", "Refused: angles not set"); return false; }
  if (_state != ServoState::SAFE_IDLE) { LOG("SERVO", "Refused: busy (%s)", servoStateName(_state)); return false; }
  if (!moveTo(_open)) return false;
  _state = ServoState::MOVING_TO_OPEN;
  LOG("SERVO", "Pressing the pedal -> %d deg", _open);
  return true;
}

void ServoManager::release() {
  if (_state == ServoState::SAFE_IDLE) return;
  int to = _idle >= 0 ? _idle : _target;       // no idle angle saved: stay put, then detach
  moveTo(to);
  _state = ServoState::RELEASING;
  LOG("SERVO", "Releasing -> %d deg", to);
}

bool ServoManager::manualAngle(int a) {
  if (_locked) { LOG("SERVO", "Refused: LOCKED OUT (servo clear)"); return false; }
  if (a < SERVO_SAFE_MIN_ANGLE || a > SERVO_SAFE_MAX_ANGLE) {
    LOG("SERVO", "Refused: %d is outside %d..%d", a, SERVO_SAFE_MIN_ANGLE, SERVO_SAFE_MAX_ANGLE);
    return false;
  }
  if (!moveTo(a)) return false;
  _state = ServoState::MANUAL;
  LOG("SERVO", "Manual -> %d deg (holding; 'servo stop' removes torque)", a);
  return true;
}

void ServoManager::stop() {
  if (g_servo.attached()) g_servo.detach();
  _state = ServoState::SAFE_IDLE;
  LOG("SERVO", "Stopped and detached (no torque)");
}

void ServoManager::update() {
  uint32_t el = millis() - _since;
  switch (_state) {
    case ServoState::MOVING_TO_OPEN:
      if (el >= SERVO_MOVE_MS) { _state = ServoState::HOLDING_OPEN; _since = millis(); }
      break;
    case ServoState::HOLDING_OPEN:
      if (el >= SERVO_MAX_HOLD_MS) { LOG("SERVO", "Max hold %lu ms reached - releasing", (unsigned long)SERVO_MAX_HOLD_MS); release(); }
      break;
    case ServoState::RELEASING:
      if (el >= SERVO_MOVE_MS) {
        if (g_servo.attached()) g_servo.detach();     // no holding torque at rest
        _state = ServoState::SAFE_IDLE;
        LOG("SERVO", "At rest, detached");
      }
      break;
    case ServoState::MANUAL:
      if (el >= SERVO_MAX_HOLD_MS) { LOG("SERVO", "Manual hold timeout - detaching"); stop(); }
      break;
    default: break;
  }
}

void ServoManager::setIdleAngle(int a) {
  _idle = constrain(a, SERVO_SAFE_MIN_ANGLE, SERVO_SAFE_MAX_ANGLE);
  Preferences p; if (p.begin("reusebin", false)) { p.putInt("sv_idle", _idle); p.end(); }
  LOG("SERVO", "Idle angle saved: %d", _idle);
}

void ServoManager::setOpenAngle(int a) {
  _open = constrain(a, SERVO_SAFE_MIN_ANGLE, SERVO_SAFE_MAX_ANGLE);
  Preferences p; if (p.begin("reusebin", false)) { p.putInt("sv_open", _open); p.end(); }
  LOG("SERVO", "Open (pedal pressed) angle saved: %d", _open);
}

void ServoManager::lockout(const char *why) {
  _locked = true;
  LOG("ERROR", "Servo LOCKED OUT: %s", why);
}

void ServoManager::clearLockout() {
  _locked = false;
  LOG("SERVO", "Lockout cleared");
}

void ServoManager::printStatus() {
  LOG("SERVO", "%s | %s | idle %d, open %d%s | target %d", servoStateName(_state),
      g_servo.attached() ? "attached" : "detached", _idle, _open,
      calibrated() ? "" : " (NOT SET)", _target);
  if (_locked) LOG("SERVO", "LOCKED OUT");
}
