import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const when = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: { name: 'Daily 20:00', parameters: { rule: { interval: [{ field: 'days', triggerAtHour: 20 }] } } },
  output: [{}]
});

const report = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Build Report In Backend',
    parameters: {
      method: 'GET',
      url: API + '/reports/daily',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"title": "Daily lab report - 2026-09-26", "lines": ["Bookings: none in this period."], "dedupe_key": "daily-report:2026-09-26"}]
});

const send = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Send To Administrators',
    parameters: {
      method: 'POST',
      url: API + '/notify',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "admins", kind: "DAILY_REPORT", title: String($json.title).slice(0, 160), body: String($json.lines.join(" ")).slice(0, 500), link: "/admin/operations", severity: "info", dedupe_key: $json.dedupe_key }) }}')
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"created": 1, "duplicate": false}]
});

const recordRun = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Record Run', executeOnce: true, onError: 'continueRegularOutput',
    parameters: {
      method: 'POST',
      url: API + '/runs',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ workflow: "06-daily-report", status: "success", summary: $("Build Report In Backend").item.json.title, execution_id: $execution.id }) }}')
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Daily lab report\nThe backend computes every figure from recorded rows (no estimates); n8n only schedules and delivers. Idempotent per day via dedupe key. Add an Email/Slack node in parallel to Send To Administrators for an external channel.", [], { color: 4 });

export default workflow('smartlab-06', 'Smart Lab 06 - Daily lab report')
  .add(when).to(report).to(send).to(recordRun).add(note);
