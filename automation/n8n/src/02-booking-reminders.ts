import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const every5 = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: { name: 'Every 5 Minutes', parameters: { rule: { interval: [{ field: 'minutes', minutesInterval: 5 }] } } },
  output: [{}]
});

const upcoming = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Get Bookings Starting Soon',
    parameters: {
      method: 'GET',
      url: API + '/bookings/upcoming?within_minutes=20',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"bookings": [{"booking_id": 42, "reminder_sent": false}]}]
});

const each = node({
  type: 'n8n-nodes-base.splitOut',
  version: 1,
  config: { name: 'One Item Per Booking', parameters: { fieldToSplitOut: 'bookings' } },
  output: [{"booking_id": 42, "reminder_sent": false}]
});

const notReminded = node({
  type: 'n8n-nodes-base.filter',
  version: 2.3,
  config: { name: 'Not Reminded Yet', parameters: { conditions: {"options": {"caseSensitive": true, "leftValue": "", "typeValidation": "loose"}, "conditions": [{"leftValue": expr('{{ $json.reminder_sent }}'), "operator": {"type": "boolean", "operation": "false"}}], "combinator": "and"} } },
  output: [{"booking_id": 42, "reminder_sent": false}]
});

const remind = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Raise Reminder',
    parameters: {
      method: 'POST',
      url: expr(API + '/bookings/{{ $json.booking_id }}/remind'),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({}) }}')
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"created": true}]
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
      jsonBody: expr('{{ JSON.stringify({ workflow: "02-booking-reminders", status: "success", summary: "Reminders raised: " + $input.all().filter(i => i.json.created).length, execution_id: $execution.id }) }}')
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Upcoming booking reminders\nIdempotent: the backend raises at most one reminder per booking - shared with the portal's own lazy reminder, so a retry or both paths firing never sends two.", [], { color: 4 });

export default workflow('smartlab-02', 'Smart Lab 02 - Upcoming booking reminders')
  .add(every5).to(upcoming).to(each).to(notReminded).to(remind).to(recordRun).add(note);
