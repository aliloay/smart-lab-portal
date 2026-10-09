#include "TransactionManager.h"
#include "config.h"
#include "Log.h"
#include "LoadCellManager.h"
#include "DisplayManager.h"
#include "NFCManager.h"
#include "ServoManager.h"
#include "LidSensorManager.h"
#include "RFIDManager.h"
#include "WiFiManager.h"
#include "BackendClient.h"
#include "FaultManager.h"

const char *binStateName(BinState s) {
  static const char *N[] = {"BOOT", "SELF_TEST", "IDLE", "WAITING_FOR_AUTHORIZATION", "AUTHORIZED",
                            "OPENING", "OPEN", "WAITING_FOR_USER", "CLOSING", "VERIFYING",
                            "AWAITING_TAG_CONFIRMATION", "TRANSACTION_VERIFIED", "TRANSACTION_FAILED",
                            "FAULT", "OFFLINE"};
  return N[(uint8_t)s];
}

void TransactionManager::go(BinState s) {
  if (s == _state) return;
  LOG("TRANSACTION", "%s -> %s", binStateName(_state), binStateName(s));
  _state = s;
  _enteredMs = millis();
  _rfidStarted = false;
}

// ------------------------------------------------------------------ boot --
void TransactionManager::begin() {
  go(BinState::SELF_TEST);
  FaultManager &f = _p.faults;
  if (!_p.scale.available()) f.set(FAULT_HX711_UNAVAILABLE);
  else if (!_p.scale.calibrated()) f.set(FAULT_SCALE_NOT_CALIBRATED, "returns/checkouts are recorded without a weight check");
  if (!_p.lcd.available()) f.set(FAULT_LCD_UNAVAILABLE);
  if (!_p.nfc.available()) f.set(FAULT_PN532_UNAVAILABLE, "no scans possible");
  if (!_p.servo.calibrated()) f.set(FAULT_SERVO_NOT_SET, "the lid will not be opened");
  if (_p.lid.state() == LidState::LID_UNKNOWN) f.set(FAULT_REED_UNKNOWN, "lid state not confirmed");
  if (_p.rfid.status() == RfidStatus::RFID_ERROR) f.set(FAULT_RFID_ERROR);
  LOG("SYSTEM", "Self-test: faults %s; RFID %s", f.describe().c_str(), rfidStatusName(_p.rfid.status()));
  _p.lcd.setIdle("SMART BIN", "Ready");
  go(BinState::IDLE);
  LOG("SYSTEM", "READY");
}

// ------------------------------------------------------------------ loop --
void TransactionManager::update() {
  FaultManager &f = _p.faults;
  uint32_t el = millis() - _enteredMs;
  if (_p.wifi.connected()) f.clear(FAULT_WIFI_DOWN); else f.set(FAULT_WIFI_DOWN);
  if (_p.lid.state() != LidState::LID_UNKNOWN) f.clear(FAULT_REED_UNKNOWN);
  if (_p.scale.available()) f.clear(FAULT_HX711_UNAVAILABLE); else f.set(FAULT_HX711_UNAVAILABLE);

  switch (_state) {
    case BinState::IDLE:
    case BinState::OFFLINE:
    case BinState::FAULT:
      idleTasks();
      break;

    case BinState::AUTHORIZED: {           // weigh + inventory BEFORE opening
      if (!_rfidStarted) { _rfidStarted = true; _p.rfid.startInventory(); }
      float g;
      if (!weighStable(WEIGH_BEFORE_TIMEOUT_MS, &g) || _p.rfid.busy()) break;
      _obs.weightBeforeG = g;
      _obs.rfidUsed = _p.rfid.lastInventoryValid();
      if (_obs.rfidUsed) _obs.rfidBefore = _p.rfid.lastInventory();
      LOG("TRANSACTION", "Before: %s, RFID %s", fmtGrams(g).c_str(),
          _obs.rfidUsed ? _obs.rfidBefore.toString().c_str() : rfidStatusName(_p.rfid.status()));
      if (!_p.servo.open()) {
        if (_obs.kind == TxKind::RETURN) _p.portal.returnDone(_uid, false, false, g, NAN, extraJson());
        else _p.portal.commandStatus(_commandId, "FAILED", "LID_UNAVAILABLE", "The servo refused to move");
        fail("ERROR", "Lid unavailable");
        break;
      }
      go(BinState::OPENING);
      break;
    }

    case BinState::OPENING:                // only the reed says the lid opened
      if (_p.lid.state() == LidState::LID_OPEN) {
        _obs.lidOpened = true;
        _itemSeenMs = _changeSinceMs = _settledMs = 0;
        go(BinState::OPEN);
      } else if (el >= LID_OPEN_TIMEOUT_MS) {
        _p.servo.release();
        f.set(FAULT_LID_OPEN_TIMEOUT, "pedal pressed, reed never showed OPEN");
        _p.servo.lockout("lid did not open - check the pedal linkage, then 'servo clear'");
        _obs.lidOpened = false;
        if (_obs.kind == TxKind::RETURN) {
          _p.portal.returnDone(_uid, false, _p.lid.state() == LidState::LID_CLOSED, _obs.weightBeforeG, NAN, extraJson());
        } else {
          _p.portal.commandStatus(_commandId, "FAILED", "LID_NOT_OPENED", "The lid did not open");
        }
        fail("ERROR", "Lid did not open");
      }
      break;

    case BinState::OPEN:
      _p.lcd.show(_assetName.substring(0, 16), _obs.kind == TxKind::RETURN ? "PUT IT IN" : "TAKE IT OUT");
      go(BinState::WAITING_FOR_USER);
      break;

    case BinState::WAITING_FOR_USER: {     // lid open: wait for the item to go in / come out
      // Same rules as test mode: a change of LID_ITEM_MIN_CHANGE_G lasting
      // LID_CHANGE_HOLD_MS, then wait until it settles, then LID_HAND_CLEAR_MS
      // for the hand; no change for LID_MAX_OPEN_MS = close anyway.
      uint32_t now = millis();
      float g = _p.scale.grams();
      bool weighing = !isnan(g) && !isnan(_obs.weightBeforeG);
      bool changed = weighing && !_itemSeenMs && fabsf(g - _obs.weightBeforeG) >= LID_ITEM_MIN_CHANGE_G;
      if (!changed) _changeSinceMs = 0; else if (!_changeSinceMs) _changeSinceMs = now;
      if (changed && now - _changeSinceMs >= LID_CHANGE_HOLD_MS) { _itemSeenMs = now; _settledMs = 0; _liveDeltaG = NAN; }
      if (_itemSeenMs && !_settledMs) {
        float d = g - _obs.weightBeforeG;
        if (isnan(_liveDeltaG) || fabsf(d - _liveDeltaG) >= LID_SETTLE_BAND_G) {
          _liveDeltaG = d; _lastMoveMs = now;
          char l2[17]; snprintf(l2, sizeof l2, "%s %+.1f g", d > 0 ? "IN" : "OUT", d);
          _p.lcd.show(_assetName.substring(0, 16), l2);
        } else if (now - _lastMoveMs >= LID_SETTLE_MS) {
          _settledMs = now;
          LOG("TRANSACTION", "Weight settled at %+.1f g", _liveDeltaG);
        }
      }
      bool handClear = _settledMs && now - _settledMs >= LID_HAND_CLEAR_MS;
      bool tooLong = !_itemSeenMs ? el >= LID_MAX_OPEN_MS
                                  : (!_settledMs && now - _itemSeenMs >= LID_MAX_OPEN_MS);
      if (handClear || tooLong || el >= SERVO_MAX_HOLD_MS) {
        if (!handClear) LOG("TRANSACTION", "No (settled) weight change: closing");
        _p.servo.release();
        _p.lcd.show(_assetName.substring(0, 16), "BIN CLOSING");
        go(BinState::CLOSING);
      }
      break;
    }

    case BinState::CLOSING:
      if (_p.lid.state() == LidState::LID_CLOSED && _p.servo.idle()) {
        _obs.lidClosed = true;
        _p.lcd.show("VERIFYING", "Please wait...");
        go(BinState::VERIFYING);
      } else if (el >= LID_CLOSE_TIMEOUT_MS && !_p.faults.has(FAULT_LID_CLOSE_TIMEOUT)) {
        f.set(FAULT_LID_CLOSE_TIMEOUT, "released, reed never showed CLOSED");
        _p.lcd.show("LID OPEN", "Please close");
        _obs.lidClosed = false;
        go(BinState::VERIFYING);           // report what happened; the lid is watched from IDLE
      }
      break;

    case BinState::VERIFYING: {            // weigh + inventory AFTER closing
      if (_obs.lidClosed && !_rfidStarted) { _rfidStarted = true; _p.rfid.startInventory(); }
      float g = NAN;
      if (_obs.lidClosed && (!weighStable(WEIGH_AFTER_TIMEOUT_MS, &g) || _p.rfid.busy())) break;
      _obs.weightAfterG = g;
      if (_obs.rfidUsed && _obs.lidClosed && _p.rfid.lastInventoryValid()) _obs.rfidAfter = _p.rfid.lastInventory();
      else _obs.rfidUsed = false;
      finishVerifying();
      break;
    }

    case BinState::AWAITING_TAG_CONFIRMATION: {
      NfcScan s;
      if (_p.nfc.poll(&s)) {
        _p.lcd.show("VERIFYING", "Please wait...");
        ScanReply r = _p.portal.scan(s.uid, _verdict.deltaG, extraJson());
        if (!r.ok) { _p.lcd.show("NO CONNECTION", "Scan again"); break; }
        if (r.action == "CHECKOUT_OK") {
          bool ok = _verdict.verified && r.weightCheck != "MISMATCH";
          finish(ok, r.lcd1, ok ? r.lcd2 : String("CHECK NEEDED"));
        } else if (r.action == "WRONG_ITEM") {
          _p.lcd.show(r.lcd1, r.lcd2);     // keep waiting for the right tag
        } else {
          fail(r.lcd1.length() ? r.lcd1 : String("ERROR"), r.lcd2.length() ? r.lcd2 : String("Transaction Failed"));
        }
      } else if (el >= CHECKOUT_SCAN_TIMEOUT_MS) {
        fail("NOT CONFIRMED", "Call staff");
      }
      break;
    }

    case BinState::TRANSACTION_VERIFIED:
    case BinState::TRANSACTION_FAILED:
      if (el >= LCD_MESSAGE_MS) go(BinState::IDLE);
      break;

    default: break;
  }
}

void TransactionManager::idleTasks() {
  FaultManager &f = _p.faults;
  // A lid left open after a cycle: once it closes, that fault is over.
  if (f.has(FAULT_LID_CLOSE_TIMEOUT) && _p.lid.state() == LidState::LID_CLOSED) f.clear(FAULT_LID_CLOSE_TIMEOUT);
  if (_p.servo.calibrated()) f.clear(FAULT_SERVO_NOT_SET);
  if (!_p.servo.lockedOut()) f.clear(FAULT_LID_OPEN_TIMEOUT);

  BinState want = f.blocksLid() ? BinState::FAULT : !_p.wifi.connected() ? BinState::OFFLINE : BinState::IDLE;
  if (want != _state) go(want);
  if (_state == BinState::FAULT) _p.lcd.setIdle("FAULT", f.has(FAULT_LID_CLOSE_TIMEOUT) ? "Close the lid" : f.firstName());
  else if (_state == BinState::OFFLINE) _p.lcd.setIdle("SMART BIN", "Offline");
  else {
    // Idle: the total weight in the bin (all items), or "Ready" without a scale.
    float g = _p.scale.grams();
    char l2[17];
    if (isnan(g)) snprintf(l2, sizeof l2, "Ready");
    else snprintf(l2, sizeof l2, "%.1f g", g);
    _p.lcd.setIdle("SMART BIN", l2);
  }
  _p.lcd.update();

  NfcScan s;
  if (_p.nfc.poll(&s)) { handleScan(s); return; }

  // A settled weight change while idle, not right after a cycle: nobody asked.
  WeightState kind; float d;
  if (_p.scale.takeChange(&kind, &d) && _state == BinState::IDLE &&
      millis() - _enteredMs >= UNEXPLAINED_QUIET_MS && _p.wifi.connected()) {
    LOG("TRANSACTION", "Unexplained weight change %+.1f g", d);
    _p.portal.weightChange(d, _p.scale.grams());
  }

  if (!_p.wifi.connected()) return;
  uint32_t now = millis();
  if (now - _lastHeartbeatMs >= HEARTBEAT_MS || _lastHeartbeatMs == 0) heartbeat();
  if (_state == BinState::IDLE && now - _lastPollMs >= COMMAND_POLL_MS) {
    _lastPollMs = now;
    BinCommand c = _p.portal.nextCommand();
    if (_p.portal.reachable()) f.clear(FAULT_BACKEND_DOWN); else f.set(FAULT_BACKEND_DOWN);
    if (!c.present) return;
    if (c.command != "OPEN_LID") {
      _p.portal.commandStatus(c.id, "FAILED", "UNKNOWN_COMMAND", "Not a bin request");
      return;
    }
    _commandId = c.id;
    _assetTag = c.assetTag;
    _assetName = c.assetName.length() ? c.assetName : c.assetTag;
    _uid = "";
    _p.portal.commandStatus(c.id, "RUNNING", "OPENING", "Opening the lid");
    startCycle(TxKind::CHECKOUT);
  }
}

void TransactionManager::handleScan(const NfcScan &scan) {
  go(BinState::WAITING_FOR_AUTHORIZATION);
  _p.lcd.show("VERIFYING", "Please wait...");
  ScanReply r = _p.portal.scan(scan.uid, NAN, "");
  if (!r.ok) {
    _p.faults.set(FAULT_BACKEND_DOWN, r.httpCode == 401 ? "device key refused" : "no reply");
    _p.lcd.flash("NO CONNECTION", "Try again");      // never opens without the portal
    go(_p.wifi.connected() ? BinState::IDLE : BinState::OFFLINE);
    return;
  }
  _p.faults.clear(FAULT_BACKEND_DOWN);
  if (r.action == "OPEN_FOR_RETURN") {
    if (_p.faults.blocksLid()) {
      LOG("TRANSACTION", "Return authorised but the lid is unavailable (%s)", _p.faults.describe().c_str());
      _p.portal.returnDone(scan.uid, false, false, NAN, NAN, "");
      fail("ERROR", "Call staff");
      return;
    }
    _uid = scan.uid;
    _assetTag = r.assetTag;
    _assetName = r.assetName.length() ? r.assetName : r.assetTag;
    _commandId = -1;
    startCycle(TxKind::RETURN);
    return;
  }
  // UNKNOWN / NOT_ALLOWED / WRONG_ITEM / CHECKOUT_OK outside a cycle: show the portal's words.
  _p.lcd.flash(r.lcd1.length() ? r.lcd1 : String("UNKNOWN ITEM"), r.lcd2.length() ? r.lcd2 : String("Check asset"));
  go(BinState::IDLE);
}

void TransactionManager::startCycle(TxKind kind) {
  _obs = CycleObservation{kind};
  _verdict = Verdict();
  LOG("TRANSACTION", "%s authorised by the portal: %s", kind == TxKind::RETURN ? "RETURN" : "CHECKOUT",
      _assetTag.length() ? _assetTag.c_str() : _uid.c_str());
  // Line 1: what is happening, line 2: the item (e.g. "RETURN" / "Breadboard 1").
  _p.lcd.show(_assetName.substring(0, 16), "BIN OPENING!");
  go(BinState::AUTHORIZED);
}

bool TransactionManager::weighStable(uint32_t timeoutMs, float *grams) {
  *grams = NAN;
  if (!_p.scale.available() || !_p.scale.calibrated()) return true;     // not weighed
  if (_p.scale.stable()) { *grams = _p.scale.stableGrams(); return true; }
  return millis() - _enteredMs >= timeoutMs;                            // gave up: not weighed
}

void TransactionManager::finishVerifying() {
  _verdict = verifyCycle(_obs, WEIGHT_CHANGE_THRESHOLD_G);
  LOG("TRANSACTION", "After: %s, delta %s, RFID %s -> %s", fmtGrams(_obs.weightAfterG).c_str(),
      isnan(_verdict.deltaG) ? "n/a" : (String(_verdict.deltaG, 1) + " g").c_str(),
      _obs.rfidUsed ? ("removed " + _verdict.rfid.removed.toString() + " added " + _verdict.rfid.added.toString()).c_str()
                    : "not used",
      _verdict.summary().c_str());
  if (_obs.kind == TxKind::RETURN) {
    CompleteReply r = _p.portal.returnDone(_uid, _obs.lidOpened, _obs.lidClosed,
                                           _obs.weightBeforeG, _obs.weightAfterG, extraJson());
    if (!r.ok) { fail("NOT RECORDED", "Call staff"); return; }
    bool ok = r.recorded && _verdict.verified && r.weightCheck != "MISMATCH";
    if (ok) finish(true, "VERIFIED", "Transaction OK");
    else finish(false, r.lcd1.length() ? r.lcd1 : String("CHECK NEEDED"), r.lcd2.length() ? r.lcd2 : String("Staff review"));
  } else {
    // Checkout by weight: the portal compares before / after and records it.
    CompleteReply r = _p.portal.checkoutDone(_commandId, _obs.lidOpened, _obs.lidClosed,
                                             _obs.weightBeforeG, _obs.weightAfterG);
    if (!r.ok) { fail("NOT RECORDED", "Call staff"); return; }
    bool ok = r.recorded && r.weightCheck != "MISMATCH";
    finish(ok, r.lcd1.length() ? r.lcd1 : _assetName.substring(0, 16),
           r.lcd2.length() ? r.lcd2 : String(ok ? "ENJOY!" : "CHECK NEEDED"));
  }
}

void TransactionManager::finish(bool verified, const String &l1, const String &l2) {
  LOG("TRANSACTION", "%s: %s", verified ? "VERIFIED" : "FLAGGED FOR REVIEW", _verdict.summary().c_str());
  _p.lcd.show(l1, l2);
  go(verified ? BinState::TRANSACTION_VERIFIED : BinState::TRANSACTION_FAILED);
}

void TransactionManager::fail(const String &l1, const String &l2) {
  LOG("TRANSACTION", "FAILED: %s / %s", l1.c_str(), l2.c_str());
  _p.lcd.show(l1, l2);
  go(BinState::TRANSACTION_FAILED);
}

String TransactionManager::extraJson() const {
  String s = "\"local_verification\":{\"verdict\":\"" + _verdict.summary() + "\",\"flags\":" + _verdict.flagsJson() +
             ",\"rfid_used\":" + (_obs.rfidUsed ? "true" : "false");
  if (_obs.rfidUsed) s += ",\"rfid_removed\":" + _verdict.rfid.removed.toJsonArray() +
                          ",\"rfid_added\":" + _verdict.rfid.added.toJsonArray();
  return s + "}";
}

void TransactionManager::heartbeat() {
  _lastHeartbeatMs = millis();
  HeartbeatInfo h{_p.scale.available(), _p.scale.calibrated(), _p.nfc.available(), _p.lcd.available(),
                  _p.lid.fitted(), _p.servo.calibrated(), _p.servo.lockedOut(),
                  _p.lid.state() == LidState::LID_OPEN ? 1 : _p.lid.state() == LidState::LID_CLOSED ? 2 : 0,
                  rfidStatusName(_p.rfid.status()), "FULL_SYSTEM_MODE", _p.faults.firstName()};
  bool ok = _p.portal.heartbeat(h);
  if (ok) _p.faults.clear(FAULT_BACKEND_DOWN); else _p.faults.set(FAULT_BACKEND_DOWN);
}

void TransactionManager::printStatus() {
  LOG("TRANSACTION", "State %s | faults %s | last verdict %s", binStateName(_state),
      _p.faults.describe().c_str(), _verdict.summary().c_str());
}
