import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const every10 = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: { name: 'Every 10 Minutes', parameters: { rule: { interval: [{ field: 'minutes', minutesInterval: 10 }] } } },
  output: [{}]
});

const evaluate = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Evaluate Sensors In Backend',
    parameters: {
      method: 'GET',
      url: API + '/sensors/evaluate?max_age_minutes=30',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"no_data": false, "breaches": [{"lab_id": 1, "lab_code": "LAB_01", "metric": "temperature", "value": 34, "unit": "C", "status": "high", "min": 16, "max": 30, "title": "LAB_01 temperature high: 34C", "dedupe_key": "sensor:1:temperature:high:2026092610"}]}]
});

const each = node({
  type: 'n8n-nodes-base.splitOut',
  version: 1,
  config: { name: 'One Item Per Breach', parameters: { fieldToSplitOut: 'breaches' } },
  output: [{"lab_id": 1, "lab_code": "LAB_01", "metric": "temperature", "value": 34, "unit": "C", "status": "high", "min": 16, "max": 30, "title": "t", "dedupe_key": "k"}]
});

const alert = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Raise Threshold Alert',
    parameters: {
      method: 'POST',
      url: API + '/alerts',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ severity: "WARNING", title: $json.title, detail: "Allowed range " + ($json.min ?? "-") + " to " + ($json.max ?? "-") + " " + $json.unit + ".", lab_id: $json.lab_id, dedupe_key: $json.dedupe_key }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"created": true}]
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
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "staff", kind: "SENSOR_THRESHOLD", title: String($("One Item Per Breach").item.json.title).slice(0, 160), body: String("Latest reading outside the configured range.").slice(0, 500), link: "/admin/operations", severity: "warning", dedupe_key: $("One Item Per Breach").item.json.dedupe_key }) }}')
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
      jsonBody: expr('{{ JSON.stringify({ workflow: "08-sensor-thresholds", status: "success", summary: "Breaches: " + $("Evaluate Sensors In Backend").first().json.breaches.length, execution_id: $execution.id }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Sensor thresholds (configuration-driven)\nThresholds live in backend SENSOR_THRESHOLDS (metric=min:max). Stale readings are never treated as OK. With no sensor node installed the backend returns no_data and this workflow does nothing - no simulated values.", [], { color: 4 });

export default workflow('smartlab-08', 'Smart Lab 08 - Sensor threshold alerts')
  .add(every10).to(evaluate).to(each).to(alert).to(tell).to(recordRun).add(note);
