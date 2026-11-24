# Equipment passport (design; the existing page is kept)
The portal already has `/equipment/:id` with identity, status, history, QR marker and issues, and the Asset table already stores
`serial_number` and `next_maintenance_at`. A second passport page would duplicate it.

| Passport part | Today | Proposed |
|---|---|---|
| Identity, place, tag | exists | - |
| Runtime and use | robot events, PC sessions, bin checkouts | one "Use" strip on the same page |
| Measurements | none on the page | link to Sensor analytics with the device selected |
| Maintenance | issues, next date | due / overdue chip |
| Calibration | robot home and bin scales are versioned | table below |
| Documents | none | file link chosen by the owner |

## Calibration and maintenance manager (schema prototype, not built)
`calibration_records(id, asset_id, sensor_id, method, reference, before_value, after_value, uncertainty, done_by, done_at, due_at, note)`;
insert only, a correction is a new row. Rollback: drop the new table only if it is empty. No live migration was created.
A sensor without a record is shown as "not calibrated", which is what the registry says today.
