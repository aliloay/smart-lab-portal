---
type: "source-mirror"
source_kind: "documentation"
source_path: "docs/knowledge-platform/CLAUDE_CODE_TOOLKIT_AUDIT.md"
source_hash: "16241a5261f90fefd3f4c72c971dc78265f7cdf19255c0571e469696dc742727"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `docs/knowledge-platform/CLAUDE_CODE_TOOLKIT_AUDIT.md` - edit the original in the repository, not this note.

Systems: none

## Related
- [[docs_PROGRESS_CHECKPOINT.md]] - mentioned by docs

# Claude Code toolkit audit - 2026-10-14 (assessment only, nothing installed)

Labels: **[V]** verified here (measured or read locally) · **[R]** read in the project's own README (vendor-reported,
not run) · **[I]** inferred · **[U]** unknown.

## 1. Current setup [V]
* Global `~/.claude/settings.json`: model `opus`; effort low for Opus 5.5, medium for Sonnet 5; remote control and
  push notifications on; **no permission rules**; no global or project `CLAUDE.md`.
* Plugins: one organisation-synced bundle - 63 skills, **1 hook** (superpowers SessionStart, injects the
  "using-superpowers" text into every session). 13 plugin MCP servers listed but all need authentication, so they
  are not active. No user MCP servers.
* Memory: auto-memory `MEMORY.md` index (loaded each session) + 13 notes, 40 KB in total.
* Project knowledge: the local vault + `tools/knowledge` (BM25 + embeddings, agent, **graph.py new tonight**).
* Runtimes: Node 24.21, Python 3.14.7 (+3.12 for ur_rtde), Ollama with qwen2.5 1.5b/3b + nomic-embed-text; no Bun.

## 2. Measured baseline [V] (from local transcripts `~/.claude/projects/<repo>/*.jsonl`, read-only)
| Session | Requests | Output tokens | Cache-read tokens | Cache-write | Repeated Read calls |
|---|---|---|---|---|---|
| f3ebc4c1 | 1,977 | 2.77 M | 0.89 B | 11.2 M | 15 of 126 |
| 3b9b3107 (this one) | 8,338 | 9.87 M | **4.22 B** | 52.9 M | 48 of 173 |

Average context re-read per request in this session: **~506 k tokens**. Tool calls: Bash 2,857, Write 247, Read 173.
**Conclusion:** cost is dominated by very long sessions re-reading their own history, not by tool output or code size.

## 3. Candidates
| Tool | Identity / licence | What it does | Data flow / privacy | Fit for Smart Lab |
|---|---|---|---|---|
| CodeBurn | getagentseal/codeburn, MIT [R] | reads local session files, cost by task/model, optimize scanner, opt-in budget hooks | "The CLI sends nothing" [R]; desktop/tray anonymous report opt-in (default off in EU/unknown region) [R]; fetches LiteLLM prices [R] | **useful, low risk** as read-only CLI (`npx codeburn`, Node ≥22.13 - we have 24). Never run `optimize --apply` without review |
| Headroom | headroomlabs-ai/headroom, Apache-2.0 [R] | local compression of tool output/logs/JSON/code, reversible originals (CCR), proxy / MCP / library | anonymous beacon **on by default** (opt-out `HEADROOM_BEACON=off`) [R]; downloads a HuggingFace model for text [R]; `wrap claude` also installs Serena MCP [R] | **low value here**: tool output is a small share (§2); a proxy in front of Anthropic adds a failure point; compressing logs/stack traces risks losing the one line that matters |
| Ponytail | DietrichGebert/ponytail, MIT [R] | one prompt (SKILL.md) + hooks: "minimum that works", tests for risky logic; modes lite/full/ultra | network behaviour not stated [U]; injected size not stated [U] | **maybe, lite only**, after reading SKILL.md and hooks. Its own exemptions (validation, security, data loss, a11y) match our needs; benchmarks are vendor-reported |
| Claude-Mem | thedotmack/claude-mem, Apache-2.0 [R] | 6 lifecycle hooks capture every tool use, AI-generated summaries, SQLite + Chroma, injects context at start | summaries made by its observer service, OpenRouter/Gemini key or your Anthropic plan; optional cloud sync to cmem.ai [R]; auto-installs Bun and uv [R] | **not recommended**: duplicates MEMORY.md + the vault, records everything (camera/door context, keys in tool output) unless tagged `<private>`, adds tokens per session; claims are not separated into implemented vs proposed |
| Graphify | Graphify-Labs/graphify | see GRAPHIFY_ASSESSMENT.md | docs need an LLM pass | **replaced** by native `graph.py` (built, tested, 2026-10-14) |
| OmniRoute | **diegosouzapw/OmniRoute** (official; other results are forks/mirrors), MIT [R] | local gateway on :20128, routes to 300+ providers, fallback chains, RTK/Caveman/LLMLingua compression, quota-share pools | it **sees every prompt and response** and holds provider keys [R]; log retention not stated [U]; mentions "TLS fingerprint stealth" and shared quotas [R] | **reject**: would send private Smart Lab code to whichever provider it picks; model quality and tool-use compatibility vary; account-sharing features may break provider terms |
| "Claude Code setup" from the video | **unidentified** - the reference video could not be inspected | - | - | audited the real setup instead (§1, §5) |

Overlaps: Headroom and OmniRoute both compress and both sit in the request path - never combine them;
Claude-Mem overlaps MEMORY.md, the vault and the knowledge agent; Graphify overlaps graph.py.

## 4. Recommendation (smallest useful set)
1. **Built-ins first (no install, biggest measured lever):** one session per mission; start from
   `docs/PROGRESS_CHECKPOINT.md` + MEMORY.md instead of carrying 500 k tokens; `/compact` at milestones; put long
   specifications in a file and reference it instead of pasting them into the chat.
2. **CodeBurn CLI, read-only** - to measure (1). Approval needed: run `npx codeburn` (downloads the npm package).
3. A short project `CLAUDE.md` (~40 lines: safety rules, test commands, where things are) so they are not re-pasted
   each mission. Approval needed (it changes what every session loads).
4. Optional later: Ponytail **lite**, after its SKILL.md and hooks are read and a 3-task A/B on our code.
Not recommended: Headroom, OmniRoute, Claude-Mem, Graphify.

## 5. Acceptance tests (when approved)
Benchmark tasks: (1) find the re-ID batch bug + tests, (2) trace an env-node reading to the portal, (3) cite the
PLC decision, (4) small isolated fix with test, (5) diagnose a failing test, (6) implemented vs planned list.
Per task record from the transcript: input/output/cache tokens, requests, tool calls, repeated reads, wall time,
diff size, tests pass, citation correctness. Compare baseline vs each change, 2 runs each.
Rollback: CodeBurn = nothing installed globally with npx; CLAUDE.md = delete the file; Ponytail = `/plugin uninstall`.

