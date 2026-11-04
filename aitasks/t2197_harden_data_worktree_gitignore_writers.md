---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [install, ait_setup]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2173
followup_kind: upstream_defect
created_at: 2026-11-04 12:36
updated_at: 2026-11-04 12:52
---

## Origin

Spawned from t2191 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:1921 — setup_data_branch's fresh-worktree writes to .aitask-data/.gitignore are unchecked `>>` appends and unguarded greps under main()'s errexit, the shape t2185/t2188 hardened for the main .gitignore; a FIFO there is now refused up front, but a write failure (e.g. a umask that strips owner write on the fresh checkout) would abort setup — not probed`

## Diagnostic context

t2191 added one early precondition to `ait setup` / `install.sh` `main()`
(`refuse_nonregular_gitignores`, `aitask_setup.sh:1135`): setup refuses when the
root, `.aitask-data/` or `.aitask-scripts/` `.gitignore` exists but is not a
regular file (or a symlink to one), because git blocks on a FIFO `.gitignore`
during `snapshot_pre_setup_dirty`. That precondition also covers a **FIFO** or
**directory** `.aitask-data/.gitignore`.

It does **not** cover a **write failure** on a regular `.aitask-data/.gitignore`.
`setup_data_branch` (from `:1921`) appends several blocks to it with bare
`{ echo ...; } >> "$data_gitignore"` groups, each guarded only by a `grep -qx`
presence test:

- draft tasks
- userconfig.yaml
- `*.local.json`
- `profiles/local/`
- `chatlink_sessions/`
- …

`main()` runs under `set -euo pipefail`, so a failed append aborts setup
mid-way. Each group's status is also its last command's, so a failed first
`echo` is lost behind a later write that succeeded. That is the same
separator-gluing defect t2185 fixed in `_ait_ensure_gitignore_block` and t2188
fixed in `_ait_add_gitignore_rules`.

Reachability, as read (not probed): these writes run only on first data-branch
configuration, right after a fresh `git worktree add` of `aitask-data` (a later
`ait setup` returns early at "already configured"). git stores neither FIFOs nor
read-only modes, so the realistic trigger is a umask that strips owner write
(e.g. `0222`), or a full disk. Probe first, and record exactly which triggers
reach it, before choosing the fix.

## Suggested fix

Route the data-branch `.gitignore` groups through the per-rule writer
`_ait_add_gitignore_rules`: a group table entry per block, checked writes,
read-back, and the rc-2 warning. Do it the way t2188 routed the main task-data
rules (`_ait_gitignore_group data`). Add a bounded regression case with a write
fault, like `tests/test_setup_git.sh` 27n's echo shadow, plus a no-fault
control.
