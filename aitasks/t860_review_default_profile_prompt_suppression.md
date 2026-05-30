---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [manual_verification, task_workflow, ait_settings]
created_at: 2026-05-30 22:34
updated_at: 2026-05-30 22:34
---

## Origin

Spawned from t859 during Step 8b review.

## Upstream observation

`aitasks/metadata/profiles/default.yaml` — the `default` profile's
`description` reads "Standard interactive workflow - all questions asked
normally", yet it sets two keys that *suppress* up-front prompts:

- `manual_verification_followup_mode: never` — skips the Step 8c
  manual-verification follow-up offer entirely.
- `manual_verification_mode: autonomous` — skips the Manual Verification
  Step 1.5 up-front prompt and auto-runs the checklist.

These contradict the profile's own "all questions asked normally" framing.

## Diagnostic context

Surfaced while renaming `manual_verification_auto_mode` →
`manual_verification_mode` (t859). The two keys were added to `default.yaml`
by the t843 / t849 work. Their presence also silently invalidated the
`-default` goldens (`manual-verification-followup-default.md`) and the
`default` parity fixture in
`tests/test_skill_parity_runtime_vs_rendered.sh` — both were stale until
regenerated in t859. The root issue is that `default` no longer matches its
description.

## Suggested fix

Decide the intended `default` behavior and make config + description
consistent:
- If `default` should truly ask everything: remove both keys from
  `default.yaml` (they fall back to `ask`), then regenerate the affected
  goldens/fixtures.
- If the auto behavior is intentional: update the `default` profile
  `description` to say so, and review whether the parity test's `default`
  rows (designed to exercise the key-absent fallback) should point at a
  genuinely key-absent profile instead.
