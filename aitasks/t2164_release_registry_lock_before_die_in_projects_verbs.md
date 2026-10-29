---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [monitor, tui, robustness]
gates: [risk_evaluated]
anchor: 2163
followup_kind: upstream_defect
created_at: 2026-10-29 21:32
updated_at: 2026-10-29 21:32
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
(the `stale_lock.sh` adapter) reclaims a lock whose holder pid is dead, so the
next writer is not wedged forever. Until that reclaim runs, though, a concurrent
writer can still wait out its acquire timeout. This matters for the silent
bootstrap `ait projects add` burst on tmux restart (t1073), where a skipped
refresh is the outcome.

The registry is never corrupted by this; only the lock is held too long.

## Suggested fix

Either release explicitly before each `die` inside a locked section (the
`load_registry_or_die --locked` pattern), or add a small
`die_locked "<msg>"` helper that releases and dies. Extend
`tests/test_projects_unreadable_registry.sh` (or a sibling test) to assert that
`projects.yaml.lockd` is absent after each of these error exits.
