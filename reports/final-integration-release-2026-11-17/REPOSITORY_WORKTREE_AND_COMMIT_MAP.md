# Repository, worktree and commit map (verified 2026-11-18)

GitHub: github.com/aliloay/smart-lab-portal. **Nothing was pushed or merged remotely.**

## Checkouts (verified with `git worktree list`)
| Path | Branch | HEAD | Role | Touched by this integration |
|---|---|---|---|---|
| C:\Projects\smart-lab-portal | fix/pre-lab-hardening | 4e58b52 | owner's main checkout (untracked owner files kept) | no edits, no branch switch |
| C:\Projects\smart-lab-portal-opt | opt/claude-app-performance-2026-11-17 | 5314195 | previous Claude worktree | read only |
| C:\Projects\smart-lab-argon | opt/argon-systems-vision-2026-11-17 | fe126b7 | previous Argon worktree | read only |
| C:\Projects\smart-lab-release | release/smart-lab-final-optimization-2026-11-17 | see below | **integration / release candidate** | yes |
| OneDrive\...\smart-lab-review | review/gemini | d84c21d | Gemini review worktree | not touched |

Safety branch: `backup/before-final-integration-2026-11-18` = 4e58b52.

## Real commit graph (reported vs verified)
- Claude: reported base 4e58b52. Verified: d085b73 and 5314195 sit directly on 4e58b52.
- Argon: reported base c68adb0. Verified: fe126b7 sits on c68adb0, one commit before 4e58b52.
- 4e58b52 (AR detector v8: detectors.json + lab_detector.onnx) is the only owner commit between the two bases.
- File overlap: Claude vs Argon **0 files**; 4e58b52 vs Argon **0 files**. Both merges were conflict-free.

## Original -> integrated (no cherry-picks, original SHAs preserved)
| Original | Integrated by | Meaning |
|---|---|---|
| d085b73, 5314195 | merge e70db0e | Claude app branch |
| fe126b7 | merge c49fa07 | Argon systems branch |
| - | 35f8cb4 | integration review: pose PREDICTED, labmap delete-pending lock, face-server test fixture |
| - | bdc41aa | build stamp from build args, real build in deploy.py, build_images.ps1, /version.json |
| - | b685a43 | incidents: SQL filters, summary rows, keyset cursor; portal "Load older"; camera contract test |
| - | df3407f | status/handoff (the build deployed on 18 Nov) |
| - | final report commit | these reports |

Code rollback: `git checkout backup/before-final-integration-2026-11-18`. Running-portal rollback: see
CHANGED_FILES_COMMITS_AND_ROLLBACK.md.
