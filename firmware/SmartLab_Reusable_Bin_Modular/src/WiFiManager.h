// Wi-Fi to the Smart_Lab router. Non-blocking: begin() starts connecting,
// update() retries every WIFI_RETRY_MS and logs every connect / drop.
#pragma once
#include <Arduino.h>

class WiFiManager {
 public:
  void begin();
  void update();
  bool connected() const;
  void printStatus();
 private:
  uint32_t _lastTryMs = 0;
  bool _was = false;
};
