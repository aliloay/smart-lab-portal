# TEST.md: cli-anything-smartlab

## Part 1: Test plan (written before the tests)

### Test inventory
| File | Planned | Kind |
|---|---|---|
| `test_core.py` | ~30 | Unit tests, synthetic data, no network |
| `test_safety.py` | ~15 | Read-only guarantees: allow-list, absent command groups, no shell, no secret output |
| `test_full_e2e.py` | ~20 | The installed `cli-anything-smartlab` / `smartlab` command as a subprocess. It runs against a local fake portal (stdlib HTTP server) for deterministic API cases, and against the real local Smart Lab services for the live workflows |

### Unit tests (`test_core.py`)
| Module | What | Edge cases |
|---|---|---|
| `utils/config.py` | env overrides, repo discovery, secret readers, redacted knowledge config | missing repo, missing files, bad JSON |
| `utils/redaction.py` | key-based and text-based masking | bearer tokens, JWTs, `key=value`, RTSP URLs with passwords, door QR tokens; non-secret keys such as `PASS` counts and `prompt_tokens` are kept |
| `utils/freshness.py` | ONLINE / OFFLINE / STALE / UNKNOWN | no timestamp, naive timestamps, offline but recent, online but old |
| `core/devices.py` | portal state → CLI label, shaping, filters, summary | DEGRADED, NO_DATA, STALE threshold, unknown uid |
| `core/repo.py` | n8n trigger parsing, firmware version regexes, firmware compare, log tail + filter, report path guard, git ref validation | path traversal (`../`), non-`.md` files, bad ref names, `lines` out of range |
| `utils/api_client.py` | allow-list checks, token expiry handling, timeout → UNAVAILABLE, 401/403 → AUTH_REQUIRED, 404 → NOT_FOUND | expired token, token for another API base |
| `utils/output.py` | envelope schema, human table rendering | empty rows |

### Safety tests (`test_safety.py`)
- **No dangerous command groups:** the command tree contains no `unlock`, `door open`, `relay`, `move`, `jog`, `home`,
  `stop`, `opcua write`, `run`, `execute`, `activate`, `flash`, `shutdown`, `restart`, `delete`, `create`, `update`.
- **Allow-list:**
  - Every portal path the CLI can call is a GET on the allow-list.
  - The only POST is `/auth/login`.
  - Mutating paths (`/access/commands/next`, `/equipment/pc/poll`, `/robots/stop-relay/poll`,
    `/equipment/master/nonce`, `/devices` POST, `/emergency/...`) are refused with `Forbidden` **before any socket opens**.
- **Ollama:** `pull`, `delete`, `generate` and `chat` are refused.
- **Knowledge service:** only `/health`, `/status` and `/gpu-gate`; `/ask` is forced to `route=lookup`, so no generation.
- **Source scan:** no `shell=True`, `os.system`, `eval(` or `exec(`; every `subprocess.run` uses an argument list.
- **No secrets in output:** a fake KB key, device key and token never appear in any command's output.
- **Unauthenticated device commands:** they return AUTH_REQUIRED (exit 3) and send no request without a token.

### E2E (`test_full_e2e.py`)
- **Command resolution:** `_resolve_cli("cli-anything-smartlab")` (upstream pattern, honours `CLI_ANYTHING_FORCE_INSTALLED=1`),
  no `cwd`.
- **Against a fake portal** on a random localhost port (`SMARTLAB_API` env), with real HTTP and real JSON:
  - `--help` and `--version`;
  - `--json health`;
  - `devices list` with and without a token;
  - `devices offline`;
  - `devices inspect` for a known and an unknown uid;
  - `esp32 list`;
  - an expired token → exit 3;
  - API down → exit 4;
  - a slow API → timeout → exit 4;
  - an unknown command → exit 2.
- **Live, read-only, against this laptop's real services:**
  - `system services`, `ai models`, `knowledge search`, `firmware inventory`, `automation list`, `github status`,
    `doctor`.
  - These are verified against the real backends: Ollama's model list, the knowledge index, the repo files and git.
  - A live test **fails** (it does not skip) if the service it needs is down, so nothing that was unavailable is counted
    as a pass.

### Realistic workflows
1. **Agent morning check**
   - Simulates: an AI agent asked "is the lab OK?".
   - Chain: `doctor --json` → `devices offline --json` → `cameras status --json`.
   - Verified: the envelopes parse, every row has a status label, there is no secret.
2. **Firmware drift**
   - Simulates: "are the boards on the code in the repo?".
   - Chain: `firmware inventory` + `esp32 firmware`.
   - Verified: the versions come from the source files.
3. **Answer with evidence**
   - Simulates: "where is the relock guard implemented?".
   - Chain: `knowledge search`.
   - Verified: the cited source is the master firmware file, and the model is not run.
4. **Release check**
   - Simulates: "what is not on GitHub yet?".
   - Chain: `github status` → `github compare`.
   - Verified: the counts are integers and no fetch or push happens.

## Part 2: Results (21 Nov 2026, lab laptop, Windows 11, Python 3.12 in the clihub venv)

Command:
```text
CLI_ANYTHING_FORCE_INSTALLED=1 SMARTLAB_LIVE=1 python -m pytest -v --tb=short cli_anything/smartlab/tests
```
- The installed command was resolved from the user PATH: `C:/Projects/external-tools/bin/cli-anything-smartlab.cmd`,
  which calls the clihub venv exe; there was no module fallback.
- The live tests ran against the real portal (Docker), Ollama 0.40.16, the knowledge service, the camera services, the repo
  and git.

### Summary
| Suite | Tests | Result |
|---|---|---|
| test_core.py (unit) | 49 | passed |
| test_safety.py | 36 | passed |
| test_full_e2e.py: fake portal (installed command, real HTTP, incl. piped REPL) | 14 | passed |
| test_full_e2e.py: live, read-only, real services | 8 | passed |
| **Total** | **107** | **100 % passed** |

### Coverage notes
- **Device, ESP32, robot and PC commands:** verified end-to-end against the fake portal only. The real portal needs a
  staff sign-in, which the owner must do (`smartlab auth login`). Until then those commands return AUTH_REQUIRED (exit 3)
  on the real portal, as tested.
- **Live camera test:** run while the IP cameras were away at GIU. The services were ONLINE and the picture OFFLINE, which
  was correctly reported as not online.
- **REPL:** covered by `test_repl_with_piped_input`. Interactive prompt_toolkit mode is used only with a real console.

### Full output
```text
cli_anything/smartlab/tests/test_core.py::test_config_finds_repo_from_env PASSED [  0%]
cli_anything/smartlab/tests/test_core.py::test_config_env_overrides PASSED [  1%]
cli_anything/smartlab/tests/test_core.py::test_find_repo_walks_up PASSED [  2%]
cli_anything/smartlab/tests/test_core.py::test_secret_readers PASSED     [  3%]
cli_anything/smartlab/tests/test_core.py::test_knowledge_config_has_no_secrets PASSED [  4%]
cli_anything/smartlab/tests/test_core.py::test_missing_repo_files PASSED [  5%]
cli_anything/smartlab/tests/test_core.py::test_redact_text[Authorization: Bearer abc.def.ghi-abc.def.ghi] PASSED [  6%]
cli_anything/smartlab/tests/test_core.py::test_redact_text[token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJlMTIz-eyJhbGciOiJIUzI1NiJ9] PASSED [  7%]
cli_anything/smartlab/tests/test_core.py::test_redact_text[password: hunter22-hunter22] PASSED [  8%]
cli_anything/smartlab/tests/test_core.py::test_redact_text[rtsp://admin:pw@192.168.1.60/stream-admin:pw] PASSED [  9%]
cli_anything/smartlab/tests/test_core.py::test_redact_text[http://user:secretpw@host/x-secretpw] PASSED [ 10%]
cli_anything/smartlab/tests/test_core.py::test_redact_text[qr SLB:~AbCdEfGhIjKlMnOp-AbCdEfGhIjKlMnOp] PASSED [ 11%]
cli_anything/smartlab/tests/test_core.py::test_redact_text[service_key = 'abc123456'-abc123456] PASSED [ 12%]
cli_anything/smartlab/tests/test_core.py::test_redact_keys_but_keep_lookalikes PASSED [ 13%]
cli_anything/smartlab/tests/test_core.py::test_redact_extra_literals PASSED [ 14%]
cli_anything/smartlab/tests/test_core.py::test_device_status[True-seen0-ONLINE] PASSED [ 14%]
cli_anything/smartlab/tests/test_core.py::test_device_status[True-seen1-STALE] PASSED [ 15%]
cli_anything/smartlab/tests/test_core.py::test_device_status[False-seen2-OFFLINE] PASSED [ 16%]
cli_anything/smartlab/tests/test_core.py::test_device_status[True-None-UNKNOWN] PASSED [ 17%]
cli_anything/smartlab/tests/test_core.py::test_device_status[False-None-OFFLINE] PASSED [ 18%]
cli_anything/smartlab/tests/test_core.py::test_device_status[None-seen5-UNKNOWN] PASSED [ 19%]
cli_anything/smartlab/tests/test_core.py::test_naive_timestamp_is_utc PASSED [ 20%]
cli_anything/smartlab/tests/test_core.py::test_human_age PASSED          [ 21%]
cli_anything/smartlab/tests/test_core.py::test_label[ONLINE-10-ONLINE] PASSED [ 22%]
cli_anything/smartlab/tests/test_core.py::test_label[ONLINE-1000-STALE] PASSED [ 23%]
cli_anything/smartlab/tests/test_core.py::test_label[OFFLINE-10-OFFLINE] PASSED [ 24%]
cli_anything/smartlab/tests/test_core.py::test_label[NO_DATA-None-UNKNOWN] PASSED [ 25%]
cli_anything/smartlab/tests/test_core.py::test_label[DEGRADED-5-DEGRADED] PASSED [ 26%]
cli_anything/smartlab/tests/test_core.py::test_label[weird-5-UNKNOWN] PASSED [ 27%]
cli_anything/smartlab/tests/test_core.py::test_unknown_is_never_online PASSED [ 28%]
cli_anything/smartlab/tests/test_core.py::test_filters_and_summary PASSED [ 28%]
cli_anything/smartlab/tests/test_core.py::test_workflows_parse_triggers_and_redact PASSED [ 29%]
cli_anything/smartlab/tests/test_core.py::test_workflow_not_found PASSED [ 30%]
cli_anything/smartlab/tests/test_core.py::test_firmware_versions_ignore_build PASSED [ 31%]
cli_anything/smartlab/tests/test_core.py::test_firmware_compare_normalises_prefix PASSED [ 32%]
cli_anything/smartlab/tests/test_core.py::test_logs_tail_filters_and_redacts PASSED [ 33%]
cli_anything/smartlab/tests/test_core.py::test_report_read_guards_path PASSED [ 34%]
cli_anything/smartlab/tests/test_core.py::test_git_compare_rejects_bad_ref PASSED [ 35%]
cli_anything/smartlab/tests/test_core.py::test_need_repo PASSED          [ 36%]
cli_anything/smartlab/tests/test_core.py::test_token_expiry_and_api_binding PASSED [ 37%]
cli_anything/smartlab/tests/test_core.py::test_portal_requires_token PASSED [ 38%]
cli_anything/smartlab/tests/test_core.py::test_unreachable_is_unavailable PASSED [ 39%]
cli_anything/smartlab/tests/test_core.py::test_portal_allow_list[/devices/1] PASSED [ 40%]
cli_anything/smartlab/tests/test_core.py::test_portal_allow_list[/access/commands/next] PASSED [ 41%]
cli_anything/smartlab/tests/test_core.py::test_portal_allow_list[/emergency/activate] PASSED [ 42%]
cli_anything/smartlab/tests/test_core.py::test_portal_allow_list[/users] PASSED [ 42%]
cli_anything/smartlab/tests/test_core.py::test_probe_only_configured_urls PASSED [ 43%]
cli_anything/smartlab/tests/test_core.py::test_envelope_schema_and_redaction PASSED [ 44%]
cli_anything/smartlab/tests/test_core.py::test_human_rendering PASSED    [ 45%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED [ 46%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_version PASSED [ 47%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_health_json PASSED [ 48%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_devices_need_sign_in PASSED [ 49%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_devices_list_labels PASSED [ 50%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_devices_offline_and_esp32 PASSED [ 51%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_inspect_known_and_unknown PASSED [ 52%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_bad_token_is_auth_error PASSED [ 53%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_timeout_is_unavailable PASSED [ 54%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_api_down PASSED [ 55%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_unknown_command PASSED [ 56%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_token_never_printed PASSED [ 57%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_repl_with_piped_input PASSED [ 57%]
cli_anything/smartlab/tests/test_full_e2e.py::TestCLISubprocess::test_only_gets_reached_the_portal PASSED [ 58%]
cli_anything/smartlab/tests/test_full_e2e.py::TestLiveReadOnly::test_services_real PASSED [ 59%]
cli_anything/smartlab/tests/test_full_e2e.py::TestLiveReadOnly::test_ai_models_real PASSED [ 60%]
cli_anything/smartlab/tests/test_full_e2e.py::TestLiveReadOnly::test_knowledge_search_finds_relock_guard_without_model PASSED [ 61%]
cli_anything/smartlab/tests/test_full_e2e.py::TestLiveReadOnly::test_firmware_inventory_real PASSED [ 62%]
cli_anything/smartlab/tests/test_full_e2e.py::TestLiveReadOnly::test_automation_definitions_real PASSED [ 63%]
cli_anything/smartlab/tests/test_full_e2e.py::TestLiveReadOnly::test_github_status_real PASSED [ 64%]
cli_anything/smartlab/tests/test_full_e2e.py::TestLiveReadOnly::test_doctor_real_no_fail_on_core_services PASSED [ 65%]
cli_anything/smartlab/tests/test_full_e2e.py::TestLiveReadOnly::test_cameras_status_real PASSED [ 66%]
cli_anything/smartlab/tests/test_safety.py::test_no_dangerous_command_exists PASSED [ 67%]
cli_anything/smartlab/tests/test_safety.py::test_every_group_has_only_read_verbs PASSED [ 68%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/access/commands/next] PASSED [ 69%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/equipment/pc/poll] PASSED [ 70%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/equipment/pc/wait] PASSED [ 71%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/robots/stop-relay/poll] PASSED [ 71%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/equipment/master/nonce] PASSED [ 72%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/equipment/share-requests/nonce] PASSED [ 73%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/equipment/pc/watch-token] PASSED [ 74%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/emergency/active] PASSED [ 75%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/bookings/1/qr] PASSED [ 76%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/auth/me/door-qr] PASSED [ 77%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/security/cameras/1/frame.jpg] PASSED [ 78%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/users/1/door-photo] PASSED [ 79%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/ai/insights] PASSED [ 80%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/ai/report] PASSED [ 81%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/system/config] PASSED [ 82%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/opcua/snapshot] PASSED [ 83%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/access-events/export] PASSED [ 84%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/robots/UR5E_01/control] PASSED [ 85%]
cli_anything/smartlab/tests/test_safety.py::test_side_effect_paths_refused_before_network[/devices/../users] PASSED [ 85%]
cli_anything/smartlab/tests/test_safety.py::test_only_post_is_login PASSED [ 86%]
cli_anything/smartlab/tests/test_safety.py::test_ollama_mutations_refused[/api/pull] PASSED [ 87%]
cli_anything/smartlab/tests/test_safety.py::test_ollama_mutations_refused[/api/delete] PASSED [ 88%]
cli_anything/smartlab/tests/test_safety.py::test_ollama_mutations_refused[/api/generate] PASSED [ 89%]
cli_anything/smartlab/tests/test_safety.py::test_ollama_mutations_refused[/api/chat] PASSED [ 90%]
cli_anything/smartlab/tests/test_safety.py::test_ollama_mutations_refused[/api/create] PASSED [ 91%]
cli_anything/smartlab/tests/test_safety.py::test_ollama_mutations_refused[/api/copy] PASSED [ 92%]
cli_anything/smartlab/tests/test_safety.py::test_knowledge_only_status_paths[/ask] PASSED [ 93%]
cli_anything/smartlab/tests/test_safety.py::test_knowledge_only_status_paths[/jobs/sync] PASSED [ 94%]
cli_anything/smartlab/tests/test_safety.py::test_knowledge_only_status_paths[/reindex] PASSED [ 95%]
cli_anything/smartlab/tests/test_safety.py::test_knowledge_search_is_lookup_only PASSED [ 96%]
cli_anything/smartlab/tests/test_safety.py::test_cameras_only_health_and_metrics PASSED [ 97%]
cli_anything/smartlab/tests/test_safety.py::test_no_shell_or_eval_anywhere PASSED [ 98%]
cli_anything/smartlab/tests/test_safety.py::test_unauthenticated_device_command_sends_nothing PASSED [ 99%]
cli_anything/smartlab/tests/test_safety.py::test_secrets_never_in_output PASSED [100%]
============================ 107 passed in 23.20s =============================
```
