# Defense brief: what the project claims and what supports each claim

Status of the project (supervisor feedback, November 2026): no further features; the work is in its optimisation phase. The defense argues one thesis: **a compact, modular, locally operated platform whose value comes from integration**, where every subsystem writes to one record and every interface reads from it.

Labels used below: **verified** (checked in code or by a test run), **lab** (observed in the lab), **owner-reported** (stated by the owner, no record in the repository), **open** (not yet measured).

## 1. The five claims

| Claim | Evidence | Label | Limit to state honestly |
|---|---|---|---|
| **Local** | `AI_LOCAL_ONLY=true` by default; Ollama, voice, knowledge service, database and n8n all run on the engineer PC; dependency table in [local-network-and-offline.md](../deployment/local-network-and-offline.md) | verified in code | The formal 30-minute run with the internet unplugged is still open |
| **Lightweight** | One laptop (i7-9750H, 16 GB, GTX 1650 4 GB) runs the whole stack; measured budget of about 11.5 to 13 GB on a lab day with two cameras ([SMART_LAB_RESOURCE_BUDGET.md](../SMART_LAB_RESOURCE_BUDGET.md)) | measured 3 Nov 2026 | 16 GB is tight during image builds and test runs; these are not done during operation |
| **Modular** | Four ESP32 nodes, cameras, robot collectors and PC agents each use their own HTTP routes and device key; any of them can be absent and the portal still runs | verified (integration matrix) | Each node needs its key and the API address configured once |
| **Compact** | Each node sits in one printed enclosure with internal wiring | lab / owner-reported (PETG; the door enclosure notes allow PETG or PLA) | No temperature test of the enclosures was recorded |
| **Low cost** | Commodity parts: ESP32 boards, hobby sensors, consumer IP cameras, one existing laptop, open-source software only | qualitative | **No costed bill of materials exists in the repository.** A price table is needed before quoting a number |

"Install anywhere by powering it on" should be stated as: **after a one-time site setup** (Wi-Fi name and password and the API address in each node, device keys, camera addresses, floor calibration), the system starts with one command (`launch.bat`) and the nodes reconnect by themselves after a power cycle.

## 2. Integration: the main argument

All subsystems meet in one FastAPI backend and one PostgreSQL database (329 API operations, 42 tables). The portal, the assistants, n8n and the phone AR page read that same record. Chains that exist only because of the integration:

| Chain | Path |
|---|---|
| Entry becomes verified presence | Door node (QR + fingerprint or face) → access event → presence record → cameras confirm or contradict it |
| Stock is tied to people | Consumables weight change → inventory measurement → compared with who was inside |
| A reading becomes an action | Environment node smoke or flame → alert in the portal → n8n workflow notifies staff |
| A question is answered from live data | Staff assistant → read-only tools over the database → text, tables and charts; weekly and monthly management reports |
| A question about the system itself | Knowledge agent → Obsidian vault + repository → answer with numbered sources |
| Equipment in view | Phone camera page → QR or marker → live record of that device from the same API |
| Robot state without risk | UR5e → RTDE receive only → collector → twin in the portal; FANUC ER-4iA → controller web page (GET only) → same collector and twin (live-verified once, 14 Oct 2026) |
| Staff control of lab PCs | Admin or lab engineer in the portal → queued action → PC agent polls every 2 s → message, exam mode, screen sharing, log-off or shutdown with a warning |

Full table with protocols and authentication: [INTEGRATION_MATRIX.md](../../INTEGRATION_MATRIX.md).

### Knowledge, automation and the assistants (precise wording)

- **Obsidian vault:** 322 notes and about 1,700 wikilinks, generated from the repository (`kb.py build`): system notes, the n8n workflow catalogue, the database dictionary and one note per source file. Hand-written runbooks, decisions and incidents survive rebuilds.
- **Direction of the links:** the vault *documents* the n8n workflows and the agent *reads* the vault. n8n does not read Obsidian; it calls the backend (`/api/automation/*`), and the backend holds the rules. Say "the knowledge base documents the automation layer and lets the agent explain it", not "Obsidian drives n8n".
- **n8n:** 23 workflows; schedules (daily report 20:00, weekly report Mondays 07:00, data-quality check 06:00) and event webhooks. Workflows stay thin: they trigger, the backend decides.
- **Assistants:** common questions are answered instantly from the records without a model; open questions use a local model (qwen2.5:1.5b) with read-only tools. A booking is a proposal the user confirms; an assistant cannot act on hardware.
- **Voice and camera:** speech in and out through local faster-whisper and Piper; the phone page needs HTTPS (local certificate authority) because browsers allow the camera only in a secure context.

## 3. Questions the committee is likely to ask

**Why Docker, and why WSL 2?** The backend, database, web server, n8n and backup are Linux services. Docker gives the same pinned versions (PostgreSQL 16, n8n 2.40.7) on any PC and one-command start. On Windows, Docker Desktop runs these containers inside a small Linux virtual machine provided by WSL 2. Its memory is capped at 6 GB (`.wslconfig`), and freed cache is returned to Windows.

**Why not pure Windows?** Installing PostgreSQL, Python, Node, nginx and n8n by hand gives a setup that differs on every PC and is hard to reproduce or back up. Containers make the installation a file in the repository.

**Why not everything in Docker?** The vision service needs the GPU through DirectML and the cameras' RTSP streams; Ollama, the voice service and the robot collector also run natively on Windows. GPU access from a container on this laptop would add a second driver stack for no benefit. So: stateless web services in containers, hardware-facing services native.

**How are the CPU and GPU shared?**

| Resource | Used by |
|---|---|
| GPU (GTX 1650, 4 GB) | YOLO26s person detection for both cameras (ONNX Runtime DirectML); since 19 Oct 2026 also the local language model, after an A/B test (answers 68 s → 3 s, camera 2 unaffected). Cameras keep priority: `OLLAMA_CPU_ONLY=true` moves the model back to the CPU |
| CPU | Containers (API, database, web, n8n), tracking and identity logic, face server, voice, knowledge search, robot collector |
| RAM (measured) | Docker VM 2.5 to 4 GB; about 1.2 GB per camera process; model about 1.2 GB while loaded (unloads after 30 idle minutes) |

**Why not ROS?** The project only *observes* the robots. The UR5e already publishes its state over RTDE (50 Hz), which a Python collector with 43 tests reads directly. ROS would add a Linux host, a DDS network and a driver that takes control through the External Control URCap, which is exactly what the safety rule excludes. Robot control stays unavailable until a commissioning sign-off.

**Why not MQTT?** With four nodes on one LAN, HTTP with a device key is enough, is testable with the same tools as the rest of the API, and removes a broker that would be another point of failure.

**Why two cameras?** One camera cannot see the whole room, so a person leaves its view or is hidden. Two overlapping views cover the room; without care the same person would be counted twice. Each camera tracks on its own, and `crosscam.py` shares a confirmed name between cameras only when the floor positions agree, so one person is one identity. Both cameras are floor-calibrated (live-verified 19 Oct 2026). Limit: the name crosses only while both cameras see the person and can place them, so hidden feet or a person who has left one view can still show as "Unknown" on the other.

**Why does the camera not name people by itself?** Detection is not identity. YOLO only finds people; a name needs evidence from the door, a face match or appearance continuity. Some people stay "Unknown" by design.

**What happens if the PC fails?** The door node keeps its fail-secure behaviour and the mechanical exit; records pause. This single point of failure is the stated trade-off of a one-PC local design; nightly database backups limit data loss.

## 4. What to show, in order

1. Door entry on the node, and the event appearing in the portal.
2. Camera view confirming that person; second camera keeping the same name.
3. Environment alert and the n8n notification.
4. Consumables weight on the LCD and in the portal.
5. Assistant: a spoken question, a chart, the weekly report; then a "how is this built" question with sources.
6. Phone scan of a node's QR code showing its live record.
7. UR5e twin following the real arm; the FANUC twin if its pose check has been done.
8. PC control: message and screen sharing to a lab PC.

Open measurements that would strengthen each claim are listed in [OPTIMIZATION_AND_REMAINING_WORK.md](OPTIMIZATION_AND_REMAINING_WORK.md).
