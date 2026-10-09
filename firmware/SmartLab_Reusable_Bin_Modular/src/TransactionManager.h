// The bin's state machine (FULL_SYSTEM_MODE). The PORTAL authorises; the
// bin never opens on its own decision and never offline.
//
// RETURN (scan-driven)
//   IDLE --NFC scan--> WAITING_FOR_AUTHORIZATION --portal OPEN_FOR_RETURN-->
//   AUTHORIZED (weigh + RFID "before") --> OPENING (servo presses pedal,
//   reed must show OPEN) --> OPEN --> WAITING_FOR_USER (pedal held while the
//   item goes in) --> CLOSING (servo releases, reed must show CLOSED) -->
//   VERIFYING (weigh + RFID "after", local cross-check, POST /reusable/complete)
//   --> TRANSACTION_VERIFIED | TRANSACTION_FAILED (flagged) --> IDLE
//
// CHECKOUT (portal-driven: the person chose the item in the portal)
//   IDLE --OPEN_LID command--> AUTHORIZED --> ... same lid cycle ... -->
//   VERIFYING --> AWAITING_TAG_CONFIRMATION (the person scans the taken
//   item; the portal checks it is the chosen one, with the weight change)
//   --> TRANSACTION_VERIFIED | TRANSACTION_FAILED --> IDLE
//
// No portal = no authorisation: scans show "NO CONNECTION" (OFFLINE), the
// lid stays shut. Lid faults lock the servo out (FAULT) until staff clear them.
#pragma once
#include <Arduino.h>
#include "Verification.h"

class LoadCellManager; class DisplayManager; class NFCManager; class ServoManager;
class LidSensorManager; class RFIDManager; class WiFiManager; class BackendClient; class FaultManager;
struct NfcScan;

enum class BinState : uint8_t {
  BOOT, SELF_TEST, IDLE, WAITING_FOR_AUTHORIZATION, AUTHORIZED, OPENING, OPEN, WAITING_FOR_USER,
  CLOSING, VERIFYING, AWAITING_TAG_CONFIRMATION, TRANSACTION_VERIFIED, TRANSACTION_FAILED, FAULT, OFFLINE
};
const char *binStateName(BinState s);

struct Parts {
  LoadCellManager &scale; DisplayManager &lcd; NFCManager &nfc; ServoManager &servo;
  LidSensorManager &lid; RFIDManager &rfid; WiFiManager &wifi; BackendClient &portal; FaultManager &faults;
};

class TransactionManager {
 public:
  explicit TransactionManager(Parts p) : _p(p) {}
  void begin();          // after every part's begin(): self-test
  void update();         // call every loop()
  BinState state() const { return _state; }
  void printStatus();

 private:
  void go(BinState s);
  void idleTasks();
  void handleScan(const NfcScan &scan);
  void startCycle(TxKind kind);
  bool weighStable(uint32_t timeoutMs, float *grams);   // true when done (value or NAN)
  void finishVerifying();
  void finish(bool verified, const String &l1, const String &l2);
  void fail(const String &l1, const String &l2);
  String extraJson() const;
  void heartbeat();

  Parts _p;
  BinState _state = BinState::BOOT;
  uint32_t _enteredMs = 0, _lastHeartbeatMs = 0, _lastPollMs = 0;
  uint32_t _itemSeenMs = 0, _changeSinceMs = 0, _settledMs = 0, _lastMoveMs = 0;
  float _liveDeltaG = NAN;
  bool _rfidStarted = false;
  // the current transaction
  CycleObservation _obs;
  Verdict _verdict;
  String _uid, _assetTag, _assetName;   // name shown on the LCD (tag if the portal sent none)
  long _commandId = -1;
};
