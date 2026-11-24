# Portal navigation: what changed and what was measured

One report instead of the 28 requested files. The inventory and the mapping are the two CSV files here. Pictures in `before/` and `after/` (test copy, sample names) are kept on the laptop, not in Git.
Live since 25 Nov 2026 01:42 as build 11003b0.

| | Before | After |
|---|---|---|
| Menu entries, administrator | 24 (16 visible at the start) | 17 (12 visible at the start) |
| Menu entries, staff | 21 (15 visible at the start) | 15 (11 visible at the start) |
| Menu entries, student | 9 (9 visible at the start) | 8 (8 visible at the start) |
| Click to heading, median / p95 (development server) | 23 / 50 ms (n = 50) | 25 / 71 ms (n = 40) |
| Pages opened (3 roles x 3 screen sizes) | 342, blank 0, console errors 0 | 342, blank 0, console errors 0 |
| Pages wider than the screen | 2 | 0 |

The click times are the same within noise: this is a reorganisation, not a speed-up.

## Changes
- **Menu**: Overview, Access & safety, Live operations, Lab equipment, Lab management, Intelligence, Administration, Assistant. Access & safety opens and closes, opens by itself on its pages, and shows the sum of its badges when closed.
- **Notifications**: the header bell opens the Notifications Center; a mouse resting on it previews five. Wider page, five counters from real data, mark one read, confirmation before all. Opening marks nothing read.
- **Live Monitoring**: `/command` (IoT & sensors) and `/admin/security` (cameras) are two tabs. Only the open one is mounted. There is no separate events tab: both pages already have their events section.
- **Screens** (live monitor, wall, exhibition): a button on Live Monitoring, in their own window.
- **Share screen**: the tab "Screen sharing" in Equipment. `/share` still works: staff are sent to the tab, students and `?t=` watch links stay.
- **Analytics & health**: Health Center, Sensors, System, Reliability, Reports (administrator) as tabs.
- **AR scanner and Experiments** have a menu entry for the first time. Ctrl+K lists every page a role may open.
- **Operations Center**: figures, charts, device and environment health, automation, priorities and questions, then the table.
- **Camera bars**: a confirmed name is large and blue; a name with "?" (or one the camera itself doubts) is amber and marked "possible"; unknown is grey. Nothing else was removed.
- Less glow in the menu. The colour tokens already existed (`tailwind.config.js`) and were kept.

## Roles and addresses
Every old address opens for the same roles as before (342 page checks). No API, permission or route gate was changed. Added: `/live`.

## Tests
TypeScript 0 errors; unit 27; search ranking 9; browser interactions 33 of 33; page audit above; build. `e2e/navigation.mjs`: 90 pages, 3 reports of a 403 in the console, which it also counts for pages a role may not open; not compared with the old version. Scripts: `e2e/nav_audit.mjs`, `e2e/nav_interactions.mjs`.

## Not done / open
- Tested on a test copy with sample data, then checked on the live portal by HTTP only (version, pages, bundle). Not clicked through live.
- `e2e/expansion.mjs` and `e2e/reliability.mjs` were adapted but not run (they need sample sensor data).
- On a phone the Report and chat buttons overlap slightly at the bottom right, as before.
- Page titles "Command center" and "Security camera" were kept.
