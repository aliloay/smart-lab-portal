# Metric schema
No new table. The registry in `backend/app/services/metrics.py` describes every metric and reads the existing `sensor_readings`.

| Field | Meaning |
|---|---|
| device_id, sensor_id | database id; `DEVICE:metric` |
| metric_name, value, unit | registry name and unit |
| timestamp, freshness | stored time in UTC, age in seconds |
| quality | VALID, STALE, DEVICE_OFFLINE, OUT_OF_RANGE, UNREGISTERED |
| source, calibration_status, sampling_interval | from the registry |
| metadata | provenance and `simulated` |

Rules: an old value is never VALID; a value outside the registered range is excluded and counted; an empty time bucket stays empty
(no interpolation); PLANNED metrics have no value; `*_SIM` devices and DEMO_DATA rows are marked simulated.

| | Metrics |
|---|---|
| Stored today | temperature, humidity, smoke, flame, motion, pc_cpu_pct, pc_ram_pct, pc_disk_pct, pc_net_rx_kbps, pc_net_tx_kbps |
| Firmware prepared | wifi_rssi_dbm, device_uptime_s, free_heap_b |
| Firmware prepared, parts not bought | co2_ppm, illuminance_lux |
| Described only | pm25_ug_m3, noise_db_a, vibration_rms, water_leak, voltage_v, current_a, power_w |

## Database choice
242 k rows, 59 MB table, 125 MB database (23 Nov): plain PostgreSQL is enough. TimescaleDB would add an image change for no
measured need. Consider monthly partitions only above about 20 million rows. There is no retention on `sensor_readings`; nothing is
deleted (owner rule).

Prototype migration: `prototypes/migration_index_prototype.sql` (forward and rollback). Measured on 317,839 simulated rows: 13 MB index,
`latest` 503 -> 141 ms. Not applied to the live database, and not in Alembic.
