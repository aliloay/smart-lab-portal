// ===========================================================================
// OPTIONAL I2C SENSORS (env 0.2.0) - SCD41 (CO2) and BH1750 (light).
// Both are OFF in env_config.h until the parts exist and a bench test passed.
// No extra library. Runs on the network task only: the safety sensors on
// loop() never wait on this bus.
// VERIFY before wiring: module pull-ups go to 3V3 (never 5 V) on GPIO 21/22.
// ===========================================================================
#pragma once
#include <Wire.h>

constexpr uint8_t ADDR_SCD41 = 0x62, ADDR_BH1750 = 0x23;

uint8_t crcSensirion(const uint8_t *d) {          // poly 0x31, start 0xFF (DATASHEET)
  uint8_t c = 0xFF;
  for (int i = 0; i < 2; i++) {
    c ^= d[i];
    for (int b = 0; b < 8; b++) c = (c & 0x80) ? (c << 1) ^ 0x31 : c << 1;
  }
  return c;
}

bool i2cCmd(uint8_t addr, const uint8_t *cmd, size_t n) {
  Wire.beginTransmission(addr);
  Wire.write(cmd, n);
  return Wire.endTransmission() == 0;
}

struct I2cState {
  bool     scdOk = false, luxOk = false, luxFresh = false;
  float    co2 = 0, lux = 0;
  uint32_t co2At = 0, luxAt = 0, nextTry = 0;
};
I2cState i2c;                                     // network task only

void scdStart() {
  const uint8_t stop[2] = {0x3F, 0x86}, start[2] = {0x21, 0xB1};
  i2cCmd(ADDR_SCD41, stop, 2);                    // it may still run after a reset of the ESP32 alone
  vTaskDelay(pdMS_TO_TICKS(510));                 // DATASHEET: 500 ms after stop
  i2c.scdOk = i2cCmd(ADDR_SCD41, start, 2);       // one new value every 5 s
}
void luxStart() { const uint8_t c = 0x10; i2c.luxOk = i2cCmd(ADDR_BH1750, &c, 1); i2c.luxAt = millis(); i2c.luxFresh = false; }

void i2cBegin() {
  if (!FIT_SCD41 && !FIT_BH1750) return;
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 100000);
  Wire.setTimeOut(50);                            // a stuck bus costs 50 ms of the network task, not more
  vTaskDelay(pdMS_TO_TICKS(1000));                // DATASHEET: SCD41 needs up to 1 s after power-on
  if (FIT_SCD41) scdStart();
  if (FIT_BH1750) luxStart();
}

// Poll about once a second. A sensor that does not answer is marked failed and
// tried again every 30 s; its old value is never sent as new.
void i2cPoll(uint32_t now) {
  static uint32_t last = 0;
  if ((!FIT_SCD41 && !FIT_BH1750) || now - last < 1000) return;
  last = now;
  if ((int32_t)(now - i2c.nextTry) >= 0) {
    if (FIT_SCD41 && !i2c.scdOk) scdStart();
    if (FIT_BH1750 && !i2c.luxOk) luxStart();
    i2c.nextTry = millis() + 30000;
  }
  if (FIT_SCD41 && i2c.scdOk) {
    const uint8_t ready[2] = {0xE4, 0xB8}, rd[2] = {0xEC, 0x05};
    uint8_t b[9];
    if (!i2cCmd(ADDR_SCD41, ready, 2)) i2c.scdOk = false;
    else {
      vTaskDelay(pdMS_TO_TICKS(2));
      if (Wire.requestFrom(ADDR_SCD41, (uint8_t)3) != 3) i2c.scdOk = false;
      else {
        for (int i = 0; i < 3; i++) b[i] = Wire.read();
        if (crcSensirion(b) == b[2] && (((b[0] << 8) | b[1]) & 0x07FF)) {
          if (!i2cCmd(ADDR_SCD41, rd, 2)) i2c.scdOk = false;
          else {
            vTaskDelay(pdMS_TO_TICKS(2));
            if (Wire.requestFrom(ADDR_SCD41, (uint8_t)9) != 9) i2c.scdOk = false;
            else {
              for (int i = 0; i < 9; i++) b[i] = Wire.read();
              uint16_t ppm = (b[0] << 8) | b[1];
              if (crcSensirion(b) == b[2] && ppm >= 400 && ppm <= 5000) { i2c.co2 = ppm; i2c.co2At = millis(); }
            }
          }
        }
      }
    }
  }
  if (FIT_BH1750 && i2c.luxOk && millis() - i2c.luxAt >= 200) {   // first conversion: up to 180 ms
    if (Wire.requestFrom(ADDR_BH1750, (uint8_t)2) != 2) i2c.luxOk = false;
    else { uint8_t hi = Wire.read(), lo = Wire.read(); i2c.lux = ((hi << 8) | lo) / 1.2f; i2c.luxAt = millis(); i2c.luxFresh = true; }
  }
}
bool co2Valid() { return FIT_SCD41 && i2c.scdOk && i2c.co2At && millis() - i2c.co2At < 30000; }
bool luxValid() { return FIT_BH1750 && i2c.luxOk && i2c.luxFresh && millis() - i2c.luxAt < 30000; }
