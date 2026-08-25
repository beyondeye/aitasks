---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [git, bash_scripts, robustness, test]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-08-25 12:50
updated_at: 2026-08-25 12:50
---

## Context

Parent: t1599. This child closes the **latent** half of the surface.

The audit found **19 unscoped `task_git commit` sites**. Three (owned by
t1599_1/2/3) also stage a whole directory and are the empirical bug. The
remaining **16** already stage explicit paths but still finish with a bare
`commit`, which writes the **entire index** — a TOCTOU race: any path a
concurrent session stages between your `add` and your `commit` lands in your
commit. This is exactly how t1207 captured 5 foreign files despite a verified
16-path allowlist.

## What this child does NOT buy — state this honestly

These sites measured **near-clean** on the live `aitask-data` branch:

| pattern | swallowed |
|---|---|
| `ait: Add task t…` | 2/300 (0.7%) |
| `ait: Add child task t…` | 0/300 |
| `ait: Update task t…` | 0/6 |
| `ait: Archive completed t…` | 3/300 (1%) |

So this is **latent-race hardening, not an observed defect**. Do not describe it
as fixing a measured bug. The value is closing the race class and preventing
regression.

## Dependencies — this child is gated

`depends: [t1599_1, t1599_2, t1599_3]`. The tripwire scans every script, so it
must not land until the three primary sites are scoped and the allowlist of
deliberate index-wide commits is settled — otherwise the guard fires on work
that is already planned.

## Exclusive script ownership

This child owns `aitask_create.sh`, `aitask_update.sh`, `aitask_archive.sh`,
`aitask_zip_old.sh`, `aitask_issue_import.sh`, and the new tripwire test.

**Do NOT edit** `aitask_pick_own.sh` (t1599_1), `aitask_fold_mark.sh`
(t1599_2), `aitask_sync.sh` / `aitask_lock.sh` (t1599_3) — even if the tripwire
flags them. If it does, those children did not finish; report it rather than
editing across the boundary.

## The 16 sites

Re-derive the current list before starting (other children will have changed
some), with:

```bash
grep -rn "task_git commit" .aitask-scripts/ --include=*.sh --include=*.py | grep -v -- '-- '
```

At audit time:

- `.aitask-scripts/aitask_create.sh` — `:864`, `:902`, `:904`, `:1958`, `:2136`,
  `:2138`, `:2168`, `:2170`
- `.aitask-scripts/aitask_update.sh` — `:1777`, `:2217`
- `.aitask-scripts/aitask_archive.sh` — `:283`, `:565`, `:645`
- `.aitask-scripts/aitask_zip_old.sh` — `:546`
- `.aitask-scripts/aitask_issue_import.sh` — `:792`

Each already stages an explicit path list immediately above. Mechanical
conversion: `add <paths>` + bare `commit -m <msg>` becomes
`commit -m <msg> -- <paths>`. Keep the `add` only where a path may be
**untracked** (a pathspec cannot name a file git does not know about) — which is
the common case here, since these scripts create new task/plan files.

Note the argument order: `-m` must precede `--`, or git reads the message as a
path.

## Two sites need care, not the mechanical edit

- **`aitask_zip_old.sh:537-539`** uses
  `task_git add -u "$TASK_ARCHIVED_DIR/" "$PLAN_ARCHIVED_DIR/"` — genuinely
  **directory-scoped by design** (archive bundling; it cannot enumerate the
  bundled files). Scope the commit to those same directory pathspecs, not to a
  file list. This is a legitimate broad scope, not a bug — but it is still
  narrower than the whole index.
- **`aitask_issue_import.sh:791-792`** is `task_git add "$created_file"` followed
  by `task_git commit --amend --no-edit`. It needs the same foreign-path guard
  t1599_2 adds to `aitask_fold_mark.sh`'s amend: refuse loudly if HEAD carries
  paths outside the expected set, rather than silently rewriting (and, if
  already pushed, rewriting published history).

## Reference patterns

- `.aitask-scripts/aitask_attach.sh:196-205` — `_attach_commit()`, with a
  load-bearing comment explaining exactly this bug
- `.aitask-scripts/aitask_gate_record.sh:81-82`
- `.aitask-scripts/aitask_gate.sh:1025-1032` — scoped no-op guard via
  `task_git status --porcelain -- "$file"`

## The tripwire

New `tests/test_no_unscoped_task_commit.sh`, in the spirit of the existing
`tests/test_no_raw_tmux.sh` (which enforces the tmux-gateway rule). Fail if a
`task_git commit` line carries no `--` pathspec.

Requirements:
- A **documented allowlist** for any deliberately index-wide commit, each entry
  carrying a comment explaining why. Settle the allowlist only after
  t1599_1/2/3 have landed.
- The failure message must name the offending file:line and point at the
  reference patterns above.

**State its limits in the test's header comment and in the docs:** it is a grep,
so it catches the common single-line shape and will NOT see a commit assembled
across lines or through a variable. It is a regression tripwire, **not** a proof
of absence. Do not let it read as stronger enforcement than it is.

## Verification

- `bash tests/test_no_unscoped_task_commit.sh` — passes on the fixed tree.
- **Negative control (required):** the tripwire must FAIL when pointed at a
  deliberately reintroduced unscoped commit. Prove it by adding a temporary
  fixture line (or a fixture file the test also scans) and confirming a
  non-zero exit — a guard that cannot fail guards nothing.
- Re-run the existing suites for every touched script:
  `bash tests/test_task_create.sh`, `bash tests/test_archive_no_overbroad_add.sh`
  (the t533 precedent for exactly this bug shape), plus any
  `test_update_*` / `test_zip_old*` / `test_issue_import*` files present.
- `shellcheck .aitask-scripts/aitask_*.sh`
- Confirm no cross-boundary edits: `git diff --name-only` must not list the five
  scripts owned by t1599_1/2/3.
