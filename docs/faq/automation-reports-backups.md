# FAQ: n8n automations, reports and backups

## Q: Which n8n workflows exist?
Also asked: automations, list of workflows, what does n8n do
**A:** 26 workflows. 23 lab workflows (01–23: bookings, access denials, device offline, maintenance, daily / weekly reports, sensors, stock, robots, PCs, exam, emergency) and 3 knowledge workflows (source sync, vault health check, weekly knowledge summary).
Source: `automation/n8n/json/`

## Q: How do I get the daily report?
Also asked: daily lab report, today's summary, report for today
**A:** Ask the portal assistant "today's summary" for an instant answer. n8n workflow 06 also prepares the daily lab report at 20:00.
Source: `backend/app/services/agent.py` (report_daily), `automation/n8n/json/06-daily-report.json`

## Q: How do I get the weekly report?
Also asked: weekly lab report, report for this week, last 7 days
**A:** Ask the portal assistant "weekly report", or open the weekly report page, which downloads as a PDF (/report?period=weekly). n8n workflow 07 also prepares it every Monday at 07:00.
Source: `backend/app/services/agent.py` (report_weekly), `automation/n8n/json/07-weekly-report.json`

## Q: How do I get the monthly report?
Also asked: monthly lab report, last 30 days, report for this month
**A:** Ask the portal assistant "monthly report", or open /report?period=monthly for the PDF covering the last 30 days.
Source: `backend/app/services/agent.py` (report_monthly / range_report)

## Q: When do the scheduled workflows run?
Also asked: n8n schedule, when does the daily report run
**A:** Daily report 20:00; weekly report Monday 07:00; robotics daily summary 07:00; data-quality check 06:00; maintenance summary 08:00; vault health check 07:00; weekly knowledge summary Monday 08:00. Booking reminders, device-offline and sensor checks repeat every few minutes. A run is skipped if the laptop is asleep at that time.
Source: schedule triggers in `automation/n8n/json/*.json`

## Q: Where do notifications appear?
Also asked: alerts, how am I notified, email notifications
**A:** In the portal: the bell (notifications) and the alerts list. The automations post to the portal's own API; no email or Telegram account is configured.
Source: n8n credentials (header auth to the portal only), `backend/app/api/routes/notifications.py`

## Q: When does the database back up?
Also asked: backup schedule, how often is the database saved
**A:** Every 6 hours. Each dump is checked with pg_restore before it is kept, and a failure is retried after 5 minutes. Uploads (photos) are archived once a day. Dumps older than 14 days and uploads older than 7 days are moved, never deleted, to the archive on D:.
Source: `docker-compose.yml` (backup service)

## Q: Has a backup restore been tested?
Also asked: restore drill, can we restore the database
**A:** Yes, on 21 Nov 2026: the latest dump was restored into a new, separate database with 44 tables and 374,212 rows, on the current schema. The live database was only read.
Source: `tools/evidence/restore_drill.py`, `docs/reports/restore_drill_20261121_200629.json`
