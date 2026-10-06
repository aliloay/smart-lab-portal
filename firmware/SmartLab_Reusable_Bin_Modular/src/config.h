// ===========================================================================
// SMART LAB - REUSABLE EQUIPMENT BIN - configuration (the ONLY file to edit)
// ===========================================================================
// Every value marked VERIFY is a placeholder that must be measured on the
// real bin. Nothing here is a measured result. Unknown hardware (the old
// RFID reader) stays disabled until its model is identified.
// ===========================================================================
#pragma once
#include <Arduino.h>

// ---------------------------------------------------------------- mode -----
// HARDWARE_TEST_MODE : bring-up. Only the components enabled below are
//                      started; each can be tested alone from the Serial
//                      Monitor (115200 baud, "Newline"). The servo NEVER
//                      moves unless you type a servo command.
// FULL_SYSTEM_MODE   : the complete bin (Wi-Fi, portal, transactions).
#define HARDWARE_TEST_MODE 1
#define FULL_SYSTEM_MODE   2
#ifndef BIN_MODE                       // (a build can also pass -DBIN_MODE=2)
#define BIN_MODE HARDWARE_TEST_MODE
#endif

// ------------------------------------------- which parts are connected -----
// HARDWARE_TEST_MODE: comment a line out = that part is not started at all,
// so a missing part can never block testing another one.
#define ENABLE_LOAD_CELL_TEST
// #define ENABLE_LCD_TEST
// #define ENABLE_NFC_TEST
// #define ENABLE_SERVO_TEST
// #define ENABLE_REED_TEST
// #define ENABLE_RFID_TEST        // needs RFID_READER_MODEL != RFID_NONE

// FULL_SYSTEM_MODE starts everything except the RFID reader, which stays
// optional (see RFID below).

// ---------------------------------------------------------------- pins -----
// Proposed pin map (change here only if the wiring is different).
constexpr uint8_t PIN_HX711_DT  = 32;
constexpr uint8_t PIN_HX711_SCK = 33;
constexpr uint8_t PIN_I2C_SDA   = 21;   // LCD backpack + PN532 share this bus
constexpr uint8_t PIN_I2C_SCL   = 22;
constexpr uint8_t PIN_SERVO     = 25;   // signal only - servo power from the external 5 V rail
constexpr uint8_t PIN_REED      = 27;   // reed between this pin and GND, internal pull-up
// The 3.3 V I2C pins must never see 5 V: measure the LCD backpack's SDA/SCL
// pull-up voltage before connecting it (hardware decision, not firmware).

// ----------------------------------------------------------- load cell -----
// No calibration factor is assumed. Until "cal <grams>" is run, only raw
// counts are reported and every weight is "not calibrated".
constexpr uint8_t  WEIGHT_SAMPLE_COUNT          = 10;     // moving window (samples)
constexpr float    WEIGHT_STABILITY_THRESHOLD_G = 2.0f;   // VERIFY: max spread in the window to call it stable
constexpr uint32_t WEIGHT_STABLE_TIME_MS        = 1000;   // VERIFY: spread must hold this long
constexpr float    WEIGHT_CHANGE_THRESHOLD_G    = 10.0f;  // VERIFY: smaller changes are "no change"
constexpr uint32_t HX711_READY_TIMEOUT_MS       = 1500;   // no sample this long = HX711 unavailable
constexpr uint32_t WEIGH_BEFORE_TIMEOUT_MS      = 3000;   // wait this long for a stable "before"
constexpr uint32_t WEIGH_AFTER_TIMEOUT_MS       = 6000;   // the bin swings after the lid closes

// ----------------------------------------------------------------- LCD -----
// 0 = find it with an I2C scan (0x20-0x27, 0x38-0x3F, never PN532_ADDR).
constexpr uint8_t  LCD_I2C_ADDRESS = 0;
constexpr uint8_t  LCD_COLS = 16, LCD_ROWS = 2;
constexpr uint32_t LCD_MESSAGE_MS  = 4000;   // a result stays on screen this long

// ----------------------------------------------------------------- NFC -----
constexpr uint8_t  PN532_ADDR   = 0x24;   // what the PN532 answers on in I2C mode
constexpr uint32_t NFC_POLL_INTERVAL_MS = 200;    // how often to look for a tag
constexpr uint16_t NFC_READ_TIMEOUT_MS  = 60;     // per look (keeps the loop responsive)
constexpr uint32_t NFC_DUPLICATE_MS     = 3000;   // same UID again within this = ignored

// --------------------------------------------------------------- servo -----
// The angles are NOT known. They are set on the real pedal with
//   servo angle <n>       (move, test mode)
//   servo set idle <n>    servo set open <n>   (saved in flash)
// FULL_SYSTEM_MODE refuses to open the lid until both are saved.
constexpr int      SERVO_SAFE_MIN_ANGLE = 0;
constexpr int      SERVO_SAFE_MAX_ANGLE = 180;
constexpr int      SERVO_PULSE_MIN_US   = 500;    // MG90S range used by ESP32Servo
constexpr int      SERVO_PULSE_MAX_US   = 2400;
constexpr uint32_t SERVO_MOVE_MS        = 600;    // VERIFY: time to reach an angle
constexpr uint32_t SERVO_MAX_HOLD_MS    = 15000;  // never hold the pedal longer than this
constexpr uint32_t OPEN_HOLD_MS         = 8000;   // VERIFY: lid kept open for the item

// ---------------------------------------------------------- reed / lid -----
constexpr int      REED_LEVEL_WHEN_CLOSED = LOW;  // VERIFY: magnet at the reed when the lid is closed
constexpr uint32_t REED_DEBOUNCE_MS       = 50;
constexpr uint32_t LID_OPEN_TIMEOUT_MS    = 3000; // reed must show OPEN after the press
constexpr uint32_t LID_CLOSE_TIMEOUT_MS   = 8000; // and CLOSED after the release

// ---------------------------------------------------------------- RFID -----
// The old RFID reader's model, interface, voltage, pins, range and multi-tag
// ability are UNKNOWN. Nothing is assumed: with RFID_NONE the firmware
// compiles and runs without it, and reports RFID_DISABLED.
// To add the reader once identified: see src/RFIDManager.h ("Adding a reader").
#define RFID_NONE 0
#define RFID_READER_MODEL RFID_NONE
constexpr int      RFID_PIN_A = -1, RFID_PIN_B = -1, RFID_PIN_C = -1, RFID_PIN_D = -1;  // unknown
constexpr uint32_t RFID_INVENTORY_WINDOW_MS = 1500;  // VERIFY: read repeatedly for this long, union of tags

// ------------------------------------------------------- network/portal ----
// The portal's REAL endpoints (backend/app/api/routes/reusable.py and
// access.py). Paths live here so they can change without touching the code.
const char *const BACKEND_HOST = "192.168.1.200";   // the laptop on the Smart_Lab router
constexpr uint16_t BACKEND_PORT = 8000;
const char *const PATH_HEARTBEAT      = "/api/access/heartbeat";
const char *const PATH_NFC_SCAN       = "/api/reusable/scan";
const char *const PATH_RETURN_DONE    = "/api/reusable/complete";
const char *const PATH_COMMAND_NEXT   = "/api/access/commands/next";        // ?device_uid=
const char *const PATH_COMMAND_STATUS = "/api/access/commands/%ld/progress";
const char *const PATH_RFID_INVENTORY = "";   // no portal endpoint yet: inventories are only logged

const char *const DEVICE_ID = "REUSE_BIN_1";
const char *const LAB_ID    = "BENCH";        // "LAB_01" once installed in the Robotics Lab
const char *const FIRMWARE_VERSION = "reuse-mod-0.1";
// Fixed address on the Smart_Lab router (as the old bin firmware: .154).
#define USE_STATIC_IP 1
constexpr uint8_t STATIC_IP[4] = {192, 168, 1, 154}, GATEWAY_IP[4] = {192, 168, 1, 1},
                  SUBNET_MASK[4] = {255, 255, 255, 0};
constexpr uint32_t WIFI_RETRY_MS     = 10000;
constexpr uint32_t HTTP_TIMEOUT_MS   = 3000;
constexpr uint32_t HEARTBEAT_MS      = 30000;
constexpr uint32_t COMMAND_POLL_MS   = 2000;
constexpr uint32_t CHECKOUT_SCAN_TIMEOUT_MS = 60000;  // take the item, then scan it within this
// Wi-Fi name/password and this bin's own device key: src/secrets.h
// (gitignored; copy secrets.example.h). Never in this file.
