# Navigation and UX
| Group | Admin | Staff |
|---|---|---|
| Overview (always open) | overview, notifications | same |
| Access & safety (always open, second) | access, alerts, incidents, emergency | without emergency |
| Live operations | IoT, cameras, operations, monitor, share | same |
| Lab management | labs, bookings, equipment, devices, maintenance | same |
| Intelligence (closed) | health, sensors, analytics, reliability, reports | without reports |
| Automation & admin (closed) | users, settings, exhibition | users, exhibition |

Students keep their short menu. All old addresses stay (a test compares the lists). Groups are real buttons with `aria-expanded`, remembered per
browser; a closed group shows its badge sum; the group of the open page opens itself; compact mode (76 px) keeps icons with names in tooltips;
the phone drawer is unchanged. The search palette lists the new pages. Source: `lib/nav.ts`, `components/SideNav.tsx`.

A real fault was found and fixed by the browser test: two fast clicks on groups lost one.
Open (existing, not changed): on a 390 px phone the chat button covers part of the Report button.
