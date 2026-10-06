// HARDWARE_TEST_MODE: each enabled part is started and exercised on its own,
// plus the Serial Monitor command menu (also available in FULL_SYSTEM_MODE).
#pragma once
#include <Arduino.h>
#include "TransactionManager.h"

class SerialCommands {
 public:
  explicit SerialCommands(Parts p, TransactionManager *tx = nullptr) : _p(p), _tx(tx) {}
  void update();               // read and run commands
  void printHelp();
  bool watchScale = true;      // print the load cell every 500 ms (test mode)
 private:
  void run(String line);
  Parts _p;
  TransactionManager *_tx;
  String _buf;
};

class HardwareTests {
 public:
  explicit HardwareTests(Parts p, SerialCommands &cmd) : _p(p), _cmd(cmd) {}
  void begin();
  void update();
 private:
  Parts _p;
  SerialCommands &_cmd;
  uint32_t _lastScaleMs = 0, _lastLcdMs = 0, _lastReedMs = 0, _lastRfidMs = 0;
};
