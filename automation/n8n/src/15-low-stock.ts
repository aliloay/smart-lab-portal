import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const tick = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: { name: 'Every Hour', parameters: { rule: { interval: [{ field: 'hours', hoursInterval: 1 }] } } },
  output: [{}]
});

const check = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Check In Backend',
    parameters: {
      method: 'GET',
      url: API + '/robotics/low-stock',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"topic": "low-stock", "count": 1, "items": [{"title": "t", "body": "b", "severity": "warning", "link": "/admin/equipment", "dedupe_key": "k", "lab_id": 1}]}]
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
      jsonBody: expr('{{ JSON.stringify({ audience: "staff", kind: "LOW_STOCK", title: String($json.title).slice(0, 160), body: String($json.body).slice(0, 500), link: $json.link, severity: $json.severity, dedupe_key: $json.dedupe_key }) }}')
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
      jsonBody: expr('{{ JSON.stringify({ workflow: "15-low-stock", status: "success", summary: "Findings: " + $("Check In Backend").first().json.count, execution_id: $execution.id }) }}')
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Consumable below reorder level\nEstimated quantity at or below the bin's reorder level. Only calibrated bins are estimated.", [], { color: 4 });

export default workflow('smartlab-15', 'Smart Lab 15 - Consumable below reorder level')
  .add(tick).to(check).to(each).to(tell).to(recordRun).add(note);
