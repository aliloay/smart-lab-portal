# Maintenance and equipment

Issue reporting, the repair workflow, and each equipment item's lifecycle.

## Reporting an issue

Anyone signed in can report from **Report an issue** (top bar), a
laboratory page, an equipment page, a device, or a refused access event. The
form arrives pre-filled from wherever it was opened.

| Field | Values |
|---|---|
| Category | Damaged, Missing, Malfunction, Needs maintenance, Safety concern, Software, Network, Access control, Other |
| Laboratory | required |
| Equipment | optional: an asset or a door device of that lab, or "general laboratory issue" |
| Severity | Low, Medium, High, Critical |
| Title / description | 5+ / 10+ characters |
| Photos | optional, up to 6 per upload and 12 per issue, 12 MB each |

The report gets a ticket number `ISS-YYYY-NNNNNN` immediately. Staff are
notified; a **Critical** report is flagged as such.

Links are validated server-side: the asset, device or access event must
belong to the chosen laboratory, and a student can only link their own
access events.

## Workflow

```
            ┌──────────── rejected ◄──────────┐
            ▼                                  │
  OPEN ──► ACKNOWLEDGED ──► IN_PROGRESS ◄──► WAITING_FOR_PARTS
   │            │                │                  │
   └────────────┴────────────────┴──────────────────┴──► RESOLVED ──► CLOSED
                                                            │  (admin)
                         REOPENED ◄─────────────────────────┘
```

| Action | Who | Rule |
|---|---|---|
| acknowledge | staff | only from OPEN |
| assign | staff | assignee must be active staff; assigning an OPEN issue acknowledges it |
| status change | staff | OPEN → acknowledged / in progress / waiting / rejected; ACKNOWLEDGED → in progress / waiting / rejected; IN_PROGRESS ⇄ WAITING_FOR_PARTS |
| resolve | staff | from any active state; resolution notes required (5+ characters) |
| close | **admin** | only resolved or rejected issues |
| reopen | **admin** | resolved, rejected or closed issues |
| edit severity / category / links | staff | escalation to High or Critical notifies all staff |
| comment | reporter or staff | internal notes: staff only, never shown to students |
| add photos | reporter or staff | staff can mark them *before* / *after*; they never replace the report photos |

All of this is enforced by the API, not the UI. Students see only their own
reports (anyone else's is a 404) and cannot move them through the workflow.

Every change writes an `issue_history` row in the same transaction — the
timeline the reporter sees and the audit trail are the same records.

### Service levels

"Overdue" is a published rule, set by `ISSUE_SLA_HOURS_*` in the backend
environment and shown on the admin **Settings** page:

| Severity | Target |
|---|---|
| Critical | 24 h |
| High | 72 h |
| Medium | 7 days |
| Low | 14 days |

### Notifications

In the portal only (no email or SMS provider is configured, and none is
faked). Reporter: acknowledged, assigned, status changed, resolved, closed,
reopened, staff reply. Staff: new report, critical report, escalation,
comment on an assigned issue.

## Photos

Every upload is **decoded** (the extension is not trusted), rotated upright
from EXIF, stripped of all metadata including GPS position, scaled down, and
thumbnailed. Files are stored through the `Storage` interface
(`services/storage.py`, local disk today) and served only via authenticated
routes to people allowed to see that issue.

## Dashboards

**Staff — maintenance queue:** Critical, High, Unassigned, In progress,
Waiting for parts, Overdue, then the active issues sorted by severity.

**Admin — laboratory maintenance:** the same tiles plus resolved this month,
average resolution time, the laboratory with most issues, the top category
and the most-reported item. The **Maintenance** page (`/issues`) adds
analytics by laboratory and category.

Every number is computed from the `issues` table; with no data the tile
shows zero or "—", never an example value.

## Equipment lifecycle

Each asset (`/admin/equipment`, `/equipment/:id`) records:

| Field | Source |
|---|---|
| Asset ID (`asset_tag`), name, type (category), serial number | entered by staff |
| Laboratory and its location | `lab_id` |
| Status | Available / Checked out / Maintenance / Retired |
| Current user | set on check-out, cleared on return — **visible to staff only** |
| Last inspection | set by **Record inspection** |
| Next maintenance | set when adding the item, editing it, or recording an inspection; past dates are shown as *overdue* |
| Open issues and maintenance history | from `issues` |
| Lifecycle timeline | issues reported/resolved, inspections, status changes, and (staff only) check-outs and returns |

Rules:

- Only the borrower or staff can return a checked-out item.
- Taking an item out of CHECKED_OUT any other way ends the loan and clears
  the holder.
- A status change writes `STATUS_<new>` to `asset_transactions` with the
  before → after note.
- An inspection must schedule the next maintenance in the future (422
  otherwise).
- **Maintenance due** on the equipment list filters to overdue items.

Nothing is guessed: an item never inspected says "not recorded", an item with
no schedule says "not scheduled".
