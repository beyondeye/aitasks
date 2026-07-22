---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: [t635_33]
issue_type: chore
status: Implementing
labels: [gates, task_workflow, execution_profiles]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1220]
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/opus4_8
created_at: 2026-07-19 08:27
updated_at: 2026-07-22 18:48
---

## Context

> **Re-scoped 2026-07-22.** This task was filed as "migrate `task-workflown`'s
> stale `{% if profile.risk_evaluation %}` blocks to the `rendered_set` model"
> (the carve-out from t635_33). Planning showed that extending the fork was the
> wrong move, and the task was redirected to **retire the experiment** instead.
> The filename still carries the original slug — renaming a task mid-flight
> breaks the lock/plan pairing, so it was deliberately kept. `issue_type` moved
> `refactor` → `chore`.

`aitask-pickn` + `task-workflown` are the t928 "hardening sandbox": parallel
copies of `aitask-pick` / `task-workflow` created to test stricter fail-closed
gates without touching production. They are retired here.

**Why retire rather than migrate:**

1. **No production callers.** `grep -rn 'pickn\|workflown'` over
   `.aitask-scripts/`, `ait`, `install.sh`, `seed/`, `website/` → zero hits. The
   board and minimonitor agent launchers emit `/aitask-pick`.
2. **Silently rotted.** t635_14 removed the `profile.risk_evaluation` profile
   key; the fork still keyed 8 blocks on it, so it rendered **no** risk
   machinery under any profile ever since, and
   `tests/test_skill_render_task_workflown.sh` failed 7 asserts undetected.
   t635_33 had to copy `gate-cli.md` into the fork purely to keep its
   file-parity assert green.
3. **Superseded.** Three of the experiment's four hypotheses shipped to
   production independently — the `## Risk` + `### Code-health risk` /
   `### Goal-achievement risk` plan format, the `risk_code_health` /
   `risk_goal_achievement` frontmatter writes, and archive-time verification of
   both are exactly what `.aitask-scripts/aitask_gate_risk.sh` checks, enforced
   by `aitask_archive.sh gate_guard`.
4. **Extending it makes it worse.** The fork has no gate machinery at all; the
   Step-4 `materialize-active` the original scope asked for would have persisted
   `active_gates: [risk_evaluated]` with nothing able to record a pass, blocking
   archival forever.

The one unshipped hypothesis — the Step-9b final-response gate — is salvaged as
**t1218**, created and committed before any deletion.

## Scope

1. **Delete the fork** (40 tracked files): `.claude/skills/aitask-pickn/`,
   `.claude/skills/task-workflown/`, `.agents/skills/aitask-pickn/`,
   `.opencode/skills/aitask-pickn/`, `.opencode/commands/aitask-pickn.md`,
   `tests/test_skill_render_aitask_pickn.sh`,
   `tests/test_skill_render_task_workflown.sh`,
   `aidocs/framework/pickn_workflown_experiment.md`.
2. **Upgrade migration.** `install_skills` / `setup_codex` / `setup_opencode`
   are additive copy loops — they never remove a wrapper that vanished
   upstream, so an upgraded project would keep a discoverable `/aitask-pickn`
   in eight locations. Add `.aitask-scripts/aitask_prune_retired_skills.sh`:
   table-driven, exact-name matching (never prefix-glob — `aitask-pickn` sits
   one character from `aitask-pick`), and **content-hash ownership** against a
   committed `retired_skills_manifest.txt` so a user-modified or user-authored
   file at a retired path is preserved and warned about, never deleted.
   Directories are all-or-nothing. Rendered `*-<profile>-` closures are never
   deleted by an upgrade (their content depends on the user's own profiles, so
   ownership cannot be proven) — they are reported, with an opt-in
   `--prune-rendered` flag for explicit user-initiated cleanup. Wire into
   `install.sh` and `aitask_setup.sh`.
3. **Remove the config entry point:** `default_profiles.pickn` from
   `aitasks/metadata/project_config.yaml` (never in `VALID_PROFILE_SKILLS`).
4. **Redirect cross-references:** keep the `<skill>n` staging convention in
   `aidocs/framework/skill_authoring_conventions.md` but add the missing half —
   a staging copy is short-lived, and retiring it means pruning installed
   projects, not just deleting the source. Drop the dangling `task-workflown`
   example from t1215. CHANGELOG entry.

## Key files

- `.claude/skills/{aitask-pickn,task-workflown}/`, `.agents/skills/aitask-pickn/`,
  `.opencode/{skills/aitask-pickn,commands/aitask-pickn.md}`
- `.aitask-scripts/aitask_prune_retired_skills.sh` +
  `.aitask-scripts/retired_skills_manifest.txt` (new)
- `install.sh`, `.aitask-scripts/aitask_setup.sh`
- `tests/test_prune_retired_skills.sh` (new)
- `aidocs/framework/skill_authoring_conventions.md`, `CHANGELOG.md`

## Verification

- Repo-wide `grep -rn 'pickn\|workflown'` leaves only: CHANGELOG history, the
  quoted commit subject in `tests/fixtures/skills/README.md`, the staging
  convention in `skill_authoring_conventions.md`, the t777 history note in
  `stub-skill-pattern.md`, the prune helper's tables + test, t1218, and this
  task's own files.
- `aitask_skill_verify.sh` passes; its `.j2` discovery drops by exactly one.
- `tests/test_prune_retired_skills.sh` green — including the preserve-and-warn
  cases (modified tracked, custom untracked, modified staging wrapper, mixed
  directory, hand-edited rendered `SKILL.md`), the live-neighbour negative
  control, and an idempotent re-run that removes nothing further.
- Surviving skill-render + install/setup suites green.

## Coordination

- **t1218** — salvages the Step-9b final-response gate from this fork.
- **t1215** — its `task-workflown` example is removed by this task.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:review_approved** run=2026-07-22T15:46:03Z status=pass attempt=1 type=human
