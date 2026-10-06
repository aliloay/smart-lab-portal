#include "HardwareTests.h"
#include "config.h"
#include "Log.h"
#include "LoadCellManager.h"
#include "DisplayManager.h"
#include "NFCManager.h"
#include "ServoManager.h"
#include "LidSensorManager.h"
#include "RFIDManager.h"
#include "WiFiManager.h"
#include "FaultManager.h"
#include "Verification.h"

// ------------------------------------------------------------- commands --
void SerialCommands::printHelp() {
  Serial.println(F(
    "\nCommands (115200 baud, line ending: Newline):\n"
    "  help | status | i2c | selftest | fault | fault clear | reboot\n"
    "  LOAD CELL : tare | cal <grams> | show | watch on|off | calclear\n"
    "  LCD       : lcd <text>\n"
    "  NFC       : nfc\n"
    "  SERVO     : servo angle <n> | servo center | servo stop | servo status\n"
    "              servo set idle <n> | servo set open <n>   (saved)\n"
    "              servo open | servo close   (use the saved angles)\n"
    "              servo clear   (unlock after a lid fault)\n"
    "  REED      : reed\n"
    "  RFID      : rfid scan | rfid status\n"));
}

void SerialCommands::update() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c != '\n') { if (_buf.length() < 64) _buf += c; continue; }
    String line = _buf;
    _buf = "";
    line.trim();
    if (line.length()) run(line);
  }
}

void SerialCommands::run(String line) {
  String l = line;
  l.toLowerCase();
  if (l == "help" || l == "?") { printHelp(); return; }
  if (l == "status") {
    _p.scale.printStatus(); _p.nfc.printStatus(); _p.servo.printStatus(); _p.lid.printStatus();
    _p.rfid.printStatus();
    if (_p.lcd.available()) LOG("LCD", "LCD at 0x%02X", _p.lcd.address()); else LOG("LCD", "no LCD");
#if BIN_MODE == FULL_SYSTEM_MODE
    _p.wifi.printStatus();
#endif
    LOG("SYSTEM", "Faults: %s | uptime %lu s | free heap %u", _p.faults.describe().c_str(),
        (unsigned long)(millis() / 1000), (unsigned)ESP.getFreeHeap());
    if (_tx) _tx->printStatus();
    return;
  }
  if (l == "i2c") { i2cScan(true); return; }
  if (l == "selftest") { runVerificationSelfTest(); return; }
  if (l == "fault") { LOG("SYSTEM", "Faults: %s", _p.faults.describe().c_str()); return; }
  if (l == "fault clear") {
    _p.faults.clear(FAULT_LID_OPEN_TIMEOUT); _p.faults.clear(FAULT_LID_CLOSE_TIMEOUT);
    _p.servo.clearLockout(); return;
  }
  if (l == "reboot") { LOG("SYSTEM", "Rebooting"); delay(100); ESP.restart(); }

  // load cell
  if (l == "tare") { _p.scale.tare(); return; }
  if (l.startsWith("cal ")) { _p.scale.calibrate(l.substring(4).toFloat()); return; }
  if (l == "show") { _p.scale.printStatus(); return; }
  if (l == "watch on") { watchScale = true; return; }
  if (l == "watch off") { watchScale = false; return; }
  if (l == "calclear") { _p.scale.clearCalibration(); return; }

  // lcd
  if (l.startsWith("lcd ")) {
    if (!_p.lcd.available()) { LOG("LCD", "no LCD"); return; }
    String t = line.substring(4);
    _p.lcd.show(t.substring(0, 16), t.length() > 16 ? t.substring(16, 32) : String(""));
    LOG("LCD", "Shown: \"%s\"", t.c_str());
    return;
  }

  if (l == "nfc") { _p.nfc.printStatus(); return; }
  if (l == "reed") { _p.lid.printStatus(); return; }
  if (l == "rfid status") { _p.rfid.printStatus(); return; }
  if (l == "rfid scan") {
    if (!_p.rfid.startInventory()) LOG("RFID", "Not started: %s", rfidStatusName(_p.rfid.status()));
    return;
  }

  // servo (moves only on these commands)
  if (l.startsWith("servo")) {
    String a = l.substring(5); a.trim();
    if (a == "status") { _p.servo.printStatus(); return; }
    if (a == "stop") { _p.servo.stop(); return; }
    if (a == "center") { _p.servo.manualAngle(90); return; }
    if (a == "clear") { _p.servo.clearLockout(); _p.faults.clear(FAULT_LID_OPEN_TIMEOUT); return; }
    if (a == "open") { if (!_p.servo.open() && !_p.servo.calibrated()) LOG("SERVO", "Use 'servo angle <n>' to find the angles, then 'servo set ...'"); return; }
    if (a == "close" || a == "release") { _p.servo.release(); return; }
    if (a.startsWith("angle ")) { _p.servo.manualAngle(a.substring(6).toInt()); return; }
    if (a.startsWith("set idle ")) { _p.servo.setIdleAngle(a.substring(9).toInt()); return; }
    if (a.startsWith("set open ")) { _p.servo.setOpenAngle(a.substring(9).toInt()); return; }
  }
  LOG("SYSTEM", "Unknown command \"%s\" - type help", line.c_str());
}

// ---------------------------------------------------------------- tests --
void HardwareTests::begin() {
  LOG("SYSTEM", "HARDWARE_TEST_MODE - enabled tests:%s%s%s%s%s%s",
#ifdef ENABLE_LOAD_CELL_TEST
      " LOAD_CELL",
#else
      "",
#endif
#ifdef ENABLE_LCD_TEST
      " LCD",
#else
      "",
#endif
#ifdef ENABLE_NFC_TEST
      " NFC",
#else
      "",
#endif
#ifdef ENABLE_SERVO_TEST
      " SERVO",
#else
      "",
#endif
#ifdef ENABLE_REED_TEST
      " REED",
#else
      "",
#endif
#ifdef ENABLE_RFID_TEST
      " RFID"
#else
      ""
#endif
  );
  LOG("SYSTEM", "Wi-Fi and the portal are OFF in this mode. The servo moves only on a servo command.");
  _cmd.printHelp();
}

void HardwareTests::update() {
  uint32_t now = millis();
#ifdef ENABLE_LOAD_CELL_TEST
  WeightState kind; float d;
  if (_p.scale.takeChange(&kind, &d)) { /* logged by the manager */ }
  if (_cmd.watchScale && now - _lastScaleMs >= 500) {
    _lastScaleMs = now;
    if (!_p.scale.available()) LOG("LOADCELL", "HX711 not responding");
    else if (!_p.scale.calibrated()) LOG("LOADCELL", "raw %.0f (not calibrated)", _p.scale.raw());
    else LOG("LOADCELL", "raw %.0f | %.1f g | %.3f kg | spread %.1f g | %s", _p.scale.raw(), _p.scale.grams(),
             _p.scale.kilograms(), _p.scale.spreadGrams(), weightStateName(_p.scale.state()));
  }
#endif
#ifdef ENABLE_LCD_TEST
  if (_p.lcd.available() && now - _lastLcdMs >= 1000) {
    _lastLcdMs = now;
    char l2[17];
    snprintf(l2, sizeof(l2), "0x%02X up %lus", _p.lcd.address(), (unsigned long)(now / 1000));
    _p.lcd.show("LCD TEST OK", l2);       // only the changed characters' line is rewritten
  }
#endif
#ifdef ENABLE_NFC_TEST
  NfcScan s;
  _p.nfc.poll(&s);                        // logs UID, length and time
#endif
#ifdef ENABLE_REED_TEST
  if (now - _lastReedMs >= 1000) { _lastReedMs = now; LOG("REED", "%s", lidStateName(_p.lid.state())); }
#endif
#ifdef ENABLE_RFID_TEST
  if (_p.rfid.enabled() && !_p.rfid.busy() && now - _lastRfidMs >= 3000) { _lastRfidMs = now; _p.rfid.startInventory(); }
#endif
  (void)now;
}
