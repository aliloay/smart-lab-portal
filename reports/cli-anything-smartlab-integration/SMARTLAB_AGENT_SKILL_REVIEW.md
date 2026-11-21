# SKILL.md review: cli-anything-smartlab

## Where it lives
| Copy | Path | Purpose |
|---|---|---|
| Canonical | `tools/smartlab_cli/skills/cli-anything-smartlab/SKILL.md` | upstream convention (`skills/cli-anything-<software>/SKILL.md`) |
| Packaged | `cli_anything/smartlab/skills/SKILL.md` (shipped via `package_data`) | installed harnesses carry their skill |
| Active for Claude Code | `C:\Projects\smart-lab-portal\.claude\skills\cli-anything-smartlab\SKILL.md` | `.claude/` is git-ignored, so this local copy makes it live; the session's skill list picked it up at once |

## Checklist (HARNESS.md phase 6.5)
| Requirement | Status |
|---|---|
| Valid YAML front matter (`name`, `description`) | yes. The description names the trigger questions ("is X online / what model / which workflow / what version / where implemented / what is not pushed") |
| Self-contained (no need to read source) | yes: install, config, sign-in, envelope, labels, exit codes, every group, recipes |
| `--json` guidance | yes, "Always use `--json`", with the envelope schema |
| Error handling for agents | yes, an exit-code table with what to do (3 → ask the owner to sign in; 4 → report, do not loop) |
| Every command group with a description | yes: 16 groups + top-level commands |
| Realistic examples | yes: 10 question → command recipes taken from real owner questions (bin online, environment ESP32, cameras, model, relock guard, daily report workflow, firmware drift, GitHub, RFID offline) |
| Safety boundaries | yes, a "Hard limits" section first: what it cannot do, and "never get around it (curl, docker exec, SQL, n8n API)" |
| Freshness and source rules | yes: quote `source`; never present a repo copy or file as live; UNKNOWN and STALE are not online |
| Preview surface | not applicable (smartlab produces no previews) |

## Deliberate limits
- The skill does **not** grant command execution beyond `smartlab`. It tells agents to stop and ask the owner for any
  action.
- It tells agents never to ask for the portal password in chat; the owner runs `smartlab auth login`.
- About 1.6 k tokens, loaded only when the skill triggers.
