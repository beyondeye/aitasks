---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [install, worktree]
assigned_to: dario-e@beyond-eye.com
anchor: 1711
followup_kind: upstream_defect
created_at: 2026-10-13 13:26
updated_at: 2026-10-13 13:36
---

## Origin

Spawned from t1964 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:4181` — `snapshot_pre_setup_dirty` returns before capturing the data-branch baseline when `.aitask-scripts/VERSION` is untracked (or HEAD is unborn), yet `commit_framework_data_files` commits whenever the data worktree exists, so dirty `aitasks/metadata/` edits are swept into setup's data commit in that state.
- `.aitask-scripts/aitask_setup.sh:4217` — `_ait_list_framework_changes` lists staged paths with rename detection on; a staged rename inside framework paths baselines only its destination, so a setup step that recreates the source commits it and turns the pending rename into an addition (needs `--no-renames`).

## Diagnostic context

t1964 gave install.sh (`ait upgrade`) its own pre-install dirty baseline, modelled on setup's `snapshot_pre_setup_dirty` / `commit_framework_files` / `commit_framework_data_files`. Plan review found the setup model itself has two holes, both reproduced against setup's logic:

1. **Data baseline behind the main bootstrap guard.** setup's snapshot returns early (empty baselines) when the main repo has no HEAD or `.aitask-scripts/VERSION` is untracked — before it reaches the data-worktree baseline. `commit_framework_data_files` has no matching main-repo guard: it commits whenever `.aitask-data` exists. So with VERSION untracked and an uncommitted edit under the data branch's `aitasks/metadata/` or `aireviewguides/`, setup commits the user's edit. The main baseline has the same mismatch in miniature: `commit_framework_files` needs no HEAD (it reads the index), so a HEAD-less repo with a staged VERSION commits against an empty baseline.
2. **Staged renames.** `git diff --cached --name-only` reports only the destination of a staged rename (diff.renames defaults on); the source has left the index, so `ls-files --modified` cannot recover it either. If a setup step recreates the source, it is not in the baseline and gets committed, converting the user's pending rename into an addition.

install.sh's fix (t1964, commit 27cc7c7d1) is the reference: each baseline is gated on exactly its committer's eligibility predicate (`_install_commit_eligible` for main — work tree + VERSION in the index, no HEAD requirement; `_install_data_worktree_present` for data, independent of the main repo), and the staged term uses `--no-renames`. `tests/test_install_upgrade_dirty_baseline.sh` cases F2, G2b and R pin the install side and show the fixture shapes.

## Suggested fix

In `snapshot_pre_setup_dirty`, capture the data baseline before and independent of the main-repo guards, and gate the main baseline on the same predicate `commit_framework_files` uses (drop the HEAD requirement). Add `--no-renames` to the staged term of `_ait_list_framework_changes`. Extend `tests/test_setup_git.sh` with the three shapes (VERSION untracked + dirty data metadata; HEAD-less + staged VERSION + staged `.gitignore`; staged rename of a framework file that a setup step recreates).
