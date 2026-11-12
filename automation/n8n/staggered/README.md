# Staggered 5-minute workflows (2026-11-12) - NOT imported

The five workflows that run every 5 minutes (02, 04, 13, 18, 21) all started in the same minute and gave the
Docker CPU spike (~176 %). These copies change ONLY the Schedule Trigger to a 6-field n8n cron (seconds first):

| Workflow | Cron | Runs at minute |
|---|---|---|
| 02 booking reminders | `0 0/5 * * * *` | 0, 5, 10 ... |
| 04 device offline escalation | `0 1/5 * * * *` | 1, 6, 11 ... |
| 13 environment hazard | `0 2/5 * * * *` | 2, 7, 12 ... |
| 18 robot offline / fault | `0 3/5 * * * *` | 3, 8, 13 ... |
| 21 exam violations | `0 4/5 * * * *` | 4, 9, 14 ... |

Same frequency (every 5 min), at most one of these five starts in any minute (was all five).
Import (owner): n8n > each workflow > Schedule Trigger > Trigger interval "Custom (Cron)" > paste the expression > Save.
Check the "next executions" preview n8n shows before saving. The credential issue (06/08/09) is separate.
