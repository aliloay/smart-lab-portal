#include "InventoryManager.h"
#include <algorithm>

bool Inventory::add(const String &raw) {
  String id = raw;
  id.trim();
  id.toUpperCase();
  if (!id.length()) return false;
  auto it = std::lower_bound(_ids.begin(), _ids.end(), id);
  if (it != _ids.end() && *it == id) return false;
  _ids.insert(it, id);
  return true;
}

bool Inventory::contains(const String &raw) const {
  String id = raw;
  id.trim();
  id.toUpperCase();
  return std::binary_search(_ids.begin(), _ids.end(), id);
}

String Inventory::toString() const {
  String s = "{";
  for (size_t i = 0; i < _ids.size(); i++) { if (i) s += ", "; s += _ids[i]; }
  return s + "}";
}

String Inventory::toJsonArray() const {
  String s = "[";
  for (size_t i = 0; i < _ids.size(); i++) { if (i) s += ','; s += '"'; s += _ids[i]; s += '"'; }
  return s + "]";
}

InventoryDiff diffInventories(const Inventory &before, const Inventory &after) {
  InventoryDiff d;
  for (const String &id : before.ids()) if (!after.contains(id)) d.removed.add(id);
  for (const String &id : after.ids()) if (!before.contains(id)) d.added.add(id);
  return d;
}
