---
type: approvals
updated: "2026-10-14 07:20"
---
# Pending approvals

| # | Decision | Why it is blocked | What happens after approval |
|---|---|---|---|
| 1 | ~~Rotate the 4 demo-account passwords~~ **Owner decision 2026-10-14: keep simple for now** (risk stays open) | live credentials, public in README since `7ae0b83` | owner sets new passwords in Users & roles; seed reads them from env; docs drop the literals — plan in `docs/knowledge-platform/NEXT_PHASE_2026-10-13.md` §2 |
| 2 | ~~Use or remove `nomic-embed-text`~~ **Approved 2026-10-14: used for hybrid search** | downloaded **before** approval (gate violation, reported) | use: hybrid search + benchmark; remove: `ollama rm nomic-embed-text` |
| 3 | ~~Approve conversation sources~~ **Approved ("fix all") - 9 sources searchable** | owner words vs assistant proposals must be reviewed | `py tools\knowledge\history.py approve <source>` per note in *History review* |
| 4 | ~~Automation deployment~~ **Approved 2026-10-14: n8n, 3 workflows active** - was: n8n (`kb.py serve` + 3 inactive drafts) or Windows Task Scheduler | new local service / scheduled task | build + test, import inactive, owner activates |
| 5 | ~~Re-sync live-edited workflows 01, 03, 05, 07~~ **Done 2026-10-14: repo = live (option b, owner delegated); owner versions recovered byte-exact first** | live ≠ repo; which one is right is the owner's call | export live → repo, or edit live |
| 6 | Restart the security camera window (GPU code) - **at the lab 2026-10-15** (re-ID start-up fix + credential masking load then) | live service | at the lab, per [[LAB_TEST_2026-10-14.md]] |
| 7 | Import ChatGPT (1) and (2) exports | not available on this laptop | put `conversations.json` in `C:\Users\dell\SmartLabKnowledge\inbox_raw`, run `history.py import` |
| 8 | ~~Graph layer~~ **Approved 2026-10-14: native graph.py built** (Graphify not installed) | - | `py tools/knowledge/graph.py related <path>` |
| 9 | Claude Code toolkit: CodeBurn read-only run (`npx codeburn`), Ponytail lite trial | downloads npm packages | see docs/knowledge-platform/CLAUDE_CODE_TOOLKIT_AUDIT.md; Headroom, OmniRoute, Claude-Mem not recommended |
