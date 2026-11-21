# System readiness scorecard

**Scoring:** an engineering judgement from this audit's evidence only.

- **Code:** quality and tests.
- **Live today:** what was observable on 21 Nov at home.
- **Demo-ready:** could the feature be shown reliably at the defense after the listed actions.

| Subsystem | Code / tests | Live today | Demo-ready | Blocking items | Evidence |
|---|---|---|---|---|---|
| Backend / API / auth | 9/10 (887 pass) | ✔ healthy, 14 ms health | **Yes after F-01** | F-01 token type | TESTED, LIVE |
| Frontend / portal | 8/10 (tsc ok) | ✔ 227 KB gzip first load | Yes | none; authenticated navigation timing not measured | LIVE, CODE |
| Door / access (master) | 8/10 | ✔ online, components ok | **Conditional** | 1N4007 diode; RFID freeze at relock (7/8) | LIVE, HISTORICAL |
| ESP32 nodes (env, bins, CAM) | 8/10 | ✔ 5/5 reachable, 0 % loss | Yes | bin tare / "empty" check (F-10); CAM `/status` leak (F-08) | LIVE |
| Network | 5/10 | works by metric | Conditional | overlapping subnets (F-02); .100 conflict (F-03) | LIVE |
| Security cameras | 8/10 (396 pass) | ✘ no stream (at GIU) | **Only at GIU** | live benchmark; pose wording | TESTED, LIVE |
| Two-camera identity | 7/10 | ✘ | Only at GIU | recovery not measured | CODE, SIMULATED |
| AR Scan | 7/10 | not tested (no phone) | Yes, with markers | box cadence 3–6 s; PC identity | CODE, HISTORICAL |
| Robots / twins | 8/10 (44 pass) | ✘ offline since 18 Nov | Only at GIU | IP conflict; operator present | LIVE, HISTORICAL |
| Robot control safety | 10/10 | ✔ off / UNAVAILABLE | Yes | none | LIVE, CODE |
| PC fleet / relay | 8/10 (40 + 6 pass) | ✘ (at GIU) | Only at GIU | PC-10 0.9; PC-11 sticker; Hemaly IP | DB HISTORICAL |
| AI assistant (portal) | 8/10 | not measured (no credentials) | Yes | GPU reload (F-05) | TESTED (backend) |
| Knowledge assistant | 7/10 (64 pass) | ✔ answering, 11.7–18.4 s on CPU | Conditional | F-05, F-06, F-07 | TESTED (measured) |
| Obsidian vault | 6/10 | ✔ index fresh (18:01) | Yes | 322 recursive mirrors; 182 broken links | VERIFIED |
| n8n automations | 7/10 | ✔ running, 0 failures in 7 days | Yes | no error workflow, timeouts or webhook retries; missed daily runs | LIVE, CODE |
| Backups | 6/10 | ✔ last 15:58 UTC | Yes | retention, encryption, restore test | LIVE |
| Source control | 8/10 | 5 commits unpushed | Yes after push | – | LIVE |
| Documentation accuracy | 6/10 | – | – | CLAUDE.md model/GPU line; v7 vs v8; "14 PCs" | LIVE |

## Overall

- **Software:** release quality. **Live hardware evidence:** incomplete until GIU.
- **The four highest-value actions:**
  1. Fix F-01.
  2. Fit the door diode.
  3. Fix the AI GPU reload.
  4. Run the GIU camera, robot and PC session with the network fixes applied.
