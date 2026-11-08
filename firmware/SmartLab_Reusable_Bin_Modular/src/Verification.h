// Local cross-check of one lid cycle: does what the sensors saw agree with
// the authorised action? Pure logic (no hardware): see "selftest".
//
//   AUTHORISED ACTION (RETURN / CHECKOUT, decided by the portal)
//   + lid confirmed OPEN then CLOSED (reed)
//   + weight change in the expected direction (load cell, if calibrated)
//   + RFID difference in the expected direction (only if RFID is available)
//   = VERIFIED, otherwise FLAGGED_FOR_REVIEW with every reason.
//
// Which item each RFID/NFC ID belongs to is the portal's knowledge, so
// "wrong item" and "unknown asset" are decided by the portal (and by
// expectedId below when the caller knows the expected RFID ID).
#pragma once
#include <Arduino.h>
#include "InventoryManager.h"

enum class TxKind : uint8_t { RETURN, CHECKOUT };

struct CycleObservation {
  TxKind kind;
  bool lidOpened = false, lidClosed = false;
  float weightBeforeG = NAN, weightAfterG = NAN;   // NAN = not weighed / not calibrated
  bool rfidUsed = false;                          // both inventories were taken
  Inventory rfidBefore, rfidAfter;
  String expectedRfidId;                          // optional: the authorised item's RFID ID
};

// Bit flags: why a cycle is not verified.
enum : uint16_t {
  F_LID_DID_NOT_OPEN   = 1 << 0,
  F_LID_LEFT_OPEN      = 1 << 1,
  F_NO_WEIGHT          = 1 << 2,   // not weighed: informational, does not flag by itself
  F_NO_WEIGHT_CHANGE   = 1 << 3,
  F_WEIGHT_WRONG_WAY   = 1 << 4,
  F_RFID_NO_CHANGE     = 1 << 5,
  F_RFID_WRONG_WAY     = 1 << 6,
  F_MULTIPLE_ITEMS     = 1 << 7,
  F_WRONG_ITEM         = 1 << 8,
  F_SENSOR_MISMATCH    = 1 << 9,   // RFID and load cell disagree
};

struct Verdict {
  bool verified = false;
  uint16_t flags = 0;
  float deltaG = NAN;               // after - before
  InventoryDiff rfid;
  String summary() const;           // "VERIFIED" or "FLAGGED: SENSOR_MISMATCH, ..."
  String flagsJson() const;         // ["SENSOR_MISMATCH", ...]
};

Verdict verifyCycle(const CycleObservation &o, float changeThresholdG);
bool runVerificationSelfTest();     // the spec's examples, PASS/FAIL on Serial
