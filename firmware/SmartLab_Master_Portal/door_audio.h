// ===========================================================================
// Door speaker: spoken prompts, beeps, the denial buzz and the alarm siren.
// ===========================================================================
// ESP32 GPIO22 (sigma-delta output) -> [R-C low-pass, R x C ~ 47 us]
//   -> PAM8403 "L" input (its "R" input tied to its input ground)
//   -> 3 W / 8 ohm speaker on "L OUT +" / "L OUT -" (both live: never to GND).
// The amplifier takes its 5 V on its own wires from the 5 V supply, not
// through the relay module; its GND is common with the ESP32.
//
// How it plays without ever blocking the door:
//   a hardware timer at VOICE_RATE (16000 Hz) feeds one sample per tick
//   from flash to the sigma-delta modulator; the door code only queues what
//   to say (audioPlay) and carries on. A new announcement REPLACES the one
//   playing - the newest event is what the person needs to hear.
// The timer interrupt is not IRAM-safe (core default), so it pauses while
// flash is written (NVS) - a short gap in the sound, never a crash.
// In silence the output is held LOW (no switching): an idle 50 % pattern is
// what made the amplifier buzz between announcements. Each announcement
// fades the output up from 0 V and back down (~12 ms each), so no click.
//
// Loudness is limited in software (audioVolume, % of full scale): start low
// and raise it while watching the lock - a supply dip must never release it.
// ===========================================================================
#pragma once
#include <Arduino.h>
#include <string.h>
#include <driver/sdm.h>
#include "door_voice.h"

constexpr uint8_t AUDIO_PIN = 22;
constexpr uint8_t AUDIO_VOLUME_DEFAULT = 100;  // %; chosen by ear on the bench (2026-10-04, 3.3k/100nF filter)
volatile uint8_t  audioVolume = AUDIO_VOLUME_DEFAULT;

// One step of an announcement.
enum : uint8_t { SEG_END = 0, SEG_CLIP, SEG_TONE, SEG_SQUARE, SEG_GAP };
struct AudioSeg {
  uint8_t  kind;
  uint8_t  clip;       // SEG_CLIP: VoiceId
  uint16_t f0, f1;     // SEG_TONE / SEG_SQUARE: start and end frequency, Hz (sweep)
  uint16_t ms;         // tone / gap length
};
constexpr uint8_t AUDIO_MAX_SEGS = 16;

// Builders, for readable announcements:
//   audioPlay({ aBeep(), aSay(VOICE_DENIED) });
inline AudioSeg aSay(uint8_t clip)                          { return {SEG_CLIP, clip, 0, 0, 0}; }
inline AudioSeg aTone(uint16_t hz, uint16_t ms)             { return {SEG_TONE, 0, hz, hz, ms}; }
inline AudioSeg aSweep(uint16_t a, uint16_t b, uint16_t ms) { return {SEG_TONE, 0, a, b, ms}; }
inline AudioSeg aBuzz(uint16_t ms)                          { return {SEG_SQUARE, 0, 420, 420, ms}; }
inline AudioSeg aGap(uint16_t ms)                           { return {SEG_GAP, 0, 0, 0, ms}; }

// --- shared between the door code and the timer interrupt ------------------
static portMUX_TYPE audioMux = portMUX_INITIALIZER_UNLOCKED;
static AudioSeg  audioNext[AUDIO_MAX_SEGS];
static volatile bool audioNextReady = false;
static volatile bool audioPlaying = false;

// --- owned by the interrupt ---------------------------------------------------
static AudioSeg  aSegs[AUDIO_MAX_SEGS];
static uint8_t   aIdx = 0;
static uint32_t  aPos = 0, aLen = 0, aPhase = 0;
static sdm_channel_handle_t audioSdm = nullptr;
static hw_timer_t *audioTimer = nullptr;
static bool      audioReady = false;
static int16_t   aBias = -128;               // output level offset: -128 = 0 V (idle)
static bool      aFading = false;            // list finished: ramping down to 0 V

static uint32_t segSamples(const AudioSeg &s) {
  if (s.kind == SEG_CLIP) return s.clip < VOICE_COUNT ? VOICE_CLIPS[s.clip].len : 0;
  return (uint32_t)s.ms * VOICE_RATE / 1000;
}

static void audioTick() {
  portENTER_CRITICAL_ISR(&audioMux);
  if (audioNextReady) {
    memcpy(aSegs, audioNext, sizeof(aSegs));
    audioNextReady = false;
    aIdx = 0; aPos = 0; aPhase = 0;
    aLen = segSamples(aSegs[0]);
    aFading = aSegs[0].kind == SEG_END;         // empty list = stop: fade out
    audioPlaying = !aFading || aBias > -128;
  }
  portEXIT_CRITICAL_ISR(&audioMux);
  if (!audioPlaying) return;

  if (aFading) {                               // ramp down to 0 V, then stop switching
    if (aBias > -128) aBias--;
    sdm_channel_set_pulse_density(audioSdm, (int8_t)aBias);
    if (aBias <= -128) audioPlaying = false;
    return;
  }
  if (aBias < 0) {                             // ramp up from 0 V before the sound
    aBias++;
    sdm_channel_set_pulse_density(audioSdm, (int8_t)aBias);
    return;
  }

  while (aPos >= aLen) {                       // next segment
    if (++aIdx >= AUDIO_MAX_SEGS || aSegs[aIdx].kind == SEG_END) {
      aFading = true;                          // done: fade out
      return;
    }
    aPos = 0; aPhase = 0;
    aLen = segSamples(aSegs[aIdx]);
  }

  const AudioSeg &s = aSegs[aIdx];
  int32_t v = 0;                               // -128 .. 127
  if (s.kind == SEG_CLIP) {
    v = (int32_t)VOICE_CLIPS[s.clip].data[aPos] - 128;
  } else if (s.kind == SEG_TONE || s.kind == SEG_SQUARE) {
    // Frequency sweeps linearly f0 -> f1; phase is a 32-bit accumulator.
    uint32_t f = s.f0 + (int32_t)(s.f1 - s.f0) * (int32_t)aPos / (int32_t)(aLen ? aLen : 1);
    aPhase += (uint32_t)(((uint64_t)f << 32) / VOICE_RATE);
    if (s.kind == SEG_SQUARE) {
      v = (aPhase & 0x80000000u) ? 110 : -110;                  // harsh, buzzer-like
    } else {
      int32_t t = (int32_t)(aPhase >> 24);                      // 0..255 triangle
      v = (t < 128 ? t * 2 - 128 : 383 - t * 2) * 7 / 8;       // softer than a square
    }
  }
  aPos++;
  sdm_channel_set_pulse_density(audioSdm, (int8_t)(v * audioVolume / 100));
}

// --- door-side API -------------------------------------------------------------
bool audioBegin() {
  sdm_config_t cfg = {};
  cfg.gpio_num = AUDIO_PIN;
  cfg.clk_src = SDM_CLK_SRC_DEFAULT;
  cfg.sample_rate_hz = 1000000;                // modulator clock: far above audio
  if (sdm_new_channel(&cfg, &audioSdm) != ESP_OK || sdm_channel_enable(audioSdm) != ESP_OK) {
    Serial.println("[AUDIO][FAIL] sigma-delta output not available - speaker off");
    return false;
  }
  sdm_channel_set_pulse_density(audioSdm, -128);   // idle: held at 0 V
  audioTimer = timerBegin(8000000);            // 8 MHz: 16000 Hz is an exact divisor
  if (!audioTimer) {
    Serial.println("[AUDIO][FAIL] no hardware timer - speaker off");
    return false;
  }
  timerAttachInterrupt(audioTimer, &audioTick);
  timerAlarm(audioTimer, 8000000 / VOICE_RATE, true, 0);
  audioReady = true;
  Serial.printf("[AUDIO] speaker on GPIO%u, %lu Hz, volume %u%%, %u clips\n", AUDIO_PIN,
                (unsigned long)VOICE_RATE, audioVolume, (unsigned)VOICE_COUNT);
  return true;
}

// Replace whatever is playing with this announcement (up to AUDIO_MAX_SEGS steps).
void audioPlay(std::initializer_list<AudioSeg> segs) {
  if (!audioReady) return;
  AudioSeg list[AUDIO_MAX_SEGS] = {};
  uint8_t n = 0;
  for (const AudioSeg &s : segs) {
    if (n >= AUDIO_MAX_SEGS - 1) break;
    if (s.kind == SEG_CLIP && s.clip >= VOICE_COUNT) continue;   // e.g. no name clip
    list[n++] = s;
  }
  portENTER_CRITICAL(&audioMux);
  memcpy(audioNext, list, sizeof(audioNext));
  audioNextReady = true;
  portEXIT_CRITICAL(&audioMux);
}

void audioStop() { audioPlay({}); }
bool audioBusy() { return audioPlaying || audioNextReady; }
