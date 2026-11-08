// Inventories as SETS of unique tag IDs, and the before/after difference:
//   removed = BEFORE - AFTER      added = AFTER - BEFORE
// Any number of items may change in one transaction.
// Pure logic (no hardware), so it can be tested on its own.
#pragma once
#include <Arduino.h>
#include <vector>

class Inventory {
 public:
  bool add(const String &id);                  // false if already there
  bool contains(const String &id) const;
  size_t size() const { return _ids.size(); }
  void clear() { _ids.clear(); }
  const std::vector<String> &ids() const { return _ids; }   // sorted, unique
  String toString() const;                     // {A001, A002}
  String toJsonArray() const;                  // ["A001","A002"]
 private:
  std::vector<String> _ids;
};

struct InventoryDiff {
  Inventory removed, added;
  bool changed() const { return removed.size() || added.size(); }
};

InventoryDiff diffInventories(const Inventory &before, const Inventory &after);
