# Device keys: from the shared key to one key per node (post-lab plan)

Status 2026-11-16. **Nothing in this document has been done or flashed.** It exists so the migration can be done one node at a time, after the lab test, without locking a node out.

## 1. How device authentication works today (from `backend/app/api/deps.py`)
- Every device endpoint (`require_device`) accepts **either**
  - the shared `DEVICE_API_KEY` - only while `DEVICE_SHARED_KEY=true` (the default). Such a caller is identified as `*` and may report as any device; **or**
  - a device's **own** key: the backend stores only its SHA-256 (`devices.key_hash`); the caller is then bound to exactly that `device_uid` (`device_scope` returns 403 for any other uid). A lab PC's own key only opens `/api/equipment/...`.
- So the backend already supports per-device keys. What is missing is putting an own key into each node's firmware.

## 2. State on the lab laptop (checked 2026-11-16 by fingerprint only - no key value printed or stored)
| Node | Key in its local `secrets.h` | Key issued in the database |
|---|---|---|
| Master (door) `MASTER_LAB01` | own key (32 chars) | yes |
| Environment `ENV_LAB01` | own key (32 chars) | yes |
| Consumable bin `BIN_NODE_1` | **the shared key** | no |
| Reusable bin `REUSE_BIN_1` (Modular, reuse-mod-0.1) | **the shared key** | no |
| Reusable bin (legacy single-file firmware) | a different key that no database row holds | no |
| ESP32-CAM | no `DEVICE_KEY` (different mechanism) | - |
| Robot Stop | no `secrets.h` on this laptop (not commissioned) | - |
This is what the board was last built with on this laptop; what is flashed on a board can only be confirmed at the board.

**Consequence:** `DEVICE_SHARED_KEY=false` would lock out the consumable bin and the Modular reusable bin. Keep `true` for the lab test.
Risk of the shared mode: one compromised node (or anyone who reads one `secrets.h`) can post as any other device, including door reports - larger blast radius.

## 3. Migration, one node at a time (after the lab)
1. Pick one node (start with the Consumable bin). Portal: **Devices -> that device -> issue key**. The key is shown once; store it in a protected place, never in Git, chat or reports.
2. Put the key into that node's `secrets.h` (git-ignored) as `DEVICE_KEY`. Compile; **bench test before flashing**: power the board away from the lab network if needed; no actuator connected.
3. Flash that one node. Verify on the portal: node online, a real report accepted (e.g. weigh a known mass), `403 This device key belongs to another device` when it tries another uid (tests cover this: `backend/tests/test_device_keys.py`).
4. Repeat for the next node. After **every** node has its own key and has reported successfully:
5. Set `DEVICE_SHARED_KEY=false` in `.env` (owner), recreate only the backend; confirm each node is still online.
6. Optionally rotate the old shared `DEVICE_API_KEY` (this also changes the PC enrolment kit code - see `pc_enroll_code()`; rebuild the kit).
**Rollback** for a node: re-flash its previous `secrets.h` (kept offline), and set `DEVICE_SHARED_KEY=true` again if shared-key nodes are still in service. The database keeps the issued hashes; nothing is deleted.

## 4. Do not
- Do not issue, rotate or print keys in the lab session; do not flash a node you cannot reach to re-flash.
- Do not flip `DEVICE_SHARED_KEY` before every node in the table above has been verified on its own key.
