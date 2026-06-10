---
priority: medium
effort: medium
depends: [t635_12, t635_13]
issue_type: refactor
status: Ready
labels: [gates, execution_profiles, task_workflow]
created_at: 2026-06-10 18:55
updated_at: 2026-06-10 18:55
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

## References

- `aidocs/gates/integration-roadmap.md` (Phase 4)
- `.claude/skills/task-workflow/profiles.md`
