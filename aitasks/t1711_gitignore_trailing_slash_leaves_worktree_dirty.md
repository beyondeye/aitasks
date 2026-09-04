---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [worktree, aitask_pick]
created_at: 2026-09-04 16:37
updated_at: 2026-09-04 16:37
---

## Origin

Reported from downstream: `thinking_app` hit this as **t374** (2026-09-04) and fixed
it in its own `.gitignore`. This repo carries the identical line, so every
aitasks-managed project that gets its `.gitignore` from here — or that was set up by
copying it — has the same latent defect.

A one-character fix is **already applied uncommitted** in this working tree
(`.gitignore`, the `.aitask-data/` line) by the agent that filed this task. Review it,
then land it with the sweep and the gate below.

## The defect

The task-data block ignores the data directory with a **trailing slash**:

```
# Task data (lives on aitask-data branch, accessed via symlinks)
.aitask-data/
aitasks
aiplans
```

A trailing-slash pattern matches a **directory only**. In the primary checkout
`.aitask-data` *is* a real directory, so it is ignored and nobody notices. In a
**linked worktree** `aitask_init_data.sh --link-worktree` creates `.aitask-data` as a
**symlink** (`ait_link_worktree_data()` in `lib/data_symlinks.sh`), which the pattern
does not match.

Note that `aitasks` and `aiplans`, two lines below, carry no slash and therefore ignore
both shapes. The inconsistency sits inside a single block whose own comment says
"accessed via symlinks".

## Consequence

`git status` in the worktree reports `?? .aitask-data`. That makes the tree dirty, and
the whole chain follows:

1. `git worktree remove` (no `--force`) refuses: `fatal: '<path>' contains modified or
   untracked files`, exit 128. Git refuses on **untracked** files, not only modified
   ones.
2. `aitask_task_worktree.sh` honours that refusal → `WORKTREE_KEPT dirty` +
   `BRANCH_KEPT skipped`.
3. `aitask_merge_task.sh cleanup` rolls it up to
   `CLEANED_PARTIAL:WORKTREE_KEPT=dirty,BRANCH_KEPT=skipped`.
4. Per `merge-broker.md`, `CLEANED_PARTIAL` routes to **stop-in-flight** ("Never
   archive over residue") — so the task cannot archive.

This fires on **every worktree-profile task**, on runs where the merge itself succeeded
and `git log main..aitask/<branch>` was empty. The manual recovery is to `rm` the
symlink and retry cleanup, which first requires an agent to diagnose it.

## Proof of the semantics

Minimal and self-contained; both halves were run in scratch repos differing **only** in
the trailing slash:

```
$ printf 'withslash/\nnoslash\n' > .gitignore
$ ln -s target withslash; ln -s target noslash
?? withslash          # NOT ignored
                      # noslash: IGNORED
$ rm withslash noslash; mkdir withslash noslash
                      # both IGNORED as directories
```

End of chain, same controlled comparison:

```
# .gitignore = "withslash/"   -> ?? withslash
$ git worktree remove ../wt
fatal: '../wt' contains modified or untracked files, use --force to delete it   (exit 128)

# .gitignore = "withslash"    -> clean
$ git worktree remove ../wt   -> removed
```

## Suggested fix

Drop the trailing slash so the pattern matches both shapes, exactly as `aitasks` and
`aiplans` already do two lines below.

**Verify at the seam that broke**, not with `git check-ignore` in the primary — the
primary was never the failing case, and `check-ignore` on an existing real directory
answers about the directory. Cut a worktree, run `aitask_init_data.sh
--link-worktree`, and assert `git status --short` is clean and
`aitask_merge_task.sh cleanup` reports `CLEANED` rather than `CLEANED_PARTIAL`.

## This is the third instance of one class

Downstream, `aitasks/` and `aiplans/` had the identical trailing-slash symlink mismatch
fixed earlier, and `.aitask-data/` was missed. Worth a sweep of this repo's
`.gitignore` for any other `<name>/` entry naming something a worktree materialises as a
symlink, rather than fixing one line and moving on.

The authoritative set to sweep against is `lib/data_symlinks.sh`:
`AIT_DATA_DIR_NAME` plus every `AIT_DATA_LINKS` entry — the one definition
`ait_link_worktree_data()` reads.

## Consider a gate, not just a fix

Downstream t374 shipped a structural gate alongside the fix, and the same shape would
work here (the framework has its own `tests/` suite): build a throwaway repo, copy the
tracked `.gitignore` into it, create a real **symlink** per name derived from
`lib/data_symlinks.sh`, and assert `git status --porcelain` reports none of them
untracked — plus a control symlink no pattern matches, asserted to *be* reported, so a
harness that has stopped observing fails loudly instead of passing vacuously.

Asking git rather than re-implementing pattern matching matters here: directory-only
matching is precisely the semantic a hand-rolled matcher gets wrong, and it is the
semantic that caused this bug. One such assertion covers three regressions — the slash
returning, the line being deleted outright, and a later `!` negation un-ignoring it.

One trap found downstream and worth repeating: if the test reads `.gitignore` at
runtime, that file must be **declared as a test input**, or the test runner reports
UP-TO-DATE across the very edit under test and the gate never runs.

## Note for whoever lands this

`install.sh` lists `.gitignore` only in `check_paths` — the paths it *commits* if
changed — and never writes the file's content. So this fix does not propagate to
existing installs on its own; each downstream project has to fix its own copy (as
`thinking_app` did in t374). Consider whether the seed/install path should carry the
corrected line for **new** installs.
