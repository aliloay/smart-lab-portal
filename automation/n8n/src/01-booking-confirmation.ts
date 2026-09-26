import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const onConfirmed = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Booking Confirmed Event',
    parameters: { httpMethod: 'POST', path: 'smartlab-booking-confirmed', authentication: 'headerAuth', responseMode: 'onReceived' },
    credentials: { httpHeaderAuth: newCredential('Smart Lab webhook token') }
  },
  output: [{ body: { event_id: 'uuid', type: 'booking.confirmed', object: { type: 'booking', id: '42' }, user_id: 2, lab_id: 1 } }]
});

const getContext = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Get Booking Readiness',
    parameters: {
      method: 'GET',
      url: expr(API + '/bookings/{{ $json.body.object.id }}'),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth'
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{ booking_id: 42, user_id: 2, lab_code: 'LAB_01', start_time: '2026-09-26T10:00:00Z', link: '/bookings/42/qr', readiness: { level: 'warning', warnings: ['Critical issue open'], notes: [] } }]
});

const needsBriefing = ifElse({
  version: 2.2,
  config: {
    name: 'Lab Needs Heads-up?',
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'loose' },
        conditions: [{ leftValue: expr('{{ $json.readiness.level }}'), operator: { type: 'string', operation: 'notEquals' }, rightValue: 'ok' }],
        combinator: 'and'
      }
    }
  }
});

const notifyStudent = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Send Briefing To Student',
    parameters: {
      method: 'POST',
      url: API + '/notify',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "user", user_id: $json.user_id, kind: "BOOKING_BRIEFING", title: "Before your " + $json.lab_code + " session", body: [...$json.readiness.warnings, ...$json.readiness.notes].join(" ").slice(0, 490), link: $json.link, severity: $json.readiness.level === "warning" ? "warning" : "info", booking_id: $json.booking_id, dedupe_key: "booking-briefing:" + $json.booking_id }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{ created: 1, duplicate: false }]
});

const recordRun = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Record Run',
    executeOnce: true,
    onError: 'continueRegularOutput',
    parameters: {
      method: 'POST',
      url: API + '/runs',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ workflow: "01-booking-confirmation", status: "success", summary: "Briefing for booking " + $("Get Booking Readiness").item.json.booking_id, execution_id: $execution.id }) }}')
    },
    credentials: { httpTemplatedCustomAuth: newCredential('Smart Lab automation key') }
  },
  output: [{ recorded: true }]
});

const note = sticky('## Booking confirmation briefing\nThe portal already confirms the booking. This adds a heads-up only when the lab is not in a normal state (controller offline, critical issue, equipment in maintenance). Readiness is decided by the backend. Never cancels.', [], { color: 4 });

export default workflow('smartlab-01', 'Smart Lab 01 - Booking confirmation briefing')
  .add(onConfirmed)
  .to(getContext)
  .to(needsBriefing.onTrue(notifyStudent.to(recordRun)))
  .add(note);
