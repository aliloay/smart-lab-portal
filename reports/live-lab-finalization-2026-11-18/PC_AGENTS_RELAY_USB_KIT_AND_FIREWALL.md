# PC_AGENTS_RELAY_USB_KIT_AND_FIREWALL.md

- **Evidence Class**: `LIVE_PHYSICAL` (Engineer PC `S2PC136` + 6 GIU Lab 20 Student PCs + Admin Laptop verified live on-site at GIU on 18 Nov) + `UNIT_TEST` (`20 passed`).

---

## 1. Live Breakthrough: GIU Firewall Rule Applied & 6 Student PCs Online via `S2PC136` Relay (`LIVE_PHYSICAL`)

On 17 Nov, student lab PCs (`10.40.20.0/24`) could not reach the portal because `relay.py` on the Engineer PC (`S2PC136`, `10.30.11.136`) was not running and Windows Firewall blocked inbound TCP `8000`.
**Today (18 Nov at GIU), with our updated USB kit and relay running on `S2PC136` (`10.30.11.136` $\leftrightarrow$ `192.168.1.100` $\rightarrow$ `192.168.1.200:8000`), the full dual-NIC relay bridge is LIVE and verified across 8 physical workstations:**

| `device_uid` | Portal Name | Hostname | Reported IP(s) | OS Account | Agent Version | Foreground App | Status & Last Seen Age | Evidence Class |
|---|---|---|---|---|---|---|---|---|
| `PC_ADMIN_LAPTOP` | `ADMIN-LAPTOP` | `ali` | `192.168.1.200`, `172.20.10.2` | `dell` | `1.0` | `chrome.exe` | **`ONLINE`** (`4.2 s`) | `LIVE_PHYSICAL` |
| `PC_ENG` | `HEMALY - ENGINEER PC` | `S2PC136` | `192.168.1.100`, `10.30.11.136` | `ahmed.el-hemaly` | `1.0` + `relay.py` | `msedge.exe` | **`ONLINE`** (`1.5 s`) | `LIVE_PHYSICAL` |
| `PC_GIULAB20-PC4` | `PC-02` | `GIULAB20-PC4` | `10.40.20.4` | `ali.abozeid` | `1.0` | `msedge.exe` | **`ONLINE`** (`8.0 s`) | `LIVE_PHYSICAL` |
| `PC_GIULAB20-PC13` | `PC_GIULAB20-PC13` | `GIULAB20-PC13` | `10.40.20.13` | `ali.abozeid` | `0.9` | `powershell.exe` | **`ONLINE`** (`4.0 s`) | `LIVE_PHYSICAL` |
| `PC_GIULAB20-PC14` | `PC_GIULAB20-PC14` | `GIULAB20-PC14` | `10.40.20.14` | `pansih.abudif` | `1.0` | `explorer.exe` | **`ONLINE`** (`13.0 s`) | `LIVE_PHYSICAL` |
| `PC_GIULAB20-PC17` | `PC_GIULAB20-PC17` | `GIULAB20-PC17` | `10.40.20.17` | `ali.elalawi` | `1.0` | `msedge.exe` | **`ONLINE`** (`12.2 s`) | `LIVE_PHYSICAL` |
| `PC_GIULAB20-PC18` | `PC_GIULAB20-PC18` | `GIULAB20-PC18` | `10.40.20.18` | `ali.abozeid` | `1.0` | `AtmelStudio.exe` | **`ONLINE`** (`11.8 s`) | `LIVE_PHYSICAL` |
| `PC_GIULAB20-PC19` | `PC_GIULAB20-PC19` | `GIULAB20-PC19` | `10.40.20.19` | `ali.abozeid` | `1.0` | `vlc.exe` | **`ONLINE`** (`11.9 s`) | `LIVE_PHYSICAL` |
| `PC_GIULAB20-PC8` | `PC-06` | `GIULAB20-PC8` | `10.40.20.8` | — | `0.9` | — | **`OFFLINE`** (`13 d`) | `LIVE_SERVICE` (Powered off / signed out) |
| `PC_GIULAB20-PC11` | `PC_GIULAB20-PC11` | `GIULAB20-PC11` | `10.40.20.11` | — | `0.9` | — | **`OFFLINE`** (`13 d`) | `LIVE_SERVICE` (Powered off / signed out) |
| `PC_GIULAB20-PC12` | `PC_GIULAB20-PC12` | `GIULAB20-PC12` | `10.40.20.12` | — | `0.9` | — | **`OFFLINE`** (`13 d`) | `LIVE_SERVICE` (Powered off / signed out) |

---

## 2. Verification of USB Kit (`lab_usb_kit`), Relay, LAN Presence & mDNS

1. **859 / 859 USB Kit Manifest Verification (`LIVE_SERVICE` + `UNIT_TEST`)**:
   - `py tools/pc_agent/make_kit.py --no-bundle` verified: `kit 1.1 bundle e8e7e4fc890e: 859 files, 0 MB, secret scan clean`.
   - `Test-KitFile` in `Install-CurrentUser.ps1` and `Check-CurrentUser.ps1` accepts both exact byte SHA-256 and CRLF$\rightarrow$LF normalized SHA-256 for text files (`.ps1`, `.md`, `.json`, `.py`, `.txt`), eliminating the Git CRLF mismatch failure while still rejecting tampered files.
2. **Relay Resilience & Subnet ACLs (`tools/relay/relay.py`)**:
   - `relay.py` enforces `--allow 10.30.11.0/24 10.40.20.0/24 192.168.1.0/24 127.0.0.0/8` (refusing phone hotspot or unauthorized subnets) and automatically falls back to `0.0.0.0` if the primary `--listen` IP is not yet bound at Windows login (`test_serve_falls_back_to_all_interfaces_when_specific_ip_is_unavailable`).
3. **LAN Presence (`tools/lan_presence/lan_presence.py`)**:
   - Verified that `lan_presence.py` posts to `/api/equipment/pc/presence` (updating only the `lan` presence sub-field in `list_equipment`), and **never** sets `d.is_online = True` or creates a fake `RUNNING` session when a PC's agent is offline (`PC_GIULAB20-PC8/11/12` remain `online: false`).
4. **mDNS (`tools/mdns/announce.py`)**:
   - Verified PID `35936` binds exclusively to `192.168.1.200` (the Smart Lab router Ethernet interface) and announces `smartlab.local -> 192.168.1.200`.
5. **Clock Offset Observation (`-67.5 s`)**:
   - All GIU domain PCs (`PC_ENG` and `PC_GIULAB20-PC4..19`) report `"clock_offset_s": -67.51` to `-67.56`, meaning the GIU Active Directory domain clock is `67.5 seconds` ahead of the portal laptop's clock (or the laptop clock is 67.5 s behind UTC while on hotspot). Because `equipment.py` records `last_seen_at = datetime.now(timezone.utc)` using the server's clock and stores `clock_offset_s` diagnostically, liveness (`is_fresh`) is unaffected.
