# Frontend (portal)

React 18.3, TypeScript 5.7, Vite 6, Tailwind CSS 3.4, react-router 7, Recharts 2.13, three.js 0.169 with react-three-fiber 8.17, jsQR 1.4. Built in Docker (`node:22-alpine`) and served by nginx (`nginx:alpine`) with TLS from the local Smart Lab CA.

| Area | Location |
|---|---|
| Routes (47 route entries) | [`frontend/src/App.tsx`](../../frontend/src/App.tsx) |
| Pages (operations, labs, bookings, access, security camera, equipment, inventory, robots, reports, AI, scan, admin) | [`frontend/src/pages/`](../../frontend/src/pages/) |
| Components (robot twin, screen sharing, PC controls, safety, system health) | [`frontend/src/components/`](../../frontend/src/components/) |
| API client and auth context | [`frontend/src/lib/api.ts`](../../frontend/src/lib/api.ts), [`frontend/src/lib/auth.tsx`](../../frontend/src/lib/auth.tsx) |
| Visibility-aware polling (hidden tabs stop polling) | [`frontend/src/lib/visibleInterval.ts`](../../frontend/src/lib/visibleInterval.ts) |
| nginx, security headers, TLS entrypoint | [`frontend/nginx.conf`](../../frontend/nginx.conf), `security_headers.conf`, `40-smartlab-tls.sh` |
| Browser tests (Playwright scripts) | [`frontend/e2e/`](../../frontend/e2e/) (`click_everything.mjs`, `responsive_audit.mjs`, …) |

Develop locally:

```powershell
cd frontend
npm ci
npm run dev          # Vite dev server; API calls go to the backend on :8000
npx tsc --noEmit     # type check
npx vite build       # production build
```

Screenshots of the real portal: [`docs/screenshots/`](../screenshots/), [`docs/paper_figures/portal_2026-10-19/`](../paper_figures/portal_2026-10-19/), [`docs/media/portal/`](../media/portal/).
