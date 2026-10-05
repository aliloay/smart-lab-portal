// ===========================================================================
// ENVIRONMENT NODE - configuration. Every pin, interval and threshold lives
// here; nothing else in the firmware hard-codes a number.
//
// Words used below:
//   VERIFY   - not yet confirmed on the actual module; measure before trusting
//   START    - a starting value chosen on paper, to be tuned on the bench
//   DATASHEET- taken from the part's datasheet, not measured here
// ===========================================================================
#pragma once
#include <Arduino.h>
#include <WiFi.h>

// --- identity --------------------------------------------------------------
#define NODE_NAME        "ENVIRONMENT_NODE"
#define FIRMWARE_VERSION "0.1.0"
// The portal knows this node as ENV_LAB01 and issued its device key for that
// name (secrets.h). Another id would be refused by the portal.
static const char *DEVICE_ID = "ENV_LAB01";
// BENCH = the home bring-up bench (its data stays apart from the lab's).
// "LAB_01" once the node is installed in the Robotics Lab.
static const char *LAB_ID = "LAB_01";   // moved from BENCH 2026-10-05: same lab as the door (emergency controls)

// --- modes -------------------------------------------------------------------
// LOCAL TEST MODE: readings, events and health go to Serial only; nothing is
// sent to the portal. Set false only at bring-up phase 9 (backend).
constexpr bool LOCAL_TEST_MODE = false;   // phase 9 (2026-10-05): reporting to the portal
// Wi-Fi is separate from the backend, so it can be tested in local mode.
constexpr bool WIFI_ENABLED = true;

// --- which sensors are wired: DEFAULTS only ------------------------------------
// At run time "fit <sensor> on|off" changes these and keeps the choice in
// flash, so bring-up goes one sensor at a time without re-flashing. An input
// that is enabled with nothing connected reports nonsense, so everything
// starts OFF.
constexpr bool DEFAULT_FIT_DHT   = false;
constexpr bool DEFAULT_FIT_PIR1  = false;
constexpr bool DEFAULT_FIT_PIR2  = false;
constexpr bool DEFAULT_FIT_MQ    = false;   // MQ-2 AO (through the divider)
constexpr bool DEFAULT_FIT_MQ_DO = false;   // MQ-2 DO - optional, needs its own divider
constexpr bool DEFAULT_FIT_FLAME = false;   // all five channels of the round board

// --- pins: ESP32-WROOM-32 DevKit (no PSRAM: confirmed from the boot log) -----
// Not used, and why: 0, 2, 5, 12, 15 boot-strapping; 6-11 the flash chip;
// 1, 3 the USB serial; 14 drives a PWM signal at boot (a sensor output must
// not fight it). 34-39 are inputs only and have no internal pull resistors.
// Analog inputs use ADC1 (GPIO 32-39): ADC2 cannot be read while Wi-Fi is on.
constexpr uint8_t PIN_DHT   = 4;    // DHT22 "out" (digital, bidirectional)
constexpr uint8_t PIN_PIR1  = 27;   // PIR 1 OUT  - zone 1
constexpr uint8_t PIN_PIR2  = 26;   // PIR 2 OUT  - zone 2
constexpr uint8_t PIN_MQ_AO = 39;   // MQ-2 AO through the 10k/15k divider (ADC1_CH3, "VN"); was 34 - noisy on the bench
constexpr uint8_t PIN_MQ_DO = 25;   // MQ-2 DO - only through its own divider
// Round flame board, header pins D1A1..D5A5, board at 3.3 V. MEASURED on the
// bench (2026-10-05): D1A1 is a comparator output (3.3 V idle, 0 V on flame);
// D2A2..D5A5 are ANALOG (~0 V idle, rising with IR: 0.17-0.32 V with a lighter
// at 30-50 cm, 3.15 V once). So channel 1 is read digitally, 2-5 on ADC1 pins
// (ADC1 keeps working while Wi-Fi is on).
constexpr uint8_t PIN_FLAME[5]       = {13, 32, 33, 35, 36};
constexpr bool    FLAME_IS_ANALOG[5] = {false, true, true, true, true};

// --- DHT22 ---------------------------------------------------------------------
constexpr uint32_t DHT_INTERVAL_MS = 2500;   // DATASHEET: at most one reading per 2 s
constexpr uint8_t  DHT_FAIL_LIMIT  = 3;      // failed reads in a row -> ERROR
constexpr uint32_t DHT_STALE_MS    = 15000;  // last valid reading older -> not valid
constexpr float    DHT_MIN_C = -40.0f, DHT_MAX_C = 80.0f;   // DATASHEET range
constexpr float    TEMP_HIGH_C    = 35.0f;   // START (lab policy)
constexpr float    TEMP_NORMAL_C  = 33.0f;   // back to normal below this
constexpr float    HUM_HIGH_PCT   = 70.0f;   // START
constexpr float    HUM_NORMAL_PCT = 65.0f;

// --- PIR (HC-SR501 type) ---------------------------------------------------------
constexpr int      PIR_ACTIVE_LEVEL = HIGH;   // OUT high = motion (VERIFY by measuring)
constexpr uint32_t PIR_WARMUP_MS    = 60000;  // settles about 1 min after power-up (VERIFY)
constexpr uint32_t PIR_DEBOUNCE_MS  = 100;
constexpr uint32_t PIR_HOLD_MS      = 5000;   // added to the module's own delay (Tx pot)

// --- flame (round 5-channel board) --------------------------------------------
constexpr int      FLAME_ACTIVE_LEVEL       = LOW;   // VERIFY by measuring each output
constexpr uint32_t FLAME_SAMPLE_INTERVAL_MS = 10;
constexpr uint32_t FLAME_WINDOW_MS          = 300;   // look-back window (<= 640 ms)
constexpr uint8_t  FLAME_CONFIRM_PCT        = 40;    // % of window samples that saw IR
constexpr uint32_t FLAME_CLEAR_MS           = 3000;  // no IR sample for this long -> cleared
// Analog channels: IR raises the voltage. START value between the measured
// idle (~0 V) and lighter readings - to be tuned from the logged CSV,flame data.
constexpr uint16_t FLAME_ANALOG_THRESHOLD_MV = 160;


// --- MQ-2 -----------------------------------------------------------------------
constexpr uint32_t MQ_SAMPLE_INTERVAL_MS = 100;
constexpr uint8_t  MQ_FILTER_WINDOW      = 10;      // moving average: 10 x 100 ms = 1 s
constexpr uint32_t MQ_WARMUP_MS          = 180000;  // PROTOTYPE warm-up after each power-on
constexpr uint32_t MQ_BASELINE_MS        = 30000;   // clean-air average after the warm-up
constexpr float    MQ_DIVIDER_RATIO      = 0.6f;    // 15k / (10k + 15k): pin = AO x 0.6
constexpr float    MQ_WARNING_RATIO      = 1.5f;    // filtered / baseline - START
constexpr float    MQ_CRITICAL_RATIO     = 2.0f;    // START
constexpr float    MQ_WARNING_CLEAR_RATIO  = 1.3f;  // hysteresis on the way down
constexpr float    MQ_CRITICAL_CLEAR_RATIO = 1.8f;
constexpr uint32_t MQ_RISE_CONFIRM_MS    = 500;     // a worse level must hold this long
constexpr uint32_t MQ_FALL_CONFIRM_MS    = 5000;    // a better level must hold this long
constexpr uint16_t MQ_ABS_CRITICAL_PIN_MV = 2800;   // CRITICAL whatever the baseline (AO ~4.7 V)
constexpr uint16_t MQ_SATURATION_RAW     = 4050;    // ADC at full scale -> CRITICAL at once
constexpr uint16_t MQ_FAULT_LOW_PIN_MV   = 50;      // ~0 V at the pin: AO wire off / no power
constexpr uint32_t MQ_FAULT_MS           = 5000;
constexpr uint32_t MQ_LOG_INTERVAL_MS    = 1000;    // CSV,mq line (warm-up curve, drift)
constexpr int      MQ_DO_ACTIVE_LEVEL    = LOW;     // VERIFY
constexpr uint32_t MQ_DO_DEBOUNCE_MS     = 200;

// --- reporting and network ---------------------------------------------------------
constexpr uint32_t DIAG_INTERVAL_MS           = 10000;  // one-line status on Serial
constexpr uint32_t SNAPSHOT_INTERVAL_MS       = 30000;  // full JSON snapshot
constexpr uint32_t HEARTBEAT_INTERVAL_MS      = 30000;  // backend mode only
constexpr uint32_t WIFI_RECONNECT_INTERVAL_MS = 10000;
constexpr uint32_t HTTP_TIMEOUT_MS            = 2500;   // network task only
constexpr uint8_t  EVENT_QUEUE_LEN            = 32;
static const char *BACKEND_HOST = "192.168.1.200";      // the lab laptop
constexpr uint16_t BACKEND_PORT = 8000;
// Fixed address on the lab network, as in the architecture plan.
static const IPAddress LOCAL_IP(192, 168, 1, 152), GATEWAY(192, 168, 1, 1),
                       SUBNET(255, 255, 255, 0);
