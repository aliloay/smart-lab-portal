import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const offlineEvent = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Device Offline Event',
    parameters: { httpMethod: 'POST', path: 'smartlab-device-offline', authentication: 'headerAuth', responseMode: 'onReceived' },
    credentials: { httpHeaderAuth: newCredential('Smart Lab webhook token') }
  },
  output: [{"body": {"type": "device.offline", "device_id": 1}}]
});

const every5 = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: { name: 'Every 5 Minutes', parameters: { rule: { interval: [{ field: 'minutes', minutesInterval: 5 }] } } },
  output: [{}]
});

const scan = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Get Offline Devices', executeOnce: true,
    parameters: {
      method: 'GET',
      url: API + '/devices/offline',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"offline": [{"device_id": 1, "name": "Master", "level": 2, "audience": "staff", "severity": "warning", "title": "Master offline for 20 min - escalated", "body": "LAB_01", "dedupe_key": "device-offline:1:1:L2"}]}]
});

const each = node({
  type: 'n8n-nodes-base.splitOut',
  version: 1,
  config: { name: 'One Item Per Device', parameters: { fieldToSplitOut: 'offline' } },
  output: [{"device_id": 1, "level": 2, "audience": "staff", "severity": "warning", "title": "t", "body": "b", "dedupe_key": "k"}]
});

const tell = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Notify By Escalation Level',
    parameters: {
      method: 'POST',
      url: API + '/notify',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: $json.audience, kind: "DEVICE_OFFLINE", title: $json.title, body: $json.body, link: "/admin/devices", severity: $json.severity, dedupe_key: $json.dedupe_key }) }}')
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
      jsonBody: expr('{{ JSON.stringify({ workflow: "04-device-offline-escalation", status: "success", summary: "Offline devices: " + $("Get Offline Devices").first().json.offline.length, execution_id: $execution.id }) }}')
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Device offline escalation\nLevel 1 at the stale threshold -> staff; level 2 at 15 min -> staff again; level 3 at 60 min -> administrators, critical. One notification per outage per level (dedupe key).\nThe scheduled scan also makes the backend record new outages when nobody has the portal open.", [], { color: 4 });

export default workflow('smartlab-04', 'Smart Lab 04 - Device offline alert with escalation')
  .add(offlineEvent).to(scan).to(each).to(tell).to(recordRun).add(every5).to(scan).add(note);
