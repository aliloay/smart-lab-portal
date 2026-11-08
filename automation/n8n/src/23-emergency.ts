import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const emergency = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Emergency Set',
    parameters: { httpMethod: 'POST', path: 'smartlab-emergency-set', authentication: 'headerAuth', responseMode: 'onReceived' },
    credentials: { httpHeaderAuth: newCredential('Smart Lab webhook token') }
  },
  output: [{"body": {"type": "emergency.set", "lab_id": 1, "payload": {"lab_code": "LAB_01", "version": 3, "door_mode": "UNLOCKED", "alarm": true, "message": "Fire drill", "active": true}}}]
});

const getState = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Get Emergency State',
    parameters: {
      method: 'GET',
      url: expr(API + '/emergency/{{ $json.body.lab_id }}'),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"lab_id": 1, "lab_code": "LAB_01", "version": 3, "active": true, "has_door": true, "applied": false, "notices": [{"user_id": 2, "name": "Ali", "title": "EVACUATE LAB_01 now", "body": "The evacuation alarm is on.", "severity": "critical", "dedupe_key": "emergency:1:v3:2"}]}]
});

const each = node({
  type: 'n8n-nodes-base.splitOut',
  version: 1,
  config: { name: 'One Item Per Person Inside', parameters: { fieldToSplitOut: 'notices' } },
  output: [{"user_id": 2, "name": "Ali", "title": "EVACUATE LAB_01 now", "body": "b", "severity": "critical", "dedupe_key": "k"}]
});

const warn = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Warn Person Inside',
    parameters: {
      method: 'POST',
      url: API + '/notify',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "user", user_id: $json.user_id, kind: "EMERGENCY", title: $json.title, body: $json.body, link: "/", severity: $json.severity, dedupe_key: $json.dedupe_key }) }}')
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"created": 1, "duplicate": false}]
});

const wait = node({
  type: 'n8n-nodes-base.wait',
  version: 1.1,
  config: { name: 'Give The Door 30 s', parameters: { resume: 'timeInterval', amount: 30, unit: 'seconds' } },
  output: [{"lab_id": 1}]
});

const checkAgain = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Check Door Applied It', executeOnce: true,
    parameters: {
      method: 'GET',
      url: expr(API + '/emergency/{{ $json.lab_id }}'),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"lab_id": 1, "lab_code": "LAB_01", "version": 3, "active": true, "has_door": true, "applied": false, "controller_online": false}]
});

const notApplied = ifElse({
  version: 2.2,
  config: { name: 'Door Has Not Applied It?', parameters: { conditions: {"options": {"caseSensitive": true, "leftValue": "", "typeValidation": "loose"}, "conditions": [{"leftValue": expr('{{ $json.active && $json.has_door && !$json.applied }}'), "operator": {"type": "boolean", "operation": "true", "singleValue": true}}], "combinator": "and"} } }
});

const tellAdmins = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Alert Admins',
    parameters: {
      method: 'POST',
      url: API + '/notify',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "admins", kind: "EMERGENCY", title: String("Door at " + $json.lab_code + " has NOT applied the emergency").slice(0, 160), body: ($json.controller_online === false ? "The door controller is offline. " : "The door controller has not confirmed after 30 s. ") + "Act at the door in person.", link: "/admin/emergency", severity: "critical", dedupe_key: "emergency-unapplied:" + $json.lab_id + ":v" + $json.version }) }}')
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"created": 1}]
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
      jsonBody: expr('{{ JSON.stringify({ workflow: "23-emergency", status: "success", summary: $json.lab_code + " v" + $json.version + ($json.has_door ? ": door " + ($json.applied ? "applied it" : "did not confirm") : ": no door controller"), execution_id: $execution.id }) }}')
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Emergency\nSet by an admin in the Emergency tab. 1) Everyone INSIDE that lab gets a notice telling them what to do (leave / lockdown / the admin's message). 2) After 30 s: if the door controller has not confirmed the new state, the admins are told to act at the door.\n\nThis workflow NEVER opens or locks anything - the door applies the state itself.", [], { color: 3 });

export default workflow('smartlab-23', 'Smart Lab 23 - Emergency: warn people inside, check the door')
  .add(emergency).to(getState).to(each).to(warn)
  .add(getState).to(wait).to(checkAgain).to(notApplied.onTrue(tellAdmins))
  .add(checkAgain).to(recordRun)
  .add(note);
