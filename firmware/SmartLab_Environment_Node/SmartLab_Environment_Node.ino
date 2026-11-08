// ===========================================================================
// SMART LAB - ENVIRONMENT NODE (Robotics Lab, System 2)   ENVIRONMENT_NODE 0.1.0
// ===========================================================================
// A separate ESP32 from the door. It MONITORS ONLY: it senses, decides what
// the readings mean and reports them - it never switches anything. Not a
// certified fire or gas detector: the MQ-2 and the flame board are indicators.
//
// Sensors: DHT22 (temperature, humidity), two PIRs (motion, zones 1 and 2),
// MQ-2 (smoke/gas indication, analog through a divider), round 5-channel
// flame board. Wiring and bring-up steps: README.md in this folder.
//
// Files: env_config.h  every pin, interval and threshold
//        env_events.h  one event per state change, safety events first
//        env_sensors.h acquisition, filtering, debounce, health
//        env_network.h Wi-Fi + portal on their own task (never blocks sensing)
//        env_console.h Serial diagnostics, self-test, test commands
// Board: ESP32 Dev Module (ESP32-WROOM-32), esp32 core 3.3.11.
// Libraries: "DHT sensor library" + "Adafruit Unified Sensor" (Adafruit).
//
// Replaces the env-0.2 draft (never run on hardware). Kept from it: device
// id ENV_LAB01 and its key, lab BENCH, fixed IP .152, the portal endpoints
// and the CSV log lines. New: two PIRs, MQ-2 analog with warm-up and
// baseline, five flame channels, health, events, test commands, and no
// network call on the sensor loop.
// ===========================================================================
#include "env_config.h"
#include "secrets.h"     // WIFI_SSID, WIFI_PASS, DEVICE_KEY (gitignored)
#include "env_events.h"
#include "env_sensors.h"
#include "env_network.h"
#include "env_console.h"

void setup() {
  Serial.begin(115200);
  delay(300);                                  // let the USB serial settle
  bootMs = millis();
  printBanner();
  Serial.println("[INIT] Board initialized");

  analogReadResolution(12);
  eventQueue = xQueueCreate(EVENT_QUEUE_LEN, sizeof(EnvEvent));
  fitLoad();
  sensorsBegin(millis());
  printFitted();
  Serial.println("[INIT] Sensors initialized");

  networkBegin();
  if (WIFI_ENABLED) Serial.printf("[INIT] WiFi: connecting to \"%s\" as %s\n", WIFI_SSID, LOCAL_IP.toString().c_str());
  else Serial.println("[INIT] WiFi: disabled");
  Serial.printf("[INIT] Backend: %s\n", LOCAL_TEST_MODE ? "LOCAL TEST MODE - nothing is sent" : "portal reporting ON");

  enableLoopWDT();                             // loop() stuck for > 5 s -> reset, reason logged
  emitEvent(EV_BOOT, "node");
  Serial.println("Type 'help' for the test commands.");
}

void loop() {
  uint32_t now = millis();
  sensorsUpdate(now);     // flame every 10 ms, MQ every 100 ms, DHT every 2.5 s
  wifiWatch(now);         // one event per Wi-Fi change
  publish(now);           // copy for the network task
  consoleUpdate(now);     // commands, live views, status line
  delay(1);
}
