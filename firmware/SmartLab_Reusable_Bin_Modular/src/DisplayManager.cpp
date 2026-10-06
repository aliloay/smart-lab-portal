#include "DisplayManager.h"
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include "config.h"
#include "Log.h"

bool i2cPresent(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

uint8_t i2cScan(bool print) {
  uint8_t found = 0;
  for (uint8_t a = 0x08; a < 0x78; a++) {
    if (!i2cPresent(a)) continue;
    found++;
    if (print) {
      const char *what = a == PN532_ADDR ? " (PN532 address)"
                       : (a >= 0x20 && a <= 0x27) || (a >= 0x38 && a <= 0x3F) ? " (LCD backpack range)" : "";
      LOG("I2C", "Device found at 0x%02X%s", a, what);
    }
  }
  if (print && !found) LOG("I2C", "No I2C device answered on SDA=GPIO%u SCL=GPIO%u", PIN_I2C_SDA, PIN_I2C_SCL);
  return found;
}

bool DisplayManager::begin() {
  uint8_t addr = LCD_I2C_ADDRESS;
  if (addr == 0) {
    for (uint8_t a = 0x20; a <= 0x3F && !addr; a++) {
      bool lcdRange = (a <= 0x27) || (a >= 0x38);
      if (lcdRange && a != PN532_ADDR && i2cPresent(a)) addr = a;
    }
  } else if (!i2cPresent(addr)) {
    addr = 0;
  }
  if (!addr) {
    LOG("ERROR", "LCD not found (no I2C device at 0x20-0x27 / 0x38-0x3F except 0x%02X)", PN532_ADDR);
    return false;
  }
  _addr = addr;
  _lcd = new LiquidCrystal_I2C(addr, LCD_COLS, LCD_ROWS);
  _lcd->init();
  _lcd->backlight();
  _row[0] = _row[1] = "\x01";        // force the first write
  LOG("LCD", "I2C device found at 0x%02X - LCD started", addr);
  show(_idle1, _idle2);
  return true;
}

void DisplayManager::write(uint8_t row, const String &text) {
  String t = text.substring(0, LCD_COLS);
  while (t.length() < LCD_COLS) t += ' ';
  if (t == _row[row]) return;          // unchanged: no rewrite, no flicker
  _row[row] = t;
  _lcd->setCursor(0, row);
  _lcd->print(t);
}

void DisplayManager::show(const String &line1, const String &line2) {
  _flashUntil = 0;
  if (!_lcd) return;
  write(0, line1);
  write(1, line2);
}

void DisplayManager::flash(const String &line1, const String &line2, uint32_t ms) {
  if (_lcd) { write(0, line1); write(1, line2); }
  _flashUntil = millis() + (ms ? ms : LCD_MESSAGE_MS);
  if (_flashUntil == 0) _flashUntil = 1;
}

void DisplayManager::setIdle(const String &line1, const String &line2) {
  _idle1 = line1; _idle2 = line2;
}

void DisplayManager::update() {
  if (_flashUntil && (int32_t)(millis() - _flashUntil) >= 0) {
    _flashUntil = 0;
    if (_lcd) { write(0, _idle1); write(1, _idle2); }
  }
}
