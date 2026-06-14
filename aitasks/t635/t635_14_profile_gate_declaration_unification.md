---
priority: medium
effort: medium
depends: [t635_12, t635_13]
issue_type: refactor
status: Ready
labels: [gates, execution_profiles, task_workflow]
created_at: 2026-06-10 18:55
updated_at: 2026-06-14 17:36
---

## Context

Phase 4 of `aidocs/gates/integration-roadmap.md`. Pseudo-gates are toggled
today by profile keys via Jinja at render time (`risk_evaluation`,
`manual_verification_followup_mode`, ...); the gate framework toggles via
per-task `gates:` frontmatter + registry at runtime. Without unification,
every converted checkpoint ends up configured in two places.

## Principle to implement (locked in roadmap Phase 4)

Profiles stop being the RUNTIME toggle for converted checkpoints. Instead,
profiles (and the registry's `default_gates`) choose which gates get
DECLARED in `gates:` at planning time; the registry defines how gates run.
Never configure the same checkpoint in two places.

## Scope

- task-workflow planning writes `gates:` into new tasks from the active
  profile / `default_gates` (framework doc integration table row for
  planning.md).
- For checkpoints already converted (build/tests t635_12, risk t635_13):
  retire the duplicated Jinja profile-gating, keeping the user-visible
  opt-in semantics (a profile that disables risk evaluation simply does not
  declare the risk gate).
- Document the declaration model in
  `.claude/skills/task-workflow/profiles.md` and the profile schema.
- Unconverted pseudo-gates (manual-verification family, 8b/8d follow-ups)
  keep their Jinja gating untouched — they migrate only if/when converted.
- Read `aidocs/framework/agent_runtime_guards_audit.md` before moving any
  runtime guard into a Jinja gate or vice versa.

## Coordination (from t635_2)

t635_2 added the first gate-related execution-profile key, `record_gates`
(opt-in bool), and registered it in `.aitask-scripts/lib/profile_editor.py`
(`PROFILE_SCHEMA` + `PROFILE_FIELD_INFO`) under a new **"Gates"**
`PROFILE_FIELD_GROUPS` entry. When this task introduces `default_gates`,
register it the same way (schema + field info + the existing "Gates" group) and
pick a clear user-facing name consistent with `record_gates`.

## Coordination (from t635_3)

t635_3 added the registry per-gate `blocks_dependents` flag and the per-task
`also_blocks_dependents:` frontmatter field (extra gates required before a task's
dependents unblock). The unblock logic is **dormant until this task** makes
profiles / `default_gates` populate `gates:` at planning time — once a task
declares gates, a declared gate marked `blocks_dependents` becomes a dependent
unblock requirement and the t635_3 mechanism goes live. Keep the two in sync: the
gates a profile declares determine which become unblock requirements;
`also_blocks_dependents` is the per-task escape hatch on top of the
profile/registry defaults. See `aidocs/gates/dependency-unblock-semantics.md`.

## References

- `aidocs/gates/integration-roadmap.md` (Phase 4)
- `aidocs/gates/dependency-unblock-semantics.md` (t635_3 — blocks_dependents / also_blocks_dependents)
- `.claude/skills/task-workflow/profiles.md`
