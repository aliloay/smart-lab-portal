---
type: "source-mirror"
source_kind: "source-code"
source_path: "firmware/tools/door_audio_test/door_audio_test.ino"
source_hash: "36f7ef5c1e44a0281c7e23fc0e89c38eaf714aafa215a4cf061b65ae3e9918bf"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `firmware/tools/door_audio_test/door_audio_test.ino` - edit the original in the repository, not this note.

Systems: none

```ino
// ===========================================================================
// DOOR SPEAKER BENCH TEST (flashed on the door ESP32 temporarily)
// ===========================================================================
// Verifies the PAM8403 + speaker on GPIO22 before the speaker goes into the
// door firmware. Holds the lock LOCKED (GPIO26 HIGH via the BC557, first instruction) and
// the old buzzer OFF (GPIO21 LOW); nothing else on the door board is driven.
// Re-flash SmartLab_Master_Portal afterwards - the door does not work while
// this test is on the board.
//
// Build: copy door_audio.h and door_voice.h from ../../SmartLab_Master_Portal
// next to this file (they are generated / shared there), board ESP32 Dev
// Module, Partition Scheme "Huge APP (3MB No OTA/1MB SPIFFS)".
//
// Serial 115200, commands:
//   vol <0-100>   loudness in % of full scale (starts at 20)
//   list          the voice clips          say <n|NAME>  play one clip
//   beep | buzz | siren | deny | grant | welcome | all | stop
// Every command is also printed as "CSV,audio,<ms>,<command>,<volume>".
// ===========================================================================
#include "door_audio.h"

constexpr uint8_t RELAY_PIN = 26, RELAY_LOCKED_LEVEL = HIGH;  // lock on NO, relay IN via BC557 (inverting)
constexpr uint8_t RED_LED_BUZZER_PIN = 21;

int allNext = -1;     // "all": index of the next clip to play

void logCmd(const String &c) {
  Serial.printf("CSV,audio,%lu,%s,%u\n", (unsigned long)millis(), c.c_str(), audioVolume);
}

int clipByName(const String &s) {
  static const char *names[] = {
    "BOOT", "WELCOME", "VERIFY", "HELLO", "WELCOME_IN", "DENIED", "TIME_UP", "MISMATCH",
    "TRY_AGAIN", "CLOSE_DOOR", "FORCED", "EVACUATE", "LOCKDOWN", "EM_OPEN",
    "NAME_USER1", "NAME_USER2", "NAME_USER3", "NAME_USER4", "NAME_USER5"};
  if (isDigit(s[0])) return s.toInt();
  for (int i = 0; i < (int)(sizeof(names) / sizeof(names[0])); i++)
    if (s.equalsIgnoreCase(names[i])) return i;
  return -1;
}

void command(String line) {
  line.trim();
  if (!line.length()) return;
  logCmd(line);
  String arg = line.indexOf(' ') > 0 ? line.substring(line.indexOf(' ') + 1) : "";
  if (line.startsWith("vol")) {
    audioVolume = constrain(arg.toInt(), 0, 100);
    Serial.printf("[TEST] volume %u%%\n", audioVolume);
    audioPlay({aTone(880, 250)});
  } else if (line == "list") {
    for (int i = 0; i < VOICE_COUNT; i++)
      Serial.printf("  %2d  %5.2f s\n", i, VOICE_CLIPS[i].len / (float)VOICE_RATE);
  } else if (line.startsWith("say")) {
    int c = clipByName(arg);
    if (c < 0 || c >= VOICE_COUNT) Serial.println("[TEST] no such clip (try: list)");
    else audioPlay({aSay(c)});
  } else if (line == "beep")    audioPlay({aTone(1500, 120), aGap(80), aTone(1500, 120)});
  else if (line == "buzz")      audioPlay({aBuzz(600)});
  else if (line == "siren")     audioPlay({aSweep(600, 1400, 700), aSweep(1400, 600, 700),
                                           aSweep(600, 1400, 700), aSweep(1400, 600, 700)});
  else if (line == "deny")      audioPlay({aBuzz(250), aGap(60), aBuzz(250), aGap(150),
                                           aSay(VOICE_DENIED), aSay(VOICE_TRY_AGAIN)});
  else if (line == "grant")     audioPlay({aTone(1320, 90), aTone(1760, 140), aGap(100),
                                           aSay(VOICE_HELLO), aSay(voiceNameFor("USER1")),
                                           aGap(80), aSay(VOICE_WELCOME_IN)});
  else if (line == "welcome")   audioPlay({aTone(988, 90), aTone(1319, 140), aGap(100), aSay(VOICE_WELCOME)});
  // Diagnosis: what the output does while nothing plays. "low" holds GPIO22
  // near 0 V (no switching), "mid" back to 50 % (fast switching = silence).
  else if (line == "low")       { audioStop(); delay(50); sdm_channel_set_pulse_density(audioSdm, -128);
                                  Serial.println("[TEST] idle output held LOW (no switching)"); }
  else if (line == "mid")       { audioStop(); delay(50); sdm_channel_set_pulse_density(audioSdm, 0);
                                  Serial.println("[TEST] idle output at 50 % (switching)"); }
  else if (line == "all")       allNext = 0;
  else if (line == "stop")      { allNext = -1; audioStop(); }
  else Serial.println("[TEST] vol <n> | list | say <n|NAME> | beep | buzz | siren | deny | grant | welcome | all | stop");
}

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, RELAY_LOCKED_LEVEL);   // LOCKED first, as the door firmware
  pinMode(RED_LED_BUZZER_PIN, OUTPUT);
  digitalWrite(RED_LED_BUZZER_PIN, LOW);         // old buzzer stays silent
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== DOOR SPEAKER BENCH TEST === (relay held LOCKED, buzzer off)");
  if (audioBegin()) {
    delay(200);
    audioPlay({aTone(880, 150), aGap(50), aSay(VOICE_BOOT)});
  }
  command("help");
}

void loop() {
  static String line;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { command(line); line = ""; }
    else if (c != '\r' && line.length() < 40) line += c;
  }
  if (allNext >= 0 && !audioBusy()) {
    if (allNext >= VOICE_COUNT) { allNext = -1; Serial.println("[TEST] all clips played"); }
    else { Serial.printf("[TEST] clip %d\n", allNext); audioPlay({aSay(allNext), aGap(400)}); allNext++; }
  }
  delay(5);
}

```
