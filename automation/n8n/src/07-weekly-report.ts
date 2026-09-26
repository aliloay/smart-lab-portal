import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const when = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: { name: 'Mondays 07:00', parameters: { rule: { interval: [{ field: 'weeks', weeksInterval: 1, triggerAtDay: [1], triggerAtHour: 7 }] } } },
  output: [{}]
});

const report = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Build Report In Backend',
    parameters: {
      method: 'GET',
      url: API + '/reports/weekly',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"title": "Weekly lab report - 2026-09-20 to 2026-09-26", "lines": ["Bookings: none in this period."], "dedupe_key": "weekly-report:2026-09-26"}]
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
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "admins", kind: "WEEKLY_REPORT", title: String($json.title).slice(0, 160), body: String($json.lines.join(" ")).slice(0, 500), link: "/admin/operations", severity: "info", dedupe_key: $json.dedupe_key }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
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
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ workflow: "07-weekly-report", status: "success", summary: $("Build Report In Backend").item.json.title, execution_id: $execution.id }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Weekly lab report\nThe backend computes every figure from recorded rows (no estimates), including the previous week for comparison; n8n only schedules and delivers. Idempotent per period via dedupe key.", [], { color: 4 });

export default workflow('smartlab-07', 'Smart Lab 07 - Weekly lab report')
  .add(when).to(report).to(send).to(recordRun).add(note);
