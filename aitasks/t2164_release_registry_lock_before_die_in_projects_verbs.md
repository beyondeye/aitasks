---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [monitor, tui, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2163
followup_kind: upstream_defect
created_at: 2026-10-29 21:32
updated_at: 2026-10-29 21:45
---

## Origin

Spawned from t2163 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_projects.sh:493-502` (as of t2163's commit `c0483ba6e`) — `cmd_update`'s "No registered projects." / "Project '<name>' is not registered." dies run while the registry mutex is held and never release it. The lock is left to stale-pid reclaim. The same pattern occurs in `set_registry_group` (788-793), `rename_registry_group` (813-818), `cmd_add`'s invalid-config-slug die, and `group sync`'s invalid-slug die.

## Diagnostic context

t2163 added `load_registry_or_die [--locked]` to `aitask_projects.sh`. With
`--locked`, it calls `registry_lock_release "$REGISTRY_LOCK_DIR"` before `die`
whenever the registry cannot be read, so an unreadable registry never leaves
`projects.yaml.lockd` behind (pinned by `tests/test_projects_unreadable_registry.sh`).

The other `die` calls made **after** `registry_lock_or_die` have no such release:
- `cmd_update`: "No registered projects." and "Project '<name>' is not registered."
- `set_registry_group`: "Project '<name>' is not registered."
- `rename_registry_group`: "No registered project has group '<old>'."
- `cmd_add`: the invalid `project.project_group` config-slug die, which runs inside the lock.
- `group sync`: the invalid config-slug die inside its loop.

Each of these exits with the lock dir still present. `lib/registry_lock.sh`
(the `stale_lock.sh` adapter) reclaims a lock whose recorded holder pid is
dead, so for a standalone command the leftover is probably freed by the next
acquire. That was **not measured** in t2163.

The case worth checking first is `cmd_doctor`, which runs
`( cmd_update "$name" "$new_path" )` in a subshell. If the lock records the
long-lived doctor process as its holder, a failed update there would leave a
lock whose holder is still alive, and the doctor's later `cmd_remove` in the
same run could then block for its full acquire timeout. Verify which pid the
lock records before relying on this.

The registry is never corrupted by this; only the lock is held too long.

## Suggested fix

Either release explicitly before each `die` inside a locked section (the
`load_registry_or_die --locked` pattern), or add a small
`die_locked "<msg>"` helper that releases and dies. Extend
`tests/test_projects_unreadable_registry.sh` (or a sibling test) to assert that
`projects.yaml.lockd` is absent after each of these error exits.
