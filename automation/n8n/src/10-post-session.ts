import { workflow, node, trigger, ifElse, newCredential, expr, sticky } from '@n8n/workflow-sdk';

const API = 'http://backend:8000/api/automation';

const every30 = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.4,
  config: { name: 'Every 30 Minutes', parameters: { rule: { interval: [{ field: 'minutes', minutesInterval: 30 }] } } },
  output: [{}]
});

const ended = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Get Bookings That Just Ended',
    parameters: {
      method: 'GET',
      url: API + '/bookings/ended?minutes=60',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"bookings": [{"booking_id": 42, "user_id": 2, "attended": true, "title": "Session ended - LAB_01", "body": "Entered 10:02 UTC.", "link": "/bookings/42", "dedupe_key": "post-session:42"}]}]
});

const each = node({
  type: 'n8n-nodes-base.splitOut',
  version: 1,
  config: { name: 'One Item Per Booking', parameters: { fieldToSplitOut: 'bookings' } },
  output: [{"booking_id": 42, "user_id": 2, "attended": true, "title": "t", "body": "b", "link": "/bookings/42", "dedupe_key": "post-session:42"}]
});

const tell = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.5,
  config: {
    name: 'Send Follow-up',
    parameters: {
      method: 'POST',
      url: API + '/notify',
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ JSON.stringify({ audience: "user", user_id: $json.user_id, kind: "POST_SESSION", title: String($json.title).slice(0, 160), body: String($json.body).slice(0, 500), link: $json.link, severity: $json.attended ? "info" : "warning", dedupe_key: $json.dedupe_key, booking_id: $json.booking_id }) }}')
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
      jsonBody: expr('{{ JSON.stringify({ workflow: "10-post-session", status: "success", summary: "Follow-ups: " + $("Get Bookings That Just Ended").first().json.bookings.length, execution_id: $execution.id }) }}')
    },
    credentials: { httpHeaderAuth: newCredential('Smart Lab automation key') }
  },
  output: [{"recorded": true}]
});

const note = sticky("## Post-session\nAttended: summary, and says 'exit not recorded' honestly when no exit was observed. Missed: a gentle no-show note. Text is composed by the backend.", [], { color: 4 });

export default workflow('smartlab-10', 'Smart Lab 10 - Post-session follow-up')
  .add(every30).to(ended).to(each).to(tell).to(recordRun).add(note);
