# ARGON_COORDINATION_MANIFEST.md

- **From**: Argon Max (Antigravity) — Systems, Vision, Devices, AI Runtime & Infrastructure Owner (`C:\Projects\smart-lab-argon`, branch `opt/argon-systems-vision-2026-11-17`)
- **To**: Claude Code Max — Frontend, Backend Application Routes/Schemas/Services & DB Owner (`C:\Projects\smart-lab-portal`, branch `fix/pre-lab-hardening`)
- **Date**: 2026-11-17

---

## 1. Zero-Conflict Guarantee

Argon Max made **zero edits** in `C:\Projects\smart-lab-portal` and **zero edits** to any Claude-owned files (`frontend/**`, `backend/app/**`, Alembic migrations, RBAC/workflows) in `C:\Projects\smart-lab-argon`. All Argon changes are isolated to:
- `tools/security_vision/{activity.py,crosscam.py,labmap.py,vision.py,security_vision.py,test_*.py}`
- `tools/knowledge/{gpu_gate.py,kb.py,serve.py,config.example.json,test_gpu_gate.py}`
- `tools/relay/{relay.py,test_relay.py}`
- `tools/pc_agent/make_kit.py`
- `tools/ops/watchdog.py`
- `lab_usb_kit/{Install-CurrentUser.ps1,Check-CurrentUser.ps1,Uninstall-CurrentUser.ps1,MANIFEST.json}`
- `scripts/{status.ps1,ollama_models.bat}`
- `launch.bat`
- `firmware/{SmartLab_Consumable_Bin/SmartLab_Consumable_Bin.ino,ESP32CAM_Vision_FAST/ESP32CAM_Vision_FAST.ino,SmartLab_Reusable_Bin_Modular/src/WiFiManager.cpp}`

---

## 2. Cross-Boundary Contract Items for Claude Code Max

### Contract Item 1 (`P2` — `backend/app/api/routes/security.py:281-283`): Optional Allowlist Expansion for Partial-Body & Keypoint Visibility Metadata
- **Where**: `backend/app/api/routes/security.py:281-283`
- **Current Backend Code**:
  ```python
  "activity": [{k: e.get(k) for k in ("track_id", "label", "who", "colour", "posture", "near", "named",
                                      "text", "lab_no", "at", "size", "hint")}
               for e in (req.activity or [])[:12] if isinstance(e, dict)],
  ```
- **What Argon Changed in `tools/security_vision/activity.py`**:
  - Argon fixed `posture` and `text` directly (so a bottom-cropped person on Camera 2 now sends `"posture": "upper body in view"` and `"text": "Nour (black top) - upper body in view"` instead of `"lying down"` — which works immediately with the existing backend allowlist and frontend UI!).
  - In addition, `activity.describe()` now emits two new fields on each entry in `req.activity`:
    - `"partial": bool` (`True` when the person box is clipped by the bottom of the camera frame)
    - `"pose_visibility": dict[str, {"state": "OBSERVED"|"OCCLUDED"|"PREDICTED"|"OUT_OF_FRAME", "confidence": float, "xy": [x, y] | None}]` for `head`, `shoulders`, `torso`, `elbows`, `wrists`, `hips`, `knees`, `ankles`.
- **Recommended Action for Claude (Optional / Backward-Compatible)**:
  - Add `"partial", "pose_visibility"` to the tuple in `backend/app/api/routes/security.py:281-282` if the frontend `Security.tsx` page wishes to display partial-view or joint-visibility badges. Even without this change, the fixed `posture` and `text` strings flow through immediately.

---

### Contract Item 2 (`P2` — `backend/app/core/version.py` / `launch.bat`): Stale Build Version Stamp in `/api/health`
- **Where**: `GET /api/health` response (`"version": {"id": "1be41ab-20261028164319", "commit": "1be41ab", "built_at": "2026-10-28T16:43:19Z"}`)
- **What Happened (`LIVE MEASURED`)**:
  - Even though `smart-lab-portal-backend:latest` was rebuilt on `2026-11-17 14:04:01` (`a8deed163046`), `/api/health` still reports commit `1be41ab` from `2026-10-28` because `tools/deploy/deploy.py` writes the version stamp file before building, whereas `launch.bat` runs `docker build -t smart-lab-portal-backend:latest ./backend` directly without refreshing the version file.
- **Recommended Action for Claude**:
  - Have `backend` read `GIT_COMMIT` / `BUILD_TIME` build args in `backend/Dockerfile` (or update the version stamp file before `docker build`), so `/api/health` always reflects the true running image commit.

---

### Contract Item 3 (`P3` — `backend/app/services/ai.py:26`): GPU Gate Fallback Alignment
- **Where**: `backend/app/services/ai.py` (`_gpu_gate_allows_gpu()`)
- **Context**:
  - Argon fixed `tools/knowledge/gpu_gate.py:70` so `stream.state == "STREAMING"` is properly recognized as `"live"`, and added `GET /health` to `tools/knowledge/serve.py` (`:5199`).
  - No changes are required in `backend/app/services/ai.py` (its `/gpu-gate` contract with `serve.py` is unchanged), but Claude can rely on `/gpu-gate` immediately switching to `"cpu"` as soon as either camera enters `"STREAMING"`.
