---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/SMART_LAB_NETWORK_CONFIGURATION.md"
source_hash: "880212fd845922312db5156ccaffefedbe37c360676ccf7a9cfdace1481e02b6"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/SMART_LAB_NETWORK_CONFIGURATION.md` - edit the original in the repository, not this note.

Systems: none

# Smart Lab - network configuration (2026-11-03)

## Addresses (Smart Lab router network 192.168.1.0/24, no internet)
| Device | Address | Set where |
|---|---|---|
| Huawei Smart Lab router | 192.168.1.1 | router |
| FANUC ER-4iA controller | 192.168.1.100 | pendant |
| UR5e controller | 192.168.1.102 | pendant |
| ESP32-CAM (door face) | 192.168.1.150 | firmware |
| Master ESP32 (door) | 192.168.1.151 | firmware (do not touch) |
| Environment node | 192.168.1.152 | firmware |
| Sorting / reuse bins | 192.168.1.153 / .154 | firmware |
| Security cameras 1 / 2 | 192.168.1.155 / .156 | router DHCP reservation |
| Portal laptop (Dell G3) | 192.168.1.200 /24, **no gateway** | Windows Ethernet adapter |
| Lab engineer PC, USB-Ethernet | 192.168.1.210 /24, no gateway | engineer PC (with lab engineer) |
| GIU lab PCs | 10.40.20.x (GIU DHCP) | GIU IT - not changed by us |

Router DHCP pool: keep it outside the static range (e.g. .10-.90) so no phone ever gets .100-.210.

## The overlap problem (measured 2026-11-03)
At home the Wi-Fi is also 192.168.1.0/24 (laptop 192.168.1.8, router .1). Both adapters then own the same /24 and
Windows sends 192.168.1.x out of the adapter with the lower metric - the Wi-Fi. `lab_preflight.ps1` shows it as
"Robots reached over the cable: WARN".

Options compared:
| Option | Verdict |
|---|---|
| Renumber the Smart Lab network | Rejected: robots, ESP32 firmware and the door node hard-code 192.168.1.x |
| Swap interface metrics (Ethernet first) | Rejected: with 192.168.1.x Wi-Fi, its DNS / router .1 would go down the lab cable |
| **Phone hotspot for internet at the lab** | **Chosen**: hotspots use 172.20.10.x (iPhone) / 192.168.43.x (Android) - no overlap at all |
| **/32 host routes per lab device** | **Prepared** (`scripts\fix_lab_routing.ps1`): only when the Wi-Fi is 192.168.1.x too |

### fix_lab_routing.ps1
- `scripts\fix_lab_routing.ps1` - dry run: prints where each lab address leaves now. Changes nothing.
- `-Apply` (administrator): one /32 route per lab device on the Ethernet adapter (a /32 always wins over a /24).
- Rollback: `-Revert`, or simply reboot (the routes are in the active store only). Internet and DNS are untouched.

## Ports on the portal laptop
| Port | Service | Reachable from |
|---|---|---|
| 80 / 443 | web portal (nginx, redirects 80 -> 443) | lab LAN + GIU (via relay) |
| 8000 | API | lab LAN + GIU (via relay) |
| 8080 / 8443 | web alternate ports | lab LAN |
| 5000 | face server (ESP32-CAM) | lab LAN |
| 5100 | security camera 1 service | lab LAN |
| 5101, 5199, 5320, 4840, 11434, 5433 | camera 2, knowledge, voice, OPC UA, Ollama, Postgres | this laptop only (127.0.0.1) |

## Firewall (`firmware\face_server\allow_firewall.bat`, run once as administrator)
Rules "Smart Lab face server" and "Smart Lab ports" now accept **only** 192.168.1.0/24 and 10.40.20.0/24.
A hotspot or cafe Wi-Fi peer cannot reach any portal port. Check: `lab_preflight.ps1` -> Firewall row.
Rollback: `netsh advfirewall firewall delete rule name="Smart Lab ports"` (and "Smart Lab face server").

## TLS certificate
`deploy/tls/server.crt` (reissued 2026-11-03 from the same CA, old one in backups/tls_20261103) names:
localhost, smartlab.local, 127.0.0.1, 192.168.1.200, 192.168.1.210, 10.40.20.17, 10.40.20.18, 10.40.20.19.
If the engineer PC's GIU address is different: `py tools\tls\make_local_ca.py --ip 192.168.1.200 --ip 192.168.1.210
--ip <ENG_GIU_IP> --name smartlab.local`, then `docker compose exec frontend nginx -s reload`.

