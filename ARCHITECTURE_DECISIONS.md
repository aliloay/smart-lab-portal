# Architecture decisions

| # | Decision | Why | Consequence |
|---|---|---|---|
| 1 | One backend (FastAPI + PostgreSQL) as the single record; devices only report over HTTP | Simple, testable, works on a LAN without a broker | No MQTT broker; each device needs a key and the API address |
| 2 | Local-first: everything runs on one PC on the lab network | Privacy, no running costs, works without internet | One PC is a single point of failure; nightly backups mitigate data loss |
| 3 | Fail-secure lock on the relay's NO contact | A fault or power loss must leave the door locked | Unlocking needs power; mechanical exit always works |
| 4 | Detection ≠ identity: YOLO only detects people; names need door, face or look evidence | Avoid naming people by guess | Some people stay "Unknown"; that is intended |
| 5 | Robots are read-only; control adapters stay unavailable until commissioning sign-off | Safety | The twin mirrors; nothing can move a robot from the portal |
| 6 | n8n schedules and notifies; the backend decides | Rules stay in tested code, workflows stay thin | Workflow changes cannot change a rule by accident |
| 7 | AI local only by default (`AI_LOCAL_ONLY=true`, Ollama) | No lab data leaves the PC | Smaller models; cloud is an explicit opt-in |
| 8 | Assistants cannot act on hardware; bookings are proposals the user confirms | Safety and accountability | Assistants are read-mostly |
| 9 | Phone camera over HTTPS with a local CA | Browsers allow the camera only in a secure context | Each phone trusts the CA once |
| 10 | Knowledge vault generated from the repository | Documentation follows the code | Generated notes are overwritten; hand notes live in their own folders |
| 11 | Pinned images (n8n 2.40.7, PostgreSQL 16) | Reproducibility | Upgrades are deliberate |
| 12 | Web services in Docker on WSL 2; hardware-facing services (vision, Ollama, voice, robot collector) native on Windows | Containers give pinned, reproducible Linux services with one start command; the GPU (DirectML) and device streams are simpler natively | Two kinds of process to start; `launch.bat` starts both. The Docker VM is capped at 6 GB |
| 13 | No ROS | The robots are only observed; RTDE already provides the UR5e state at 50 Hz to a small Python collector | No ROS host or driver to maintain; ROS-based control would be a separate, commissioned project |
| 14 | Two overlapping cameras with floor-calibrated name sharing | One view cannot cover the room; the overlap must not count a person twice | Both cameras need a floor calibration |
| 15 | GPU shared by detection and the language model, cameras first | A/B test on 19 Oct 2026: answers 68 s → 3 s, camera 2 unaffected | `OLLAMA_CPU_ONLY=true` returns the model to the CPU if a camera suffers |
