---
type: "source-mirror"
source_kind: "source-code"
source_path: "firmware/SmartLab_Reusable_Bin_Modular/SmartLab_Reusable_Bin_Modular.ino"
source_hash: "19c0186cf8ca93058a267fe724a52a69b3415ac9c9c006b1d460a69d3397abe4"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `firmware/SmartLab_Reusable_Bin_Modular/SmartLab_Reusable_Bin_Modular.ino` - edit the original in the repository, not this note.

Systems: [[Reusables bin]]

```ino
// ===========================================================================
// SMART LAB - SMART REUSABLE EQUIPMENT BIN (modular firmware)      ESP32
// ===========================================================================
// Mode and connected parts: src/config.h. Wi-Fi and device key: src/secrets.h.
// Procedures, pin map, expected output: README.md in this folder.
//
// STATUS: compiled; NOT yet run on hardware. Every hardware value marked
// VERIFY in config.h must be measured on the real bin.
// ===========================================================================
#include <Wire.h>
#include "src/config.h"
#include "src/Log.h"
#include "src/LoadCellManager.h"
#include "src/DisplayManager.h"
#include "src/NFCManager.h"
#include "src/ServoManager.h"
#include "src/LidSensorManager.h"
#include "src/RFIDManager.h"
#include "src/WiFiManager.h"
#include "src/BackendClient.h"
#include "src/FaultManager.h"
#include "src/TransactionManager.h"
#include "src/HardwareTests.h"

LoadCellManager  scale;
DisplayManager   lcd;
NFCManager       nfc;
ServoManager     servo;
LidSensorManager lid;
RFIDManager      rfid;
WiFiManager      wifi;
BackendClient    portal;
FaultManager     faults;

Parts parts{scale, lcd, nfc, servo, lid, rfid, wifi, portal, faults};
TransactionManager tx(parts);
#if BIN_MODE == FULL_SYSTEM_MODE
SerialCommands commands(parts, &tx);
#else
SerialCommands commands(parts);
#endif
HardwareTests tests(parts, commands);

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  LOG("BOOT", "Smart Reusable Bin - %s - %s", FIRMWARE_VERSION,
      BIN_MODE == FULL_SYSTEM_MODE ? "FULL_SYSTEM_MODE" : "HARDWARE_TEST_MODE");

#if BIN_MODE == FULL_SYSTEM_MODE
  constexpr bool useScale = true, useLcd = true, useNfc = true, useServo = true, useReed = true, useRfid = true;
#else
  #ifdef ENABLE_LOAD_CELL_TEST
  constexpr bool useScale = true;
  #else
  constexpr bool useScale = false;
  #endif
  #ifdef ENABLE_LCD_TEST
  constexpr bool useLcd = true;
  #else
  constexpr bool useLcd = false;
  #endif
  #ifdef ENABLE_NFC_TEST
  constexpr bool useNfc = true;
  #else
  constexpr bool useNfc = false;
  #endif
  #ifdef ENABLE_SERVO_TEST
  constexpr bool useServo = true;
  #else
  constexpr bool useServo = false;
  #endif
  #ifdef ENABLE_REED_TEST
  constexpr bool useReed = true;
  #else
  constexpr bool useReed = false;
  #endif
  #ifdef ENABLE_RFID_TEST
  constexpr bool useRfid = true;
  #else
  constexpr bool useRfid = false;
  #endif
#endif

  if (useLcd || useNfc) {
    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
    Wire.setClock(100000);
    delay(1000);                         // the PN532 needs ~1 s after power-up
    i2cScan(true);
  }
  if (useScale) scale.begin(); else LOG("LOADCELL", "Not enabled");
  if (useLcd)   lcd.begin();   else LOG("LCD", "Not enabled");
  if (useNfc)   nfc.begin();   else LOG("NFC", "Not enabled");
  if (useReed)  lid.begin();   else LOG("REED", "Not enabled (lid state UNKNOWN)");
  if (useServo) servo.begin(); else LOG("SERVO", "Not enabled");
  if (useRfid)  rfid.begin();  else LOG("RFID", "Not enabled");

#if BIN_MODE == FULL_SYSTEM_MODE
  wifi.begin();
  uint32_t t0 = millis();
  while (millis() - t0 < 300) { lid.update(); delay(10); }   // first debounced lid reading
  tx.begin();
  LOG("SYSTEM", "Type 'help' for commands");
#else
  tests.begin();
#endif
}

void loop() {
  scale.update();
  lid.update();
  servo.update();
  rfid.update();
  lcd.update();
  commands.update();
#if BIN_MODE == FULL_SYSTEM_MODE
  wifi.update();
  tx.update();
#else
  tests.update();
#endif
}

```
