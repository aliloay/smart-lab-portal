# Sensor analytics (`/admin/sensors`, staff)
Source: `frontend/src/pages/SensorAnalytics.tsx`, `lib/metricCsv.ts`.
Shows every stored measurement with age, quality, calibration and provenance; 24 h / 7 d / 30 d / 90 d history; average with lowest-highest
band; gaps left empty; same period before; coverage; change per hour (not a forecast); rejected values counted; CSV export protected against
spreadsheet formulas; planned sensors listed without values.

Limits: no anomaly limit, because none is validated. Device events are not drawn on the chart. The negative PC network values are excluded
here; the agent bug itself is still open. Pictures `graphics/sensor_analytics*.png` use **simulated** data.
Performance: file 19. Rollback: remove route and menu entry.
