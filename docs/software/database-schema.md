# Database schema

PostgreSQL 16. Generated on 9 Nov 2026 from the SQLAlchemy models (`backend/app/models/tables.py`); migrations are in `backend/alembic/versions` and are applied by the API at start. **Only structure is documented here; no data from the live database.**

42 tables.

## integration_events

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| event_id | VARCHAR(36) |  |  |  |
| event_type | VARCHAR(48) |  |  |  |
| occurred_at | DATETIME |  |  |  |
| lab_id | INTEGER |  | yes |  |
| user_id | INTEGER |  | yes |  |
| device_id | INTEGER |  | yes |  |
| object_type | VARCHAR(32) |  | yes |  |
| object_id | VARCHAR(48) |  | yes |  |
| correlation_id | VARCHAR(64) |  | yes |  |
| payload | JSON |  | yes |  |
| delivery_status | VARCHAR(16) |  |  |  |
| attempts | INTEGER |  |  |  |
| next_attempt_at | DATETIME |  | yes |  |
| delivered_at | DATETIME |  | yes |  |
| last_error | VARCHAR(255) |  | yes |  |

## labs

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| code | VARCHAR(32) |  |  |  |
| name | VARCHAR(128) |  |  |  |
| description | TEXT |  |  |  |
| location | VARCHAR(128) |  |  |  |
| capacity | INTEGER |  |  |  |
| category | VARCHAR(64) |  |  |  |
| has_controller | BOOLEAN |  |  |  |
| exclusive_booking | BOOLEAN |  |  |  |
| require_booking_for_rfid | BOOLEAN |  |  |  |
| is_active | BOOLEAN |  |  |  |
| created_at | DATETIME |  |  |  |

## roles

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| name | VARCHAR(32) |  |  |  |
| description | VARCHAR(255) |  |  |  |

## system_settings

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| key | VARCHAR(64) | PK |  |  |
| value | TEXT |  |  |  |
| updated_at | DATETIME |  |  |  |

## users

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| email | VARCHAR(255) |  |  |  |
| username | VARCHAR(64) |  | yes |  |
| full_name | VARCHAR(255) |  |  |  |
| hashed_password | VARCHAR(255) |  |  |  |
| role | VARCHAR(48) |  |  |  |
| is_active | BOOLEAN |  |  |  |
| auth_subject | VARCHAR(32) |  | yes |  |
| student_id | VARCHAR(64) |  | yes |  |
| department | VARCHAR(128) |  | yes |  |
| created_at | DATETIME |  |  |  |
| fingerprint_enrolled_at | DATETIME |  | yes |  |
| face_enrolled_at | DATETIME |  | yes |  |

## assets

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| asset_tag | VARCHAR(64) |  |  |  |
| name | VARCHAR(128) |  |  |  |
| category | VARCHAR(64) |  |  |  |
| lab_id | INTEGER |  |  | labs.id |
| status | VARCHAR(48) |  |  |  |
| notes | TEXT |  |  |  |
| created_at | DATETIME |  |  |  |
| serial_number | VARCHAR(64) |  | yes |  |
| holder_id | INTEGER |  | yes | users.id |
| checked_out_at | DATETIME |  | yes |  |
| last_inspected_at | DATETIME |  | yes |  |
| next_maintenance_at | DATETIME |  | yes |  |
| nfc_uid | VARCHAR(32) |  | yes |  |
| bin_item | BOOLEAN |  |  |  |
| unit_mass_g | FLOAT |  | yes |  |

## audit_logs

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| actor_user_id | INTEGER |  | yes | users.id |
| action | VARCHAR(64) |  |  |  |
| entity_type | VARCHAR(48) |  |  |  |
| entity_id | VARCHAR(48) |  | yes |  |
| detail | JSON |  | yes |  |
| ip_address | VARCHAR(64) |  | yes |  |
| created_at | DATETIME |  |  |  |

## face_submissions

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| user_id | INTEGER |  |  | users.id |
| status | VARCHAR(16) |  |  |  |
| photo_keys | JSON |  | yes |  |
| thumb_keys | JSON |  | yes |  |
| photo_count | INTEGER |  |  |  |
| created_at | DATETIME |  |  |  |
| reviewed_by_id | INTEGER |  | yes | users.id |
| reviewed_at | DATETIME |  | yes |  |
| reason | VARCHAR(255) |  | yes |  |
| samples_saved | INTEGER |  | yes |  |

## lab_emergencies

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| lab_id | INTEGER | PK |  | labs.id |
| door_mode | VARCHAR(16) |  |  |  |
| door_until | DATETIME |  | yes |  |
| message | VARCHAR(96) |  |  |  |
| message_until | DATETIME |  | yes |  |
| alarm | BOOLEAN |  |  |  |
| speak | BOOLEAN |  |  |  |
| version | INTEGER |  |  |  |
| updated_by_id | INTEGER |  | yes | users.id |
| updated_at | DATETIME |  |  |  |

## personal_qr_credentials

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| user_id | INTEGER |  |  | users.id |
| token_sha256 | VARCHAR(64) |  |  |  |
| issued_at | DATETIME |  |  |  |
| issued_by_id | INTEGER |  | yes | users.id |
| revoked_at | DATETIME |  | yes |  |

## rfid_credentials

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| uid_hex | VARCHAR(32) |  |  |  |
| label | VARCHAR(64) |  |  |  |
| user_id | INTEGER |  |  | users.id |
| is_active | BOOLEAN |  |  |  |
| issued_at | DATETIME |  |  |  |
| revoked_at | DATETIME |  | yes |  |

## workcell_setups

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| robot_key | VARCHAR(16) |  |  |  |
| name | VARCHAR(64) |  |  |  |
| data | JSON |  |  |  |
| created_by_id | INTEGER |  | yes | users.id |
| created_at | DATETIME |  |  |  |

## devices

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| device_uid | VARCHAR(64) |  |  |  |
| name | VARCHAR(128) |  |  |  |
| device_type | VARCHAR(48) |  |  |  |
| lab_id | INTEGER |  |  | labs.id |
| ip_address | VARCHAR(64) |  | yes |  |
| firmware_version | VARCHAR(64) |  | yes |  |
| last_seen_at | DATETIME |  | yes |  |
| is_online | BOOLEAN |  |  |  |
| door_closed | BOOLEAN |  | yes |  |
| component_state | JSON |  | yes |  |
| key_hash | VARCHAR(64) |  | yes |  |
| asset_id | INTEGER |  | yes | assets.id |
| mode | VARCHAR(16) |  | yes |  |
| is_master_pc | BOOLEAN |  |  |  |

## device_commands

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| device_id | INTEGER |  |  | devices.id |
| command | VARCHAR(32) |  |  |  |
| args | JSON |  | yes |  |
| status | VARCHAR(16) |  |  |  |
| step | VARCHAR(32) |  | yes |  |
| message | VARCHAR(255) |  | yes |  |
| target_user_id | INTEGER |  | yes | users.id |
| requested_by_id | INTEGER |  | yes | users.id |
| created_at | DATETIME |  |  |  |
| expires_at | DATETIME |  |  |  |
| sent_at | DATETIME |  | yes |  |
| completed_at | DATETIME |  | yes |  |

## experiments

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| code | VARCHAR(32) |  |  |  |
| name | VARCHAR(160) |  |  |  |
| subsystem | VARCHAR(32) |  |  |  |
| operator_id | INTEGER |  | yes | users.id |
| device_id | INTEGER |  | yes | devices.id |
| firmware_version | VARCHAR(64) |  | yes |  |
| hardware_configuration | TEXT |  |  |  |
| configuration | JSON |  | yes |  |
| environment | TEXT |  |  |  |
| network_state | TEXT |  |  |  |
| data_mode | VARCHAR(24) |  |  |  |
| test_condition | TEXT |  |  |  |
| expected_result | TEXT |  |  |  |
| actual_result | TEXT |  |  |  |
| result | VARCHAR(16) |  | yes |  |
| notes | TEXT |  |  |  |
| status | VARCHAR(16) |  |  |  |
| started_at | DATETIME |  | yes |  |
| ended_at | DATETIME |  | yes |  |
| created_at | DATETIME |  |  |  |

## inventory_bins

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| code | VARCHAR(32) |  |  |  |
| lab_id | INTEGER |  |  | labs.id |
| device_id | INTEGER |  | yes | devices.id |
| item_name | VARCHAR(64) |  |  |  |
| category | VARCHAR(32) |  |  |  |
| tare_g | FLOAT |  | yes |  |
| unit_mass_g | FLOAT |  | yes |  |
| noise_g | FLOAT |  | yes |  |
| calibrated_at | DATETIME |  | yes |  |
| min_change_g | FLOAT |  | yes |  |
| reorder_qty | INTEGER |  | yes |  |
| stock_max | INTEGER |  | yes |  |
| last_mass_g | FLOAT |  | yes |  |
| last_measured_at | DATETIME |  | yes |  |
| notes | TEXT |  |  |  |
| is_active | BOOLEAN |  |  |  |
| created_at | DATETIME |  |  |  |

## lab_devices

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| lab_id | INTEGER |  |  | labs.id |
| device_id | INTEGER |  |  | devices.id |
| role | VARCHAR(64) |  |  |  |

## pc_account_keys

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| device_id | INTEGER |  |  | devices.id |
| account | VARCHAR(64) |  |  |  |
| key_hash | VARCHAR(64) |  |  |  |
| created_at | DATETIME |  |  |  |

## policy_violations

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| device_id | INTEGER |  |  | devices.id |
| lab_id | INTEGER |  |  | labs.id |
| kind | VARCHAR(32) |  |  |  |
| detail | VARCHAR(255) |  |  |  |
| os_user | VARCHAR(64) |  | yes |  |
| reviewed | BOOLEAN |  |  |  |
| created_at | DATETIME |  |  |  |

## robot_home_calibrations

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| device_id | INTEGER |  |  | devices.id |
| version | INTEGER |  |  |  |
| home_q | JSON |  |  |  |
| home_tcp | JSON |  | yes |  |
| tolerance_deg | FLOAT |  |  |  |
| note | VARCHAR(255) |  |  |  |
| created_by_id | INTEGER |  | yes | users.id |
| created_at | DATETIME |  |  |  |

## security_zones

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| device_id | INTEGER |  |  | devices.id |
| name | VARCHAR(64) |  |  |  |
| kind | VARCHAR(16) |  |  |  |
| asset_id | INTEGER |  | yes | assets.id |
| x | FLOAT |  |  |  |
| y | FLOAT |  |  |  |
| w | FLOAT |  |  |  |
| h | FLOAT |  |  |  |
| alert_on_motion | BOOLEAN |  |  |  |
| ref_version | INTEGER |  |  |  |
| created_at | DATETIME |  |  |  |

## alerts

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| lab_id | INTEGER |  | yes | labs.id |
| device_id | INTEGER |  | yes | devices.id |
| severity | VARCHAR(48) |  |  |  |
| title | VARCHAR(128) |  |  |  |
| detail | TEXT |  |  |  |
| is_resolved | BOOLEAN |  |  |  |
| created_at | DATETIME |  |  |  |
| resolved_at | DATETIME |  | yes |  |
| dedupe_key | VARCHAR(160) |  | yes |  |
| state | VARCHAR(16) |  |  |  |
| acknowledged_at | DATETIME |  | yes |  |
| acknowledged_by_id | INTEGER |  | yes | users.id |
| owner_id | INTEGER |  | yes | users.id |
| resolved_by_id | INTEGER |  | yes | users.id |
| resolution | VARCHAR(500) |  | yes |  |
| fingerprint | VARCHAR(160) |  | yes |  |
| occurrences | INTEGER |  |  |  |
| last_seen_at | DATETIME |  | yes |  |
| reopened_count | INTEGER |  |  |  |
| provenance | VARCHAR(24) |  |  |  |
| experiment_id | INTEGER |  | yes | experiments.id |

## bookings

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| user_id | INTEGER |  |  | users.id |
| lab_id | INTEGER |  |  | labs.id |
| start_time | DATETIME |  |  |  |
| end_time | DATETIME |  |  |  |
| reason | TEXT |  |  |  |
| status | VARCHAR(48) |  |  |  |
| created_at | DATETIME |  |  |  |
| cancelled_at | DATETIME |  | yes |  |
| first_entry_at | DATETIME |  | yes |  |
| last_entry_at | DATETIME |  | yes |  |
| entry_count | INTEGER |  |  |  |
| provenance | VARCHAR(24) |  |  |  |
| experiment_id | INTEGER |  | yes | experiments.id |

## experiment_trials

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| experiment_id | INTEGER |  |  | experiments.id |
| repeat_number | INTEGER |  |  |  |
| input | TEXT |  |  |  |
| expected | TEXT |  |  |  |
| actual | TEXT |  |  |  |
| measurement | FLOAT |  | yes |  |
| unit | VARCHAR(24) |  | yes |  |
| result | VARCHAR(16) |  | yes |  |
| notes | TEXT |  |  |  |
| recorded_by_id | INTEGER |  | yes | users.id |
| recorded_at | DATETIME |  |  |  |

## inventory_measurements

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| bin_id | INTEGER |  |  | inventory_bins.id |
| mass_g | FLOAT |  |  |  |
| recorded_at | DATETIME |  |  |  |

## security_events

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| device_id | INTEGER |  |  | devices.id |
| lab_id | INTEGER |  |  | labs.id |
| zone_id | INTEGER |  | yes | security_zones.id |
| kind | VARCHAR(32) |  |  |  |
| detail | VARCHAR(255) |  |  |  |
| people_seen | INTEGER |  |  |  |
| people_inside | INTEGER |  |  |  |
| snapshot_key | VARCHAR(255) |  | yes |  |
| created_at | DATETIME |  |  |  |
| acknowledged_at | DATETIME |  | yes |  |
| acknowledged_by_id | INTEGER |  | yes | users.id |
| provenance | VARCHAR(24) |  |  |  |
| experiment_id | INTEGER |  | yes | experiments.id |

## sensor_readings

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| lab_id | INTEGER |  |  | labs.id |
| device_id | INTEGER |  | yes | devices.id |
| metric | VARCHAR(48) |  |  |  |
| value | FLOAT |  |  |  |
| unit | VARCHAR(16) |  |  |  |
| recorded_at | DATETIME |  |  |  |
| provenance | VARCHAR(24) |  |  |  |
| experiment_id | INTEGER |  | yes | experiments.id |

## access_attempts

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| lab_id | INTEGER |  | yes | labs.id |
| device_id | INTEGER |  | yes | devices.id |
| user_id | INTEGER |  | yes | users.id |
| booking_id | INTEGER |  | yes | bookings.id |
| method | VARCHAR(48) |  |  |  |
| result | VARCHAR(48) |  |  |  |
| denial_reason | VARCHAR(48) |  | yes |  |
| credential_ref | VARCHAR(64) |  | yes |  |
| created_at | DATETIME |  |  |  |

## access_events

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| event_type | VARCHAR(48) |  |  |  |
| lab_id | INTEGER |  | yes | labs.id |
| user_id | INTEGER |  | yes | users.id |
| booking_id | INTEGER |  | yes | bookings.id |
| device_id | INTEGER |  | yes | devices.id |
| method | VARCHAR(48) |  | yes |  |
| result | VARCHAR(48) |  | yes |  |
| reason | VARCHAR(64) |  | yes |  |
| message | VARCHAR(255) |  |  |  |
| event_metadata | JSON |  | yes |  |
| created_at | DATETIME |  |  |  |
| provenance | VARCHAR(24) |  |  |  |
| experiment_id | INTEGER |  | yes | experiments.id |

## access_sessions

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| lab_id | INTEGER |  |  | labs.id |
| user_id | INTEGER |  |  | users.id |
| booking_id | INTEGER |  | yes | bookings.id |
| device_id | INTEGER |  | yes | devices.id |
| entry_method | VARCHAR(48) |  |  |  |
| second_factor | VARCHAR(48) |  | yes |  |
| started_at | DATETIME |  |  |  |
| door_opened_at | DATETIME |  | yes |  |
| door_closed_at | DATETIME |  | yes |  |
| ended_at | DATETIME |  | yes |  |
| end_reason | VARCHAR(48) |  | yes |  |
| provenance | VARCHAR(24) |  |  |  |
| experiment_id | INTEGER |  | yes | experiments.id |

## asset_transactions

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| asset_id | INTEGER |  |  | assets.id |
| user_id | INTEGER |  |  | users.id |
| lab_id | INTEGER |  |  | labs.id |
| action | VARCHAR(32) |  |  |  |
| created_at | DATETIME |  |  |  |
| note | VARCHAR(255) |  |  |  |
| booking_id | INTEGER |  | yes | bookings.id |
| device_id | INTEGER |  | yes | devices.id |
| source | VARCHAR(16) |  |  |  |
| mass_delta_g | FLOAT |  | yes |  |
| weight_check | VARCHAR(16) |  | yes |  |

## booking_items

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| booking_id | INTEGER |  |  | bookings.id |
| kind | VARCHAR(16) |  |  |  |
| asset_id | INTEGER |  | yes | assets.id |
| inventory_bin_id | INTEGER |  | yes | inventory_bins.id |
| quantity | INTEGER |  | yes |  |
| label | VARCHAR(128) |  |  |  |
| created_at | DATETIME |  |  |  |

## equipment_sessions

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| device_id | INTEGER |  |  | devices.id |
| asset_id | INTEGER |  | yes | assets.id |
| lab_id | INTEGER |  |  | labs.id |
| state | VARCHAR(16) |  |  |  |
| user_id | INTEGER |  | yes | users.id |
| booking_id | INTEGER |  | yes | bookings.id |
| detail | JSON |  | yes |  |
| started_at | DATETIME |  |  |  |
| ended_at | DATETIME |  | yes |  |

## incident_notes

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| alert_id | INTEGER |  |  | alerts.id |
| user_id | INTEGER |  | yes | users.id |
| kind | VARCHAR(16) |  |  |  |
| text | VARCHAR(2000) |  |  |  |
| created_at | DATETIME |  |  |  |

## inventory_transactions

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| bin_id | INTEGER |  |  | inventory_bins.id |
| kind | VARCHAR(16) |  |  |  |
| delta_mass_g | FLOAT |  | yes |  |
| delta_qty_est | INTEGER |  | yes |  |
| qty_est_after | INTEGER |  | yes |  |
| actual_count | INTEGER |  | yes |  |
| user_id | INTEGER |  | yes | users.id |
| booking_id | INTEGER |  | yes | bookings.id |
| attribution | VARCHAR(24) |  |  |  |
| recorded_by_id | INTEGER |  | yes | users.id |
| note | VARCHAR(255) |  |  |  |
| recorded_at | DATETIME |  |  |  |

## qr_tokens

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| token | VARCHAR(128) |  |  |  |
| booking_id | INTEGER |  |  | bookings.id |
| user_id | INTEGER |  |  | users.id |
| lab_id | INTEGER |  |  | labs.id |
| valid_from | DATETIME |  |  |  |
| valid_until | DATETIME |  |  |  |
| issued_at | DATETIME |  |  |  |
| revoked_at | DATETIME |  | yes |  |
| last_used_at | DATETIME |  | yes |  |
| use_count | INTEGER |  |  |  |

## robot_events

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| device_id | INTEGER |  |  | devices.id |
| lab_id | INTEGER |  |  | labs.id |
| kind | VARCHAR(32) |  |  |  |
| joint | INTEGER |  | yes |  |
| detail | JSON |  | yes |  |
| source | VARCHAR(16) |  |  |  |
| occurred_at | DATETIME |  |  |  |
| received_at | DATETIME |  |  |  |
| booking_id | INTEGER |  | yes | bookings.id |
| context | JSON |  | yes |  |
| severity | VARCHAR(12) |  |  |  |
| provenance | VARCHAR(24) |  |  |  |
| experiment_id | INTEGER |  | yes | experiments.id |

## issues

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| ticket_number | VARCHAR(32) |  | yes |  |
| reporter_id | INTEGER |  |  | users.id |
| lab_id | INTEGER |  |  | labs.id |
| asset_id | INTEGER |  | yes | assets.id |
| device_id | INTEGER |  | yes | devices.id |
| access_event_id | INTEGER |  | yes | access_events.id |
| category | VARCHAR(48) |  |  |  |
| severity | VARCHAR(48) |  |  |  |
| status | VARCHAR(48) |  |  |  |
| title | VARCHAR(140) |  |  |  |
| description | TEXT |  |  |  |
| additional_comments | TEXT |  |  |  |
| assigned_to_id | INTEGER |  | yes | users.id |
| resolution_notes | TEXT |  |  |  |
| created_at | DATETIME |  |  |  |
| updated_at | DATETIME |  |  |  |
| acknowledged_at | DATETIME |  | yes |  |
| resolved_at | DATETIME |  | yes |  |
| closed_at | DATETIME |  | yes |  |
| provenance | VARCHAR(24) |  |  |  |
| experiment_id | INTEGER |  | yes | experiments.id |

## issue_comments

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| issue_id | INTEGER |  |  | issues.id |
| author_id | INTEGER |  |  | users.id |
| body | TEXT |  |  |  |
| is_internal | BOOLEAN |  |  |  |
| created_at | DATETIME |  |  |  |

## issue_history

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| issue_id | INTEGER |  |  | issues.id |
| actor_id | INTEGER |  | yes | users.id |
| event_type | VARCHAR(48) |  |  |  |
| old_status | VARCHAR(48) |  | yes |  |
| new_status | VARCHAR(48) |  | yes |  |
| message | VARCHAR(500) |  |  |  |
| detail | JSON |  | yes |  |
| is_internal | BOOLEAN |  |  |  |
| created_at | DATETIME |  |  |  |

## issue_photos

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| issue_id | INTEGER |  |  | issues.id |
| uploaded_by_id | INTEGER |  |  | users.id |
| stage | VARCHAR(48) |  |  |  |
| storage_key | VARCHAR(255) |  |  |  |
| thumb_key | VARCHAR(255) |  |  |  |
| original_filename | VARCHAR(255) |  |  |  |
| content_type | VARCHAR(32) |  |  |  |
| size_bytes | INTEGER |  |  |  |
| width | INTEGER |  |  |  |
| height | INTEGER |  |  |  |
| created_at | DATETIME |  |  |  |

## notifications

| Column | Type | Key | Null | References |
|---|---|---|---|---|
| id | INTEGER | PK |  |  |
| user_id | INTEGER |  |  | users.id |
| kind | VARCHAR(48) |  |  |  |
| severity | VARCHAR(16) |  |  |  |
| title | VARCHAR(160) |  |  |  |
| body | VARCHAR(500) |  |  |  |
| link | VARCHAR(160) |  | yes |  |
| issue_id | INTEGER |  | yes | issues.id |
| booking_id | INTEGER |  | yes | bookings.id |
| is_read | BOOLEAN |  |  |  |
| created_at | DATETIME |  |  |  |
| read_at | DATETIME |  | yes |  |
| dedupe_key | VARCHAR(160) |  | yes |  |
| source | VARCHAR(16) |  | yes |  |
