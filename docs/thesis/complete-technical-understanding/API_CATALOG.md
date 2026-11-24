# API catalog

355 routes, read from the decorators in `backend/app/api/routes/` (commit 11003b0). The *who* column is read from the function's dependencies; "see code" = decided elsewhere.


## access.py
| Method | Address | Who | Function |
|---|---|---|---|
| POST | `/api/access/validate-qr` | device key | `validate_qr_endpoint` (line 66) |
| POST | `/api/access/validate-rfid` | device key | `validate_rfid_endpoint` (line 96) |
| POST | `/api/access/events` | device key | `post_event` (line 133) |
| POST | `/api/access/grant` | device key | `record_grant` (line 181) |
| POST | `/api/access/deny` | device key | `record_deny` (line 239) |
| POST | `/api/access/heartbeat` | device key | `heartbeat` (line 303) |
| POST | `/api/access/telemetry` | device key | `telemetry` (line 376) |

## admin.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/access-events` | signed in | `access_events` (line 50) |
| GET | `/api/access-sessions` | staff | `access_sessions` (line 125) |
| GET | `/api/access-sessions/lookup` | signed in | `session_lookup` (line 150) |
| GET | `/api/access-sessions/{session_id}` | signed in | `session_detail` (line 173) |
| GET | `/api/summary` | staff | `summary` (line 222) |
| GET | `/api/users` | staff | `list_users` (line 300) |
| GET | `/api/users/next-auth-subject` | admin | `next_subject` (line 321) |
| POST | `/api/users/{user_id}/remove` | admin | `remove_user` (line 344) |
| PATCH | `/api/users/{user_id}` | staff | `update_user` (line 376) |
| GET | `/api/users/{user_id}/access-setup` | admin | `user_access_setup` (line 433) |
| POST | `/api/users/{user_id}/rfid` | admin | `add_rfid` (line 443) |
| GET | `/api/devices` | staff | `list_devices` (line 459) |
| POST | `/api/devices` | admin | `create_device` (line 475) |
| PATCH | `/api/devices/{device_id}/name` | admin | `rename_device` (line 493) |
| POST | `/api/devices/{device_id}/key` | admin | `issue_device_key` (line 513) |
| DELETE | `/api/devices/{device_id}/key` | admin | `revoke_device_key` (line 540) |
| GET | `/api/assets` | signed in | `list_assets` (line 589) |
| GET | `/api/assets/{asset_id}` | signed in | `asset_detail` (line 602) |
| POST | `/api/assets` | staff | `create_asset` (line 684) |
| PATCH | `/api/assets/{asset_id}` | staff | `update_asset` (line 698) |
| POST | `/api/assets/{asset_id}/inspect` | staff | `inspect_asset` (line 721) |
| POST | `/api/assets/{asset_id}/checkout` | signed in | `checkout_asset` (line 743) |
| POST | `/api/assets/{asset_id}/return` | signed in | `return_asset` (line 768) |
| GET | `/api/alerts` | staff | `list_alerts` (line 803) |
| POST | `/api/alerts/{alert_id}/resolve` | staff | `resolve_alert` (line 814) |
| GET | `/api/access-events/export` | staff | `export_events` (line 832) |
| GET | `/api/reports/access` | staff | `access_report` (line 881) |
| GET | `/api/reports/overview` | staff | `reports_overview` (line 907) |
| PUT | `/api/users/{user_id}/password` | staff | `set_user_password` (line 1028) |

## ai.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/ai/status` | staff | `status` (line 32) |
| GET | `/api/ai/student/status` | signed in | `student_status` (line 37) |
| GET | `/api/ai/maintenance-priorities` | staff | `priorities` (line 49) |
| POST | `/api/ai/ask` | staff | `ask` (line 161) |
| POST | `/api/ai/ask/stream` | staff | `ask_stream` (line 180) |
| POST | `/api/ai/student/ask/stream` | signed in | `student_ask_stream` (line 202) |
| GET | `/api/ai/report` | staff | `management_report` (line 222) |
| GET | `/api/ai/insights` | staff | `insights` (line 231) |
| POST | `/api/ai/summaries/{kind}` | staff | `summary` (line 238) |
| POST | `/api/ai/student/ask` | signed in | `student_ask` (line 245) |
| GET | `/api/ai/tools` | staff | `list_tools` (line 266) |
| POST | `/api/ai/tools/{name}` | staff | `call_tool` (line 279) |
| POST | `/api/ai/feedback` | signed in | `feedback` (line 312) |
| GET | `/api/ai/feedback/review` | staff | `feedback_review` (line 322) |

## analytics.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/analytics/operations` | staff | `operations` (line 21) |
| GET | `/api/analytics/system` | staff | `system` (line 29) |
| GET | `/api/analytics/kpis` | staff | `kpis` (line 37) |
| GET | `/api/analytics/labs/{lab_id}` | signed in | `lab_twin` (line 43) |
| GET | `/api/analytics/me` | signed in | `me` (line 53) |
| GET | `/api/analytics/trends` | staff | `trends` (line 60) |
| GET | `/api/analytics/export.csv` | staff | `export_csv` (line 67) |
| GET | `/api/analytics/anomalies` | staff | `anomalies` (line 85) |
| POST | `/api/analytics/anomalies/raise` | staff | `raise_anomaly` (line 99) |

## auth.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/auth/username-suggestion` | see code | `username_suggestion` (line 35) |
| POST | `/api/auth/login` | see code | `login` (line 41) |
| POST | `/api/auth/register` | admin | `register` (line 87) |
| GET | `/api/auth/signup-config` | see code | `signup_config` (line 121) |
| POST | `/api/auth/signup` | see code | `signup` (line 129) |
| POST | `/api/auth/ws-ticket` | signed in | `ws_ticket` (line 196) |
| GET | `/api/auth/me` | signed in | `me` (line 204) |
| GET | `/api/auth/me/access-setup` | signed in | `my_access_setup` (line 209) |
| POST | `/api/auth/me/door-qr` | signed in | `create_my_door_qr` (line 218) |
| GET | `/api/auth/me/door-qr` | signed in | `my_door_qr_status` (line 236) |
| DELETE | `/api/auth/me/door-qr` | signed in | `revoke_my_door_qr` (line 244) |

## automation.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/automation/health` | see code | `health` (line 44) |
| GET | `/api/automation/events` | see code | `events` (line 51) |
| GET | `/api/automation/bookings/upcoming` | see code | `upcoming` (line 67) |
| GET | `/api/automation/bookings/ended` | see code | `ended` (line 73) |
| GET | `/api/automation/bookings/{booking_id}` | see code | `booking` (line 79) |
| POST | `/api/automation/bookings/{booking_id}/remind` | see code | `remind` (line 87) |
| GET | `/api/automation/access/denials` | see code | `denials` (line 101) |
| GET | `/api/automation/devices/offline` | see code | `devices_offline` (line 109) |
| GET | `/api/automation/maintenance` | see code | `maintenance` (line 114) |
| GET | `/api/automation/issues/{issue_id}` | see code | `issue` (line 119) |
| GET | `/api/automation/reports/daily` | see code | `report_daily` (line 127) |
| GET | `/api/automation/reports/weekly` | see code | `report_weekly` (line 132) |
| GET | `/api/automation/sensors/evaluate` | see code | `sensors` (line 137) |
| GET | `/api/automation/data-quality` | see code | `quality` (line 143) |
| GET | `/api/automation/maintenance/priorities` | see code | `maintenance_ranked` (line 148) |
| GET | `/api/automation/ai/weekly-summary` | see code | `ai_weekly` (line 154) |
| GET | `/api/automation/anomalies` | see code | `anomaly_scan` (line 169) |
| GET | `/api/automation/robotics/{topic}` | see code | `robotics_topic` (line 201) |
| GET | `/api/automation/emergency/{lab_id}` | see code | `emergency_state` (line 215) |
| POST | `/api/automation/notify` | see code | `post_notify` (line 246) |
| POST | `/api/automation/alerts` | see code | `post_alert` (line 273) |
| POST | `/api/automation/runs` | see code | `post_run` (line 294) |

## bookings.py
| Method | Address | Who | Function |
|---|---|---|---|
| POST | `/api/bookings` | signed in | `create` (line 113) |
| GET | `/api/bookings/equipment-options` | signed in | `booking_equipment_options` (line 138) |
| GET | `/api/bookings` | signed in | `list_bookings` (line 148) |
| GET | `/api/bookings/{booking_id}` | signed in | `get_booking` (line 176) |
| POST | `/api/bookings/{booking_id}/confirm` | staff | `confirm` (line 182) |
| POST | `/api/bookings/{booking_id}/reject` | staff | `reject` (line 201) |
| POST | `/api/bookings/{booking_id}/cancel` | signed in | `cancel` (line 216) |
| GET | `/api/bookings/{booking_id}/qr` | signed in | `booking_qr` (line 232) |
| GET | `/api/bookings/{booking_id}/sessions` | signed in | `booking_sessions` (line 277) |
| GET | `/api/bookings/{booking_id}/trace` | signed in | `booking_trace` (line 298) |

## commands.py
| Method | Address | Who | Function |
|---|---|---|---|
| POST | `/api/users/{user_id}/fingerprint/enroll` | staff | `request_enrollment` (line 73) |
| POST | `/api/users/{user_id}/rfid/enroll` | staff | `request_card_enrollment` (line 137) |
| POST | `/api/users/{user_id}/rfid/remove` | staff | `request_card_removal` (line 148) |
| GET | `/api/users/{user_id}/rfid` | staff | `user_cards` (line 169) |
| GET | `/api/device-commands/{command_id}` | staff | `command_status` (line 198) |
| POST | `/api/device-commands/{command_id}/cancel` | staff | `cancel_command` (line 210) |
| GET | `/api/access/commands/next` | device key | `next_command` (line 231) |
| POST | `/api/access/commands/{command_id}/progress` | device key | `report_progress` (line 271) |

## emergency.py
| Method | Address | Who | Function |
|---|---|---|---|
| POST | `/api/emergency/session` | admin | `open_session` (line 90) |
| GET | `/api/emergency/status` | admin | `status_all` (line 121) |
| GET | `/api/emergency/active` | signed in | `active_broadcasts` (line 145) |
| POST | `/api/emergency/labs/{lab_id}` | see code | `act` (line 189) |
| POST | `/api/emergency/labs/{lab_id}/normal` | see code | `back_to_normal` (line 237) |
| POST | `/api/emergency/pcs` | see code | `pcs` (line 267) |
| PUT | `/api/emergency/password` | see code | `change_password` (line 305) |
| GET | `/api/access/emergency` | device key | `for_controller` (line 318) |
| GET | `/api/safety/triage` | staff | `safety_triage` (line 335) |
| GET | `/api/insights/proactive` | staff | `proactive_insights` (line 343) |

## enrollment.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/enrollment/camera/snapshot` | staff | `camera_snapshot` (line 70) |
| GET | `/api/users/{user_id}/face` | staff | `face_status` (line 93) |
| POST | `/api/users/{user_id}/face/capture` | staff | `face_capture` (line 113) |
| POST | `/api/users/{user_id}/face/auto` | staff | `face_auto_start` (line 149) |
| GET | `/api/users/{user_id}/face/auto` | staff | `face_auto_status` (line 158) |
| DELETE | `/api/users/{user_id}/face/auto` | staff | `face_auto_stop` (line 167) |
| POST | `/api/users/{user_id}/face/reset` | staff | `face_reset` (line 176) |
| POST | `/api/users/{user_id}/face/finish` | staff | `face_finish` (line 199) |
| POST | `/api/users/{user_id}/face/upload` | staff | `face_upload` (line 234) |
| GET | `/api/users/{user_id}/door-photo` | staff | `door_photo_info` (line 311) |
| GET | `/api/users/{user_id}/door-photo/current.jpg` | staff | `door_photo_current` (line 320) |
| GET | `/api/users/{user_id}/door-photo/candidate/{cid}.jpg` | staff | `door_photo_candidate` (line 329) |
| POST | `/api/users/{user_id}/door-photo/choose` | staff | `door_photo_choose` (line 341) |
| POST | `/api/users/{user_id}/door-photo/upload` | staff | `door_photo_upload` (line 357) |

## equipment.py
| Method | Address | Who | Function |
|---|---|---|---|
| POST | `/api/equipment/state` | device key | `report_state` (line 135) |
| POST | `/api/equipment/violations` | device key | `report_violation` (line 212) |
| GET | `/api/equipment` | staff | `list_equipment` (line 230) |
| GET | `/api/equipment/{device_id}/sessions` | staff | `sessions` (line 283) |
| GET | `/api/equipment/aas.json` | staff | `aas_export` (line 299) |
| GET | `/api/equipment/violations` | staff | `list_violations` (line 307) |
| PUT | `/api/equipment/{device_id}/mode` | staff | `set_mode` (line 324) |
| GET | `/api/equipment/master/nonce` | staff | `master_nonce` (line 387) |
| POST | `/api/equipment/master/claim` | staff | `master_claim` (line 416) |
| GET | `/api/equipment/master` | staff | `current_master` (line 455) |
| PUT | `/api/equipment/{device_id}/master` | staff | `set_master` (line 465) |
| POST | `/api/equipment/pc/presence` | device key | `report_lan_presence` (line 494) |
| GET | `/api/equipment/pc/lan-targets` | device key | `lan_targets` (line 536) |
| GET | `/api/equipment/pc/poll` | device key | `pc_poll` (line 556) |
| POST | `/api/equipment/pc/frame` | device key | `pc_frame` (line 623) |
| POST | `/api/equipment/{device_id}/screen/start` | staff | `screen_start` (line 656) |
| GET | `/api/equipment/{device_id}/screen.jpg` | staff | `screen_frame` (line 667) |
| POST | `/api/equipment/{device_id}/screen/stop` | staff | `screen_stop` (line 685) |
| POST | `/api/equipment/{device_id}/message` | staff | `send_message` (line 701) |
| POST | `/api/equipment/{device_id}/message/clear` | staff | `clear_message` (line 733) |
| POST | `/api/equipment/{device_id}/action` | staff | `pc_action` (line 790) |
| GET | `/api/equipment/{device_id}/actions` | staff | `pc_actions` (line 832) |
| POST | `/api/equipment/pc/action-result` | device key | `pc_action_result` (line 853) |
| POST | `/api/equipment/broadcast/start` | staff | `broadcast_start` (line 885) |
| POST | `/api/equipment/broadcast/stop` | staff | `broadcast_stop` (line 917) |
| GET | `/api/equipment/broadcast/status` | signed in | `broadcast_status` (line 932) |
| GET | `/api/equipment/share-requests/nonce` | signed in | `share_nonce` (line 951) |
| POST | `/api/equipment/share-requests` | signed in | `share_ask` (line 961) |
| GET | `/api/equipment/share-requests/mine` | signed in | `share_mine` (line 985) |
| GET | `/api/equipment/share-requests` | staff | `share_list` (line 992) |
| POST | `/api/equipment/share-requests/{req_id}` | staff | `share_decide` (line 1002) |
| POST | `/api/equipment/share-requests/mine/stop` | signed in | `share_stop_mine` (line 1023) |
| POST | `/api/equipment/broadcast/frame` | staff | `broadcast_frame_from_browser` (line 1036) |
| POST | `/api/equipment/pc/broadcast-frame` | device key | `broadcast_frame_from_master` (line 1050) |
| GET | `/api/equipment/broadcast/frame.jpg` | signed in | `broadcast_frame` (line 1085) |
| POST | `/api/equipment/pc/enroll` | see code | `pc_enroll` (line 1127) |
| GET | `/api/equipment/pc/agent-bundle` | device key | `pc_agent_bundle` (line 1171) |
| GET | `/api/equipment/pc/watch-token` | device key | `pc_watch_token` (line 1181) |
| GET | `/api/equipment/broadcast/watch/status` | see code | `broadcast_watch_status` (line 1197) |
| GET | `/api/equipment/broadcast/watch/frame.jpg` | see code | `broadcast_watch_frame` (line 1207) |
| GET | `/api/equipment/pc/wait` | device key | `pc_wait` (line 1235) |

## experiments.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/experiments` | staff | `list_experiments` (line 95) |
| POST | `/api/experiments` | staff | `create` (line 107) |
| GET | `/api/experiments/{exp_id}` | staff | `detail` (line 121) |
| POST | `/api/experiments/{exp_id}/start` | staff | `start` (line 126) |
| POST | `/api/experiments/{exp_id}/trials` | staff | `add_trial` (line 142) |
| POST | `/api/experiments/{exp_id}/stop` | staff | `stop` (line 152) |

## face_submissions.py
| Method | Address | Who | Function |
|---|---|---|---|
| POST | `/api/auth/me/face-submission` | signed in | `submit_photos` (line 130) |
| GET | `/api/auth/me/face-submission` | signed in | `my_submission` (line 193) |
| POST | `/api/auth/me/face-submission/withdraw` | signed in | `withdraw` (line 199) |
| GET | `/api/face-submissions` | staff | `waiting` (line 211) |
| GET | `/api/users/{user_id}/face/submission` | staff | `pending_for_user` (line 219) |
| GET | `/api/face-submissions/{sid}/photos/{n}` | signed in | `submission_photo` (line 226) |
| POST | `/api/face-submissions/{sid}/approve` | staff | `approve` (line 254) |
| POST | `/api/face-submissions/{sid}/review` | staff | `review_photos` (line 317) |
| POST | `/api/face-submissions/{sid}/retake` | staff | `retake` (line 405) |
| POST | `/api/face-submissions/{sid}/reject` | staff | `reject` (line 423) |

## incidents.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/incidents` | staff | `list_incidents` (line 122) |
| GET | `/api/incidents/quality` | staff | `incident_quality` (line 180) |
| GET | `/api/incidents/{incident_id}` | staff | `get_incident` (line 200) |
| POST | `/api/incidents/{incident_id}/actions` | staff | `act` (line 226) |

## inventory.py
| Method | Address | Who | Function |
|---|---|---|---|
| POST | `/api/inventory/measurements` | device key | `post_measurements` (line 41) |
| GET | `/api/inventory/bins` | staff | `list_bins` (line 119) |
| POST | `/api/inventory/bins` | staff | `create_bin` (line 129) |
| PATCH | `/api/inventory/bins/{bin_id}` | staff | `update_bin` (line 146) |
| GET | `/api/inventory/bins/{bin_id}/history` | staff | `bin_history` (line 167) |
| POST | `/api/inventory/bins/{bin_id}/count` | staff | `record_count` (line 202) |
| POST | `/api/inventory/bins/{bin_id}/zero` | staff | `zero_bin` (line 261) |
| POST | `/api/inventory/bins/{bin_id}/calibration` | staff | `calibration_start` (line 330) |
| GET | `/api/inventory/bins/{bin_id}/calibration` | staff | `calibration_status` (line 341) |
| POST | `/api/inventory/bins/{bin_id}/calibration/finish` | staff | `calibration_finish` (line 348) |
| DELETE | `/api/inventory/bins/{bin_id}/calibration` | staff | `calibration_cancel` (line 380) |
| GET | `/api/inventory/bins/{bin_id}/items` | staff | `list_items` (line 401) |
| POST | `/api/inventory/bins/{bin_id}/items/{item_id}/select` | staff | `select_item` (line 406) |
| POST | `/api/inventory/bins/{bin_id}/items/{item_id}/remove` | staff | `remove_item` (line 434) |

## issues.py
| Method | Address | Who | Function |
|---|---|---|---|
| POST | `/api/issues` | signed in | `create_issue` (line 44) |
| GET | `/api/issues` | signed in | `list_issues` (line 54) |
| GET | `/api/issues/summary` | staff | `issue_summary` (line 106) |
| GET | `/api/issues/{issue_id}` | signed in | `get_issue` (line 113) |
| PATCH | `/api/issues/{issue_id}` | signed in | `update_issue` (line 119) |
| POST | `/api/issues/{issue_id}/acknowledge` | signed in | `acknowledge` (line 144) |
| POST | `/api/issues/{issue_id}/assign` | signed in | `assign` (line 150) |
| POST | `/api/issues/{issue_id}/status` | signed in | `change_status` (line 156) |
| POST | `/api/issues/{issue_id}/resolve` | signed in | `resolve` (line 163) |
| POST | `/api/issues/{issue_id}/close` | signed in | `close` (line 169) |
| POST | `/api/issues/{issue_id}/reopen` | signed in | `reopen` (line 176) |
| POST | `/api/issues/{issue_id}/comments` | signed in | `add_comment` (line 184) |
| POST | `/api/issues/{issue_id}/photos` | signed in | `upload_photos` (line 200) |
| GET | `/api/issues/{issue_id}/photos` | signed in | `list_photos` (line 228) |
| GET | `/api/issues/{issue_id}/photos/{photo_id}/file` | signed in | `photo_file` (line 234) |

## knowledge.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/knowledge/status` | staff | `knowledge_status` (line 33) |
| POST | `/api/knowledge/ask` | staff | `knowledge_ask` (line 49) |

## labs.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/labs` | signed in | `list_labs` (line 64) |
| GET | `/api/labs/overview` | signed in | `labs_overview` (line 70) |
| POST | `/api/labs` | admin | `create_lab` (line 130) |
| PATCH | `/api/labs/{lab_id}` | admin | `update_lab` (line 152) |
| GET | `/api/labs/environment/all` | signed in | `all_environments` (line 170) |
| GET | `/api/labs/health` | signed in | `labs_health` (line 187) |
| GET | `/api/labs/headcount` | signed in | `labs_headcount` (line 198) |
| GET | `/api/labs/{lab_id}` | signed in | `lab_detail` (line 232) |
| GET | `/api/labs/hazards/active` | signed in | `hazards_active` (line 304) |
| GET | `/api/labs/{lab_id}/environment` | signed in | `lab_environment` (line 313) |
| GET | `/api/labs/{lab_id}/availability` | signed in | `lab_availability` (line 326) |
| GET | `/api/labs/{lab_id}/activity` | signed in | `lab_activity` (line 353) |
| GET | `/api/labs/{lab_id}/issues` | signed in | `lab_issues` (line 382) |
| GET | `/api/labs/{lab_id}/sensors` | signed in | `lab_sensors` (line 394) |
| GET | `/api/labs/{lab_id}/at` | staff | `lab_at_time` (line 406) |

## metrics.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/metrics/registry` | staff | `registry` (line 17) |
| GET | `/api/metrics/latest` | staff | `latest` (line 22) |
| GET | `/api/metrics/history` | staff | `history` (line 27) |
| GET | `/api/metrics/coverage` | staff | `coverage` (line 38) |
| GET | `/api/metrics/diagnose/{device_id}` | staff | `diagnose` (line 43) |
| GET | `/api/metrics/timeline` | staff | `timeline` (line 51) |

## monitor.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/monitor` | staff | `wall_screen` (line 206) |

## notifications.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/notifications` | signed in | `list_notifications` (line 19) |
| GET | `/api/notifications/inbox` | signed in | `inbox` (line 32) |
| GET | `/api/notifications/unread-count` | signed in | `unread_count` (line 63) |
| POST | `/api/notifications/{notification_id}/read` | signed in | `mark_read` (line 72) |
| POST | `/api/notifications/read-all` | signed in | `mark_all_read` (line 86) |

## opcua.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/opcua/snapshot` | see code | `snapshot` (line 41) |

## reliability.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/reliability/graph` | staff | `graph` (line 47) |
| POST | `/api/reliability/graph/whatif` | staff | `whatif` (line 57) |
| GET | `/api/reliability/incidents/{incident_id}/investigate` | staff | `investigate_incident` (line 68) |
| GET | `/api/reliability/alert-quality` | staff | `alert_quality` (line 76) |
| GET | `/api/reliability/drift` | staff | `drift_check` (line 84) |
| POST | `/api/reliability/drift/accept` | admin | `drift_accept` (line 95) |
| GET | `/api/reliability/performance` | staff | `performance` (line 106) |
| GET | `/api/reliability/queries` | admin | `queries` (line 126) |
| POST | `/api/reliability/performance/baseline` | admin | `capture_baseline` (line 132) |
| GET | `/api/reliability/policy` | staff | `policy_table` (line 147) |
| POST | `/api/reliability/policy/evaluate` | staff | `policy_evaluate` (line 158) |
| POST | `/api/reliability/diagnose` | staff | `diagnose` (line 173) |
| GET | `/api/reliability/capacity` | staff | `capacity` (line 190) |
| GET | `/api/reliability/backups` | staff | `backups` (line 209) |
| GET | `/api/reliability/evaluation` | staff | `get_evaluation` (line 218) |
| GET | `/api/reliability/briefing` | staff | `get_briefing` (line 230) |

## reports_center.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/reports-center` | staff | `catalogue` (line 32) |
| GET | `/api/reports-center/timeline` | staff | `timeline` (line 37) |
| GET | `/api/reports-center/inventory-discrepancies` | staff | `inventory_discrepancies` (line 45) |
| GET | `/api/reports-center/asset-lifecycle` | staff | `asset_lifecycle` (line 50) |
| GET | `/api/reports-center/{kind}` | staff | `report` (line 55) |

## reusable.py
| Method | Address | Who | Function |
|---|---|---|---|
| POST | `/api/reusable/checkout` | signed in | `request_checkout` (line 189) |
| POST | `/api/reusable/staff-checkout` | staff | `staff_checkout` (line 235) |
| POST | `/api/reusable/staff-return` | staff | `staff_return` (line 284) |
| GET | `/api/reusable/items` | signed in | `bin_items` (line 310) |
| GET | `/api/reusable/last-unknown` | staff | `last_unknown` (line 339) |
| PUT | `/api/reusable/assets/{asset_id}/mass` | staff | `set_mass` (line 351) |
| PUT | `/api/reusable/assets/{asset_id}/tag` | staff | `assign_tag` (line 369) |
| POST | `/api/reusable/scan` | device key | `scan` (line 677) |
| POST | `/api/reusable/complete` | device key | `complete_return` (line 686) |
| POST | `/api/reusable/checkout-complete` | device key | `checkout_complete` (line 695) |
| POST | `/api/reusable/weight-change` | device key | `weight_change` (line 705) |

## robots.py
| Method | Address | Who | Function |
|---|---|---|---|
| POST | `/api/robots/telemetry` | device key | `telemetry` (line 202) |
| POST | `/api/robots/events` | device key | `events` (line 283) |
| GET | `/api/robots` | signed in | `robots` (line 347) |
| GET | `/api/robots/{device_id}` | staff | `robot` (line 371) |
| GET | `/api/robots/{device_id}/events` | staff | `robot_events` (line 388) |
| GET | `/api/robots/{device_id}/movements` | staff | `movements` (line 398) |
| GET | `/api/robots/{device_id}/movements/{event_id}` | staff | `movement` (line 408) |
| POST | `/api/robots/{device_id}/home` | admin | `calibrate_home` (line 424) |
| GET | `/api/robots/{device_id}/control` | staff | `control_status` (line 508) |
| POST | `/api/robots/{device_id}/control/request` | staff | `control_request` (line 513) |
| POST | `/api/robots/{device_id}/control/release` | staff | `control_release` (line 525) |
| POST | `/api/robots/{device_id}/control/command` | staff | `control_command` (line 545) |
| POST | `/api/robots/{device_id}/control/stop` | staff | `control_global_stop` (line 565) |
| POST | `/api/robots/{device_id}/control/auto-home/cancel` | staff | `control_auto_home_cancel` (line 578) |
| GET | `/api/robots/stop-relay/poll` | device key | `stop_relay_poll` (line 599) |
| POST | `/api/robots/{device_id}/control/recover` | admin | `control_recover` (line 624) |

## scan.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/scan/registry` | staff | `registry` (line 38) |
| GET | `/api/scan/asset` | staff | `asset` (line 43) |
| GET | `/api/scan/marker.png` | staff | `marker_png` (line 53) |
| GET | `/api/scan/marker.svg` | staff | `marker_svg` (line 72) |
| GET | `/api/scan/markers.json` | staff | `markers_page` (line 86) |
| GET | `/api/scan/markers.pdf` | staff | `markers_pdf` (line 96) |
| GET | `/api/scan/link.png` | staff | `link_png` (line 110) |
| POST | `/api/scan/people` | staff | `people` (line 130) |
| POST | `/api/scan/identify` | staff | `identify` (line 170) |
| POST | `/api/scan/ask` | staff | `ask` (line 225) |
| GET | `/api/scan/appearance/refs` | staff | `appearance_refs` (line 278) |
| POST | `/api/scan/appearance` | staff | `appearance_match` (line 286) |

## search.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/search` | staff | `search` (line 34) |
| GET | `/api/search/index` | staff | `search_index` (line 112) |

## security.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/security/config` | device key | `config` (line 132) |
| POST | `/api/security/zones/realign` | device key | `realign_zones` (line 199) |
| POST | `/api/security/state` | device key | `report_state` (line 264) |
| POST | `/api/security/events` | device key | `report_event` (line 310) |
| GET | `/api/security/cameras` | staff | `cameras` (line 435) |
| GET | `/api/security/cameras/{device_id}/frame.jpg` | staff | `frame` (line 452) |
| GET | `/api/security/cameras/{device_id}/identity` | staff | `identity_evidence` (line 484) |
| GET | `/api/security/cameras/{device_id}/suggestions` | staff | `suggestions` (line 501) |
| GET | `/api/security/cameras/{device_id}/zones` | staff | `list_zones` (line 567) |
| POST | `/api/security/cameras/{device_id}/zones` | staff | `add_zone` (line 574) |
| PUT | `/api/security/cameras/{device_id}/zones/{zone_id}` | staff | `update_zone` (line 588) |
| POST | `/api/security/cameras/{device_id}/zones/{zone_id}/accept` | staff | `accept_zone` (line 607) |
| DELETE | `/api/security/cameras/{device_id}/zones/{zone_id}` | staff | `delete_zone` (line 622) |
| GET | `/api/security/events` | staff | `events` (line 648) |
| GET | `/api/security/events/{event_id}/snapshot.jpg` | staff | `event_snapshot` (line 660) |
| POST | `/api/security/events/{event_id}/ack` | staff | `acknowledge` (line 669) |
| GET | `/api/security/cameras/{device_id}/recording` | admin | `recording_status` (line 737) |
| POST | `/api/security/cameras/{device_id}/recording/{action}` | admin | `recording_switch` (line 745) |
| GET | `/api/security/cameras/{device_id}/known` | admin | `known_people` (line 833) |
| POST | `/api/security/cameras/{device_id}/confirm` | admin | `confirm_person` (line 842) |
| GET | `/api/security/cameras/{device_id}/dataset` | admin | `dataset_status` (line 868) |
| POST | `/api/security/cameras/{device_id}/dataset/{action}` | admin | `dataset_switch` (line 877) |
| GET | `/api/security/cameras/{device_id}/recordings` | admin | `recordings` (line 891) |
| POST | `/api/security/cameras/{device_id}/recordings/{name}/delete` | admin | `recording_delete` (line 899) |
| POST | `/api/security/cameras/{device_id}/recordings/{name}/link` | admin | `recording_link` (line 916) |
| GET | `/api/security/recordings/play` | see code | `recording_play` (line 929) |

## system.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/system/status` | signed in | `system_status` (line 62) |
| GET | `/api/system/config` | admin | `system_config` (line 99) |
| GET | `/api/system/data-mode` | staff | `get_data_mode` (line 124) |
| PUT | `/api/system/data-mode` | admin | `set_data_mode` (line 132) |
| GET | `/api/system/services` | staff | `services` (line 194) |
| GET | `/api/system/health` | staff | `system_health` (line 225) |

## uiperf.py
| Method | Address | Who | Function |
|---|---|---|---|
| POST | `/api/uiperf/report` | staff | `report` (line 60) |
| GET | `/api/uiperf/reports` | admin | `reports` (line 67) |

## voice.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/voice/status` | signed in | `voice_status` (line 43) |
| POST | `/api/voice/transcribe` | signed in | `transcribe` (line 60) |
| POST | `/api/voice/speak` | signed in | `speak` (line 93) |

## workcell.py
| Method | Address | Who | Function |
|---|---|---|---|
| GET | `/api/workcell/{robot_key}` | staff | `setups` (line 46) |
| PUT | `/api/workcell/{robot_key}/{name}` | admin | `save` (line 59) |
