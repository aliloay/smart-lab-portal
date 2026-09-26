import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const created = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Issue Created Event',
    parameters: { httpMethod: 'POST', path: 'smartlab-issue-created', authentication: 'headerAuth', responseMode: 'onReceived' },
    credentials: { httpHeaderAuth: newCredential('Smart Lab webhook token') }
  },
  output: [{"body": {"type": "issue.created", "object": {"type": "issue", "id": "7"}}}]
});

const issue = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Get Issue Context',
    parameters: {
      method: 'GET',
      url: expr(API + '/issues/{{ $json.body.object.id }}'),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"issue_id": 7, "ticket": "ISS-2026-000007", "title": "Scope dead", "severity": "HIGH", "lab_code": "LAB_01", "assigned": false, "link": "/issues/7", "bookings_next_24h": 2}]
});

const urgent = ifElse({
  version: 2.2,
  config: { name: 'Urgent And Lab In Use?', parameters: { conditions: {"options": {"caseSensitive": true, "leftValue": "", "typeValidation": "loose"}, "conditions": [{"leftValue": expr('{{ $json.severity }}'), "operator": {"type": "string", "operation": "notEquals"}, "rightValue": "LOW"}, {"leftValue": expr('{{ $json.severity }}'), "operator": {"type": "string", "operation": "notEquals"}, "rightValue": "MEDIUM"}, {"leftValue": expr('{{ $json.bookings_next_24h }}'), "operator": {"type": "number", "operation": "gt"}, "rightValue": 0}], "combinator": "and"} } }
});

const tellUrgent = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Notify Staff Of Impact',
    parameters: {
      method: 'POST',
      url: API + '/notify',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "staff", kind: "MAINTENANCE_DIGEST", title: String($json.severity + " issue in a booked lab: " + $json.ticket).slice(0, 160), body: String($json.title + " - " + $json.bookings_next_24h + " booking(s) in " + $json.lab_code + " in the next 24 h.").slice(0, 500), link: $json.link, severity: $json.severity === "CRITICAL" ? "critical" : "warning", dedupe_key: "issue-impact:" + $json.issue_id }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"created": 1, "duplicate": false}]
});

const daily = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: { name: 'Daily 08:00', parameters: { rule: { interval: [{ field: 'days', triggerAtHour: 8 }] } } },
  output: [{}]
});

const digest = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Get Maintenance Digest',
    parameters: {
      method: 'GET',
      url: API + '/maintenance',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"open_issues": 3, "overdue": [{"ticket": "ISS-1"}], "unassigned_urgent": [], "assets_due": [], "dedupe_day": "2026-09-26"}]
});

const anything = ifElse({
  version: 2.2,
  config: { name: 'Anything Needs Attention?', parameters: { conditions: {"options": {"caseSensitive": true, "leftValue": "", "typeValidation": "loose"}, "conditions": [{"leftValue": expr('{{ $json.overdue.length + $json.unassigned_urgent.length + $json.assets_due.length }}'), "operator": {"type": "number", "operation": "gt"}, "rightValue": 0}], "combinator": "and"} } }
});

const tellDigest = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Send Maintenance Digest',
    parameters: {
      method: 'POST',
      url: API + '/notify',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "staff", kind: "MAINTENANCE_DIGEST", title: String("Maintenance digest: " + $json.overdue.length + " overdue, " + $json.unassigned_urgent.length + " urgent unassigned").slice(0, 160), body: String([...$json.overdue.map(i => i.ticket + " overdue"), ...$json.unassigned_urgent.map(i => i.ticket + " unassigned"), ...$json.assets_due.map(a => a.name + (a.overdue ? " maintenance overdue" : " maintenance due"))].join("; ")).slice(0, 500), link: "/issues", severity: "warning", dedupe_key: "maintenance-digest:" + $json.dedupe_day }) }}')
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
      jsonBody: expr('{{ JSON.stringify({ workflow: "05-maintenance-automation", status: "success", summary: "Maintenance notification sent", execution_id: $execution.id }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Maintenance automation\nEvent path: a HIGH/CRITICAL issue in a lab with bookings in the next 24 h is flagged to staff at once.\nDaily path: overdue (per published SLA), urgent unassigned, and equipment due for maintenance within 7 days.", [], { color: 4 });

export default workflow('smartlab-05', 'Smart Lab 05 - Maintenance automation')
  .add(created).to(issue).to(urgent.onTrue(tellUrgent.to(recordRun))).add(daily).to(digest).to(anything.onTrue(tellDigest.to(recordRun))).add(note);
