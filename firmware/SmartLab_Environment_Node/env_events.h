// ===========================================================================
// EVENTS - a state change worth telling someone about.
// Raised ONCE per change (never repeated while the state holds), printed at
// once, and - outside local test mode - queued for the network task, safety
// events ahead of everything else.
// ===========================================================================
#pragma once

enum EventType : uint8_t {
  EV_BOOT,
  EV_MOTION_STARTED, EV_MOTION_STOPPED,
  EV_FLAME_DETECTED, EV_FLAME_CLEARED,
  EV_GAS_WARNING, EV_GAS_CRITICAL, EV_GAS_NORMAL,
  EV_GAS_DO_ALARM, EV_GAS_DO_CLEAR,
  EV_TEMPERATURE_HIGH, EV_TEMPERATURE_NORMAL,
  EV_HUMIDITY_HIGH, EV_HUMIDITY_NORMAL,
  EV_SENSOR_READY, EV_SENSOR_FAILURE, EV_SENSOR_RECOVERED,
  EV_WIFI_CONNECTED, EV_WIFI_DISCONNECTED,
  EV_COUNT
};

static const char *const EVENT_NAMES[EV_COUNT] = {
  "BOOT",
  "MOTION_STARTED", "MOTION_STOPPED",
  "FLAME_DETECTED", "FLAME_CLEARED",
  "GAS_WARNING", "GAS_CRITICAL", "GAS_NORMAL",
  "GAS_DO_ALARM", "GAS_DO_CLEAR",
  "TEMPERATURE_HIGH", "TEMPERATURE_NORMAL",
  "HUMIDITY_HIGH", "HUMIDITY_NORMAL",
  "SENSOR_READY", "SENSOR_FAILURE", "SENSOR_RECOVERED",
  "WIFI_CONNECTED", "WIFI_DISCONNECTED",
};

// Safety events are sent before anything else.
bool eventIsSafety(EventType t) {
  return t == EV_FLAME_DETECTED || t == EV_GAS_WARNING || t == EV_GAS_CRITICAL ||
         t == EV_GAS_DO_ALARM || t == EV_SENSOR_FAILURE;
}

struct EnvEvent {
  uint32_t  ms;          // node millis() when it happened
  EventType type;
  char      source[12];  // "pir_1", "flame_3", "mq_1", "dht22", "wifi", "node"
  float     value;       // the value behind it, NAN when there is none
};

QueueHandle_t eventQueue = nullptr;   // loop() -> network task
uint32_t      eventsTotal = 0, eventsDropped = 0;

void emitEvent(EventType t, const char *source, float value = NAN) {
  EnvEvent e;
  e.ms = millis();
  e.type = t;
  strlcpy(e.source, source, sizeof(e.source));
  e.value = value;
  eventsTotal++;

  // For a person reading the monitor...
  Serial.printf("[EVENT] %-18s %-8s", EVENT_NAMES[t], e.source);
  if (!isnan(value)) Serial.printf(" value=%.2f", value);
  Serial.println(eventIsSafety(t) ? "   <-- SAFETY" : "");
  // ...and for the measurement log (tools/bringup/serial_log.py).
  if (isnan(value)) Serial.printf("CSV,event,%lu,%s,%s,\n", (unsigned long)e.ms, EVENT_NAMES[t], e.source);
  else Serial.printf("CSV,event,%lu,%s,%s,%.2f\n", (unsigned long)e.ms, EVENT_NAMES[t], e.source, value);

  // Local test mode sends nothing, so nothing is queued.
  if (LOCAL_TEST_MODE || !eventQueue) return;
  BaseType_t ok = eventIsSafety(t) ? xQueueSendToFront(eventQueue, &e, 0)
                                   : xQueueSendToBack(eventQueue, &e, 0);
  if (ok != pdTRUE) {
    eventsDropped++;
    Serial.println("[EVENT][WARN] event queue full - event not queued for the portal");
  }
}
