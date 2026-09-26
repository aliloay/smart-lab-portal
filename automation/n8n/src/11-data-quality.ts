import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const daily = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: { name: 'Daily 06:00', parameters: { rule: { interval: [{ field: 'days', triggerAtHour: 6 }] } } },
  output: [{}]
});

const check = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Run Checks In Backend',
    parameters: {
      method: 'GET',
      url: API + '/data-quality',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"failing": 1, "summary": "1 check(s) need attention", "dedupe_key": "data-quality:2026-09-26"}]
});

const failing = ifElse({
  version: 2.2,
  config: { name: 'Any Check Failing?', parameters: { conditions: {"options": {"caseSensitive": true, "leftValue": "", "typeValidation": "loose"}, "conditions": [{"leftValue": expr('{{ $json.failing }}'), "operator": {"type": "number", "operation": "gt"}, "rightValue": 0}], "combinator": "and"} } }
});

const tell = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Notify Administrators',
    parameters: {
      method: 'POST',
      url: API + '/notify',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "admins", kind: "DATA_QUALITY", title: String("Data quality: " + $json.failing + " check(s) need attention").slice(0, 160), body: String($json.summary).slice(0, 500), link: "/admin/operations", severity: "info", dedupe_key: $json.dedupe_key }) }}')
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
      jsonBody: expr('{{ JSON.stringify({ workflow: "11-data-quality", status: "success", summary: $("Run Checks In Backend").item.json.summary, execution_id: $execution.id }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Data quality\nRead-only consistency checks (stale sessions, entries on cancelled bookings, unattributed events, devices never reporting, implausible sensor values...). Nothing is modified - a human decides.", [], { color: 4 });

export default workflow('smartlab-11', 'Smart Lab 11 - Daily data quality check')
  .add(daily).to(check).to(failing.onTrue(tell.to(recordRun))).add(note);
