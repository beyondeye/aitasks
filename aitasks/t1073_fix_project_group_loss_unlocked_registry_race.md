---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [backend, projects, concurrency]
created_at: 2026-06-25 10:00
updated_at: 2026-06-25 10:00
---

## Problem

Project-group assignments (the "Project Groups" tab in the settings TUI) silently
reset to ungrouped — observed twice, correlated with a PC restart. When it happens,
**all** group assignments are wiped at once, and they do not come back.

## Root cause: unlocked read-modify-write of the per-user project registry

Project-group membership is stored **only** in the per-user registry
`~/.config/aitasks/projects.yaml` (the 5th `project_group` field per entry).
Confirmed that neither `aitasks` nor `aitasks_go` mirrors the group in its repo
`aitasks/metadata/project_config.yaml` — so once the registry value is lost there
is no config-fallback to heal it (`group_effective` / `cmd_add` fall back to repo
config, which is empty), and the group stays gone permanently.

`cmd_add` in `.aitask-scripts/aitask_projects.sh` performs a **whole-file**
read-modify-write: it reads the entire registry into an in-memory TSV snapshot
(`list_registry_entries`), rebuilds it, and writes the whole file back via
`atomic_write`. There is **no file locking** anywhere in `aitask_projects.sh`
(no `flock`). `atomic_write` (temp file + `mv`) makes each *individual* write
atomic — preventing torn/partial files — but does **nothing** about lost updates:
two processes can each read, then each write, and the last writer clobbers the
other's changes with its own stale snapshot.

`cmd_add` fires **automatically and silently** on every tmux session bootstrap:
`.aitask-scripts/lib/tmux_bootstrap.sh:106` runs
`aitask_projects.sh add "$root" >/dev/null 2>&1 || true`. The reporter's workflow
(`ait ide` in the aitasks root, then opening other-project TUIs via the TUI
switcher — `tui_switcher.py::_ensure_session_live`) fans out many of these
bootstrap `add` calls in a short burst, especially right after a restart when the
whole workspace is re-opened.

### Why ALL groups vanish at once

A single slow bootstrap `cmd_add` that snapshotted the registry **before** the
groups were assigned (or before a concurrent writer's commit), and committed its
whole-file snapshot **after**, overwrites every group in one write — not just one
entry's delta. This matches the "all assignments wiped" symptom exactly. The
restart burst maximizes the number of in-flight writers and thus the chance one
commits a stale, pre-group snapshot last.

## Evidence (reproduced)

- **Lost-update race proven:** with a temp registry, 10 concurrent
  `aitask_projects.sh add` calls (5 on `aitasks`, 5 on `aitasks_go`) left
  `aitasks`'s `last_opened` at its original date — all 5 of its updates were
  silently lost (only the last writer's snapshot survived).
- Registry parser/round-trip (`agent_launch_utils.py --list-registry` +
  `build_registry_yaml`) correctly preserves the 5th `project_group` field —
  the defect is concurrency, not serialization.
- The exact all-groups-wipe is timing-dependent (read-before-assign /
  write-after-assign window); it was not reproduced frame-perfectly in a shell
  harness, but the lost-update mechanism that produces it is demonstrated.

## Suggested fix

1. **Serialize all registry mutations under an `flock`** on the registry file (or
   a sibling lockfile) spanning the *entire* read-modify-write, not just the
   write. Cover every mutating verb in `aitask_projects.sh`: `cmd_add`,
   `cmd_remove`, `cmd_update` (repoint), `cmd_prune`, and the group writers
   (`set_registry_group`, `rename_registry_group`, the `group sync` path).
2. Consider narrowing `cmd_add`'s bootstrap refresh to update only the **target**
   entry's `last_opened` in place (still under the lock), so a bootstrap add can
   never rewrite unrelated entries' fields even in principle.
3. Keep `atomic_write` for crash-safety; the lock is the missing piece for
   lost-update safety.

## Acceptance criteria

- A regression test launches N concurrent `aitask_projects.sh add` /
  `group set` operations against a temp registry and asserts that **all** group
  assignments and **all** `last_opened` bumps survive (no lost updates).
- Manual verification: assign groups via the settings TUI, then fan out several
  project TUIs via the switcher / restart the workspace; groups persist.

## Key files

- `.aitask-scripts/aitask_projects.sh` — registry writers (`cmd_add`,
  `set_registry_group`, `rename_registry_group`, `group sync`, `atomic_write`)
- `.aitask-scripts/lib/tmux_bootstrap.sh:106` — silent auto-fire of `add` on
  session bootstrap
- `.aitask-scripts/lib/agent_launch_utils.py` — registry parser (`--list-registry`)
- `.aitask-scripts/lib/tui_switcher.py` — `_ensure_session_live` bootstrap trigger
- Note macOS portability of `flock` (not present by default) — see
  `aidocs/framework/shell_conventions.md` / `sed_macos_issues.md` for the
  platform-encapsulation pattern; may need a portable lock helper.
