---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tests, test_infrastructure, ait_setup, data_integrity]
gates: [risk_evaluated]
created_at: 2026-09-14 17:48
updated_at: 2026-09-14 17:48
---

## Problem

Four test-fixture files from `tests/test_data_branch_setup.sh` are committed in
this project's **real** task-data branch (`.aitask-data`, reached through the
`aitasks -> .aitask-data/aitasks` symlink):

| file | content | test origin |
|---|---|---|
| `aitasks/t1_alpha.md` | empty | PC1 seed in the `$TMPDIR_11` scenario (`: > aitasks/t1_alpha.md`) |
| `aitasks/t2_beta.md` | empty | same |
| `aitasks/t10_gamma.md` | empty | same |
| `aitasks/t5_remote_task.md` | `---\nRemote task` | PC1/PC2 scenario in `$TMPDIR_4` (`echo "Remote task" >> aitasks/t5_remote_task.md`) |

They were committed by the auto-sync commit `2dabfae81` ("ait: Auto-commit task
changes before sync", 2026-08-27 14:22). That commit also carries an unrelated
real task edit (`t1632_...`), so the fixtures were already sitting untracked in
the real data worktree when a sync auto-committed them. 2026-08-27 is the day
t1627 and t1631 reworked `setup_data_branch` and this test file, so an
intermediate test run during that work is the likely source. **This is not
verified.**

(The files' mtime of 2026-09-06 09:19 matches `~/.aitask/bin`, so it most likely
records a later `ait setup` checkout, not the leak.)

## Observable effect

None of the four files has a frontmatter mapping. Every board trail scan
(`lib/trail_discovery.py::_iter_active_task_frontmatter`) therefore reports them
as unreadable, and entering By-Trail or pressing `s` shows the warning *"Trail
scan skipped 4 unreadable active task file(s): t10_gamma.md, t1_alpha.md,
t2_beta.md (+1 more) — the list may be incomplete"*. This is a permanent false
alarm that hides a real torn-read signal. Anything else that globs
`aitasks/t*.md` may see the same four bogus files and IDs (t1, t2, t5, t10).

Found while exploring a one-off, non-reproducible board crash on the freeze
trail (`art:trail-frozen-codeagents`). The crash itself is **not** part of this
task: headless runs under PyPy and CPython, driving `z` → selector → Enter →
`v` / Enter / `s` at 160x48, 120x36 and 80x24, all rendered with no exception,
and the user reports it no longer happens.

## Scope

1. **Remove the four files** from the task-data branch with a scoped commit
   (`./.aitask-scripts/aitask_task_commit.sh` / `./ait git rm` with an explicit
   pathspec, never a bare commit of the shared index). Before deleting, confirm
   that no real task claims IDs 1, 2, 5 or 10 at those paths.
2. **Find the leak path.** Work out how `test_data_branch_setup.sh` wrote into
   the real `.aitask-data` and not a `$TMPDIR_*` tree. Candidates to check:
   an empty or unset `$TMPDIR_N`, a subshell `cd` whose target was missing
   before the current `cd ... || exit 1` guards existed, and `SCRIPT_DIR` /
   `PROJECT_DIR` resolution pointing `setup_data_branch` at the real repo.
   Determine whether the **current** file can still leak. Do not assume it
   cannot just because guards exist now.
3. **Close it with a regression check.** For example, fingerprint the real
   repo's data worktree (`git -C "$PROJECT_DIR/.aitask-data" status --porcelain`
   plus the untracked `aitasks/t*.md` list) before and after the test, and fail
   on any change. If the path is still open, fix the test (or `setup_data_branch`)
   so a failed setup can never fall through to writes against the real tree.
   Run the check against the pre-fix code first, so the regression check is
   seen to fail before it is trusted.

## Out of scope

- The board crash (not reproducible, no traceback).
- Making trail discovery tolerate frontmatter-less files differently. Reporting
  them as unreadable is the intended fail-loud behaviour (see the
  `_iter_active_task_frontmatter` docstring); the bug is that these files exist.
