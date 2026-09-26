# AI assistant, priorities and trends

Three additions on top of the Operations Center. Two work without AI.

| Feature | Needs an AI key? | Where |
|---|---|---|
| **What to fix first**: ranked maintenance list | No, deterministic | Operations Center, Maintenance page |
| **Trends**: week over week, no-show and late rates, per-lab table | No | Operations Center → Trends |
| **Export**: bookings / sessions / events / weekly trends as CSV, print to PDF | No | Operations Center → download icon |
| **Ask the lab**: chat about usage, access, devices, maintenance | Yes | Operations Center |
| **AI summaries**: open issues, weekly report | Yes | Maintenance page button, n8n workflow 07 |

## How the assistant works

```
staff question ─► FastAPI /api/ai/ask ─► Claude (claude-opus-5)
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
* **Staff and administrators only.** Students get 403. Every question is written
  to the audit log (`AI_QUESTION`), with a per-user limit
  (`AI_QUESTIONS_PER_HOUR`, default 30).
* **Untrusted text.** Issue titles and descriptions are written by users. They
  reach the model only inside tool results, and the system prompt tells the
  model to treat them as data, never as instructions.
* **No biometric or personal data** is sent. Tools return aggregates, ticket
  text and lab codes.
* **Optional.** With `ANTHROPIC_API_KEY` empty, `/api/ai/status` reports
  `configured: false`, the panel says so, and nothing else changes.
* **Refusal fallback.** Requests enable the Claude API's server-side fallback
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

## Setup

1. Create a key at https://console.anthropic.com (pay-per-use; a lab-scale
   question costs a few cents).
2. Add it to `.env` (never commit it):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
3. Restart: `docker compose --profile automation up -d --build` (or `launch.bat`).
4. Operations Center → **Ask the lab**.

Optional settings (backend env): `AI_MODEL` (default `claude-opus-5`),
`AI_EFFORT` (default `medium`; use `high` for deeper answers),
`AI_MAX_TOOL_ROUNDS` (6), `AI_QUESTIONS_PER_HOUR` (30).

## Endpoints

| Method | Path | Auth |
|---|---|---|
| GET | `/api/ai/status` | staff |
| POST | `/api/ai/ask` `{question, history[]}` | staff |
| POST | `/api/ai/summaries/issues` · `/api/ai/summaries/weekly` | staff |
| GET | `/api/ai/maintenance-priorities` | staff (no AI needed) |
| GET | `/api/analytics/trends?weeks=` | staff |
| GET | `/api/analytics/export.csv?kind=bookings\|sessions\|events\|weekly&days=` | staff |
| GET | `/api/automation/maintenance/priorities` · `/api/automation/ai/weekly-summary` | `X-Automation-Key` (n8n) |

Tests: `backend/tests/test_ai.py` uses a fake Claude client, so the tool loop,
access control, limits and the AI-off path are verified without API calls.
