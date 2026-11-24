# Performance
Test copy, 317,839 simulated rows, small sample (2 runs each): compare the order of size, not single milliseconds. Live services ran at the same time.

| Request | No index | Prototype index |
|---|---|---|
| metrics/latest, first call | 503 ms | 141 ms |
| coverage 30 days, first call | 211 ms | 148 ms |
| history 24 h / 90 d | 28 / 29 ms | 20 / 32 ms |
| diagnose | 29 ms | 15 ms |
| timeline 7 days | 16 ms | 27 ms |
| system/health (existing) | 34 ms | 38 ms |

`latest` and `coverage` are cached (20 / 60 s), so repeats take about 10-20 ms. The differences below 20 ms are noise. The index costs 13 MB.
There is no "before" for the new requests: they did not exist. The live database was not timed.

| Page file | Size (gzip) |
|---|---|
| Health Center | 11.9 kB (4.2) |
| Sensor analytics | 20.7 kB (7.4); charts file shared with existing pages |
| Exhibition | 6.0 kB (2.6) |

All three load only when opened or in idle time. Polling stops in hidden tabs. Repeat: `prototypes/measure_metrics_api.py`.
