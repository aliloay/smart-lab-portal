# AI assistant, priorities and trends

Additions on top of the Operations Center. Several work without AI.

The AI part runs on either:

* **Ollama — free, on your own computer** (default when no Claude key is set).
  No account, no per-question cost, nothing leaves the machine.
* **Claude API — paid, optional.** Better answers, costs a few cents a question.

| Feature | Needs AI? | Where |
|---|---|---|
| **What to fix first**: ranked maintenance list | No, deterministic | Operations Center, Maintenance page |
| **Trends**: week over week, no-show and late rates, per-lab table | No | Operations Center → Trends |
| **Export**: bookings / sessions / events / weekly trends as CSV, print to PDF | No | Operations Center → download icon |
| **Ask the lab**: chat about usage, access, devices, maintenance | Yes | Operations Center |
| **AI summaries**: open issues, weekly report | Yes | Maintenance page button, n8n workflow 07 |
| **Ask Smart Lab** (students): my bookings, my reports, free labs | Yes | Student dashboard |

## Two assistants

| | Staff assistant | Student helper |
|---|---|---|
| Who | Lab staff, administrators | Any signed-in user |
| Sees | Analytics through 8 read-only tools | Only the caller's own bookings and reports, plus the lab list with booked time slots (never who booked) |
| Free model (Ollama) | `qwen2.5:3b` (can call tools) | `qwen2.5:1.5b` (lighter, no tools) |
| Claude model | `claude-opus-5` | `claude-haiku-4-5` |
| Limit per user | 30 questions/hour | 20 questions/hour |
| Audit action | `AI_QUESTION` | `AI_STUDENT_QUESTION` |

The student helper does not choose what to look up. The backend fetches that
student's data and hands it to the model as context, which is why a small
model is enough. If no AI is set up, the student card is hidden.

## How the assistant works

```
staff question ─► FastAPI /api/ai/ask ─► Ollama qwen2.5:3b  or  Claude
                                            │  calls read-only tools
                                            ▼
               app/services/ai.py tools = the SAME functions the portal uses:
               operations overview, trends, daily/weekly report, maintenance
               priorities, open issues, anomalies, lab readiness, lab list
                                            │  results (from PostgreSQL)
                                            ▼
                         answer grounded in recorded data ─► chat panel
```

* **Grounded.** The model gets numbers only through tools that query the
  database. The system prompt forbids estimating, and requires saying "nothing
  recorded" when a tool returns nothing.
* **Read-only.** There is no tool that writes. The assistant cannot open doors,
  change bookings, or assign or close issues.
* **Staff and administrators only.** Students get 403 (they have their own helper, above). Every question is written
  to the audit log (`AI_QUESTION`), with a per-user limit
  (`AI_QUESTIONS_PER_HOUR`, default 30).
* **Untrusted text.** Issue titles and descriptions are written by users. They
  reach the model only inside tool results, and the system prompt tells the
  model to treat them as data, never as instructions.
* **No biometric or personal data** is sent. Tools return aggregates, ticket
  text and lab codes.
* **Optional.** With no provider, `/api/ai/status` reports
  `configured: false`, the panel says how to set it up, and nothing else
  changes. If Ollama is configured but not running, or a model is not
  downloaded, the panel says exactly that.
* **Refusal fallback (Claude only).** Requests enable the Claude API's server-side fallback
  (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`). If the
  model declines, the API retries on a fallback model in the same call.

## Maintenance priority score (deterministic)

| Factor | Points |
|---|---|
| Severity | CRITICAL 100 · HIGH 60 · MEDIUM 30 · LOW 10 |
| Overdue vs the published SLA | +40, plus up to +20 for how far past it |
| Safety category | +20 |
| Nobody assigned | +10 |
| Confirmed bookings in that lab within 24 h | +5 each, max +25 |

The order is reproducible and explainable without AI. The AI summary explains
and groups it; it never reorders it.

## Trend definitions

* Weeks start Monday in `LOCAL_TIMEZONE`. The current week is marked partial (`*`).
* **No-show:** a finished confirmed booking with no recorded door entry.
* **Late:** the first entry is more than 15 minutes after the booking start. The
  rate is out of attended bookings.
* A week where nothing finished has no rate (gap), not 0%.

## Setup — free (Ollama), recommended

Tested sizing: 16 GB RAM with a 4 GB NVIDIA GPU (GTX 1650) runs both models on
the GPU. Without a GPU they still run on the CPU, just slower.

1. Install Ollama for Windows from https://ollama.com/download and start it
   (it sits in the tray and starts with Windows).
2. In PowerShell, download the two models (about 3 GB in total, one time):
   ```
   ollama pull qwen2.5:3b
   ollama pull qwen2.5:1.5b
   ```
3. Restart the portal (`launch.bat`). From then on `launch.bat` starts Ollama
   if it is not already running, and downloads any missing model in a
   minimized "Smart Lab - AI models" window (so step 2 is optional). Docker
   reaches Ollama at `http://host.docker.internal:11434`; nothing to add to
   `.env`.
4. Staff: Operations Center → **Ask the lab**. Students: dashboard →
   **Ask Smart Lab**.

If you also have `ANTHROPIC_API_KEY` in `.env` but want the free model, add
`AI_PROVIDER=ollama`.

The first question after a restart takes 5–20 s while the model loads; after
that answers take a few seconds. Small local models are less precise than
Claude: the numbers still come from the database, but check important figures
on the charts. For better staff answers on a stronger PC, set
`OLLAMA_MODEL=qwen2.5:7b` (and `ollama pull qwen2.5:7b`).

## Setup — Claude (paid, optional)

1. Create a key at https://console.anthropic.com (pay-per-use; a lab-scale
   question costs a few cents).
2. Add it to `.env` (never commit it):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
3. Restart: `launch.bat` (or `docker compose up -d --build`).

Optional settings (backend env): `AI_PROVIDER` (`auto`/`ollama`/`anthropic`),
`OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_STUDENT_MODEL`, `OLLAMA_NUM_CTX` (16384),
`AI_MODEL` (default `claude-opus-5`), `AI_STUDENT_MODEL` (`claude-haiku-4-5`),
`AI_EFFORT` (default `medium`), `AI_MAX_TOOL_ROUNDS` (6),
`AI_QUESTIONS_PER_HOUR` (30), `AI_STUDENT_ENABLED` (true),
`AI_STUDENT_QUESTIONS_PER_HOUR` (20).

## Endpoints

| Method | Path | Auth |
|---|---|---|
| GET | `/api/ai/status` | staff |
| GET | `/api/ai/student/status` · POST `/api/ai/student/ask` | any signed-in user |
| POST | `/api/ai/ask` `{question, history[]}` | staff |
| POST | `/api/ai/summaries/issues` · `/api/ai/summaries/weekly` | staff |
| GET | `/api/ai/maintenance-priorities` | staff (no AI needed) |
| GET | `/api/analytics/trends?weeks=` | staff |
| GET | `/api/analytics/export.csv?kind=bookings\|sessions\|events\|weekly&days=` | staff |
| GET | `/api/automation/maintenance/priorities` · `/api/automation/ai/weekly-summary` | `X-Automation-Key` (n8n) |

Tests: `backend/tests/test_ai.py` uses a fake Claude client and
`backend/tests/test_ai_local.py` a fake Ollama server, so the tool loops,
student data isolation, access control, limits and the AI-off path are
verified without any model running.
