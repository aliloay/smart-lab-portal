# Voice for the AI assistant (local, 2026-10-26)

How to use it: press the AI bubble and choose **Talk** (recording starts), or press the **mic** next to "Ask". Speak, then
press the mic again (or it stops by itself at 30 s). The question appears as text and is answered through the same
path as a typed question, with the same tools, permissions and hourly limit. Door and robot commands are never
possible from the assistant. Spoken questions get a short spoken answer (the first sentences), which you can stop
with "Stop speaking".

| Part | What | Where |
|---|---|---|
| Speech-to-text | faster-whisper `base.en`, CPU int8, 2 threads, **one at a time** (busy = 429) | `voice_service.py` on this laptop |
| Text-to-speech | Piper `en_US-lessac-medium` (local), sentence by sentence; falls back to the browser's voice | same |
| Portal | `POST /api/voice/transcribe` and `POST /api/voice/speak` (signed-in users; hourly limit), `GET /api/voice/status` | `backend/app/api/routes/voice.py` |
| Browser | MediaRecorder (opus), mic released after every question; `lib/voice.ts`, `components/ai.tsx` | |

Nothing is stored: the audio is decoded in memory and dropped, and no recording or transcript is written to disk or the database.
The microphone needs the HTTPS portal address (or localhost), the same as the phone camera.

## Start
```
py -3.12 tools/voice/voice_service.py      # 127.0.0.1:5320; key VOICE_KEY in tools/voice/voice.env (git-ignored)
```
Backend `.env`: `VOICE_KEY=<same value>` (compose passes `VOICE_URL` / `VOICE_KEY`), then rebuild/restart the backend.
Models (git-ignored): Whisper is cached from Hugging Face on first start (`Systran/faster-whisper-base.en`, ~140 MB);
`models/en_US-lessac-medium.onnx` + `.json` from `rhasspy/piper-voices` v1.0.0 (63 MB).
`VOICE_STT_MODEL=tiny.en` is faster (see below).

## Measured on this laptop (2026-10-26)
Synthetic test speech (Piper voice, 5 lab questions). This is **not** a real voice or accent; a test with real
speakers is still to do.

| STT model (CPU int8, 2 threads) | per question | word error rate | load |
|---|---|---|---|
| tiny.en | 0.76 s | 2.9 % | 1.6 s |
| **base.en** (default: usually more robust to real voices) | 1.28 s | 5.7 % | cached |
| small.en | 5.0 s | 6.9 % | too slow |

| End to end | Result |
|---|---|
| API: transcribe (opus) / answer (common questions) / speak 300 chars | p50 1.45 s / 0.21 s / 1.9 s |
| Browser (fake mic, Chrome): stop -> question shown / answer shown / first spoken audio | 3.0-3.5 s / 3.0-3.5 s / 4.3-5.3 s, 3/3 PASS, mic released |
| Camera service during nonstop transcription (21 in a row) | 10.0 analyses/s idle and during (no change) |

Tests: `tools/voice/test_voice_service.py` (6), `backend/tests/test_voice.py` (5), `frontend/e2e/voice_talk.mjs`.
