---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [install, ait_setup]
gates: [risk_evaluated]
anchor: 2173
followup_kind: upstream_defect
created_at: 2026-11-04 18:10
updated_at: 2026-11-04 18:10
---

## Origin

Spawned from t2197 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:1135 — refuse_nonregular_gitignores accepts a .gitignore that is "a symlink to a regular file", and _ait_add_gitignore_rules' `-f` guard follows links; git does not follow a symlinked in-tree .gitignore, so setup/upgrade write rules through the link and report "Added ... to .gitignore" for rules git never applies (root .gitignore and .aitask-scripts/.gitignore) — as read, not probed end-to-end`

## Diagnostic context

t2197 hardened setup_data_branch Step 3's `.aitask-data/.gitignore` writes. Its
review established, from `git help gitignore` (2.56): "Git does not follow
symbolic links when accessing a .gitignore file in the working tree." Test 41
in `tests/test_data_branch_setup.sh` pins that premise on this git: a
`.gitignore` symlink whose target lists `aitasks/metadata/userconfig.yaml`
gives `git check-ignore` rc 1, while the same bytes as a regular file give 0.

t2197 therefore made a regular, non-symlink `.aitask-data/.gitignore` a
precondition of Step 3 (abort through abort_data_branch_setup), because with a
symlinked file Step 4's `git add .` committed migrated secrets even though every
write and grep read-back through the link succeeded.

The main-repo routes were left as they are (out of scope):
- `refuse_nonregular_gitignores` (`aitask_setup.sh:1135`, t2191) refuses a FIFO
  or directory but allows a symlink to a regular file, and its message says so.
- `_ait_add_gitignore_rules` returns 2 only for an existing path that is not
  `-f` (which follows links), so a symlinked root `.gitignore` is written
  through and the success lines (`Added ...`, `... rule added to .gitignore`)
  claim an ignore that git does not apply. setup_data_branch Step 7, the
  re-run repair `setup_data_gitignore_symlink_safe`, every `_ait_setup_gitignore_group`
  helper and the install.sh upgrade routes all share this writer.

Probe first: confirm on a real fixture that a symlinked root `.gitignore`
leaves e.g. `/aitasks` or `aiwork/` shown by `git status` after setup reports
the rule added. Also decide what the right outcome is for the main repo: the
user's own rules in a symlinked root .gitignore are equally ignored by git, so
this may warrant a refusal with a fix (like t2197) or an advisory warning
rather than a silent write.

## Suggested fix

Treat a symlinked `.gitignore` as "cannot inspect" (rc 2 / refusal) in the
shared writer or in `refuse_nonregular_gitignores`, with a message naming git's
no-follow rule, and pin it with a git check-ignore-based test (the t2197
Test 41 premise control is the pattern).
