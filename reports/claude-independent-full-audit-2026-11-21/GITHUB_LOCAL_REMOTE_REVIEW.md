# GitHub, local and remote review

- **Inspected:** 2026-11-21 19:06:01 and 19:24:01 (UTC+2), read-only.
- **Commands:** `git status`, `git branch -vv`, `git log`, `git worktree list`, `git ls-remote origin`, `gh repo view`, `git rev-list`, `git ls-files`, `git count-objects -vH`.

## Revisions

| Item | Value |
|---|---|
| Local branch | `fix/pre-lab-hardening` |
| Local HEAD | `f32d7b33f27a94ed259068a8d7e00a325a41b299` ("Checkpoint: fix garbled paths") |
| GitHub default branch | `main` (`gh repo view`: defaultBranchRef=main, PUBLIC, pushedAt 2026-11-21T14:21:16Z) |
| `origin/main` | `35d2a10209cc` |
| `origin/fix/pre-lab-hardening` | `35d2a10209cc` |
| Local ahead / behind origin | **5 ahead / 0 behind**. `35d2a10` is an ancestor of HEAD, so it is a fast-forward with no conflict. |
| Changed during the audit? | No. Both `ls-remote` checks returned the same SHA. |

Note: the brief's "known HEAD 3758fa9" is now 8 commits behind local HEAD (3758fa9 → f397f21 … f32d7b3).

### Unpushed commits

```
f32d7b3 Checkpoint: fix garbled paths
ebd6758 Checkpoint 21 Nov evening + signed-in live CLI results ...
a0814c7 Assistant: live one-line answers ...     <- the deployed backend image
f5ba8ac smartlab: read-only agent-native Smart Lab CLI ...
5b458f4 Knowledge assistant on qwen3:1.7b ...
```

The deployed images were built from `a0814c7` (backend) and `8fcef6f` (frontend). `git diff --stat <commit> HEAD -- backend` and `-- frontend` are both empty, so the live portal equals HEAD.

## Working tree

- **Tracked modifications:** none.
- **Untracked (8 paths):**
  - `docs/HANDOFF_2026-11-11_evening.md`
  - `docs/reports/closure-2026-11-11-evening/`
  - `docs/reports/final-closure/`
  - `docs/reports/max-performance-security-closure/`
  - 3 showcase MP4s under `reports/final-smart-lab-closure-2026-11-18/`
  - `reports/gemini-final-giu-capacity-optimization-2026-11-18/` (not read, per the brief)
- Recommendation: keep the MP4s untracked or use Git LFS. The film v1 contained readable account names, as noted in the checkpoint.

## Branches and worktrees

- **Worktrees (7):**
  - `smart-lab-portal` (this one)
  - `smart-lab-argon` (detached `7619717`)
  - `smart-lab-claude-final`
  - `smart-lab-cli`
  - `smart-lab-portal-opt`
  - `smart-lab-release`
  - `OneDrive/.../smart-lab-review` (`review/gemini`)
- None was modified by this audit.
- Local `main` points at `fdfd1fe` and is "behind 129": it is stale, but harmless.
- There are about 8 `backup/*` branches, which is good practice.

## Sensitive files

- `git ls-files` contains only `*.example` files for secrets (`secrets.example.h` ×7, `camera.env.example`, `robot.env.example`).
- The real files are present locally and ignored, confirmed with `git check-ignore`:
  - `firmware/ESP32CAM_Vision_FAST/secrets.h`
  - `tools/knowledge/config.json`
  - `tools/pc_agent/agent.env`
  - `.env`
- **Not tracked:** `tools/pc_agent/SmartLab_PC_agent_UPDATE.zip` (ignored).
- **To check (owner):** `docs/screenshots/users-roles.png` may show account names or emails. I did not open the image.
- `backend/data/marker_art/face-server.jpg` is a marker image, not a person (by filename; not opened).

## Size and hygiene

- **Largest tracked files:**
  - `backend/data/models/lab_detector.onnx`: 37 MB
  - `all_detector.onnx` and `bin_detector.onnx`: 10 MB each
  - CAD STEP files duplicated across 4 output folders: about 11 MB each
- **Loose objects:** `count-objects`: 9,693 loose objects, **422 MB**; packs 17.8 MB; prune-packable 1,890. Running `git gc` (an owner action) would reclaim most of this.
- **Tracked files:** 2,323.
- **Build folders:** firmware `build/` folders are present on disk. None is tracked (`git ls-files firmware | grep /build/` = 0).

## Verdict

- **Pushed?** No (5 commits).
- **Conflicts?** None.
- **Secrets tracked?** None found.
- **Oversized files?** Moderate: models plus duplicated CAD files.
