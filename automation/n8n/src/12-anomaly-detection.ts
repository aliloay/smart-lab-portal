import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const hourly = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: { name: 'Every Hour', parameters: { rule: { interval: [{ field: 'hours', hoursInterval: 1 }] } } },
  output: [{}]
});

const scan = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Run Anomaly Rules',
    parameters: {
      method: 'GET',
      url: API + '/anomalies?hours=24',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"count": 1, "anomalies": [{"rule": "denial_burst", "severity": "warning", "lab_code": "LAB_01", "count": 4, "detail": "4 refusals within 10 min.", "dedupe_key": "anomaly:denial_burst:1:2026-09-26"}]}]
});

const each = node({
  type: 'n8n-nodes-base.splitOut',
  version: 1,
  config: { name: 'One Item Per Anomaly', parameters: { fieldToSplitOut: 'anomalies' } },
  output: [{"rule": "denial_burst", "severity": "warning", "lab_code": "LAB_01", "count": 4, "detail": "d", "dedupe_key": "k"}]
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
      jsonBody: expr('{{ JSON.stringify({ audience: "staff", kind: "ANOMALY", title: String("Anomaly: " + $json.rule.replaceAll("_", " ") + ($json.lab_code ? " at " + $json.lab_code : "")).slice(0, 160), body: String($json.detail).slice(0, 500), link: "/admin/access", severity: $json.severity, dedupe_key: $json.dedupe_key }) }}')
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
      jsonBody: expr('{{ JSON.stringify({ workflow: "12-anomaly-detection", status: "success", summary: "Anomalies: " + $("Run Anomaly Rules").first().json.count, execution_id: $execution.id }) }}')
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Rule-based anomaly detection\nExplainable rules only, evaluated in the backend: denial bursts, repeated identity mismatch, after-hours access, forced entry / door held open, device flapping, refusals far above the lab's own 7-day baseline. No ML model - there is no training data. One notification per rule, lab and day.", [], { color: 4 });

export default workflow('smartlab-12', 'Smart Lab 12 - Rule-based anomaly detection')
  .add(hourly).to(scan).to(each).to(tell).to(recordRun).add(note);
