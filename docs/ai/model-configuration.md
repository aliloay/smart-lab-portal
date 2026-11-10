# Model configuration

Settings in `backend/app/core/config.py`, set through `.env`:

| Variable | Default | Meaning |
|---|---|---|
| `AI_LOCAL_ONLY` | `true` | **100 % local** (owner requirement, 26 Oct 2026): a cloud key is ignored and there is no silent cloud fallback |
| `AI_PROVIDER` | `auto` | With `AI_LOCAL_ONLY=true` always Ollama. Only if `AI_LOCAL_ONLY=false` **and** `ANTHROPIC_API_KEY` is set does `auto` use the Claude API |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Staff assistant (must support tool calling; fits a 4 GB GPU) |
| `OLLAMA_STUDENT_MODEL` | `qwen2.5:1.5b` | Student assistant |
| `OLLAMA_CPU_ONLY` | `false` | Force CPU inference, for example when the cameras need the GPU |
| `AI_STUDENT_ENABLED` | `true` | Student assistant on/off |
| `ANTHROPIC_API_KEY` | empty | Optional and ignored while `AI_LOCAL_ONLY=true`; using it requires internet |
| `AI_MODEL`, `AI_STUDENT_MODEL` | Claude model names | Used only with the Claude API |

Local inference: Ollama on the engineer PC (127.0.0.1:11434). Since 19 Oct 2026 both assistants run `qwen2.5:1.5b`-class models on the GTX 1650 by the owner's decision (answers about 3 s instead of 68 s on CPU, cameras unaffected); revert with `OLLAMA_CPU_ONLY=true` if a camera suffers. Knowledge agent model: `tools/knowledge/config.json` (`qwen2.5:3b`, CPU by default).
