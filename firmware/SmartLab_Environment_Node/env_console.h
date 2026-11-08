// ===========================================================================
// CONSOLE - live diagnostics and test commands on the USB serial port.
// Serial Monitor: 115200 baud, line ending "Newline" (or "Both NL & CR").
// ===========================================================================
#pragma once
#include <esp_system.h>

enum StreamMode : uint8_t { ST_NONE, ST_ALL, ST_DHT, ST_PIR, ST_MQ, ST_FLAME, ST_PINS };
StreamMode streamMode = ST_NONE;
uint32_t   lastStreamMs = 0, lastDiagMs = 0, lastSnapshotMs = 0, lastDhtShown = 0;
bool       selfTestDone = false;
constexpr uint32_t SELF_TEST_AT_MS = 4000;   // after the first DHT22 read (2.5 s)

const char *wifiText() {
  if (!WIFI_ENABLED) return "DISABLED";
  return WiFi.status() == WL_CONNECTED ? "CONNECTED" : "DISCONNECTED";
}
const char *resetReasonText() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON:  return "power-on";
    case ESP_RST_SW:       return "software restart";
    case ESP_RST_PANIC:    return "CRASH (panic)";
    case ESP_RST_INT_WDT:  return "WATCHDOG (interrupt)";
    case ESP_RST_TASK_WDT: return "WATCHDOG (task)";
    case ESP_RST_WDT:      return "WATCHDOG";
    case ESP_RST_BROWNOUT: return "BROWNOUT (supply dipped)";
    case ESP_RST_EXT:      return "reset pin";
    case ESP_RST_DEEPSLEEP:return "deep sleep";
    default:               return "other";
  }
}
void uptimeText(char *out, size_t n, uint32_t ms) {
  uint32_t s = ms / 1000;
  snprintf(out, n, "%02lu:%02lu:%02lu", (unsigned long)(s / 3600),
           (unsigned long)(s / 60 % 60), (unsigned long)(s % 60));
}

void printBanner() {
  Serial.println();
  Serial.println("================================================");
  Serial.println("SMART LAB ENVIRONMENT NODE");
  Serial.printf("Device: %s   Lab: %s\n", DEVICE_ID, LAB_ID);
  Serial.printf("Firmware: %s %s\n", NODE_NAME, FIRMWARE_VERSION);
  Serial.println("Monitoring only - it never switches anything.");
  Serial.println("Not a certified fire/gas detector (indicators).");
  Serial.println("================================================");
  Serial.printf("[INIT] Chip %s rev %d, %d cores, flash %lu MB, PSRAM %s\n",
                ESP.getChipModel(), (int)ESP.getChipRevision(), (int)ESP.getChipCores(),
                (unsigned long)(ESP.getFlashChipSize() / (1024 * 1024)),
                psramFound() ? "yes" : "none");
  Serial.printf("[INIT] Reset reason: %s\n", resetReasonText());
}

void printFitted() {
  Serial.printf("[FIT] dht=%s pir1=%s pir2=%s mq=%s mqdo=%s flame=%s%s%s%s%s  (change: fit <name> on|off)\n",
                fit.dht ? "on" : "off", fit.pir1 ? "on" : "off", fit.pir2 ? "on" : "off",
                fit.mq ? "on" : "off", fit.mqDo ? "on" : "off",
                fit.flame[0] ? "1" : "-", fit.flame[1] ? "2" : "-", fit.flame[2] ? "3" : "-",
                fit.flame[3] ? "4" : "-", fit.flame[4] ? "5" : "-");
}

// ------------------------------------------------------------- blocks ---
void printDht(uint32_t now) {
  Serial.printf("DHT22 [%s]\n", healthName(dhtS.health));
  if (!fit.dht) { Serial.println("  (not fitted - enable with: fit dht on)"); return; }
  if (dhtS.validAtMs == 0) {
    Serial.printf("  no valid reading yet (%lu reads, %lu failed)\n",
                  (unsigned long)dhtS.reads, (unsigned long)dhtS.fails);
    return;
  }
  Serial.printf("  Temperature: %.1f C\n  Humidity:    %.1f %%\n", dhtS.tempC, dhtS.humPct);
  Serial.printf("  (reading %.1f s old%s, %lu reads, %lu failed)\n",
                (now - dhtS.validAtMs) / 1000.0f, dhtValid(now) ? "" : " - STALE, not valid",
                (unsigned long)dhtS.reads, (unsigned long)dhtS.fails);
}

void printPir(uint32_t now) {
  for (int i = 0; i < 2; i++) {
    Pir &p = pirs[i];
    Serial.printf("PIR%d (zone %d) [%s]", i + 1, i + 1, healthName(p.health));
    if (!*p.fitted) { Serial.printf("  (not fitted - fit pir%d on)\n", i + 1); continue; }
    if (p.health == H_WARMING_UP) {
      uint32_t left = PIR_WARMUP_MS - min(PIR_WARMUP_MS, now - p.warmStartMs);
      Serial.printf("  %lu s left", (unsigned long)(left / 1000));
    } else {
      Serial.printf("  %s", p.motion ? "MOTION" : "CLEAR");
    }
    Serial.printf("   (OUT pin %s, %lu triggers)\n", p.raw ? "ACTIVE" : "idle", (unsigned long)p.triggers);
  }
  Serial.printf("motion_any: %s\n", motionAny() ? "YES" : "no");
}

void printMq(uint32_t now) {
  Serial.printf("MQ2 [%s]", healthName(mq.health));
  if (!fit.mq) { Serial.println("  (not fitted - fit mq on)"); return; }
  if (mq.health == H_WARMING_UP) {
    uint32_t left = MQ_WARMUP_MS - min(MQ_WARMUP_MS, now - mq.phaseStartMs);
    Serial.printf("  %lu:%02lu left - readings are NOT environmental data yet",
                  (unsigned long)(left / 60000), (unsigned long)(left / 1000 % 60));
  } else if (mq.health == H_BASELINE) {
    uint32_t left = MQ_BASELINE_MS - min(MQ_BASELINE_MS, now - mq.phaseStartMs);
    Serial.printf("  collecting clean-air baseline, %lu s left", (unsigned long)(left / 1000));
  }
  Serial.println();
  Serial.printf("  mq_raw:      %u (ADC 0-4095)\n", (unsigned)mq.raw);
  Serial.printf("  pin:         %.3f V   (AO at the module ~%.2f V)\n", mq.pinMv / 1000.0f, mqAoMv(mq.pinMv) / 1000.0f);
  Serial.printf("  mq_filtered: %.3f V   (1 s average at the pin)\n", mq.filtMv / 1000.0f);
  if (mq.baselineMv) Serial.printf("  baseline:    %.3f V   ratio %.2f\n", mq.baselineMv / 1000.0f, mq.ratio);
  Serial.printf("  mq_level:    %s   mq_alarm: %s\n", gasLevelName(mq.level),
                mq.level >= GAS_WARNING ? "YES" : "no");
  if (fit.mqDo) Serial.printf("  DO comparator: %s\n", mq.doStable ? "ALARM" : "clear");
}

void printFlame(uint32_t) {
  Serial.printf("FLAME [%s]  CH1 digital, CH2-5 analog (> %u mV)", healthName(flameHealth()),
                (unsigned)FLAME_ANALOG_THRESHOLD_MV);
  if (!flameAnyFitted()) { Serial.println("  (not fitted - fit flame on)"); return; }
  Serial.println();
  for (int i = 0; i < 5; i++) {
    Serial.printf("  CH%d (GPIO %2u): ", i + 1, flamePin(i));
    if (!fit.flame[i]) { Serial.println("not fitted"); continue; }
    Serial.printf("%-6s  now %s", flames[i].flame ? "FLAME" : "CLEAR", flames[i].raw ? "IR" : "--");
    if (FLAME_IS_ANALOG[i]) Serial.printf("  %4u mV", (unsigned)flames[i].analog);
    Serial.printf("  (%lu detections)\n", (unsigned long)flames[i].detections);
  }
  Serial.printf("flame_any: %s\n", flameAny() ? "YES" : "no");
  // For tuning the analog threshold: CH1 level, then CH2..CH5 in mV.
  Serial.printf("CSV,flame,%lu,%d,%u,%u,%u,%u\n", (unsigned long)millis(), flames[0].raw ? 1 : 0,
                (unsigned)flames[1].analog, (unsigned)flames[2].analog,
                (unsigned)flames[3].analog, (unsigned)flames[4].analog);
}

void printWifi() {
  Serial.printf("WiFi: %s", wifiText());
  if (WiFi.status() == WL_CONNECTED)
    Serial.printf("   SSID %s   IP %s   RSSI %d dBm", WiFi.SSID().c_str(),
                  WiFi.localIP().toString().c_str(), (int)WiFi.RSSI());
  Serial.println();
  Serial.printf("Backend: %s\n", LOCAL_TEST_MODE ? "LOCAL TEST MODE (nothing is sent)" : "portal reporting ON");
}

void printDashboard(uint32_t now) {
  char up[12];
  uptimeText(up, sizeof(up), now);
  Serial.println("==================================================");
  Serial.printf("SMART LAB ENVIRONMENT NODE   %s   fw %s   up %s\n", DEVICE_ID, FIRMWARE_VERSION, up);
  Serial.println("==================================================");
  printWifi();
  Serial.println("--------------------------------------------------");
  printDht(now);
  printPir(now);
  printMq(now);
  printFlame(now);
  Serial.println("--------------------------------------------------");
  Serial.printf("Events since boot: %lu (not queued: %lu)\n", (unsigned long)eventsTotal, (unsigned long)eventsDropped);
  Serial.println("System: RUNNING");
  Serial.println("==================================================");
}

// Phase 1: what every assigned pin reads right now, fitted or not.
void printPins() {
  Serial.printf("[PINS] DHT G4=%d  PIR1 G27=%d  PIR2 G26=%d  MQ_DO G25=%d  MQ_AO G%u=%umV  G34=%umV  FLAME",
                digitalRead(PIN_DHT), digitalRead(PIN_PIR1), digitalRead(PIN_PIR2),
                digitalRead(PIN_MQ_DO), PIN_MQ_AO, (unsigned)analogReadMilliVolts(PIN_MQ_AO),
                (unsigned)analogReadMilliVolts(34));
  for (int i = 0; i < 5; i++) {
    if (FLAME_IS_ANALOG[i]) Serial.printf(" G%u=%umV", flamePin(i), (unsigned)analogReadMilliVolts(flamePin(i)));
    else Serial.printf(" G%u=%d", flamePin(i), digitalRead(flamePin(i)));
  }
  Serial.println();
}

// One line every DIAG_INTERVAL_MS when no test stream is running.
void printDiagLine(uint32_t now) {
  char up[12];
  uptimeText(up, sizeof(up), now);
  Serial.printf("[STATUS] up %s | WiFi %s | DHT %s", up, wifiText(), healthName(dhtS.health));
  if (dhtValid(now)) Serial.printf(" %.1fC %.1f%%", dhtS.tempC, dhtS.humPct);
  Serial.printf(" | PIR1 %s PIR2 %s",
                pirs[0].health == H_ONLINE ? (pirs[0].motion ? "MOTION" : "clear") : healthName(pirs[0].health),
                pirs[1].health == H_ONLINE ? (pirs[1].motion ? "MOTION" : "clear") : healthName(pirs[1].health));
  Serial.printf(" | MQ %s", healthName(mq.health));
  if (mq.health == H_READY) Serial.printf(" %s r=%.2f", gasLevelName(mq.level), mq.ratio);
  Serial.printf(" | FLAME %s\n", flameAnyFitted() ? (flameAny() ? "DETECTED" : "clear") : "NOT_FITTED");
}

// The JSON a later portal integration would carry (fitted sensors only).
void buildSnapshot(JsonBuf &j, uint32_t now) {
  j.add("{\"device_id\":\"%s\",\"firmware\":\"%s\",\"uptime_ms\":%lu,\"wifi\":\"%s\"",
        DEVICE_ID, FIRMWARE_VERSION, (unsigned long)now, wifiText());
  if (WiFi.status() == WL_CONNECTED) j.add(",\"rssi\":%d", (int)WiFi.RSSI());
  if (fit.dht) {
    j.add(",\"dht22\":{\"status\":\"%s\",\"valid\":%s", healthName(dhtS.health), dhtValid(now) ? "true" : "false");
    if (dhtS.validAtMs) j.add(",\"temperature_c\":%.2f,\"humidity_percent\":%.2f,\"age_ms\":%lu",
                              dhtS.tempC, dhtS.humPct, (unsigned long)(now - dhtS.validAtMs));
    j.add("}");
  }
  for (int i = 0; i < 2; i++) {
    if (!*pirs[i].fitted) continue;
    j.add(",\"pir_%d\":{\"status\":\"%s\",\"motion\":%s}", i + 1, healthName(pirs[i].health),
          pirs[i].health == H_ONLINE && pirs[i].motion ? "true" : "false");
  }
  if (fit.pir1 || fit.pir2) j.add(",\"motion_any\":%s", motionAny() ? "true" : "false");
  if (fit.mq) {
    j.add(",\"mq2\":{\"mq_status\":\"%s\",\"mq_raw\":%u,\"mq_pin_mv\":%u,\"mq_filtered\":%u",
          healthName(mq.health), (unsigned)mq.raw, (unsigned)mq.pinMv, (unsigned)mq.filtMv);
    if (mq.health == H_READY)
      j.add(",\"baseline_mv\":%u,\"ratio\":%.3f,\"mq_level\":\"%s\",\"mq_alarm\":%s",
            (unsigned)mq.baselineMv, mq.ratio, gasLevelName(mq.level), mq.level >= GAS_WARNING ? "true" : "false");
    j.add("}");
  }
  if (flameAnyFitted()) {
    j.add(",\"flame\":{\"status\":\"%s\"", healthName(flameHealth()));
    for (int i = 0; i < 5; i++) if (fit.flame[i]) j.add(",\"flame_%d\":%s", i + 1, flames[i].flame ? "true" : "false");
    j.add(",\"flame_any\":%s}", flameAny() ? "true" : "false");
  }
  j.add("}");
}

void printSnapshot(uint32_t now) {
  char buf[900];
  JsonBuf j(buf, sizeof(buf));
  buildSnapshot(j, now);
  Serial.printf("SNAPSHOT %s%s\n", buf, j.overflow ? "  (TRUNCATED)" : "");
}

// Startup self-test: says only what can actually be checked from here.
void selfTest(uint32_t now) {
  Serial.println("------------------ SELF-TEST -------------------");
  if (!fit.dht) Serial.println("DHT22: NOT FITTED");
  else if (dhtS.validAtMs) Serial.printf("DHT22: OK (%.1f C, %.1f %%)\n", dhtS.tempC, dhtS.humPct);
  else Serial.println("DHT22: FAIL - no valid reading (wiring, '+' on 3V3, GPIO 4, pull-up)");

  if (!fit.mq) Serial.println("MQ2:   NOT FITTED");
  else if (mq.filtMv < MQ_FAULT_LOW_PIN_MV)
    Serial.printf("MQ2:   FAIL - pin at %u mV: AO wire, divider or 5 V supply missing\n", (unsigned)mq.filtMv);
  else Serial.printf("MQ2:   WARMING (signal present: %.2f V at the pin) - not trusted yet\n", mq.filtMv / 1000.0f);

  if (!flameAnyFitted()) Serial.println("FLAME: NOT FITTED");
  else {
    Serial.println("FLAME: UNVERIFIED - a digital output cannot be proven electrically;");
    Serial.println("       type 'flame' and show each sensor a flame");
    for (int i = 0; i < 5; i++)
      if (fit.flame[i] && flames[i].raw)
        Serial.printf("       CH%d reads IR at start: IR source in view, or the active level is wrong\n", i + 1);
  }
  for (int i = 0; i < 2; i++) {
    if (!*pirs[i].fitted) Serial.printf("PIR%d:  NOT FITTED\n", i + 1);
    else Serial.printf("PIR%d:  WARMING (60 s) - presence cannot be proven electrically; 'pir' test after\n", i + 1);
  }
  Serial.println("------------------------------------------------");
}

// ------------------------------------------------------------- commands ---
void printHelp() {
  Serial.println("Commands (Newline line ending):");
  Serial.println("  help              this list");
  Serial.println("  status            everything, once");
  Serial.println("  all               everything, every second (stop: 'stop')");
  Serial.println("  dht | pir | mq | flame   one sensor, live (stop: 'stop')");
  Serial.println("  pins              raw level of every assigned pin, live (wiring checks)");
  Serial.println("  wifi              Wi-Fi state");
  Serial.println("  json              the snapshot JSON, once");
  Serial.println("  fit               which sensors are enabled");
  Serial.println("  fit <dht|pir1|pir2|mq|mqdo|flame|flame1..flame5> <on|off>");
  Serial.println("  baseline          take the MQ-2 clean-air baseline again");
  Serial.println("  stop              stop a live view");
  Serial.println("  restart           reboot the board");
}

bool setFit(const char *name, bool on, uint32_t now) {
  if (!strcmp(name, "dht"))       { fit.dht = on;  dhtBegin(now); }
  else if (!strcmp(name, "pir1")) { fit.pir1 = on; pirBegin(pirs[0], now); }
  else if (!strcmp(name, "pir2")) { fit.pir2 = on; pirBegin(pirs[1], now); }
  else if (!strcmp(name, "mq"))   { fit.mq = on;   mqBegin(now); }
  else if (!strcmp(name, "mqdo")) { fit.mqDo = on; if (on) pinMode(PIN_MQ_DO, INPUT); }
  else if (!strcmp(name, "flame")) { for (int i = 0; i < 5; i++) { fit.flame[i] = on; flameBegin(i); } }
  else if (!strncmp(name, "flame", 5) && name[5] >= '1' && name[5] <= '5' && !name[6]) {
    int i = name[5] - '1';
    fit.flame[i] = on;
    flameBegin(i);
  } else return false;
  fitSave();
  return true;
}

void runCommand(char *line, uint32_t now) {
  char *cmd = strtok(line, " \t");
  if (!cmd) return;
  char *a1 = strtok(nullptr, " \t"), *a2 = strtok(nullptr, " \t");
  for (char *c = cmd; *c; c++) *c = tolower(*c);
  Serial.printf("> %s%s%s%s%s\n", cmd, a1 ? " " : "", a1 ? a1 : "", a2 ? " " : "", a2 ? a2 : "");

  if (!strcmp(cmd, "help"))         printHelp();
  else if (!strcmp(cmd, "status"))  printDashboard(now);
  else if (!strcmp(cmd, "all"))     { streamMode = ST_ALL; lastStreamMs = 0; }
  else if (!strcmp(cmd, "dht"))     { streamMode = ST_DHT; dhtUpdate(now, true); printDht(now); lastDhtShown = dhtS.lastTryMs; }
  else if (!strcmp(cmd, "pir"))     { streamMode = ST_PIR; lastStreamMs = 0; }
  else if (!strcmp(cmd, "mq"))      { streamMode = ST_MQ; lastStreamMs = 0; }
  else if (!strcmp(cmd, "flame"))   { streamMode = ST_FLAME; lastStreamMs = 0; }
  else if (!strcmp(cmd, "pins"))    { streamMode = ST_PINS; lastStreamMs = 0; }
  else if (!strcmp(cmd, "wifi"))    printWifi();
  else if (!strcmp(cmd, "json"))    printSnapshot(now);
  else if (!strcmp(cmd, "stop"))    { streamMode = ST_NONE; Serial.println("[CMD] live view stopped"); }
  else if (!strcmp(cmd, "restart")) { Serial.println("[CMD] restarting..."); Serial.flush(); ESP.restart(); }
  else if (!strcmp(cmd, "baseline")) {
    if (mq.health == H_READY || mq.health == H_BASELINE) mqStartBaseline(now);
    else Serial.printf("[CMD] MQ-2 is %s - a baseline needs the warm-up done\n", healthName(mq.health));
  } else if (!strcmp(cmd, "fit")) {
    if (a1 && a2 && (!strcmp(a2, "on") || !strcmp(a2, "off"))) {
      if (!setFit(a1, !strcmp(a2, "on"), now)) Serial.println("[CMD] unknown sensor - see 'help'");
    }
    printFitted();
  } else Serial.println("[CMD] unknown command - type 'help'");
}

void consoleUpdate(uint32_t now) {
  static char line[64];
  static uint8_t len = 0;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') { line[len] = 0; runCommand(line, now); len = 0; continue; }
    if (len < sizeof(line) - 1) line[len++] = c;
  }

  if (!selfTestDone && now - bootMs >= SELF_TEST_AT_MS) { selfTestDone = true; selfTest(now); }

  switch (streamMode) {
    case ST_ALL:   if (now - lastStreamMs >= 1000) { lastStreamMs = now; printDashboard(now); } break;
    case ST_PIR:   if (now - lastStreamMs >= 250)  { lastStreamMs = now; printPir(now); } break;
    case ST_MQ:    if (now - lastStreamMs >= 500)  { lastStreamMs = now; printMq(now); } break;
    case ST_FLAME: if (now - lastStreamMs >= 250)  { lastStreamMs = now; printFlame(now); } break;
    case ST_PINS:  if (now - lastStreamMs >= 500)  { lastStreamMs = now; printPins(); } break;
    case ST_DHT:   if (dhtS.lastTryMs != lastDhtShown) { lastDhtShown = dhtS.lastTryMs; printDht(now); } break;
    case ST_NONE:
      if (now - lastDiagMs >= DIAG_INTERVAL_MS) { lastDiagMs = now; printDiagLine(now); }
      if (now - lastSnapshotMs >= SNAPSHOT_INTERVAL_MS) { lastSnapshotMs = now; printSnapshot(now); }
      break;
  }
}
