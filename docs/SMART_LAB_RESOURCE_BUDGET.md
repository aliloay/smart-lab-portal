# Smart Lab - resource budget (Dell G3 3590, measured 2026-11-03)

Hardware (measured): Intel i7-9750H 6C/12T, 16 GB RAM (16,213 MB visible), NVIDIA GTX 1650 4 GB (driver 616.92)
+ Intel UHD 630. C: ~44 GB free, D: ~825 GB free (pagefile on D:).

## Measured tonight (all 12 services + Docker running, tests running in parallel)
| Item | Measured | Note |
|---|---:|---|
| Docker/WSL VM (vmmemWSL) | 5,034 MB | Postgres itself: 53 MB anonymous + page cache; backend 272 MB; web 12 MB |
| Security camera 1 / 2 | ~1,230 MB each | python + ONNX DirectML models |
| Ollama qwen2.5:1.5b (CPU while cameras run) | 1,188 MB | now unloads after 30 idle minutes (was 24 h) |
| Ollama nomic-embed-text | ~390 MB | unloads after 30 min (was 2 h) |
| VS Code | ~1,400-1,800 MB | |
| Claude Code | ~700 MB | |
| Chrome (few tabs) | ~450-1,100 MB | |
| Other services (face, knowledge, voice, opcua, monitors, agents) | ~1,500 MB | |
| Free RAM | 250-1,900 MB | lowest during test runs + backend build |

## Changes made tonight
- Ollama keep-alive 24 h / 2 h -> 30 min; one context size (4096) so the model is loaded once, never reloaded.
- `%USERPROFILE%\.wslconfig`: Docker VM capped at 6 GB, freed page cache returned to Windows (autoMemoryReclaim).
  Active after the next reboot or `wsl --shutdown`.
- Status window shows free RAM and warns under 1.5 GB.

## Expected budget on lab day (no tests, no builds, VS Code closed or one window)
| Item | MB |
|---|---:|
| Windows + drivers | ~2,800 |
| Docker VM (capped, reclaiming) | 2,500-4,000 |
| 2 cameras | ~2,450 |
| Ollama while answering / idle | ~1,600 / 0 |
| Other services | ~1,500 |
| Browser (portal, 3 tabs) | ~600 |
| **Total** | **~11,500-13,000 -> 3-4.5 GB free** |

## Rules for a smooth run on 16 GB
1. Do not build Docker images or run test suites during the demo.
2. One VS Code window at most; one browser window.
3. If Status shows LOW MEMORY: close the browser tabs first, then VS Code.
4. More RAM: 32 GB removes the problem entirely (check whether this G3's RAM slots allow it before buying).

## Not done (needs a measurement or owner decision)
- Assistant on the GPU while cameras are live (Gemini's num_batch idea): against the camera-first rule; needs the
  real two-camera A/B at the lab.
- Hard memory limits per container: current usage is far below; limits would only add OOM risk.
