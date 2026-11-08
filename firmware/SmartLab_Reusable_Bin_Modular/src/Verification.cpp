#include "Verification.h"
#include "Log.h"

static const struct { uint16_t bit; const char *name; } FLAG_NAMES[] = {
  {F_LID_DID_NOT_OPEN, "LID_DID_NOT_OPEN"}, {F_LID_LEFT_OPEN, "LID_LEFT_OPEN"},
  {F_NO_WEIGHT, "NOT_WEIGHED"}, {F_NO_WEIGHT_CHANGE, "NO_WEIGHT_CHANGE"},
  {F_WEIGHT_WRONG_WAY, "WEIGHT_WRONG_DIRECTION"}, {F_RFID_NO_CHANGE, "RFID_NO_CHANGE"},
  {F_RFID_WRONG_WAY, "RFID_WRONG_DIRECTION"}, {F_MULTIPLE_ITEMS, "MULTIPLE_ITEMS_CHANGED"},
  {F_WRONG_ITEM, "WRONG_ITEM"}, {F_SENSOR_MISMATCH, "SENSOR_MISMATCH"},
};

String Verdict::summary() const {
  if (verified) return flags & F_NO_WEIGHT ? "VERIFIED (not weighed)" : "VERIFIED";
  String s = "FLAGGED:";
  for (auto &f : FLAG_NAMES) if (flags & f.bit && f.bit != F_NO_WEIGHT) { s += ' '; s += f.name; }
  return s;
}

String Verdict::flagsJson() const {
  String s = "[";
  bool first = true;
  for (auto &f : FLAG_NAMES) if (flags & f.bit) { if (!first) s += ','; s += '"'; s += f.name; s += '"'; first = false; }
  return s + "]";
}

Verdict verifyCycle(const CycleObservation &o, float thr) {
  Verdict v;
  const bool ret = o.kind == TxKind::RETURN;
  if (!o.lidOpened) v.flags |= F_LID_DID_NOT_OPEN;
  if (o.lidOpened && !o.lidClosed) v.flags |= F_LID_LEFT_OPEN;

  // Load cell: -1 decrease, 0 no change, +1 increase, 2 unknown.
  int w = 2;
  if (isnan(o.weightBeforeG) || isnan(o.weightAfterG)) {
    v.flags |= F_NO_WEIGHT;
  } else {
    v.deltaG = o.weightAfterG - o.weightBeforeG;
    w = v.deltaG >= thr ? 1 : v.deltaG <= -thr ? -1 : 0;
    if (w == 0) v.flags |= F_NO_WEIGHT_CHANGE;
    else if ((w == 1) != ret) v.flags |= F_WEIGHT_WRONG_WAY;
  }

  // RFID: only when both inventories exist.
  int r = 2;
  if (o.rfidUsed) {
    v.rfid = diffInventories(o.rfidBefore, o.rfidAfter);
    size_t in = v.rfid.added.size(), out = v.rfid.removed.size();
    r = (in && !out) ? 1 : (out && !in) ? -1 : (!in && !out) ? 0 : 3;   // 3 = both ways
    if (r == 0) v.flags |= F_RFID_NO_CHANGE;
    else if (r == 3 || (r == 1) != ret) v.flags |= F_RFID_WRONG_WAY;
    if (in + out > 1) v.flags |= F_MULTIPLE_ITEMS;
    if (o.expectedRfidId.length()) {
      const Inventory &moved = ret ? v.rfid.added : v.rfid.removed;
      if (moved.size() && !moved.contains(o.expectedRfidId)) v.flags |= F_WRONG_ITEM;
    }
    // The two sensors disagree about whether anything moved / which way.
    if (w != 2 && ((w == 0) != (r == 0) || (w != 0 && r != 0 && r != 3 && w != r)))
      v.flags |= F_SENSOR_MISMATCH;
  }
  v.verified = (v.flags & ~F_NO_WEIGHT) == 0;
  return v;
}

// --------------------------------------------------------------- selftest --
static Inventory inv(std::initializer_list<const char *> ids) {
  Inventory i;
  for (auto id : ids) i.add(id);
  return i;
}

static bool expect(const char *name, const Verdict &v, bool verified, uint16_t mustHave) {
  bool ok = v.verified == verified && (v.flags & mustHave) == mustHave;
  Serial.printf("  %s  %-44s -> %s\n", ok ? "PASS" : "FAIL", name, v.summary().c_str());
  return ok;
}

bool runVerificationSelfTest() {
  LOG("TRANSACTION", "Verification self-test (logic only, no hardware):");
  bool ok = true;
  const float T = 10.0f;
  CycleObservation o;

  // Spec example: before {A001,A002,A003}, take A001 -> after {A002,A003}.
  o = CycleObservation{TxKind::CHECKOUT};
  o.lidOpened = o.lidClosed = true; o.weightBeforeG = 500; o.weightAfterG = 420;
  o.rfidUsed = true; o.rfidBefore = inv({"A001", "A002", "A003"}); o.rfidAfter = inv({"A002", "A003"});
  o.expectedRfidId = "A001";
  Verdict v = verifyCycle(o, T);
  ok &= expect("checkout A001: removed {A001}, weight -80 g", v, true, 0);
  ok &= v.rfid.removed.toString() == "{A001}";

  // Return A001.
  o = CycleObservation{TxKind::RETURN};
  o.lidOpened = o.lidClosed = true; o.weightBeforeG = 420; o.weightAfterG = 500;
  o.rfidUsed = true; o.rfidBefore = inv({"A002", "A003"}); o.rfidAfter = inv({"A001", "A002", "A003"});
  o.expectedRfidId = "A001";
  ok &= expect("return A001: added {A001}, weight +80 g", verifyCycle(o, T), true, 0);

  // Multiple changes: before {A001,A002,B001,E001} -> after {A002,E001}.
  o = CycleObservation{TxKind::CHECKOUT};
  o.lidOpened = o.lidClosed = true; o.weightBeforeG = 900; o.weightAfterG = 700;
  o.rfidUsed = true; o.rfidBefore = inv({"A001", "A002", "B001", "E001"}); o.rfidAfter = inv({"A002", "E001"});
  v = verifyCycle(o, T);
  ok &= expect("two items removed {A001,B001}", v, false, F_MULTIPLE_ITEMS);
  ok &= v.rfid.removed.toString() == "{A001, B001}";

  // Wrong item: Arduino #1 requested, #2 removed.
  o = CycleObservation{TxKind::CHECKOUT};
  o.lidOpened = o.lidClosed = true; o.weightBeforeG = 500; o.weightAfterG = 420;
  o.rfidUsed = true; o.rfidBefore = inv({"ARD1", "ARD2"}); o.rfidAfter = inv({"ARD1"});
  o.expectedRfidId = "ARD1";
  ok &= expect("requested ARD1, ARD2 removed", verifyCycle(o, T), false, F_WRONG_ITEM);

  // RFID: nothing removed, but the weight dropped.
  o = CycleObservation{TxKind::CHECKOUT};
  o.lidOpened = o.lidClosed = true; o.weightBeforeG = 500; o.weightAfterG = 400;
  o.rfidUsed = true; o.rfidBefore = inv({"A002"}); o.rfidAfter = inv({"A002"});
  ok &= expect("RFID no change, weight -100 g", verifyCycle(o, T), false, F_SENSOR_MISMATCH);

  // No RFID, weight agrees.
  o = CycleObservation{TxKind::RETURN};
  o.lidOpened = o.lidClosed = true; o.weightBeforeG = 100; o.weightAfterG = 180;
  ok &= expect("no RFID, return +80 g", verifyCycle(o, T), true, 0);

  // Return, but nothing went in.
  o = CycleObservation{TxKind::RETURN};
  o.lidOpened = o.lidClosed = true; o.weightBeforeG = 100; o.weightAfterG = 102;
  ok &= expect("return, +2 g only", verifyCycle(o, T), false, F_NO_WEIGHT_CHANGE);

  // Lid never opened.
  o = CycleObservation{TxKind::RETURN};
  ok &= expect("lid did not open", verifyCycle(o, T), false, F_LID_DID_NOT_OPEN);

  // Not calibrated: lid cycle fine, weight unknown -> verified (not weighed).
  o = CycleObservation{TxKind::RETURN};
  o.lidOpened = o.lidClosed = true;
  ok &= expect("not weighed, no RFID", verifyCycle(o, T), true, F_NO_WEIGHT);

  LOG("TRANSACTION", "Verification self-test: %s", ok ? "ALL PASS" : "FAILURES ABOVE");
  return ok;
}
