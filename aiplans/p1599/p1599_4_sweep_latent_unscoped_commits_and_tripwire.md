---
Task: t1599_4_sweep_latent_unscoped_commits_and_tripwire.md
Parent Task: aitasks/t1599_scope_task_data_commits_to_their_own_paths.md
Sibling Tasks: aitasks/t1599/t1599_1_*.md, aitasks/t1599/t1599_2_*.md, aitasks/t1599/t1599_3_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# p1599_4 — Sweep the latent unscoped commits, add a tripwire

## Context

Closes the **latent** half of t1599's surface. The audit found 19 unscoped
`task_git commit` sites; three are owned by siblings, and the remaining **16**
already stage explicit paths but finish with a bare `commit`, which writes the
whole index — the TOCTOU race that cost t1207 five foreign files despite a
verified 16-path allowlist.

**Gated on t1599_1, t1599_2 and t1599_3.** The tripwire scans every script, so it
must not land until the primary sites are scoped and the allowlist of deliberate
index-wide commits is settled.

## What this does NOT buy — say so plainly

Measured on the live `aitask-data` branch, these sites are near-clean:
`Add task` 2/300 (0.7%), `Add child task` 0/300, `Update task` 0/6,
`Archive completed` 3/300 (1%). This is **latent-race hardening, not an observed
defect**. Do not describe it as fixing a measured bug in the commit message or
the docs.

## Step 1 — Re-derive the site list

Siblings will have changed some. Start from:

```bash
grep -rn "task_git commit" .aitask-scripts/ --include=*.sh --include=*.py | grep -v -- '-- '
```

At audit time: `aitask_create.sh` (8 sites), `aitask_update.sh` (2),
`aitask_archive.sh` (3), `aitask_zip_old.sh` (1), `aitask_issue_import.sh` (1).

## Step 2 — Mechanical conversion

Each site already stages an explicit path list immediately above. Convert
`add <paths>` + bare `commit -m <msg>` to `commit -m <msg> -- <paths>`, keeping
the `add` where a path may be **untracked** — the common case here, since these
scripts create new task/plan files. `-m` before `--`.

## Step 3 — The two sites that need judgement

- **`aitask_zip_old.sh:537-539`** uses `add -u "$TASK_ARCHIVED_DIR/" …` and is
  genuinely **directory-scoped by design** (archive bundling cannot enumerate the
  bundled files). Scope the commit to those same directory pathspecs — still far
  narrower than the whole index. This is not a bug; do not "fix" it into a file
  list.
- **`aitask_issue_import.sh:791-792`** is an `add` + `commit --amend --no-edit`.
  Give it the same foreign-path refusal t1599_2 adds to `aitask_fold_mark.sh`:
  refuse loudly if HEAD carries paths outside the expected set rather than
  silently rewriting (and, if already pushed, rewriting published history).

## Step 4 — The tripwire

New `tests/test_no_unscoped_task_commit.sh`, modelled on the existing
`tests/test_no_raw_tmux.sh`. Fail if a `task_git commit` line carries no `--`
pathspec.

- A **documented allowlist**, each entry carrying a comment explaining why that
  commit is deliberately index-wide. Settle it only after the siblings land.
- The failure message must name file:line and point at the reference patterns
  (`aitask_attach.sh:196-205`, `aitask_gate_record.sh:81-82`,
  `aitask_gate.sh:1025-1032`).
- **State its limits** in the test header and any docs: it is a grep, so it
  catches the common single-line shape and will NOT see a commit assembled across
  lines or through a variable. It is a regression tripwire, **not** a proof of
  absence.

## Verification

- `bash tests/test_no_unscoped_task_commit.sh` passes on the fixed tree.
- **Negative control (required):** the tripwire must FAIL when pointed at a
  deliberately reintroduced unscoped commit (a fixture line or fixture file it
  also scans). A guard that cannot fail guards nothing.
- Re-run the suites for every touched script, including
  `tests/test_archive_no_overbroad_add.sh` — the t533 precedent for exactly this
  bug shape.
- `shellcheck .aitask-scripts/aitask_*.sh`.
- **Boundary check:** `git diff --name-only` must not list `aitask_pick_own.sh`,
  `aitask_fold_mark.sh`, `aitask_sync.sh` or `aitask_lock.sh`. If the tripwire
  flags them, the siblings did not finish — report it rather than editing across
  the ownership boundary.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.
