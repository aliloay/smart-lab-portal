---
type: "catalogue"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---

# Workflow catalogue

23 workflow definitions from `automation/n8n/json/` (the files mounted into n8n). Live state comes from the private export of the running n8n (`kb.py live-export`).

| Workflow | Live | Trigger | Writes | External | File |
|---|---|---|---|---|---|
| [[Smart Lab 01 - Booking confirmation briefing]] | active | webhook | yes | none | `automation/n8n/json/01-booking-confirmation.json` |
| [[Smart Lab 02 - Upcoming booking reminders]] | active | scheduleTrigger | yes | none | `automation/n8n/json/02-booking-reminders.json` |
| [[Smart Lab 03 - Access denial intelligence]] | active | webhook | yes | none | `automation/n8n/json/03-access-denial-intelligence.json` |
| [[Smart Lab 04 - Device offline alert with escalation]] | active | webhook, scheduleTrigger | yes | none | `automation/n8n/json/04-device-offline-escalation.json` |
| [[Smart Lab 05 - Maintenance automation]] | active | webhook, scheduleTrigger | yes | none | `automation/n8n/json/05-maintenance-automation.json` |
| [[Smart Lab 06 - Daily lab report]] | active | scheduleTrigger | yes | none | `automation/n8n/json/06-daily-report.json` |
| [[Smart Lab 07 - Weekly lab report]] | active | scheduleTrigger | yes | none | `automation/n8n/json/07-weekly-report.json` |
| [[Smart Lab 08 - Sensor threshold alerts]] | active | scheduleTrigger | yes | none | `automation/n8n/json/08-sensor-thresholds.json` |
| [[Smart Lab 09 - Pre-booking lab readiness check]] | active | scheduleTrigger | yes | none | `automation/n8n/json/09-pre-booking-check.json` |
| [[Smart Lab 10 - Post-session follow-up]] | active | scheduleTrigger | yes | none | `automation/n8n/json/10-post-session.json` |
| [[Smart Lab 11 - Daily data quality check]] | active | scheduleTrigger | yes | none | `automation/n8n/json/11-data-quality.json` |
| [[Smart Lab 12 - Rule-based anomaly detection]] | active | scheduleTrigger | yes | none | `automation/n8n/json/12-anomaly-detection.json` |
| [[Smart Lab 13 - Environment hazard escalation]] | active | scheduleTrigger | yes | none | `automation/n8n/json/13-environment-hazard-escalation.json` |
| [[Smart Lab 14 - Environment _ bin node offline]] | active | scheduleTrigger | yes | none | `automation/n8n/json/14-node-offline.json` |
| [[Smart Lab 15 - Consumable below reorder level]] | active | scheduleTrigger | yes | none | `automation/n8n/json/15-low-stock.json` |
| [[Smart Lab 16 - Stock change with nobody inside]] | active | scheduleTrigger | yes | none | `automation/n8n/json/16-unattended-stock-change.json` |
| [[Smart Lab 17 - Reusable item overdue]] | active | scheduleTrigger | yes | none | `automation/n8n/json/17-asset-overdue.json` |
| [[Smart Lab 18 - Robot offline or fault]] | active | scheduleTrigger | yes | none | `automation/n8n/json/18-robot-offline-fault.json` |
| [[Smart Lab 19 - Robot running without a booking]] | active | scheduleTrigger | yes | none | `automation/n8n/json/19-robot-without-booking.json` |
| [[Smart Lab 20 - Lab PC offline]] | active | scheduleTrigger | yes | none | `automation/n8n/json/20-pc-offline.json` |
| [[Smart Lab 21 - Exam-mode reports]] | active | scheduleTrigger | yes | none | `automation/n8n/json/21-exam-violations.json` |
| [[Smart Lab 22 - Robotics Lab daily summary]] | active | scheduleTrigger | yes | none | `automation/n8n/json/22-robotics-daily.json` |
| [[Smart Lab 23 - Emergency_ warn people inside, check the door]] | active | webhook | yes | none | `automation/n8n/json/23-emergency.json` |
