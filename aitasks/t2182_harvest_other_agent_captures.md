---
priority: low
effort: low
depends: []
issue_type: test
status: Ready
labels: [sitrep]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 2175
followup_kind: risk_mitigation
created_at: 2026-11-03 10:40
updated_at: 2026-11-03 11:51
---

## Origin

Risk-mitigation ("after") follow-up for t2175_2, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — heuristics tuned on Claude Code rendering:
"The passage-start detection and the marker search are tuned on Claude Code's
tool-call layout. On codex/opencode captures the passage range may be wrong, or
the marker invisible; the result is a linked duplicate triage item, never
suppressed advice · severity: medium"

## Goal

Once codex and opencode agents have finished picks that end in the
workflow-end banner (and have been frozen, so `capture.txt` exists), add
fixtures modelled on their real layout to `tests/fixtures/sitrep_harvest/`
(synthetic, as the README requires: real captures hold other projects'
content) and extend `tests/test_sitrep_harvest.py` / `tests/test_sitrep_harvest.sh`:

- the banner parses (indentation, glyphs, wrapping in that agent's renderer);
- the wrap-up passage starts at that agent's closing-message marker
  (`lib/sitrep_harvest.py` `MSG_RE` / `PROMPT_RE` are Claude-Code-only today);
- the `HARVEST_RUN:` first output line of the harvest call is visible in that
  agent's tool-call display, so piped-then-captured Stopped runs match instead
  of duplicating — or, if it is not, document the duplicate as expected.

Fix whatever heuristics those fixtures break. Identity must stay
normalization-free (explicit run id, archival commit, byte-exact passage).
