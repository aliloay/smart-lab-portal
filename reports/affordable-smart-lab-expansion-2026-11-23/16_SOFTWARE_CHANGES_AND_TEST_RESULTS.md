# Software changes and tests (24 Nov 2026)
| Area | Files | Rollback |
|---|---|---|
| Backend | services/metrics.py, routes/metrics.py, main.py, agent.py (5 lines) | remove router line and 5 lines |
| Frontend | lib/nav.ts, SideNav, Layout, HealthCenter, SensorAnalytics, Exhibition, exhibit.ts, metricCsv.ts, api.ts, App.tsx | restore Layout/App |
| Firmware | env_config.h, env_network.h, env_i2c.h | restore two files |
| Tests | test_metrics, test_metric_questions, nav.test.ts, expansion.mjs, navigation.mjs | - |

| Check | Result |
|---|---|
| Backend full suite (throw-away PostgreSQL) | **1,004 passed, 3 skipped, 1 failed** |
| The failed test | `test_robot_model_question_is_not_answered_with_the_ai_model`: 503, no AI model reachable from the test container. The same test fails with the same 503 on the unchanged main checkout |
| New backend tests | 72 passed |
| TypeScript | 0 errors |
| Frontend unit | 26 passed |
| Production build | OK |
| Browser, new pages (admin, staff, student; 390, 768, 1440, 1920 px) | 30 of 30 |
| Browser, navigation regression (existing) | 104 of 104 |
| Firmware compile, sensors off / on | OK / OK |

Not done: no live-portal check (not deployed), no hardware test, no screen-reader test, no measured user study. The browser filter ignores refused
local-agent requests and the requests the test blocks on purpose. Status: **uncommitted, not deployed**. No schema change.
