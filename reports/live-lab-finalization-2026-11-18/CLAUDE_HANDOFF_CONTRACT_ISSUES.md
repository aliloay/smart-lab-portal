# CLAUDE_HANDOFF_CONTRACT_ISSUES.md

- **From**: Gemini / Argon Max (`C:\Projects\smart-lab-argon`, branch `opt/gemini-live-lab-finalization-2026-11-18`)
- **To**: Claude Code Max (`C:\Projects\smart-lab-portal`, branch `fix/pre-lab-hardening`)
- **Date**: 2026-11-18 (On-site at GIU)

---

## 1. Independent Verification of Prior Claude Claims (`Section 1.3`)

| Prior Claude Claim | Independent Live Verification Result (`LIVE_SERVICE` at GIU) | Status |
|---|---|---|
| **Motion bundle gzip reduced `38.5 KB` $\rightarrow$ `26.3 KB` (`d085b73`)** | Verified live in `https://127.0.0.1/` HTML: `<link rel="modulepreload" crossorigin href="/assets/motion-TaJcjnZ4.js">` (`LazyMotion` + `domAnimation` split chunk active). | **VERIFIED (`LIVE_SERVICE`)** |
| **`/api/incidents` SQL-side state/lab filters, summary rows, keyset cursor (`5314195`, `b685a43`)** | Verified in commit `b685a43` and live DB (`EXPLAIN ANALYZE` on `alerts` top 100 uses `Index Scan Backward using ix_alerts_created_at`, execution time **`0.327 ms`**). | **VERIFIED (`LIVE_SERVICE`)** |
| **Assistant instant answers for stock, door state, and node capabilities (`89ba1be`, `279c625`)** | Verified live via `POST http://127.0.0.1:5199/ask` (`route="lookup"`): `"What do the ESP32 nodes measure and in what units?"` completed in **`95.1 ms`**; camera number sharing completed in **`6.1 ms`**. | **VERIFIED (`LIVE_SERVICE`)** |
| **Build stamp from image build args (`bdc41aa`): `/api/health` and `/version.json` report the real build** | **FALSIFIED ON LIVE RUNNING CONTAINERS (`LIVE_SERVICE` at `16:43` & `17:09`)**:<br>- `GET http://127.0.0.1:8000/api/health` returned `{"version": {"id": "unstamped", "note": "deployed without tools/deploy/deploy.py"}}`.<br>- `GET https://127.0.0.1/version.json` returned the SPA `index.html` fallback.<br>- **Why**: When `launch.bat` rebuilt `smart-lab-portal-backend:latest` (`d79acf90c4aa`) and `smart-lab-portal-frontend:latest` (`6f789b334e74`) at `14:14` today at GIU, `launch.bat:242` ran plain `docker build` without `--build-arg BUILD_COMMIT` or `BUILD_TIME`! Gemini fixed `launch.bat:242` in `opt/gemini-live-lab-finalization-2026-11-18` to call `tools\deploy\build_images.ps1`. | **FIXED IN `launch.bat` BY GEMINI (Needs container recreate after Claude finishes test run)** |

---

## 2. Backend / Frontend Contract Issues Handed to Claude Code Max

### Contract Issue 1 (`P1` — `backend/app/api/routes/robots.py:205`): `POST /api/robots/telemetry` Unconditionally Marks `is_online = True` Even When `req.state in ("UNKNOWN", "TELEMETRY_STALE")`
- **File & Line**: `backend/app/api/routes/robots.py:205`
- **Actual Code**:
  ```python
  d.last_seen_at, d.is_online = now, True
  ```
- **Problem**:
  - Even though Gemini fixed `tools/robot_monitor/robot_collector.py` (`opt/gemini-live-lab-finalization-2026-11-18`) so the collector no longer spams `/robots/telemetry` when `state == "UNKNOWN"` or after the first `"TELEMETRY_STALE"` transition, the backend route `POST /api/robots/telemetry` itself sets `d.last_seen_at, d.is_online = now, True` even when `req.state in ("UNKNOWN", "TELEMETRY_STALE")` and `req.q is None`!
- **Suggested Backend Fix for Claude**:
  - In `backend/app/api/routes/robots.py:205`, only update `d.last_seen_at = now` and `d.is_online = True` when `req.state not in ("UNKNOWN", "TELEMETRY_STALE")` (or when `req.q is not None`), and set `d.is_online = False` when `req.state == "TELEMETRY_STALE"`.

---

### Contract Issue 2 (`P2` — `backend/app/api/routes/security.py:281-283`): Forward `"partial"` and `"pose_visibility"` in `req.activity` Allowlist
- **File & Line**: `backend/app/api/routes/security.py:281-283`
- **Actual Code**:
  ```python
  "activity": [{k: e.get(k) for k in ("track_id", "label", "who", "colour", "legs", "posture", "near", "named",
                                      "text", "lab_no", "at", "size", "hint")}
               for e in (req.activity or [])[:12] if isinstance(e, dict)],
  ```
- **Suggested Backend Fix for Claude**:
  - Add `"partial", "pose_visibility"` to the allowlist tuple in `security.py:281-282` so the portal API and WebSocket consumers preserve the 8-part `pose_visibility` (`PREDICTED` / `OCCLUDED` / `OUT_OF_FRAME`) and `partial` flags emitted by `tools/security_vision/activity.py`.

---

### Contract Issue 3 (`P2` — `backend/app/services/ai.py`): Bound Embedding / Ollama Timeout When Cameras Are Live
- **File**: `backend/app/services/ai.py`
- **Problem**:
  - If any backend code calls Ollama `/api/embeddings` or `/api/embed` without `"options": {"num_gpu": 0}`, Ollama loads `nomic-embed-text` onto `CUDA0`, which contends with the two DirectML camera processes on the GTX 1650 and can stall for 55+ seconds.
- **Suggested Backend Fix for Claude**:
  - Ensure any direct Ollama call in `backend/app/services/ai.py` always includes `"options": {"num_gpu": 0}` when `/gpu-gate` returns `"cpu"` (or always for embeddings).
