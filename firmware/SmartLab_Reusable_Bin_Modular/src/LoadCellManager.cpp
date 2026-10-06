#include "LoadCellManager.h"
#include <Preferences.h>
#include "config.h"
#include "Log.h"

static_assert(WEIGHT_SAMPLE_COUNT >= 2 && WEIGHT_SAMPLE_COUNT <= 32, "WEIGHT_SAMPLE_COUNT 2..32");

const char *weightStateName(WeightState s) {
  switch (s) {
    case WeightState::STABLE_READING:  return "STABLE_READING";
    case WeightState::WEIGHT_INCREASE: return "WEIGHT_INCREASE";
    case WeightState::WEIGHT_DECREASE: return "WEIGHT_DECREASE";
    default:                           return "NO_STABLE_READING";
  }
}

bool LoadCellManager::begin() {
  LOG("LOADCELL", "Initializing HX711 (DT=GPIO%u, SCK=GPIO%u)...", PIN_HX711_DT, PIN_HX711_SCK);
  // No reset in begin(): the library's reset ends in a read() that waits
  // FOREVER for the HX711 - with none connected the board would hang here
  // (seen on the bare ESP32, 2026-10-07). Reset only once it has answered.
  // fastProcessor = true: the library stretches each clock pulse by 1 us.
  // At the ESP32's speed the bare pulses are too short for the HX711 and the
  // bits come out wrong (seen: wandering values, then 0x400000 / -1 frozen).
  _hx.begin(PIN_HX711_DT, PIN_HX711_SCK, true, false);
  // With nothing connected, DT would float and read as random "samples".
  // Pulled up, a missing HX711 simply never reports ready.
  pinMode(PIN_HX711_DT, INPUT_PULLUP);
  load();
  _available = _hx.wait_ready_timeout(HX711_READY_TIMEOUT_MS, 5);
  if (_available) {
    _hx.reset();                          // safe now: a sample is ready
    _hx.set_gain(_gain == 64 ? HX711_CHANNEL_A_GAIN_64 : HX711_CHANNEL_A_GAIN_128, true);
  }
  if (!_available) {
    LOG("ERROR", "HX711 not responding (DT never went LOW in %lu ms): check VCC, GND, DT, SCK",
        (unsigned long)HX711_READY_TIMEOUT_MS);
    return false;
  }
  _lastSampleMs = millis();
  LOG("LOADCELL", "OK - HX711 answering (gain %u)", _gain);
  if (calibrated()) LOG("LOADCELL", "Calibration loaded: offset %ld, factor %.4f counts/g",
                        (long)_offset, _factor);
  else LOG("LOADCELL", "NOT calibrated: raw counts only (run: tare, then cal <grams>)");
  return true;
}

void LoadCellManager::update() {
  uint32_t now = millis();
  if (!_hx.is_ready()) {
    if (_available && now - _lastSampleMs > HX711_READY_TIMEOUT_MS) {
      _available = false;
      _stable = false;
      _state = WeightState::NO_STABLE_READING;
      LOG("ERROR", "HX711 stopped answering");
    }
    return;
  }
  float v = _hx.read();                       // ready: returns at once
  if (!_available) LOG("LOADCELL", "HX711 answering again");
  _available = true;
  _lastSampleMs = now;
  _window[_i] = v;
  _i = (_i + 1) % WEIGHT_SAMPLE_COUNT;
  if (_n < WEIGHT_SAMPLE_COUNT) _n++;
  float sum = 0;
  for (uint8_t k = 0; k < _n; k++) sum += _window[k];
  _raw = sum / _n;

  if (!calibrated() || _n < WEIGHT_SAMPLE_COUNT) { _stable = false; _state = WeightState::NO_STABLE_READING; return; }
  bool calm = spreadGrams() <= WEIGHT_STABILITY_THRESHOLD_G;
  if (!calm) { _calmSinceMs = 0; _stable = false; _state = WeightState::NO_STABLE_READING; return; }
  if (_calmSinceMs == 0) _calmSinceMs = now;
  if (now - _calmSinceMs < WEIGHT_STABLE_TIME_MS) return;
  if (!_stable) {
    _stable = true;
    float g = grams();
    if (!isnan(_lastStableG) && fabsf(g - _lastStableG) >= WEIGHT_CHANGE_THRESHOLD_G) {
      _changeKind = g > _lastStableG ? WeightState::WEIGHT_INCREASE : WeightState::WEIGHT_DECREASE;
      _changeDelta = g - _lastStableG;
      _changePending = true;
      _state = _changeKind;
      LOG("LOADCELL", "%s %+.1f g (now %.1f g)", weightStateName(_changeKind), _changeDelta, g);
    } else {
      _state = WeightState::STABLE_READING;
    }
    if (isnan(_lastStableG) || fabsf(g - _lastStableG) >= WEIGHT_CHANGE_THRESHOLD_G) _lastStableG = g;
  }
}

float LoadCellManager::grams() const {
  if (!calibrated() || isnan(_raw)) return NAN;
  return (_raw - (float)_offset) / _factor;
}

float LoadCellManager::spreadGrams() const {
  if (!calibrated() || _n == 0) return NAN;
  float lo = _window[0], hi = _window[0];
  for (uint8_t k = 1; k < _n; k++) { lo = min(lo, _window[k]); hi = max(hi, _window[k]); }
  return fabsf((hi - lo) / _factor);
}

bool LoadCellManager::takeChange(WeightState *kind, float *deltaG) {
  if (!_changePending) return false;
  _changePending = false;
  if (kind) *kind = _changeKind;
  if (deltaG) *deltaG = _changeDelta;
  return true;
}

bool LoadCellManager::averageNow(uint8_t n, float *out) {
  double sum = 0;
  for (uint8_t k = 0; k < n; k++) {
    if (!_hx.wait_ready_timeout(HX711_READY_TIMEOUT_MS, 2)) return false;
    sum += _hx.read();
    _lastSampleMs = millis();          // busy reading, not silent: no "stopped answering" alarm
  }
  *out = (float)(sum / n);
  return true;
}

bool LoadCellManager::tare() {
  float avg;
  if (!averageNow(20, &avg)) { LOG("ERROR", "Tare failed: HX711 not answering"); return false; }
  _offset = (int32_t)lroundf(avg);
  _n = 0; _stable = false; _lastStableG = NAN; _calmSinceMs = 0;
  save();
  LOG("LOADCELL", "Tare done: zero offset %ld counts (saved)", (long)_offset);
  return true;
}

bool LoadCellManager::calibrate(float knownGrams) {
  if (knownGrams <= 0) { LOG("ERROR", "cal needs the reference mass in grams, e.g. cal 500"); return false; }
  float avg;
  if (!averageNow(20, &avg)) { LOG("ERROR", "Calibration failed: HX711 not answering"); return false; }
  float counts = avg - (float)_offset;
  if (fabsf(counts) < 50) {
    LOG("ERROR", "Only %.0f counts above zero: is the mass on the platform, and was 'tare' run empty?", counts);
    return false;
  }
  _factor = counts / knownGrams;
  _n = 0; _stable = false; _lastStableG = NAN; _calmSinceMs = 0;
  save();
  LOG("LOADCELL", "Calibrated with %.1f g: %.0f counts -> factor %.4f counts/g (saved)",
      knownGrams, counts, _factor);
  return true;
}

void LoadCellManager::clearCalibration() {
  _offset = 0; _factor = 0; save();
  LOG("LOADCELL", "Calibration cleared");
}

void LoadCellManager::printStatus() {
  LOG("LOADCELL", "HX711 %s | raw %s | offset %ld | factor %s | weight %s (%.3f kg) | spread %s | %s",
      _available ? "OK" : "NOT RESPONDING",
      isnan(_raw) ? "n/a" : String(_raw, 0).c_str(), (long)_offset,
      calibrated() ? String(_factor, 4).c_str() : "not calibrated",
      fmtGrams(grams()).c_str(), isnan(kilograms()) ? 0.0f : kilograms(),
      fmtGrams(spreadGrams()).c_str(), weightStateName(_state));
}

void LoadCellManager::save() {
  Preferences p;
  if (!p.begin("reusebin", false)) return;
  p.putInt("lc_off", _offset);
  p.putFloat("lc_fac", _factor);
  p.putUChar("lc_gain", _gain);
  p.end();
}

void LoadCellManager::load() {
  Preferences p;
  if (!p.begin("reusebin", true)) return;
  _offset = p.getInt("lc_off", 0);
  _factor = p.getFloat("lc_fac", 0.0f);
  _gain = p.getUChar("lc_gain", LOAD_CELL_GAIN_DEFAULT);
  if (_gain != 64 && _gain != 128) _gain = LOAD_CELL_GAIN_DEFAULT;
  p.end();
}

bool LoadCellManager::setGain(uint8_t g) {
  if (g != 64 && g != 128) { LOG("ERROR", "gain must be 64 or 128"); return false; }
  _gain = g;
  // "forced" applies it with a read that waits for the HX711: only if it answers.
  _hx.set_gain(g == 64 ? HX711_CHANNEL_A_GAIN_64 : HX711_CHANNEL_A_GAIN_128, _available && _hx.is_ready());
  _n = 0; _stable = false; _calmSinceMs = 0; _lastStableG = NAN;
  bool hadCal = calibrated();
  _factor = 0.0f;                      // counts per gram change with the gain
  save();
  LOG("LOADCELL", "Gain %u set (saved)%s", g, hadCal ? " - calibration cleared: run tare + cal again" : "");
  return true;
}

void LoadCellManager::hxReset() {
  _hx.power_down();                    // PD_SCK HIGH > 60 us
  delay(2);
  _hx.power_up();
  _hx.set_gain(_gain == 64 ? HX711_CHANNEL_A_GAIN_64 : HX711_CHANNEL_A_GAIN_128, false);
  _n = 0; _stable = false; _calmSinceMs = 0;
  _lastSampleMs = millis();
  LOG("LOADCELL", "HX711 power-cycled (PD_SCK high 2 ms, then low)");
}

void LoadCellManager::rawLog(uint8_t n) {
  LOG("LOADCELL", "rawlog: %u single readings (no averaging)", n);
  uint32_t t0 = millis();
  for (uint8_t i = 0; i < n; i++) {
    uint32_t w0 = millis();
    if (!_hx.wait_ready_timeout(HX711_READY_TIMEOUT_MS, 1)) {
      LOG("LOADCELL", "  #%02u +%5lu ms  NOT READY within %lu ms", i, (unsigned long)(millis() - t0),
          (unsigned long)HX711_READY_TIMEOUT_MS);
      continue;
    }
    uint32_t waited = millis() - w0;
    float v = _hx.read();
    _lastSampleMs = millis();
    LOG("LOADCELL", "  #%02u +%5lu ms  waited %3lu ms  raw %10.0f  (0x%06lX)", i, (unsigned long)(millis() - t0),
        (unsigned long)waited, v, (unsigned long)((int32_t)v & 0xFFFFFF));
  }
}
