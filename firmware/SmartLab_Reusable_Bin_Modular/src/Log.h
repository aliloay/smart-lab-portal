// Serial log lines with a fixed prefix: [LOADCELL] [LCD] [NFC] [SERVO] [REED]
// [RFID] [WIFI] [BACKEND] [TRANSACTION] [ERROR] ... (115200 baud).
#pragma once
#include <Arduino.h>

#define LOG(tag, fmt, ...) Serial.printf("[" tag "] " fmt "\n", ##__VA_ARGS__)

inline String fmtGrams(float g) { return isnan(g) ? String("n/a") : String(g, 1) + " g"; }
