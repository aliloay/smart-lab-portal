import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const denied = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Access Denied Event',
    parameters: { httpMethod: 'POST', path: 'smartlab-access-denied', authentication: 'headerAuth', responseMode: 'onReceived' },
    credentials: { httpHeaderAuth: newCredential('Smart Lab webhook token') }
  },
  output: [{"body": {"type": "access.denied", "lab_id": 1, "payload": {"reason": "TOKEN_UNKNOWN"}}}]
});

const burst = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Evaluate Denial Burst',
    parameters: {
      method: 'GET',
      url: expr(API + '/access/denials{{ $json.body.lab_id ? "?lab_id=" + $json.body.lab_id : "" }}'),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"level": "warning", "count": 3, "lab_code": "LAB_01", "lab_id": 1, "message": "3 refusals at LAB_01 in 10 min", "by_reason": {"TOKEN_UNKNOWN": 3}, "dedupe_key": "denial-burst:1:1"}]
});

const isBurst = ifElse({
  version: 2.2,
  config: { name: 'Is It A Burst?', parameters: { conditions: {"options": {"caseSensitive": true, "leftValue": "", "typeValidation": "loose"}, "conditions": [{"leftValue": expr('{{ $json.level }}'), "operator": {"type": "string", "operation": "equals"}, "rightValue": "warning"}], "combinator": "and"} } }
});

const raiseAlert = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Raise Security Alert',
    parameters: {
      method: 'POST',
      url: API + '/alerts',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ severity: "WARNING", title: "Repeated refusals at " + $json.lab_code, detail: $json.message + ". Reasons: " + Object.entries($json.by_reason).map(([k, v]) => k + " x" + v).join(", "), lab_id: $json.lab_id, dedupe_key: $json.dedupe_key }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"created": true, "alert_id": 1}]
});

const tellStaff = node({
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
      jsonBody: expr('{{ JSON.stringify({ audience: "staff", kind: "SECURITY_EVENT", title: String("Repeated refusals at " + $("Evaluate Denial Burst").item.json.lab_code).slice(0, 160), body: String($("Evaluate Denial Burst").item.json.message + " - check the camera and who is at the door.").slice(0, 500), link: "/admin/access", severity: "warning", dedupe_key: $("Evaluate Denial Burst").item.json.dedupe_key }) }}')
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
      jsonBody: expr('{{ JSON.stringify({ workflow: "03-access-denial-intelligence", status: "success", summary: "Burst at " + $("Evaluate Denial Burst").item.json.lab_code, execution_id: $execution.id }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Access denial intelligence\n1 refusal = normal (early, wrong code). 3 within 10 min = warning (thresholds in backend config). One alert per burst via dedupe key.\n\nThis workflow NEVER locks or unlocks anything - the door decides on its own.", [], { color: 3 });

export default workflow('smartlab-03', 'Smart Lab 03 - Access denial intelligence')
  .add(denied).to(burst).to(isBurst.onTrue(raiseAlert.to(tellStaff).to(recordRun))).add(note);
