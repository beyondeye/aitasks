---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [install, ait_setup]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2173
followup_kind: upstream_defect
created_at: 2026-11-03 23:48
updated_at: 2026-11-04 08:49
---

## Origin

Spawned from t2185 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:4780 — _ait_list_framework_changes' git ls-files --others --exclude-standard probe, reached from snapshot_pre_setup_dirty (:4862, the first git step in main()), blocks on a FIFO .gitignore on git 2.56.0 (untracked FIFO, or a tracked .gitignore replaced by one while git walks a directory), so 'ait setup' still hangs before setup_data_branch; install.sh's snapshot_pre_install_dirty likely shares the shape (not measured). A single early precondition (refuse/warn when .gitignore exists but is not a regular file) before any git probe would cover git's own reads`
- `.aitask-scripts/aitask_setup.sh:3187 — _ait_add_gitignore_rules (t2178) writes its separator, comment and rules as { echo ""; echo "# comment"; printf ...; }, checking only the last status: a transient failure of the separator echo on a .gitignore whose last line lacks a newline glues the comment onto that rule (probe: 'keep-me' -> 'keep-me# Some comment', rc 0, "Added rule-a/"), the same defect Change Request 1 fixed in _ait_ensure_gitignore_block`

## Diagnostic context

t2185 hardened the framework's own reads and appends of the main `.gitignore`
(the `_ait_rewrite_data_gitignore_lines` `[[ -f ]]` gate and the Step 7 block
writer `_ait_ensure_gitignore_block`). Its premise, inherited from t2178, was
"git itself does not block on a FIFO `.gitignore`". Measured during t2185 on
git 2.56.0 (one host, omg16), that holds only for some shapes:

- untracked FIFO `.gitignore`: `git ls-files --others --exclude-standard`,
  `git status --porcelain` and `git add -- .gitignore` all time out (124);
  `git diff --name-only -- .gitignore` and an `ls-files` pathspec of only
  root files (`-- README.md`) return 0;
- tracked `.gitignore` replaced by a FIFO: `ls-files --others
  --exclude-standard` with no pathspec returns 0 in a repo whose files are all
  tracked at the root, but `-- sub/` (a directory git walks) times out;
  `git add -- .gitignore` returns 128 (fails, does not hang).

xtrace of a bounded `snapshot_pre_setup_dirty` (both shapes) stops in
`_ait_list_framework_changes`' `git ls-files --others --exclude-standard --
<framework paths>`. `main()` calls `snapshot_pre_setup_dirty` before
`setup_data_branch`, so a full `ait setup` with a FIFO `.gitignore` hangs
before any of t2185's code runs. t2185's fixes stand on their own (the
readonly/directory aborts in Step 7 are reached; the helpers can be called
directly) but do not make `ait setup` survive a FIFO end to end.
`tests/test_setup_git.sh` 27f's comment ("git 2.56 does not block on a FIFO
there") is true for its fixture (a tracked .gitignore swapped for a FIFO in a
root-only repo) but not in general.

The second bullet is t2178's per-rule writer: the same separator-status defect
t2185's review found in `_ait_ensure_gitignore_block` (fixed there with
`echo "" && printf ...`, regression case in `tests/test_data_branch_setup.sh`
Test 40b, injected by shadowing `echo` for the first call only). Probe for
`_ait_add_gitignore_rules`: a counter-based `echo` shadow that fails only the
first call; a `keep-me` file with no trailing newline became
`keep-me# Some comment\nrule-a/\n` with rc 0 and `_ait_gitignore_added=rule-a/`.

## Suggested fix

- One early precondition, before any git probe, in `ait setup` main() (and
  install.sh's upgrade path, after measuring `snapshot_pre_install_dirty`):
  when `.gitignore` exists (or is a symlink) but is not a regular file, warn
  and refuse — or skip every `.gitignore` step — instead of letting git block.
  Bounded test (`run_bounded`) for both FIFO shapes, red-proven first.
- `_ait_add_gitignore_rules`: chain the writes (`echo "" && echo "# $comment"
  && printf ...`) so any failed write reaches the rc-2 / partial path; add a
  27-family regression case with the first-call-only `echo` shadow and a
  no-fault control.
