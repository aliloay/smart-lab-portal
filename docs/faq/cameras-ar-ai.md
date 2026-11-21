# FAQ: security cameras, AR scan, AI and the knowledge base

## Q: What do the security cameras do?
Also asked: AI cameras features, SECCAM, camera capabilities
**A:** Two fixed cameras (SECCAM_LAB01 and SECCAM_LAB02). They detect and track people, keep one identity across both cameras, see which seats and PCs are occupied, raise alerts when equipment is moved, and record clips.
Source: `tools/security_vision/security_vision.py`, `tools/security_vision/crosscam.py`

## Q: Which detector do the security cameras use?
Also asked: camera model, YOLO version, camera AI engine
**A:** A YOLO26s person detector in ONNX format, running on the GTX 1650 through DirectML, with a re-identification network for appearance. OpenVINO and CPU are fallbacks.
Source: `tools/security_vision/vision.py`, `docs/benchmarks/SECURITYCAM_ENGINE_AUDIT_2026-10-13.md`

## Q: Do the cameras do full-body pose?
Also asked: skeleton, keypoints, limb tracking, head tracking
**A:** Yes, when the keypoint model file is installed (models/yolov8n-pose.onnx). Then head, shoulders, elbows, wrists, torso, hips, knees and ankles are MEASURED, each with its own confidence, and a joint below 50 % confidence is shown as hidden, never guessed. Without the model file, positions are estimates from the person's box (marked PREDICTED).
Source: `tools/security_vision/pose.py`, `tools/security_vision/activity.py` (pose_visibility)

## Q: Are the security cameras working?
Also asked: camera status, is camera 1 live
**A:** Live: the portal assistant answers per camera ("Are the security cameras working?"). "Partly working" means the camera service runs but gets no picture, for example while the cameras are away from the lab.
Source: `backend/app/services/agent.py` (cameras_status), `backend/app/services/devices.py`

## Q: Which model does AR Scan use?
Also asked: AR detector version, phone AR model
**A:** lab_detector.onnx version 8 ("ft_y11s", a YOLO11s model with 12 classes), run on the server for the phone.
Source: `backend/data/models/detectors.json`

## Q: Which objects can AR Scan recognise?
Also asked: AR classes, what does the phone recognise
**A:** Reusable bin, consumables node, environment node, master node, network switch, router, UR5e, UR5e pendant, FANUC, FANUC pendant, lab PC and the door.
Source: `backend/data/models/detectors.json`

## Q: Why does AR not tell which PC it sees?
Also asked: AR PC identity, which computer is this
**A:** The detector knows "a lab PC", not which one. Scan the QR marker on the PC to get its identity and live panel.
Source: `backend/data/models/detectors.json` (lab_pc has no code), `frontend/src/pages/Scan.tsx`

## Q: Which AI model answers in the portal?
Also asked: model in use, which LLM, what model is the assistant
**A:** The portal assistant uses qwen2.5:1.5b and the project-documents assistant uses qwen3:1.7b, both local through Ollama. Live answer: ask the portal assistant "What model is the AI assistant using?".
Source: `.env` OLLAMA_MODEL, `tools/knowledge/config.json`, `docs/benchmarks/LOCAL_MODEL_BENCHMARK_2026-11-21.md`

## Q: Does the AI run on the GPU?
Also asked: AI GPU or CPU, why is the assistant slow
**A:** Only when the security cameras are not analysing. The cameras have priority on the GTX 1650; while a camera is live, the assistants run on the CPU. The decision is made by the camera-first GPU gate.
Source: `tools/knowledge/gpu_gate.py`

## Q: Where does the assistant get its knowledge?
Also asked: knowledge sources, what does the assistant read
**A:** From the project's own files: documentation, code and workflow definitions, mirrored into an Obsidian vault and searched locally. Live values come from the portal's database. Nothing is sent to the internet.
Source: `tools/knowledge/kb.py`, `tools/knowledge/serve.py`

## Q: Can the assistant show passwords or keys?
Also asked: Wi-Fi password, API key, .env values
**A:** No. Passwords, keys, tokens and .env values are excluded from the knowledge base, and the assistant refuses such questions.
Source: `tools/knowledge/agent.py` (guard), `tools/knowledge/kb.py` (DENY list)

## Q: Which model did the benchmark choose and why?
Also asked: why qwen3, model comparison, bigger model
**A:** On 21 Nov, qwen3:1.7b answered 9 of 11 facts correctly, against 7–8 for qwen2.5:1.5b. The bigger models (3B, 4B, 7B) were no better and 3–4× slower, so qwen3:1.7b serves the documents assistant. The portal assistant stays on qwen2.5:1.5b (86.5 % against 80.8 % on its own test).
Source: `docs/benchmarks/LOCAL_MODEL_BENCHMARK_2026-11-21.md`
