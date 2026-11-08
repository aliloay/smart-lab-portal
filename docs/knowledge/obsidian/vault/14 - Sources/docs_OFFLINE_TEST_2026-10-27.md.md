---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/OFFLINE_TEST_2026-10-27.md"
source_hash: "add828e7917b90fe4903c3000390d50faa9a7fa0589e4bb15ee4b89c1ddac57c"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/OFFLINE_TEST_2026-10-27.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[backend_app_core_config.py]] - mentioned by docs
- [[backend_app_services_ai.py]] - mentioned by docs

# Offline acceptance test (P8) - how to run it

Status 2026-10-27: **NOT TESTED offline yet.** The script works (dry run on the isolated copy, internet up:
12/13 checks passed, labelled "NOT AN OFFLINE TEST"; the one failure - text-to-speech 503 - happened while the
local AI benchmark was loading the CPU). The real test needs the laptop with the internet disconnected.

## What is already enforced in code (verified by reading the code, not by an offline run)
- Lab AI: `AI_LOCAL_ONLY=True` (backend/app/core/config.py) - a cloud key is ignored, no silent fallback
  (`provider()` in backend/app/services/ai.py). The assistant uses Ollama at `OLLAMA_URL` (this laptop).
- Project knowledge: tools/knowledge (local index, local embeddings via Ollama).
- Voice: faster-whisper with `local_files_only` (VOICE_OFFLINE=1) + Piper - both on this laptop.
- Browser: Content-Security-Policy allows only the portal itself (no CDN, no external fonts).

## Steps (owner, about 35 minutes)
1. Start everything as usual (`launch.bat`) and wait until the portal opens. **Stop any benchmark.**
2. Keep the Ethernet cable to Smart_Lab connected; **turn Wi-Fi off** (the Vodafone connection is the internet).
3. In a terminal in the project folder:
   `py -I tools\offline\offline_check.py --minutes 30`
   (asks for your admin e-mail and password at a hidden prompt; nothing is stored)
4. Each minute prints e.g. `13/13 pass  OFFLINE-VERIFIED round`. At the end:
   `"verdict": "OFFLINE VERIFIED"` and the file `backups\offline_check_<time>.json`.
5. Turn Wi-Fi back on.

## Pass criteria
- every round OFFLINE (the script checks 1.1.1.1:443, 8.8.8.8:53 and a DNS lookup - all must fail);
- all checks pass in every round: portal health, sign-in, summary, AI status, a lab AI answer (not a cloud model),
  project knowledge lookup, voice status, speak -> transcribe round trip, scan registry + a marker image, xlsx report
  export, OPC UA port 4840, Ollama 11434;
- 30 minutes without a failed round. Any failure: the JSON names the check and its error.

