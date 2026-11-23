# Portal and system optimisation results - 23 Nov 2026

Every row has a baseline and a measured result. Nothing here is estimated.

| # | Area | Baseline | Change | Result (measured) | Risk |
|---|---|---|---|---|---|
| 1 | Assistant "what time" questions | 40.7 s model answer | C-03 `_faq_norm` | 0.14 s median (n=5), FAQ route | low: tested both ways ("where" still refused) |
| 2 | Assistant device-status questions | 10.8 s, **wrong** answer | C-06 status guard | 0.05 s, redirect to live data | low: device noun required |
| 3 | FAQ protection (K1) | regex dead (0x08) | C-02 | question word extracted for every test question | low |
| 4 | Service lifetime | knowledge and camera services died overnight 22→23 Nov: they were children of a closed tool shell | started through `Win32_Process.Create` (independent processes), documented in the runbook | all three services survived the rest of the session; `/health` 200 | none |
| 5 | Build identity | `/api/health` `version.id = unstamped` | redeploy through `tools/deploy/build_images.ps1` | see `GITHUB_AND_DEPLOYMENT_STATUS.md` | low: rollback tags kept |
| 6 | Pose CPU share (V-F9) | about 3.3 cores per pose session | `SMARTLAB_POSE_THREADS=2` (already in `d023e98`), now measured | about 1.1-1.3 cores per session; both cameras about 2.6 of 6 cores | p50 about 25-35% slower per pass under load; inside the 1 pass/s budget |

## Frontend bundle (measured, `vite build` of `d023e98` + closure, 23 Nov)
Built in 32 s. The largest chunks:

| Chunk | Size | gzip |
|---|---|---|
| `robotModels` | 689 kB | 178 kB |
| `charts` | 388 kB | 108 kB |
| `index` (entry) | 275 kB | 82 kB |
| `threeSetup` | 195 kB | 63 kB |
| `react` | 182 kB | 60 kB |
| `Equipment` | 87 kB | 26 kB |

- **Verified in the built `index.html`:** the first load fetches only `index` (82 kB gzip), `react` (60 kB), `motion` (26 kB) and `icons` (15 kB), about 183 kB gzip in total. `robotModels`, `threeSetup` and `charts` are lazy: they load only on the robot, AR and analytics pages.
- **No change was made.** Splitting `robotModels` further (one chunk per robot) would cut the first robot-page load by roughly half of 178 kB gzip. That is a NEXT item; the research session's roadmap covers UI work.

## Not changed on purpose
- **B-12** (0.37 ms audit query): no evidence of a problem.
- **Camera detector and GPU scheduling:** cameras keep GPU priority; no camera setting was touched without live streams.
- **Portal assistant model (`qwen2.5:1.5b`) and knowledge model (`qwen3:1.7b`):** the 21 Nov benchmark choice stands; the research session evaluates alternatives.
