# Smart Lab portal - working rules for Claude Code

BSc thesis (GIU). Public repo. Start every session with `docs/PROGRESS_CHECKPOINT.md`, `git status`, `git log --oneline -6`.

## Never
- Delete/reset/truncate the live `smartlab` DB; tests only on `smartlab_test` (conftest forces it).
- Send anything that moves a robot. Control routes exist (docs/ROBOT_CONTROL.md) but every adapter stays UNAVAILABLE until the owner signs off a commissioning step; collectors stay read-only.
- Open the door from anything but the Master ESP32; change door firmware, auth or credentials.
- Edit/activate/deactivate live n8n workflows; push to GitHub; commit secrets, `.env`, `camera.env`, `robot.env`, photos of people.
- Overwrite the owner's uncommitted work (`.env.example`, `frontend/e2e/command_center.mjs`, untracked files) - copy first.
- Install packages / download models without asking. Cameras keep GPU priority; since 2026-10-19 (owner approved after an A/B: answers 68 s -> 3 s, camera 2 unaffected) both assistants run qwen2.5:1.5b on the GPU - revert with OLLAMA_CPU_ONLY=true + knowledge llm_on_cpu if a camera suffers.

## Map
- backend/ FastAPI (routes in app/api/routes) · frontend/ React+TS+Tailwind · docker-compose.yml (db, backend, frontend, n8n, backup)
- tools/security_vision (camera, native Windows Python 3.14, DirectML GTX 1650, port 5100)
- tools/robot_monitor (UR5e collector, Python 3.12 + ur_rtde) · tools/knowledge (vault, search, agent, graph; port 5199)
- firmware/ ESP32 · automation/n8n/json (repo copies; live n8n at 127.0.0.1:5678)
- Lab guides: docs/LAB_TEST_2026-10-15.md · visuals: docs/VISUAL_FOUNDATION.md

## Tests (run serially)
- Backend: `docker compose run --rm --no-deps -T -v "${PWD}\backend:/app" backend python -m pytest -q -p no:cacheprovider` (~7 min, 436 tests)
- `py -m pytest -q tools/security_vision` · `py -m pytest -q tools/robot_monitor` · `py -m pytest -q tools/knowledge`
- Frontend: `npx tsc --noEmit -p frontend` and `npx vite build` (in frontend/)
- The running backend/frontend are baked images: code changes are live only after `docker compose build backend frontend` + `up -d --no-deps backend frontend` (owner OK).

## Tools (MCP, user scope, set up 2026-10-28)
- chrome-devtools (1.12.0, headless, isolated profile, no usage stats / CrUX): console, network, perf traces, emulation. Point it at the test copy (:5176 / :8100), never click door/robot/emergency controls.
- context7 (4.4.4): current library docs. Ask for the version in package.json (Tailwind 3.4, React 18, Vite 6) - it defaults to the newest.
- Repeatable e2e / devices: our Playwright scripts (frontend/e2e/click_everything.mjs, responsive_audit.mjs), not an MCP.
- GitHub: `gh` CLI read-only (no push). DB: `docker compose exec db psql` read-only SELECTs, no DB MCP.
- claude-mem: cross-session memory (search before re-deriving past work).
- n8n-lab (local n8n MCP, 2026-10-29): READ ONLY - search_workflows / get_workflow_details / executions. Its 18 write /
  run tools are denied in ~/.claude/settings.json; never run, edit or (un)publish a workflow. The claude.ai n8n connector
  points at an expired n8n Cloud trial (404) - kept, unused.

## Working style
- Find answers with `py tools/knowledge/agent.py "<question>"` or `py tools/knowledge/graph.py related <path>` before rereading large files.
- Label claims: verified / tested offline / live-verified / unverified. Hardware results only from real measurements.
- Keep sessions to one mission; update docs/PROGRESS_CHECKPOINT.md at milestones (long sessions re-read ~500 k tokens per request).
