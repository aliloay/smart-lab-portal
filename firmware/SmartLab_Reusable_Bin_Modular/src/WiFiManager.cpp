#include "WiFiManager.h"
#include <WiFi.h>
#include "config.h"
#include "secrets.h"
#include "Log.h"

void WiFiManager::begin() {
  WiFi.mode(WIFI_STA);
  // 2026-11-17 lab: modem sleep made every report 100-300 ms slow and lost packets (ping: bins 144-161 ms / 10-50 % loss,
  // master + environment node, which already disable it, 13-14 ms / 0 %). Mains-powered node: keep the radio awake.
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
#if USE_STATIC_IP
  WiFi.config(IPAddress(STATIC_IP[0], STATIC_IP[1], STATIC_IP[2], STATIC_IP[3]),
              IPAddress(GATEWAY_IP[0], GATEWAY_IP[1], GATEWAY_IP[2], GATEWAY_IP[3]),
              IPAddress(SUBNET_MASK[0], SUBNET_MASK[1], SUBNET_MASK[2], SUBNET_MASK[3]));
#endif
  LOG("WIFI", "Connecting to \"%s\"...", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  _lastTryMs = millis();
}

bool WiFiManager::connected() const { return WiFi.status() == WL_CONNECTED; }

void WiFiManager::update() {
  bool now = connected();
  if (now != _was) {
    _was = now;
    if (now) LOG("WIFI", "Connected: %s, RSSI %d dBm", WiFi.localIP().toString().c_str(), (int)WiFi.RSSI());
    else LOG("WIFI", "Disconnected");
  }
  if (!now && millis() - _lastTryMs >= WIFI_RETRY_MS) {
    _lastTryMs = millis();
    LOG("WIFI", "Retrying...");
    WiFi.disconnect();
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    WiFi.setSleep(false);
  }
}

void WiFiManager::printStatus() {
  if (connected()) LOG("WIFI", "Connected to \"%s\" as %s, RSSI %d dBm", WIFI_SSID,
                       WiFi.localIP().toString().c_str(), (int)WiFi.RSSI());
  else LOG("WIFI", "Not connected (status %d)", (int)WiFi.status());
}
