---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/How_To_Run_System.md"
source_hash: "423ffaf45cb26f32a7ddbc7257db2e10ff535ad1dc66796c87c08263b838570b"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/How_To_Run_System.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[docs_CODEX_PROMPT.md]] - mentioned by docs
- [[docs_HANDOFF_2026-10-09.md]] - mentioned by docs
- [[docs_SECURITY_FINDINGS_2026-10-18.md]] - mentioned by docs
- [[docs_knowledge-platform_NEXT_PHASE_2026-10-13.md]] - mentioned by docs

Terminal 1:"Backend"   [ http://localhost:8000/api/docs#/ ]

cd "C:\Users\dell\OneDrive\Desktop\Bsc\codes\smart-lab-portal\backend"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\activate
alembic upgrade head
python seed.py
uvicorn app.main:app --host 0.0.0.0 --port 8000

------------------------------------------------------------------------------------------------------------------------
Terminal 2:"Main Server (laptop)"

cd "C:\Users\dell\OneDrive\Desktop\Bsc\codes\draft_codes\face_server"
python face_server.py

------------------------------------------------------------------------------------------------------------------------
Terminal 3:"Frontend"  [ http://localhost:5173 ]

cd "C:\Users\dell\OneDrive\Desktop\Bsc\codes\smart-lab-portal\frontend"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
npm install
npm run dev

------------------------------------------------------------------------------------------------------------------------
PGadmin for observing tables of db in windows
------------------------------------------------------------------------------------------------------------------------
LogIn Credentials:

ali@giu-uni.de	        (password: see README - not stored here)	     Student — you, USER1
admin@giu-uni.de     	(password: see README - not stored here)	         Administrator
ramy@giu-uni.de	        (password: see README - not stored here)	         Lab staff — Dr. Ramy, USER2
hemaly@giu-uni.de	(password: see README - not stored here)	         Lab staff — Eng. Hemaly (lab engineer, master PC), USER5
