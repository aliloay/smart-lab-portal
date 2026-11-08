// MG90S pressing the bin's existing foot-pedal linkage.
//
// Safety rules (enforced here, whatever the caller does):
//   * no movement at boot - the servo is not even attached until a command;
//   * no torque when idle - after returning to SERVO_IDLE_ANGLE it detaches;
//   * the pedal is held at most SERVO_MAX_HOLD_MS, then released by itself;
//   * angles are clamped to SERVO_SAFE_MIN/MAX_ANGLE;
//   * a LOCKOUT (set after a lid fault) refuses every movement except the
//     release, until cleared - a failure can never cause repeated motion;
//   * the angles are not known: open() is refused until both are saved
//     ("servo set idle <n>" / "servo set open <n>"), except manual
//     test-mode moves ("servo angle <n>").
// Servo power comes from the external 5 V rail with a common GND - never
// from an ESP32 pin.
#pragma once
#include <Arduino.h>

enum class ServoState : uint8_t { SAFE_IDLE, MOVING_TO_OPEN, HOLDING_OPEN, RELEASING, MANUAL };
const char *servoStateName(ServoState s);

class ServoManager {
 public:
  void begin();                        // loads the saved angles; does NOT move
  void update();                       // call every loop()

  bool calibrated() const { return _idle >= 0 && _open >= 0; }
  int idleAngle() const { return _idle; }
  int openAngle() const { return _open; }
  void setIdleAngle(int a);
  void setOpenAngle(int a);

  bool open();                         // press the pedal (holds until release() / max hold)
  void release();                      // back to idle angle, then detach (always allowed)
  bool manualAngle(int a);             // test mode: move to any safe angle, stays attached
  void stop();                         // detach now (no torque) wherever it is

  ServoState state() const { return _state; }
  bool atOpen() const { return _state == ServoState::HOLDING_OPEN; }
  bool idle() const { return _state == ServoState::SAFE_IDLE; }
  void lockout(const char *why);
  void clearLockout();
  bool lockedOut() const { return _locked; }
  void printStatus();

 private:
  bool moveTo(int angle);
  int _idle = -1, _open = -1, _target = -1, _sweepAt = -1, _sweepTo = -1;
  uint32_t _lastStepMs = 0;
  ServoState _state = ServoState::SAFE_IDLE;
  uint32_t _since = 0;
  bool _locked = false;
};
