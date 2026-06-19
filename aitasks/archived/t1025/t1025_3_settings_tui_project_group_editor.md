---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t1025_2]
issue_type: feature
status: Done
labels: [ait_settings, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-18 00:02
updated_at: 2026-06-19 15:13
completed_at: 2026-06-19 15:13
---

## Context

Third child of t1025 (depends on t1025_2). Adds an interaction surface in the
settings TUI to edit per-user project-group membership, consuming t1025_1's
registry writer + slug validator. The user explicitly requested this editor as
the primary way to manage per-user groups. See parent plan `aiplans/p1025_*.md`.

## Key Files to Modify

- `.aitask-scripts/settings/settings_app.py` (3439 lines): add a `project-groups`
  `TabPane` and/or a `ModalScreen` editor following the existing
  `EditVerifyBuildScreen` / `ProfilePickerScreen` pattern. List registered repos
  with their current group; allow assign/create/rename/clear. Reuse the
  keybinding-registry/tab-switch map (~:156).
- Membership-edit model methods (in t1025_1's model layer or a small settings
  model helper) — the screen calls one method per operation.

## Reference Files for Patterns

- `EditVerifyBuildScreen` (~:772), `ProfilePickerScreen` (~:922),
  `NewProfileScreen` (~:960) — ModalScreen compose/cancel pattern.
- t1025_1 registry writer + slug validator (must be reused; no direct YAML poke).

## Implementation Plan

Edit semantics (each encapsulated in a model method — "encapsulate cleanup in
model"; all names pass the t1025_1 slug validator, illegal input rejected/
normalized with a visible message before any write):

1. **Assign:** set one repo's `project_group` to an existing/new slug.
2. **Create:** group exists implicitly once ≥1 repo references its slug;
   duplicate slug = no-op merge.
3. **Clear:** blank → unset membership (repo → "(ungrouped)").
4. **Rename:** ONE atomic read-modify-write rewriting `project_group` on every
   member (reuse `build_registry_yaml` full-file re-serialize); rename into an
   existing slug merges groups.

## Verification

- Model-level tests vs a temp registry: assign; create (duplicate-merge);
  clear→ungrouped; rename (all members rewritten atomically); rename-into-existing
  (merge); slug rejection of `:`/`#`/`|`/space/uppercase.
- Smoke test: the project-groups tab/screen mounts.
- Manual: edit a group in the settings TUI, confirm registry + re-render
  (covered live by t1025_5).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-18T13:55:14Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-18T13:55:15Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-19T12:12:26Z status=pass attempt=1 type=human
