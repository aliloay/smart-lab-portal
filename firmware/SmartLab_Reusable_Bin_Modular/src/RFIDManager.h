// EXPERIMENTAL RFID inventory: can an (old, not yet identified) RFID
// reader list every tagged item INSIDE the bin?
//
// Nothing about the reader is assumed - not its model, interface, voltage,
// pins, range, or whether it can read several tags at once. With
// RFID_READER_MODEL == RFID_NONE (the default) the manager reports
// RFID_DISABLED and everything else works normally.
//
// An inventory is the UNION of every tag ID seen while reading repeatedly for
// RFID_INVENTORY_WINDOW_MS (a reader that only returns one tag per read may
// still list several over the window - or may not; that is what the test
// measures). Results are reported as seen, with timestamps; nothing claims the
// bin's full contents until that is proven physically.
//
// ---------------------------------------------------------------------------
// Adding a reader once it is identified (model, interface, voltage, library):
//   1. Write a class derived from RfidReader below (begin / readOnce).
//   2. Give it a number in config.h (e.g. #define RFID_MY_READER 1) and set
//      RFID_READER_MODEL to it; put its pins in RFID_PIN_A..D.
//   3. In RFIDManager.cpp, makeReader(): return new MyReader() for it.
// The rest of the firmware (inventory diff, transactions) is unchanged.
// ---------------------------------------------------------------------------
#pragma once
#include <Arduino.h>
#include <vector>
#include "InventoryManager.h"

enum class RfidStatus : uint8_t {
  RFID_DISABLED, RFID_AVAILABLE, RFID_ERROR, RFID_READING, RFID_NO_TAGS, RFID_TAGS_DETECTED
};
const char *rfidStatusName(RfidStatus s);

class RfidReader {
 public:
  virtual ~RfidReader() {}
  virtual const char *name() const = 0;
  virtual bool begin() = 0;                               // true = the reader answered
  // One read: append the tag IDs it returns now (none is fine). false = reader error.
  virtual bool readOnce(std::vector<String> &tagIds) = 0;
};

class RFIDManager {
 public:
  void begin();
  bool enabled() const { return _reader != nullptr; }
  RfidStatus status() const { return _status; }
  // Non-blocking inventory: start, then update() until done().
  bool startInventory();
  void update();
  bool busy() const { return _status == RfidStatus::RFID_READING; }
  const Inventory &lastInventory() const { return _last; }
  bool lastInventoryValid() const { return _lastValid; }
  void printStatus();

 private:
  RfidReader *_reader = nullptr;
  RfidStatus _status = RfidStatus::RFID_DISABLED;
  uint32_t _startMs = 0;
  Inventory _working, _last;
  bool _lastValid = false;
};
