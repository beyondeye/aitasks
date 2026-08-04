---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [framework, execution_profiles]
gates: [risk_evaluated]
anchor: 1311
created_at: 2026-07-29 17:03
updated_at: 2026-07-29 17:03
boardidx: 91136
---

## Origin

Risk-mitigation ("after") follow-up for t1311, created at Step 8d after
implementation landed.

## Risk addressed

Code-health risk from t1311's risk evaluation:

> **No drift guard exists** between `PROFILE_SCHEMA` and
> `task-workflow/profiles.md` / the website key tables — six keys are already
> documented in only one place, so a new key can silently land half-registered ·
> severity: medium

## Goal

Add a drift test that derives **both sides from live source** (modelled on
`tests/test_gates_reference_drift.sh`) and asserts:

- every `PROFILE_SCHEMA` key in `.aitask-scripts/lib/profile_editor.py` is
  documented in `.claude/skills/task-workflow/profiles.md` **and** in the website
  key tables, and
- every key documented in those tables exists in `PROFILE_SCHEMA`.

Derive the key lists — never restate them (see the "derive, don't duplicate"
convention). The website side currently spans at least
`website/content/docs/skills/aitask-pick/execution-profiles.md` and
`website/content/docs/tuis/settings/reference.md`; enumerate the real set as part
of the task rather than trusting this list.

**Expect the first run to fail with a backlog.** t1311 confirmed the gap is
already real: `qa_tier` is registered in `PROFILE_SCHEMA` and documented in
`profiles.md` and `execution-profiles.md`, but was **missing from
`settings/reference.md`'s QA table** (t1311 fixed only the `_index.md` group
bullet it had to touch, deliberately leaving the reference-table gap for this
task). Decide explicitly whether to fix the whole backlog in this task or to
seed an allowlist that shrinks — do not silently weaken the guard to make it
pass.

Also cover the group-membership axis: a key in `PROFILE_SCHEMA` but in no
`PROFILE_FIELD_GROUPS` entry never renders in the settings TUI. t1311's
`tests/test_profile_editor_shadow_tier.py::test_every_grouped_key_is_in_the_schema`
checks the group→schema direction only; the schema→group direction is unguarded.

## Verification

- The new test fails when a key is added to `PROFILE_SCHEMA` without touching the
  docs, and when a documented key is removed from the schema — prove both
  directions with a negative control, not just a green run.
