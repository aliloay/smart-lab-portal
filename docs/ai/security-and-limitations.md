# AI security and limitations

- **Local by default and by design.** `AI_LOCAL_ONLY=true` (the default) sends every model call to Ollama on 127.0.0.1 and ignores any cloud key; no prompt or lab data leaves the PC. A cloud model is possible only as an explicit opt-in (`AI_LOCAL_ONLY=false` plus a key), which would then need internet.
- **Role-aware.** Students get only their own data and how-to answers; lab-wide tools are staff and admin only.
- **No physical actions.** Assistants cannot open doors, switch relays or move robots. The only change they can prepare is a booking, which the user confirms.
- **Redaction.** The system guide contains no secrets, addresses or keys; the knowledge agent redacts configured literals before text reaches the model.
- **Small models make mistakes.** Answers from open questions can be wrong; instant answers and cited sources are the reliable paths. Feedback is collected at `/api/ai/feedback` for review.
- **Offline limits.** Ollama and the voice service must be running on the engineer PC; if they are down, instant answers still work and the chat reports the model as unavailable.
