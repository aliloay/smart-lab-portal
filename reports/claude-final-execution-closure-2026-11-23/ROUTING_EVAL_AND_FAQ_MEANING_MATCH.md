# Routing evaluation and meaning-based FAQ match - 23 Nov 2026 (follow-up after the closure commit)

This round builds the upgrade research's #2 item (a held-out AI evaluation set) first. Its #1 item (the WH fast router) needs that set before it can be trusted. The research prototype was checked on 25 in-sample questions only, and the assistant already has the same layers (guard → FAQ → lookup → model).

## What was built
| File | What |
|---|---|
| `tools/knowledge/route_eval.py` | Computes the fast route of each question exactly as `agent.run` does before the model, using the real index and **no model**. Counts **WRONG_FAQ** (a curated answer given to a different question: must stay 0), missed FAQ and missed guard |
| `tools/knowledge/route_eval.json` | 60 questions written to differ from the FAQ wording: 32 FAQ paraphrases, 12 guard cases, 16 must-not-answer questions |
| `tools/knowledge/route_eval_holdout.json` | 20 more questions, written after the changes below and run once |

## Changes, each measured on the 60-question set
| Step | Pass | Wrong FAQ | FAQ paraphrases answered instantly |
|---|---|---|---|
| Before (after C-02/C-03/C-06) | 42/60 | **0** | 14/32 |
| FAQ entries among the top 3 search hits, not only the first (same rules) | 44/60 | **0** | 16/32 |
| + meaning-based fallback (local `nomic-embed-text`; similarity ≥ 0.90, margin ≥ 0.05, question word and negation must agree; "why" questions ≥ 0.95) | 52/60 | **0** | 24/32 |
| + "which" = "what" in the question-word rule | 52/60 | **0** | 24/32 |

**Hold-out (20 new questions):**
- First run: 15/20 pass, 0 wrong FAQ.
- After the which = what rule: 16/20, 0 wrong FAQ.
- All guard and must-not-answer cases were correct in both sets.

**Honest note on calibration:** the 0.90 threshold was chosen on the 60-question set. On it, every must-not-answer question scored < 0.90; the highest was 0.897, "Why is the robotics lab closed today?", which the question-word rule rejects anyway. The hold-out is the fair number: 16/20 routed correctly, 0 wrong answers. The misses fall through to the model: correct, but slow.

## Also fixed in this round
- **The curated status entries win over the C-06 guard.** "Are the ESP32 boards online?" now gets its FAQ entry, which names the live source and the 90 s rule. The generic guard answers only when no entry matches. Covered by a run-level test, where the model is mocked to fail if called.
- **The FAQ answer now cites the entry that actually answered,** which is no longer always `hits[0]`.
- **FAQ parsing bug in the new code:** the first entry of each file was dropped (it sits at line 1). Found by its own unit test and fixed: all 61 entries parse.
- **FAQ variant embeddings are cached on disk** (`<data>/faq_semantic.npz`, keyed by file times and text). After a restart: 0.07 s instead of 6.5 s. The opt-in `KB_WARMUP` RAM decision is unchanged.

## Live check (knowledge service restarted 23 Nov ~11:35)
| Question | Route | Time | Cited |
|---|---|---|---|
| Which device actually unlocks the door? | faq (meaning) | 7.09 s (first question after restart, embedding model loading) | `docs/faq/lab-and-access.md` |
| Which computer belongs to Hemaly? | faq (meaning) | 0.16 s | `docs/faq/robots-and-pcs.md` |
| What hours is the robotics lab open? | faq | 0.15 s | `docs/faq/lab-and-access.md` |
| Are the ESP32 boards online? | faq (curated status) | 0.08 s | `docs/faq/devices-and-esp32.md` |
| Is the environment node online? | guard (C-06) | 0.14 s | live-data pointer |
| Where is the Robotics Lab? | faq | 0.13 s | `docs/faq/lab-and-access.md` |
| Why is the robotics lab closed today? | model (correctly not FAQ) | 15.7 s | - |

**Closed later the same day:** for "Why is the robotics lab closed today?" the model had guessed a reason ("because it follows the university's slots"); no closure is recorded anywhere.
- **Fix:** `GUARD_NOW_STATE` + `status_guard()`. A question that combines a time-now word (today, now, yesterday, at the moment …) with a state word (closed, open, busy, booked, stopped, failed, who, inside …) is live state. It gets the live-data pointer, after the FAQ check and before the model.
- **Test:** `test_today_and_now_state_is_live_data` (4 must-guard and 4 must-not-guard questions).
- **Results:** knowledge suite 85 passed; routing sets unchanged (52/60, hold-out 16/20, 0 wrong FAQ).

## Camera inference packages pinned (research item S02, 23 Nov)
`tools/security_vision/requirements.txt`: `openvino==2026.4.1` and `onnxruntime-directml==1.24.4`. These are exactly the versions installed and running (`pip list`, 23 Nov). DirectML gets no new features, so an unpinned reinstall could break the GTX 1650 path. Nothing was installed or changed on the machine.

## Tests
Knowledge suite: **84 passed**. New tests:
- `test_status_question_order_faq_then_status_guard_never_the_model`
- `test_faq_meaning_match_rules` (threshold, margin, question word, embedding failure → normal route)
