// ===========================================================================
// SENSORS - acquisition, filtering, debounce, events and health.
// Runs in loop() (core 1) only. Nothing here touches the network, and no
// call blocks for long: the DHT22 read is ~5 ms, once every 2.5 s.
// A sensor that fails only marks ITSELF as failed - the others carry on.
// ===========================================================================
#pragma once
#include <DHT.h>
#include <Preferences.h>

// ------------------------------------------------------------------ health ---
enum Health : uint8_t {
  H_NOT_FITTED, H_STARTING, H_WARMING_UP, H_BASELINE, H_ONLINE, H_READY, H_ERROR, H_FAULT
};
const char *healthName(Health h) {
  switch (h) {
    case H_NOT_FITTED: return "NOT_FITTED";
    case H_STARTING:   return "STARTING";
    case H_WARMING_UP: return "WARMING_UP";
    case H_BASELINE:   return "BASELINE";
    case H_ONLINE:     return "ONLINE";
    case H_READY:      return "READY";
    case H_ERROR:      return "ERROR";
    case H_FAULT:      return "FAULT";
  }
  return "?";
}

// ---------------------------------------------------- which sensors are wired ---
// Defaults come from env_config.h; "fit <sensor> on|off" changes them at run time
// and keeps them in flash (NVS), so bring-up needs no re-flash per sensor.
struct Fitted { bool dht, pir1, pir2, mq, mqDo, flame[5]; } fit;

void fitLoad() {
  Preferences p;
  p.begin("envfit", false);
  fit.dht  = p.getBool("dht",  DEFAULT_FIT_DHT);
  fit.pir1 = p.getBool("pir1", DEFAULT_FIT_PIR1);
  fit.pir2 = p.getBool("pir2", DEFAULT_FIT_PIR2);
  fit.mq   = p.getBool("mq",   DEFAULT_FIT_MQ);
  fit.mqDo = p.getBool("mqdo", DEFAULT_FIT_MQ_DO);
  char k[3] = "f1";
  for (int i = 0; i < 5; i++) { k[1] = '1' + i; fit.flame[i] = p.getBool(k, DEFAULT_FIT_FLAME); }
  p.end();
}

void fitSave() {
  Preferences p;
  p.begin("envfit", false);
  p.putBool("dht", fit.dht);   p.putBool("pir1", fit.pir1); p.putBool("pir2", fit.pir2);
  p.putBool("mq", fit.mq);     p.putBool("mqdo", fit.mqDo);
  char k[3] = "f1";
  for (int i = 0; i < 5; i++) { k[1] = '1' + i; p.putBool(k, fit.flame[i]); }
  p.end();
}

uint32_t bootMs = 0;

// ==================================================================== DHT22 ===
DHT dht(PIN_DHT, DHT22);

struct DhtState {
  Health   health = H_NOT_FITTED;
  float    tempC = NAN, humPct = NAN;     // last VALID reading - never made up
  uint32_t validAtMs = 0, lastTryMs = 0;
  uint8_t  failStreak = 0;
  uint32_t reads = 0, fails = 0;
  bool     tempHigh = false, humHigh = false;
} dhtS;

bool dhtValid(uint32_t now) {
  return fit.dht && dhtS.validAtMs != 0 && now - dhtS.validAtMs < DHT_STALE_MS;
}

void dhtBegin(uint32_t now) {
  dhtS = DhtState();
  if (!fit.dht) return;
  dht.begin();
  dhtS.health = H_STARTING;
  dhtS.lastTryMs = now;           // first read one interval after power-up
}

void dhtUpdate(uint32_t now, bool force = false) {
  if (!fit.dht || (!force && now - dhtS.lastTryMs < DHT_INTERVAL_MS)) return;
  dhtS.lastTryMs = now;
  bool  ok = dht.read(true);
  float t  = ok ? dht.readTemperature() : NAN;
  float h  = ok ? dht.readHumidity() : NAN;
  bool  valid = ok && !isnan(t) && !isnan(h) && t >= DHT_MIN_C && t <= DHT_MAX_C &&
                h >= 0.0f && h <= 100.0f;
  dhtS.reads++;
  if (!valid) {
    dhtS.fails++;
    Serial.printf("CSV,dht_fail,%lu\n", (unsigned long)now);
    if (dhtS.failStreak < 255) dhtS.failStreak++;
    if (dhtS.failStreak >= DHT_FAIL_LIMIT && dhtS.health != H_ERROR) {
      dhtS.health = H_ERROR;
      emitEvent(EV_SENSOR_FAILURE, "dht22", dhtS.failStreak);
    }
    return;                      // the last valid values stay, with their age
  }
  Serial.printf("CSV,dht,%lu,%.2f,%.2f\n", (unsigned long)now, t, h);
  if (dhtS.health == H_ERROR) emitEvent(EV_SENSOR_RECOVERED, "dht22");
  dhtS.health = H_ONLINE;
  dhtS.failStreak = 0;
  dhtS.tempC = t;
  dhtS.humPct = h;
  dhtS.validAtMs = now;

  if (!dhtS.tempHigh && t >= TEMP_HIGH_C)        { dhtS.tempHigh = true;  emitEvent(EV_TEMPERATURE_HIGH, "dht22", t); }
  else if (dhtS.tempHigh && t <= TEMP_NORMAL_C)  { dhtS.tempHigh = false; emitEvent(EV_TEMPERATURE_NORMAL, "dht22", t); }
  if (!dhtS.humHigh && h >= HUM_HIGH_PCT)        { dhtS.humHigh = true;   emitEvent(EV_HUMIDITY_HIGH, "dht22", h); }
  else if (dhtS.humHigh && h <= HUM_NORMAL_PCT)  { dhtS.humHigh = false;  emitEvent(EV_HUMIDITY_NORMAL, "dht22", h); }
}

// ====================================================================== PIR ===
struct Pir {
  const char *name;
  uint8_t     pin;
  bool       *fitted;
  Health      health;
  bool        raw, stable, motion;
  uint32_t    rawChangedMs, lastActiveMs, warmStartMs, triggers;
};
Pir pirs[2] = {
  {"pir_1", PIN_PIR1, &fit.pir1, H_NOT_FITTED, false, false, false, 0, 0, 0, 0},
  {"pir_2", PIN_PIR2, &fit.pir2, H_NOT_FITTED, false, false, false, 0, 0, 0, 0},
};

void pirBegin(Pir &p, uint32_t now) {
  p.health = H_NOT_FITTED;
  p.raw = p.stable = p.motion = false;
  p.rawChangedMs = p.lastActiveMs = p.triggers = 0;
  p.warmStartMs = now;
  if (!*p.fitted) return;
  // OUT is driven by the module; the pull-down only makes a loose wire read
  // "no motion" instead of floating.
  pinMode(p.pin, INPUT_PULLDOWN);
  p.health = H_WARMING_UP;
}

bool motionAny() {
  return (pirs[0].health == H_ONLINE && pirs[0].motion) ||
         (pirs[1].health == H_ONLINE && pirs[1].motion);
}

void pirUpdate(uint32_t now) {
  for (Pir &p : pirs) {
    if (!*p.fitted) continue;
    bool raw = digitalRead(p.pin) == PIR_ACTIVE_LEVEL;
    if (raw != p.raw) { p.raw = raw; p.rawChangedMs = now; }
    if (p.stable != p.raw && now - p.rawChangedMs >= PIR_DEBOUNCE_MS) p.stable = p.raw;
    if (p.stable) p.lastActiveMs = now;

    if (p.health == H_WARMING_UP) {
      if (now - p.warmStartMs < PIR_WARMUP_MS) continue;     // not trusted yet
      p.lastActiveMs = p.stable ? now : 0;   // movement during warm-up does not count
      p.health = H_ONLINE;
      emitEvent(EV_SENSOR_READY, p.name);
      p.motion = false;              // fall through: motion present now is reported
    }
    bool motion = p.stable || (p.lastActiveMs != 0 && now - p.lastActiveMs < PIR_HOLD_MS);
    if (motion == p.motion) continue;
    p.motion = motion;                              // a change: one event, not a stream
    if (motion) p.triggers++;
    Serial.printf("CSV,state,%lu,%s,%d\n", (unsigned long)now, p.name, motion ? 1 : 0);
    emitEvent(motion ? EV_MOTION_STARTED : EV_MOTION_STOPPED, p.name);
  }
}

// ==================================================================== FLAME ===
// A real flame flickers, so the comparator output pulses while it burns. A
// channel is CONFIRMED when at least FLAME_CONFIRM_PCT % of the samples in
// the last FLAME_WINDOW_MS saw IR - a single glitch cannot do that - and
// CLEARED only after FLAME_CLEAR_MS without a single IR sample.
constexpr uint8_t FLAME_WINDOW_SAMPLES = FLAME_WINDOW_MS / FLAME_SAMPLE_INTERVAL_MS;
static_assert(FLAME_WINDOW_SAMPLES >= 1 && FLAME_WINDOW_SAMPLES <= 64,
              "FLAME_WINDOW_MS / FLAME_SAMPLE_INTERVAL_MS must be 1..64");
constexpr uint8_t  FLAME_CONFIRM_HITS = (FLAME_WINDOW_SAMPLES * FLAME_CONFIRM_PCT + 99) / 100;
constexpr uint64_t FLAME_WINDOW_MASK  =
    FLAME_WINDOW_SAMPLES >= 64 ? ~0ULL : ((1ULL << FLAME_WINDOW_SAMPLES) - 1);

struct FlameCh {
  bool     raw;         // this sample saw IR
  uint16_t analog;      // analog channels: last reading, mV at the pin
  uint64_t history;     // one bit per sample, newest in bit 0
  bool     flame;       // confirmed
  uint32_t lastHitMs, detections;
};
FlameCh  flames[5];
uint32_t lastFlameSampleMs = 0;

uint8_t flamePin(int i) { return PIN_FLAME[i]; }
bool    flameAnyFitted() { for (int i = 0; i < 5; i++) if (fit.flame[i]) return true; return false; }
bool    flameAny() { for (int i = 0; i < 5; i++) if (fit.flame[i] && flames[i].flame) return true; return false; }

void flameBegin(int i) {
  flames[i] = FlameCh();
  if (!fit.flame[i]) return;
  if (FLAME_IS_ANALOG[i]) analogSetPinAttenuation(flamePin(i), ADC_11db);
  // A loose wire then reads "no flame" instead of floating (fail quiet;
  // the self-test and the 'flame' test are what prove a channel works).
  else pinMode(flamePin(i), FLAME_ACTIVE_LEVEL == LOW ? INPUT_PULLUP : INPUT_PULLDOWN);
}

bool flameSample(int i) {
  if (FLAME_IS_ANALOG[i]) {
    flames[i].analog = analogReadMilliVolts(flamePin(i));
    return flames[i].analog > FLAME_ANALOG_THRESHOLD_MV;
  }
  return digitalRead(flamePin(i)) == FLAME_ACTIVE_LEVEL;
}

void flameUpdate(uint32_t now) {
  if (now - lastFlameSampleMs < FLAME_SAMPLE_INTERVAL_MS) return;
  lastFlameSampleMs = now;
  for (int i = 0; i < 5; i++) {
    if (!fit.flame[i]) continue;
    FlameCh &f = flames[i];
    f.raw = flameSample(i);
    f.history = ((f.history << 1) | (f.raw ? 1ULL : 0ULL)) & FLAME_WINDOW_MASK;
    if (f.raw) f.lastHitMs = now;
    uint8_t hits = __builtin_popcountll(f.history);
    char name[10];
    snprintf(name, sizeof(name), "flame_%d", i + 1);
    if (!f.flame && hits >= FLAME_CONFIRM_HITS) {
      f.flame = true;
      f.detections++;
      Serial.printf("CSV,state,%lu,%s,1\n", (unsigned long)now, name);
      emitEvent(EV_FLAME_DETECTED, name, hits);
    } else if (f.flame && now - f.lastHitMs >= FLAME_CLEAR_MS) {
      f.flame = false;
      Serial.printf("CSV,state,%lu,%s,0\n", (unsigned long)now, name);
      emitEvent(EV_FLAME_CLEARED, name);
    }
  }
}

// ===================================================================== MQ-2 ===
// AO goes through a 10k/15k divider (pin = AO x 0.6), so the ESP32 pin never
// sees more than ~3.0 V even if AO reaches the 5 V supply. Everything below
// works on the pin voltage; ao_mv is shown for the person reading it.
// NOT ppm: no calibration exists. The level is the filtered reading relative
// to a clean-air baseline taken after the warm-up - a local prototype
// baseline, not a calibration.
enum GasLevel : uint8_t { GAS_UNKNOWN, GAS_NORMAL, GAS_WARNING, GAS_CRITICAL };
const char *gasLevelName(GasLevel g) {
  switch (g) {
    case GAS_NORMAL:   return "NORMAL";
    case GAS_WARNING:  return "WARNING";
    case GAS_CRITICAL: return "CRITICAL";
    default:           return "UNKNOWN";
  }
}

struct MqState {
  Health   health = H_NOT_FITTED;
  uint16_t raw = 0, pinMv = 0;                    // last sample
  uint16_t ring[MQ_FILTER_WINDOW] = {};
  uint8_t  ringN = 0, ringI = 0;
  uint32_t ringSum = 0;
  uint16_t filtMv = 0;                            // moving average, pin mV
  uint32_t phaseStartMs = 0, lastSampleMs = 0, lastLogMs = 0;
  uint32_t lowSince = 0, highSince = 0;           // fault detection
  uint64_t baseSum = 0;
  uint32_t baseN = 0;
  uint16_t baselineMv = 0;
  float    ratio = NAN;                            // filtered / baseline
  GasLevel level = GAS_UNKNOWN, pending = GAS_UNKNOWN;
  uint32_t pendingSince = 0;
  bool     doRaw = false, doStable = false;        // DO comparator (optional)
  uint32_t doChangedMs = 0;
} mq;

float mqAoMv(uint16_t pinMv) { return pinMv / MQ_DIVIDER_RATIO; }

void mqStartWarmup(uint32_t now) {
  mq.health = H_WARMING_UP;
  mq.phaseStartMs = now;
  mq.level = mq.pending = GAS_UNKNOWN;
  mq.ratio = NAN;
  mq.baselineMv = 0;
}

void mqBegin(uint32_t now) {
  mq = MqState();
  if (fit.mqDo) pinMode(PIN_MQ_DO, INPUT);         // the divider defines the level
  if (!fit.mq) return;
  analogSetPinAttenuation(PIN_MQ_AO, ADC_11db);     // ~0..3.1 V range
  mqStartWarmup(now);
}

void mqStartBaseline(uint32_t now) {
  mq.health = H_BASELINE;
  mq.phaseStartMs = now;
  mq.baseSum = 0;
  mq.baseN = 0;
  mq.level = mq.pending = GAS_UNKNOWN;
  Serial.println("[MQ] BASELINE COLLECTION - keep clean air around the sensor");
}

GasLevel mqTarget(float r, bool hardCritical, GasLevel cur) {
  if (hardCritical || r >= MQ_CRITICAL_RATIO) return GAS_CRITICAL;
  if (cur == GAS_CRITICAL && r >= MQ_CRITICAL_CLEAR_RATIO) return GAS_CRITICAL;  // hysteresis
  if (r >= MQ_WARNING_RATIO) return GAS_WARNING;
  if (cur >= GAS_WARNING && r >= MQ_WARNING_CLEAR_RATIO) return GAS_WARNING;      // hysteresis
  return GAS_NORMAL;
}

void mqClassify(uint32_t now) {
  mq.ratio = mq.baselineMv ? (float)mq.filtMv / mq.baselineMv : NAN;
  // Full scale or far above anything plausible: no waiting, no baseline needed.
  bool hard = mq.raw >= MQ_SATURATION_RAW || mq.filtMv >= MQ_ABS_CRITICAL_PIN_MV;
  GasLevel t = mqTarget(isnan(mq.ratio) ? 0.0f : mq.ratio, hard, mq.level);
  if (t == mq.level) { mq.pending = t; return; }
  if (t != mq.pending) { mq.pending = t; mq.pendingSince = now; }
  uint32_t need = t > mq.level ? MQ_RISE_CONFIRM_MS : MQ_FALL_CONFIRM_MS;
  if (hard && t == GAS_CRITICAL) need = 0;
  if (now - mq.pendingSince < need) return;
  mq.level = t;
  Serial.printf("CSV,state,%lu,gas_level,%d\n", (unsigned long)now, (int)t);
  emitEvent(t == GAS_CRITICAL ? EV_GAS_CRITICAL : t == GAS_WARNING ? EV_GAS_WARNING : EV_GAS_NORMAL,
            "mq_1", mq.ratio);
}

void mqDoUpdate(uint32_t now) {
  if (!fit.mqDo) return;
  bool raw = digitalRead(PIN_MQ_DO) == MQ_DO_ACTIVE_LEVEL;
  if (raw != mq.doRaw) { mq.doRaw = raw; mq.doChangedMs = now; }
  if (mq.doStable == mq.doRaw || now - mq.doChangedMs < MQ_DO_DEBOUNCE_MS) return;
  mq.doStable = mq.doRaw;
  Serial.printf("CSV,state,%lu,gas_do,%d\n", (unsigned long)now, mq.doStable ? 1 : 0);
  // While the heater warms up the comparator is not meaningful: logged, not raised.
  if (mq.health == H_READY || !fit.mq)
    emitEvent(mq.doStable ? EV_GAS_DO_ALARM : EV_GAS_DO_CLEAR, "mq_1_do");
}

void mqUpdate(uint32_t now) {
  if (!fit.mq || now - mq.lastSampleMs < MQ_SAMPLE_INTERVAL_MS) return;
  mq.lastSampleMs = now;
  mq.raw   = analogRead(PIN_MQ_AO);
  mq.pinMv = analogReadMilliVolts(PIN_MQ_AO);
  if (mq.ringN == MQ_FILTER_WINDOW) mq.ringSum -= mq.ring[mq.ringI];
  else mq.ringN++;
  mq.ring[mq.ringI] = mq.pinMv;
  mq.ringSum += mq.pinMv;
  mq.ringI = (mq.ringI + 1) % MQ_FILTER_WINDOW;
  mq.filtMv = mq.ringSum / mq.ringN;

  if (now - mq.lastLogMs >= MQ_LOG_INTERVAL_MS) {
    mq.lastLogMs = now;
    Serial.printf("CSV,mq,%lu,%u,%u,%u,%u,%.3f,%s,%s\n", (unsigned long)now, mq.raw, mq.pinMv,
                  mq.filtMv, mq.baselineMv, isnan(mq.ratio) ? 0.0f : mq.ratio,
                  healthName(mq.health), gasLevelName(mq.level));
  }

  // FAULT: the pin sits at ~0 V - AO wire off, divider broken or module
  // unpowered (a working MQ-2 never reads 0 V: its load resistor always
  // carries some current). Recovery restarts the warm-up: the heater may
  // have cooled.
  if (mq.filtMv < MQ_FAULT_LOW_PIN_MV) { mq.highSince = 0; if (!mq.lowSince) mq.lowSince = now; }
  else                                 { mq.lowSince = 0;  if (!mq.highSince) mq.highSince = now; }
  if (mq.health != H_FAULT && mq.lowSince && now - mq.lowSince >= MQ_FAULT_MS) {
    mq.health = H_FAULT;
    mq.level = mq.pending = GAS_UNKNOWN;
    emitEvent(EV_SENSOR_FAILURE, "mq_1", mq.filtMv);
    return;
  }
  if (mq.health == H_FAULT) {
    if (mq.highSince && now - mq.highSince >= MQ_FAULT_MS) {
      emitEvent(EV_SENSOR_RECOVERED, "mq_1", mq.filtMv);
      mqStartWarmup(now);
    }
    return;
  }

  switch (mq.health) {
    case H_WARMING_UP:                     // readings here are NOT environmental data
      if (now - mq.phaseStartMs >= MQ_WARMUP_MS) mqStartBaseline(now);
      break;
    case H_BASELINE:
      mq.baseSum += mq.filtMv;
      mq.baseN++;
      if (now - mq.phaseStartMs >= MQ_BASELINE_MS && mq.baseN > 0) {
        mq.baselineMv = mq.baseSum / mq.baseN;
        mq.health = H_READY;
        mq.level = mq.pending = GAS_NORMAL;
        Serial.printf("[MQ] BASELINE COMPLETE: %u mV at the pin (AO ~%.0f mV). "
                      "Local prototype baseline - not a calibration.\n",
                      mq.baselineMv, mqAoMv(mq.baselineMv));
        emitEvent(EV_SENSOR_READY, "mq_1", mq.baselineMv);
      }
      break;
    case H_READY:
      mqClassify(now);
      break;
    default:
      break;
  }
}

// =================================================================== common ===
void sensorsBegin(uint32_t now) {
  dhtBegin(now);
  for (Pir &p : pirs) pirBegin(p, now);
  for (int i = 0; i < 5; i++) flameBegin(i);
  mqBegin(now);
}

void sensorsUpdate(uint32_t now) {
  flameUpdate(now);        // safety first: every 10 ms
  pirUpdate(now);
  mqDoUpdate(now);
  mqUpdate(now);           // every 100 ms
  dhtUpdate(now);          // every 2.5 s (~5 ms read)
}

Health flameHealth() { return flameAnyFitted() ? H_ONLINE : H_NOT_FITTED; }
