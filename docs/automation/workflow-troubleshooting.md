# Workflow troubleshooting

| Symptom | Check |
|---|---|
| n8n container not running | `AUTOMATION_WEBHOOK_BASE` set in `.env`? `docker compose ps n8n`, `docker compose logs n8n` |
| HTTP nodes return 401 | The Header Auth credential value must equal `AUTOMATION_API_KEY` |
| HTTP nodes cannot connect | Inside the stack the backend is `http://backend:8000`, not `localhost` |
| A workflow never fires | Exports are inactive by default: activate it in the editor; check the schedule's timezone |
| Notifications not received | Portal notifications appear for staff; e-mail needs SMTP settings |
| Last run not shown in the portal | The "Record Run" node failed; open the execution in n8n |
| Live workflows differ from the repo | `py tools/knowledge/kb.py drift` lists differences; re-export with `automation/n8n/export_workflows.py` |

Historical recovery notes: [N8N_RECOVERY_2026-10-14.md](../N8N_RECOVERY_2026-10-14.md).
