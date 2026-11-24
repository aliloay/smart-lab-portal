# Troubleshooting assistant
**Built:** rule-based diagnosis (`/api/metrics/diagnose/{id}`) and exact answers before the language model. It compares the moment a device
went silent with the other nodes, its self-reported components, Wi-Fi signal if stored and repeated offline alerts. Every cause has evidence
and confidence; it states what is not recorded; it never acts.

**Questions:** `backend/tests/test_metric_questions.py` holds 153 different concrete questions (about 22 new grammar patterns plus 11 earlier
ones) answered from records: sensor, unit, range, rate, calibration, average/highest/lowest, readings and gaps, last reading, last seen, why
offline, what to check, evidence, event counts, what can and cannot be measured.

**Wrong-answer protection:** a pattern must match the whole question. 13 + 33 near-misses (another place, yesterday, a second request,
"ignore the rules", unknown device, people, SQL text, negation) must return nothing and go to the normal assistant. "Not installed" stops being
said as soon as such a sensor reports. Only staff get these answers.

**Limits:** English only; names outside the list are not understood; no measured accuracy study with real users.
**Proposal, not built:** let the local model only *rewrite* the rule result, with the rule text shown under it. No new model download.
