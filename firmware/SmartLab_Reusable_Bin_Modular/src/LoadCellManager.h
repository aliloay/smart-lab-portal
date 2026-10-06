// Load cell + HX711 under the reusable bin (this bin only - the consumable
// bin has its own). Non-blocking: update() takes a sample only when the
// HX711 has one ready.
//
//   raw        latest averaged ADC counts (always available while the HX711 answers)
//   grams      (raw - zero offset) / factor   - NAN until calibrated
//   state      NO_STABLE_READING / STABLE_READING, plus a one-shot
//              WEIGHT_INCREASE / WEIGHT_DECREASE when a new stable mass
//              differs from the previous one by >= WEIGHT_CHANGE_THRESHOLD_G
//
// Calibration (saved in flash, never assumed): tare, then cal <grams> with
// a reference mass weighed on a trusted scale.
#pragma once
#include <Arduino.h>
#include <HX711.h>
#include "config.h"

enum class WeightState : uint8_t { NO_STABLE_READING, STABLE_READING, WEIGHT_INCREASE, WEIGHT_DECREASE };
const char *weightStateName(WeightState s);

class LoadCellManager {
 public:
  bool begin();
  void update();                       // call every loop()

  bool available() const { return _available; }
  bool calibrated() const { return _factor != 0.0f; }
  float raw() const { return _raw; }                       // averaged counts, NAN if none yet
  float grams() const;                                     // NAN if not calibrated / no data
  float kilograms() const { float g = grams(); return isnan(g) ? NAN : g / 1000.0f; }
  bool stable() const { return _stable; }
  float stableGrams() const { return _stable ? grams() : NAN; }
  float spreadGrams() const;                               // window spread (calibrated only)
  WeightState state() const { return _state; }
  // The last change event (one-shot): returns true once per change.
  bool takeChange(WeightState *kind, float *deltaG);

  // Calibration
  bool tare();                         // current load = zero (blocking ~1 s)
  bool calibrate(float knownGrams);    // a known mass is on it now (blocking ~1 s)
  int32_t offset() const { return _offset; }
  float factor() const { return _factor; }
  void clearCalibration();
  void printStatus();
  void hxReset();                      // power-cycle the HX711 through PD_SCK
  bool setGain(uint8_t gain);          // 128 or 64 (channel A); clears the calibration
  uint8_t gain() const { return _gain; }
  void rawLog(uint8_t n);              // n single readings, each with its wait time (blocking)

 private:
  bool averageNow(uint8_t n, float *out);   // blocking helper for tare / cal only
  void save();
  void load();

  HX711 _hx;
  bool _available = false;
  int32_t _offset = 0;
  float _factor = 0.0f;
  uint8_t _gain = LOAD_CELL_GAIN_DEFAULT;
  float _window[32];
  uint8_t _n = 0, _i = 0;
  float _raw = NAN;
  uint32_t _lastSampleMs = 0;
  bool _stable = false;
  uint32_t _calmSinceMs = 0;
  float _lastStableG = NAN;
  WeightState _state = WeightState::NO_STABLE_READING;
  bool _changePending = false;
  WeightState _changeKind = WeightState::NO_STABLE_READING;
  float _changeDelta = 0;
};
