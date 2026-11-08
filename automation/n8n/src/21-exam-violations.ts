import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const tick = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: { name: 'Every 5 Minutes', parameters: { rule: { interval: [{ field: 'minutes', minutesInterval: 5 }] } } },
  output: [{}]
});

const check = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Check In Backend',
    parameters: {
      method: 'GET',
      url: API + '/robotics/exam-violations',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"topic": "exam-violations", "count": 1, "items": [{"title": "t", "body": "b", "severity": "warning", "link": "/admin/equipment", "dedupe_key": "k", "lab_id": 1}]}]
});

const each = node({
  type: 'n8n-nodes-base.splitOut',
  version: 1,
  config: { name: 'One Item Per Finding', parameters: { fieldToSplitOut: 'items' } },
  output: [{"title": "t", "body": "b", "severity": "warning", "link": "/admin/equipment", "dedupe_key": "k"}]
});

const tell = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Notify Staff',
    parameters: {
      method: 'POST',
      url: API + '/notify',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "staff", kind: "EXAM_VIOLATION", title: String($json.title).slice(0, 160), body: String($json.body).slice(0, 500), link: $json.link, severity: $json.severity, dedupe_key: $json.dedupe_key }) }}')
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
      jsonBody: expr('{{ JSON.stringify({ workflow: "21-exam-violations", status: "success", summary: "Findings: " + $("Check In Backend").first().json.count, execution_id: $execution.id }) }}')
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Exam-mode reports\nPrograms the PC agent saw running in exam mode. Staff decide what a report means; nothing is automatic.", [], { color: 4 });

export default workflow('smartlab-21', 'Smart Lab 21 - Exam-mode reports')
  .add(tick).to(check).to(each).to(tell).to(recordRun).add(note);
