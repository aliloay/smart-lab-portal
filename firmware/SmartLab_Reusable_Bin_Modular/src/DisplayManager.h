// 16x2 HD44780 LCD on an I2C backpack. The address is found by scanning
// (never assumed); with no LCD every call is a no-op, so nothing else is
// blocked. A line is only rewritten when its text changes (no flicker).
#pragma once
#include <Arduino.h>

class LiquidCrystal_I2C;

class DisplayManager {
 public:
  bool begin();                                  // Wire must already be started
  bool available() const { return _lcd != nullptr; }
  uint8_t address() const { return _addr; }
  void show(const String &line1, const String &line2);           // stays
  void flash(const String &line1, const String &line2,           // then back to the idle screen
             uint32_t ms = 0);
  void setIdle(const String &line1, const String &line2);
  void update();                                  // call every loop()

 private:
  void write(uint8_t row, const String &text);
  LiquidCrystal_I2C *_lcd = nullptr;
  uint8_t _addr = 0;
  String _row[2], _idle1 = "SMART BIN", _idle2 = "Ready";
  uint32_t _flashUntil = 0;
};

// Prints every device on the I2C bus; returns how many answered.
uint8_t i2cScan(bool print = true);
bool i2cPresent(uint8_t addr);
