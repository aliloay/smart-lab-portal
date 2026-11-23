# Final release and rollback runbook - 23 Nov 2026

## Release (what was done, and how to repeat it)
1. **Backup first:**
   ```
   docker compose exec -T db pg_dump -U smartlab -Fc smartlab > backups\predeploy_<date>.dump
   ```
   Verify it with `pg_restore --list` (count the entries, don't print secrets).
2. **Code:** worktree `C:\Projects\smart-lab-claude-closure` (branch `claude/final-closure-2026-11-23`, base `d023e98`). Copy the changed files into `C:\Projects\smart-lab-portal`; the list is in `CHANGED_FILES_AND_DIFF_SUMMARY.md`.
3. **Images, with a version stamp (never plain `docker build`):**
   ```
   powershell -ExecutionPolicy Bypass -File tools\deploy\build_images.ps1
   ```
   This tags the running images `:pre-<date>` as the rollback point and builds `:latest` with `BUILD_COMMIT`/`BUILD_TIME`.
4. **Restart only the two portal containers:**
   ```
   docker compose up -d --no-deps backend frontend
   ```
5. **Check:**
   - `https://localhost/api/health` → `status: ok`, `database: true`, and `version.id` equals the stamp printed in step 3.
   - Load the portal's login page.
6. **Knowledge service:**
   - Stop its `serve.py` process only.
   - Start it outside the tool's process tree, so it survives the tool session:
     ```
     Invoke-CimMethod Win32_Process Create 'cmd /k py tools\knowledge\serve.py'
     ```
     `launch.bat` also does this.
   - Run `py tools\knowledge\kb.py build` when the FAQ or docs change.
7. **Camera services:** restart only with both feeds reachable (at GIU), using `start_security_vision.bat` and `start_security_vision.bat camera2.env`.

## Rollback
| Part | Command | Time |
|---|---|---|
| Backend/frontend | `docker tag smart-lab-portal-backend:pre-<date> smart-lab-portal-backend:latest` (same for frontend), then `docker compose up -d --no-deps backend frontend` | about 1 min |
| Knowledge service | `git -C C:\Projects\smart-lab-portal checkout -- tools/knowledge docs/faq`, restart `serve.py`, `kb.py build` | about 2 min |
| Database | Not needed: no migration in this release. If ever needed: restore into a **new** database from the dump, never over `smartlab` (`CLAUDE.md`) | - |

## Do not
- Push, flash ESP32 boards, operate the door, command robots, or edit n8n workflows as part of a release.
- Delete old `:pre-*` images or `backups/` dumps.
