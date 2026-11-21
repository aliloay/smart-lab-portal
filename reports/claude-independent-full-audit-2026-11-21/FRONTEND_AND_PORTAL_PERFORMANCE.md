# Frontend and portal performance

- **Stack:** React 18.3, React Router 7, Vite 6, Tailwind 3.4, framer-motion 11 (9 files, `LazyMotion` in `main.tsx`), recharts, three / @react-three/fiber, jsqr.
- **Type check:** `npx tsc --noEmit -p frontend` exited 0. TESTED – PASSED.

## Measured: live production image, `https://127.0.0.1`, loopback

| Asset (initial load) | Raw | Transferred (gzip) |
|---|---|---|
| `index.html` | 1.07 KB | 21 ms |
| `index-*.js` | 275 KB | 81.9 KB |
| `react-*.js` | 182 KB | 60.4 KB |
| `motion-*.js` | 74 KB | 26.4 KB |
| `icons-*.js` | 80 KB | 15.5 KB |
| `index-*.css` | 171 KB | 43.0 KB |
| **Total first load** | about 782 KB | **about 227 KB** |

- 163 hashed assets in total (12.4 MB including fonts and 3D models).
- **Lazy chunks:**

| Chunk | Raw size |
|---|---|
| robotModels | 689 KB |
| charts | 388 KB |
| threeSetup | 195 KB |
| qrWorker | 131 KB |
| Equipment | 87 KB |
| CommandCenter | 63 KB |
| Scan | 53 KB |

- **Caching:** assets get `Cache-Control: public, max-age=31536000, immutable`; `index.html` gets `no-cache`.
- **Security headers:** CSP `default-src 'self'`, `script-src 'self'`, `frame-ancestors 'none'`, HSTS, X-Frame-Options DENY.
- **Not measured:** authenticated route transitions, TTI on a phone, and Lighthouse scores. I did not sign in with any credentials, and the chrome-devtools test copy (:5176/:8100) was not running.
- **I do not claim any improvement percentages.**

## Code review findings (VERIFIED FROM CODE)

These are already good and should not be replaced:

- **Route splitting:** `App.tsx` uses 38 `lazy()` routes.
- **Request handling (`lib/api.ts:1245-1320`):**
  - In-flight plus a 1 s GET deduplication window.
  - `peek()` returns cached values for instant re-render.
  - `no-store` for live state.
  - `warmGets()` prefetch.
- **Polling (`lib/visibleInterval.ts`):** stops in hidden tabs and refreshes within 2 s when the tab comes back. Alarms and emergency deliberately use plain intervals.
- **WebSocket:** one-time 30 s ticket (`/api/auth/ws-ticket`), so the token never goes in the URL.
- **Pagination:** limits on activity, sessions, robot events and security events (`api.ts:1474-1600`).
- **framer-motion:** loaded through `LazyMotion`, so only the motion chunk loads (26 KB gzip).

## Opportunities (low risk, evidence-based)

1. **Charts chunk (388 KB raw):** recharts is only on the analytics, report and dashboard pages. Confirm it is not imported by `index` or the dashboard of the default landing route. Check with `vite build --mode production` and `rollup-plugin-visualizer`; that was not run here because it needs a package install.
2. **robotModels (689 KB raw):**
   - Already lazy.
   - Ensure it is fetched only when a twin is visible, not on the Robots list.
   - Draco/meshopt compression via the existing `@gltf-transform/cli` devDependency could shrink it (unmeasured).
3. **CSS 171 KB raw / 43 KB gzip:** large for Tailwind. Check `content` globs and `safelist`; a big safelist inflates CSS.
4. **Fonts:** 4 weights × latin and latin-ext × woff and woff2 are emitted. Modern browsers fetch only woff2, but dropping latin-ext (if not needed) halves the font requests.
5. **Large lists:**
   - No virtualization library is used.
   - Notifications (7.5k rows in the DB) and the alerts history should stay server-paginated.
   - Verify the Notifications page requests a limit (`Notifications.tsx`). UNVERIFIED.
6. **Interval count:** 26 files use `setInterval`.
   - Most go through `visibleInterval`.
   - `Scan.tsx` runs four independent timers: 250 ms marker decode, 700 ms video watchdog, 3 s detector and card refresh. Phone heat was already observed (comment at `Scan.tsx:34`), so consider one rAF-driven scheduler.

## Accessibility, theme and mobile

- I did not run axe or Lighthouse in this audit.
- The repo has `frontend/e2e/responsive_audit.mjs` and `click_everything.mjs` (historical: navigation 98 / workflows 30 on 16 Nov). They were not run, because the isolated test copy was down and the brief forbids interfering with the live portal.

## Verdict

- The initial load is light: about 227 KB gzip, with long-lived cached assets.
- The architecture already applies the main techniques: lazy routes, deduplication, visibility-aware polling, `LazyMotion`.
- Navigation smoothness under authentication is **UNVERIFIED** in this audit. Measure it with the Playwright scripts on the test copy before the defense.
