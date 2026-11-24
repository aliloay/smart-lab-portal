-- PROTOTYPE, NOT APPLIED TO THE LIVE DATABASE. Read: GET /api/metrics/latest and history over a device.
-- Forward (no table lock; run outside a transaction):
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sensor_device_metric_time
    ON sensor_readings (device_id, metric, recorded_at DESC);
-- Rollback (no data is touched):
-- DROP INDEX CONCURRENTLY IF EXISTS ix_sensor_device_metric_time;
