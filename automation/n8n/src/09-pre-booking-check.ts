import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const every15 = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: { name: 'Every 15 Minutes', parameters: { rule: { interval: [{ field: 'minutes', minutesInterval: 15 }] } } },
  output: [{}]
});

const upcoming = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Get Bookings In Next Hour',
    parameters: {
      method: 'GET',
      url: API + '/bookings/upcoming?within_minutes=60',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"bookings": [{"booking_id": 42, "user_id": 2, "lab_code": "LAB_01", "link": "/bookings/42/qr", "readiness": {"level": "warning", "warnings": ["Controller offline"]}}]}]
});

const each = node({
  type: 'n8n-nodes-base.splitOut',
  version: 1,
  config: { name: 'One Item Per Booking', parameters: { fieldToSplitOut: 'bookings' } },
  output: [{"booking_id": 42, "user_id": 2, "lab_code": "LAB_01", "link": "/bookings/42/qr", "readiness": {"level": "warning", "warnings": ["Controller offline"]}}]
});

const notReady = node({
  type: 'n8n-nodes-base.filter',
  version: 2.3,
  config: { name: 'Lab Not Ready', parameters: { conditions: {"options": {"caseSensitive": true, "leftValue": "", "typeValidation": "loose"}, "conditions": [{"leftValue": expr('{{ $json.readiness.level }}'), "operator": {"type": "string", "operation": "equals"}, "rightValue": "warning"}], "combinator": "and"} } },
  output: [{"booking_id": 42, "user_id": 2, "lab_code": "LAB_01", "link": "/bookings/42/qr", "readiness": {"level": "warning", "warnings": ["Controller offline"]}}]
});

const tellStudent = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Warn Student',
    parameters: {
      method: 'POST',
      url: API + '/notify',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "user", user_id: $json.user_id, kind: "PRE_BOOKING_CHECK", title: String("Heads-up for your " + $json.lab_code + " booking").slice(0, 160), body: String($json.readiness.warnings.join(" ") + " Your booking is unchanged.").slice(0, 500), link: $json.link, severity: "warning", dedupe_key: "pre-booking:" + $json.booking_id, booking_id: $json.booking_id }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"created": 1, "duplicate": false}]
});

const tellStaff = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Warn Staff',
    parameters: {
      method: 'POST',
      url: API + '/notify',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "staff", kind: "PRE_BOOKING_CHECK", title: String("Lab not ready for booking #" + $("Lab Not Ready").item.json.booking_id).slice(0, 160), body: String($("Lab Not Ready").item.json.lab_code + ": " + $("Lab Not Ready").item.json.readiness.warnings.join(" ")).slice(0, 500), link: "/admin/bookings", severity: "warning", dedupe_key: "pre-booking-staff:" + $("Lab Not Ready").item.json.booking_id }) }}')
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
      jsonBody: expr('{{ JSON.stringify({ workflow: "09-pre-booking-check", status: "success", summary: "Warnings sent", execution_id: $execution.id }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Pre-booking check\nWarns the student and staff when a lab is not ready (controller offline, critical issue). It never cancels or changes a booking.", [], { color: 4 });

export default workflow('smartlab-09', 'Smart Lab 09 - Pre-booking lab readiness check')
  .add(every15).to(upcoming).to(each).to(notReady).to(tellStudent).to(tellStaff).to(recordRun).add(note);
