---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/VISUAL_FOUNDATION.md"
source_hash: "7ca46a606d52d81083cc3b0bbd4f6a9ce81a5c6111cebcb2dec5522783d1e67b"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/VISUAL_FOUNDATION.md` - edit the original in the repository, not this note.

Systems: none

# Smart Lab visual foundation (2026-10-14)

## Welcome after sign-in
`frontend/src/components/WelcomeIntro.tsx` - 2.4 s, CSS only, drawn over the portal, which is already
loaded underneath (nothing waits for it). Mark + "SMART LAB / Intelligent Research Environment" +
"Welcome, <first name>", blueprint grid, then fades up and away.
* Shown once per sign-in: `Login.tsx` calls `requestIntro()` after a successful login (sessionStorage
  flag). Reload / navigation never replays it. Auth logic unchanged.
* Skip: focused **Skip** button, Esc, Enter, click anywhere. Reduced motion: not shown.
* **Preview again:** add `?intro` to any portal URL, e.g. `http://localhost/?intro` (the parameter is removed).

## Smart Lab home - `/welcome` (sidebar: "Smart Lab home", all roles)
`frontend/src/pages/Welcome.tsx`, inside the normal layout (sidebar, header, permissions unchanged).
The dashboard stays at `/`.
1. Hero - `SITE_HERO` photo, greeting, "Enter the dashboard", "Discover the lab", scroll cue.
2. The equipment - cards from `EQUIPMENT`; click = detail dialog with every available view
   (role + kind + credit + source shown), link to the existing portal page (staff-only links hidden for students).
3. The laboratories - real labs from `GET /labs` (one request), hero from `LABS[code]`, equipment chips
   from `EquipmentGallery.BY_LAB`, link to `/labs/:id`.
4. Live - links to the robot twin, camera, IoT dashboard, labs. **No live values here** (no polling, no invented status).

## Motion system (`index.css`, `components/motion.tsx`)
`Reveal` = one shared IntersectionObserver, each element once, opacity + translate 18 px, 650 ms,
`--ease-out-lab` cubic-bezier(.22,1,.36,1), stagger 60-80 ms. Hero photo: 1.4 s scale 1.06 -> 1 once.
Only loop: the 1-px scroll cue (stops with reduced motion). No scroll handlers, no canvas/WebGL, no video.
The observer area extends above the viewport, so content jumped past (End key, anchors) is never left hidden.

## Images
One manifest: `frontend/src/lib/labVisuals.ts`; files: `frontend/public/lab/` (see its README).
Kinds: photo / curated / isolated / illustration / dimensional - illustrations and depth visuals are labelled
in amber as NOT photographs; derivatives carry `from` (their original). Missing image or broken file =
compact "Photo pending" / "Image file missing" tile. Real photos today: our-ur5e, our-fanuc, our-pcs
(`public/equipment/`, owner's own). Everything else pending.

## Tested (2026-10-14, dev server :5174 against the running API, Chrome headless via playwright-core)
Intro shown after login and gone by 4.3 s; no replay on reload; `?intro` replays and cleans the URL; Esc skips;
6 equipment cards (3 photos, rest pending), 11 lab links, detail dialog opens; reduced motion: no intro,
content visible; 390 px wide: no horizontal scroll; no external hosts requested; no page errors;
jump to page end: 0 of 28 reveal blocks left hidden. `npx tsc --noEmit -p frontend` clean, `vite build` OK.
Not done: deploy (needs a frontend rebuild of the running portal - owner's OK); tablet width only by layout
classes, not screenshotted; the TikTok reference effect (not inspectable - see final report).

